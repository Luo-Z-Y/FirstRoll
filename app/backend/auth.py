from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID


class AuthConfigurationError(RuntimeError):
    """Raised when hosted authentication is not configured."""


class AuthenticationError(RuntimeError):
    """Raised when a bearer token cannot be authenticated."""


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    email: str | None
    role: str

    def as_dict(self) -> dict[str, str | None]:
        return {"id": self.user_id, "email": self.email, "role": self.role}


UserTransport = Callable[[str, str, str], dict[str, Any]]


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
        return AuthenticatedUser(user_id=user_id, email=email, role=role)

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
