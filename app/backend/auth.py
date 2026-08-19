from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID

import jwt
from jwt import PyJWKClient


class AuthConfigurationError(RuntimeError):
    """Raised when hosted authentication is not configured."""


class AuthenticationError(RuntimeError):
    """Raised when a bearer token cannot be authenticated."""


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    email: str | None
    role: str
    provider: str

    def as_dict(self) -> dict[str, str | None]:
        return {
            "id": self.user_id,
            "email": self.email,
            "role": self.role,
            "provider": self.provider,
        }


UserTransport = Callable[[str, str, str], dict[str, Any]]
TokenTransport = Callable[[str], dict[str, Any]]


class SupabaseAuthVerifier:
    """Validate Supabase access tokens through the project's Auth server."""

    max_response_bytes = 256_000

    def __init__(
        self,
        url: str | None = None,
        publishable_key: str | None = None,
        transport: UserTransport | None = None,
    ) -> None:
        self.url = (url if url is not None else os.getenv("SUPABASE_URL", "")).strip().rstrip("/")
        self.publishable_key = (
            publishable_key
            if publishable_key is not None
            else os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
        ).strip()
        self.transport = transport or self._request_user

    @property
    def configured(self) -> bool:
        if not self.url or not self.publishable_key:
            return False
        parsed = urlparse(self.url)
        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and self.publishable_key.startswith("sb_publishable_")
        )

    def status(self) -> dict[str, Any]:
        return {
            "provider": "Supabase Auth",
            "state": "ready" if self.configured else "not_configured",
            "configured": self.configured,
        }

    def verify_authorisation(self, value: str | None) -> AuthenticatedUser:
        if not self.configured:
            raise AuthConfigurationError("Supabase authentication is not configured.")
        scheme, separator, token = str(value or "").strip().partition(" ")
        if separator != " " or scheme.casefold() != "bearer" or not token.strip():
            raise AuthenticationError("Sign in to continue.")
        token = token.strip()
        if len(token) > 16_384:
            raise AuthenticationError("The authentication token is invalid.")
        payload = self.transport(self.url, self.publishable_key, token)
        user_id = str(payload.get("id") or "").strip()
        try:
            UUID(user_id)
        except ValueError as exc:
            raise AuthenticationError("Supabase returned an invalid user identity.") from exc
        role = str(payload.get("role") or "").strip()
        if role != "authenticated":
            raise AuthenticationError("This account is not authorised for FirstRoll.")
        email = str(payload.get("email") or "").strip() or None
        return AuthenticatedUser(
            user_id=user_id,
            email=email,
            role=role,
            provider="supabase",
        )

    @classmethod
    def _request_user(cls, url: str, publishable_key: str, token: str) -> dict[str, Any]:
        request = Request(
            f"{url}/auth/v1/user",
            headers={
                "Accept": "application/json",
                "apikey": publishable_key,
                "Authorization": f"Bearer {token}",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=12) as response:
                body = response.read(cls.max_response_bytes + 1)
                if len(body) > cls.max_response_bytes:
                    raise AuthenticationError("Supabase returned an unexpectedly large response.")
                payload = json.loads(body.decode("utf-8"))
        except HTTPError as exc:
            if exc.code in {400, 401, 403}:
                raise AuthenticationError("Your sign-in session is invalid or has expired.") from exc
            raise AuthenticationError(f"Supabase Auth returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
            raise AuthenticationError("Supabase Auth could not validate this session.") from exc
        if not isinstance(payload, dict):
            raise AuthenticationError("Supabase returned an invalid authentication response.")
        return payload


class EntraAuthVerifier:
    """Validate Microsoft Entra External ID access tokens for the FirstRoll API."""

    max_response_bytes = 256_000

    def __init__(
        self,
        authority: str | None = None,
        client_id: str | None = None,
        required_scope: str | None = None,
        transport: TokenTransport | None = None,
    ) -> None:
        self.authority = (
            authority if authority is not None else os.getenv("ENTRA_AUTHORITY", "")
        ).strip().rstrip("/")
        self.client_id = (
            client_id if client_id is not None else os.getenv("ENTRA_API_CLIENT_ID", "")
        ).strip()
        self.required_scope = (
            required_scope
            if required_scope is not None
            else os.getenv("ENTRA_REQUIRED_SCOPE", "access_as_user")
        ).strip()
        self.transport = transport
        self._discovery: dict[str, Any] | None = None
        self._jwks_client: PyJWKClient | None = None

    @property
    def configured(self) -> bool:
        parsed = urlparse(self.authority)
        try:
            UUID(self.client_id)
        except ValueError:
            return False
        return bool(
            parsed.scheme == "https"
            and parsed.hostname
            and self.required_scope
            and len(self.required_scope) <= 256
        )

    def status(self) -> dict[str, Any]:
        return {
            "provider": "Microsoft Entra External ID",
            "state": "ready" if self.configured else "not_configured",
            "configured": self.configured,
        }

    def verify_authorisation(self, value: str | None) -> AuthenticatedUser:
        if not self.configured:
            raise AuthConfigurationError("Microsoft Entra authentication is not configured.")
        scheme, separator, token = str(value or "").strip().partition(" ")
        if separator != " " or scheme.casefold() != "bearer" or not token.strip():
            raise AuthenticationError("Sign in to continue.")
        token = token.strip()
        if len(token) > 16_384:
            raise AuthenticationError("The authentication token is invalid.")

        payload = self.transport(token) if self.transport is not None else self._decode(token)
        if not isinstance(payload, dict):
            raise AuthenticationError("Microsoft Entra returned an invalid identity response.")

        granted_scopes = {
            scope.strip() for scope in str(payload.get("scp") or "").split() if scope.strip()
        }
        if self.required_scope not in granted_scopes:
            raise AuthenticationError("This account is not authorised for the FirstRoll API.")

        user_id = str(payload.get("oid") or payload.get("sub") or "").strip()
        if not user_id or len(user_id) > 256:
            raise AuthenticationError("Microsoft Entra returned an invalid user identity.")

        return AuthenticatedUser(
            user_id=user_id,
            email=self._email(payload),
            role="authenticated",
            provider="entra",
        )

    @staticmethod
    def _email(payload: dict[str, Any]) -> str | None:
        direct = str(
            payload.get("email")
            or payload.get("preferred_username")
            or payload.get("upn")
            or ""
        ).strip()
        if direct:
            return direct
        emails = payload.get("emails")
        if isinstance(emails, list):
            return next((str(item).strip() for item in emails if str(item).strip()), None)
        return None

    def _decode(self, token: str) -> dict[str, Any]:
        try:
            discovery = self._openid_configuration()
            issuer = str(discovery["issuer"])
            jwks_uri = str(discovery["jwks_uri"])
            if self._jwks_client is None:
                self._jwks_client = PyJWKClient(
                    jwks_uri,
                    cache_keys=True,
                    lifespan=3600,
                    timeout=12,
                )
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=issuer,
                options={"require": ["aud", "exp", "iss", "sub"]},
            )
        except (jwt.PyJWTError, KeyError, TypeError, ValueError, URLError, TimeoutError) as exc:
            raise AuthenticationError(
                "Your Microsoft Entra sign-in session is invalid or has expired."
            ) from exc
        if not isinstance(payload, dict):
            raise AuthenticationError("Microsoft Entra returned an invalid identity response.")
        return payload

    def _openid_configuration(self) -> dict[str, Any]:
        if self._discovery is not None:
            return self._discovery
        request = Request(
            f"{self.authority}/v2.0/.well-known/openid-configuration",
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=12) as response:
                body = response.read(self.max_response_bytes + 1)
                if len(body) > self.max_response_bytes:
                    raise AuthenticationError(
                        "Microsoft Entra returned an unexpectedly large discovery response."
                    )
                payload = json.loads(body.decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
            raise AuthenticationError(
                "Microsoft Entra could not publish its token-verification configuration."
            ) from exc
        if not isinstance(payload, dict):
            raise AuthenticationError("Microsoft Entra returned invalid discovery metadata.")
        issuer = urlparse(str(payload.get("issuer") or ""))
        jwks_uri = urlparse(str(payload.get("jwks_uri") or ""))
        if issuer.scheme != "https" or not issuer.hostname:
            raise AuthenticationError("Microsoft Entra returned an invalid token issuer.")
        if jwks_uri.scheme != "https" or not jwks_uri.hostname:
            raise AuthenticationError("Microsoft Entra returned an invalid signing-key endpoint.")
        self._discovery = payload
        return payload


def configured_auth_verifier() -> SupabaseAuthVerifier | EntraAuthVerifier:
    """Select one identity provider explicitly; never accept tokens from both at once."""

    provider = os.getenv("FIRSTROLL_AUTH_PROVIDER", "supabase").strip().casefold()
    if provider == "entra":
        return EntraAuthVerifier()
    if provider == "supabase":
        return SupabaseAuthVerifier()
    raise AuthConfigurationError(
        "FIRSTROLL_AUTH_PROVIDER must be either 'entra' or 'supabase'."
    )
