from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import psycopg


class QuotaConfigurationError(RuntimeError):
    """Raised when the hosted quota boundary is not installed or configured."""


class QuotaServiceError(RuntimeError):
    """Raised when the configured store cannot return a trustworthy quota decision."""


class QuotaExceededError(RuntimeError):
    """Raised when a user or the whole demo has exhausted its daily allowance."""

    def __init__(self, quota: "DeepStudyQuota") -> None:
        self.quota = quota
        scope = "account" if quota.reason == "user_limit" else "public demo"
        super().__init__(
            f"The daily Deep Study limit for this {scope} has been reached. "
            f"The allowance resets at {quota.reset_at_label}."
        )


@dataclass(frozen=True)
class DeepStudyQuota:
    allowed: bool
    reason: str
    user_limit: int
    user_used: int
    user_remaining: int
    global_limit: int
    global_used: int
    global_remaining: int
    reset_at: str

    @property
    def reset_at_label(self) -> str:
        try:
            reset = datetime.fromisoformat(self.reset_at.replace("Z", "+00:00"))
            return reset.astimezone(timezone.utc).strftime("%H:%M UTC")
        except ValueError:
            return "00:00 UTC"

    def retry_after_seconds(self) -> int:
        try:
            reset = datetime.fromisoformat(self.reset_at.replace("Z", "+00:00"))
            seconds = int((reset - datetime.now(timezone.utc)).total_seconds())
            return max(60, seconds)
        except ValueError:
            return 3600

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "user": {
                "limit": self.user_limit,
                "used": self.user_used,
                "remaining": self.user_remaining,
            },
            "global": {
                "limit": self.global_limit,
                "used": self.global_used,
                "remaining": self.global_remaining,
            },
            "reset_at": self.reset_at,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "DeepStudyQuota":
        try:
            quota = cls(
                allowed=payload["allowed"] is True,
                reason=str(payload.get("reason") or "available"),
                user_limit=int(payload["user_limit"]),
                user_used=int(payload["user_used"]),
                user_remaining=int(payload["user_remaining"]),
                global_limit=int(payload["global_limit"]),
                global_used=int(payload["global_used"]),
                global_remaining=int(payload["global_remaining"]),
                reset_at=str(payload["reset_at"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise QuotaServiceError("The quota store returned an invalid quota response.") from exc
        counts = (
            quota.user_limit,
            quota.user_used,
            quota.user_remaining,
            quota.global_limit,
            quota.global_used,
            quota.global_remaining,
        )
        if any(value < 0 for value in counts) or not quota.reset_at:
            raise QuotaServiceError("The quota store returned an invalid quota response.")
        return quota


@dataclass(frozen=True)
class QuotaIdentity:
    """Verified account identity passed to quota storage after authentication."""

    provider: str
    subject: str
    # Temporary rollback input for the old Supabase RPC. It is never used or
    # persisted by the backend-owned PostgreSQL implementation.
    legacy_authorisation: str | None = field(default=None, repr=False, compare=False)

    def validated(self) -> "QuotaIdentity":
        provider = self.provider.strip().casefold()
        subject = self.subject.strip()
        if not re.fullmatch(r"[a-z0-9_-]{1,64}", provider):
            raise QuotaServiceError("The verified account provider is invalid.")
        if not subject or len(subject) > 256 or any(ord(character) < 32 for character in subject):
            raise QuotaServiceError("The verified account subject is invalid.")
        return QuotaIdentity(provider=provider, subject=subject)


QuotaTransport = Callable[[str, str, str, str], dict[str, Any]]


class SupabaseQuotaClient:
    """Legacy rollback adapter for the visitor-token-authorised Supabase RPC."""

    max_response_bytes = 128_000
    backend_owned = False

    def __init__(
        self,
        url: str | None = None,
        publishable_key: str | None = None,
        transport: QuotaTransport | None = None,
    ) -> None:
        self.url = (url if url is not None else os.getenv("SUPABASE_URL", "")).strip().rstrip("/")
        self.publishable_key = (
            publishable_key
            if publishable_key is not None
            else os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
        ).strip()
        self.transport = transport or self._request_rpc

    @property
    def configured(self) -> bool:
        parsed = urlparse(self.url)
        return bool(
            parsed.scheme == "https"
            and parsed.hostname
            and self.publishable_key.startswith("sb_publishable_")
        )

    def status(self, identity: QuotaIdentity) -> DeepStudyQuota:
        return self._call("deep_study_quota_status", identity)

    def reserve(self, identity: QuotaIdentity) -> DeepStudyQuota:
        quota = self._call("reserve_deep_study_quota", identity)
        if not quota.allowed:
            raise QuotaExceededError(quota)
        return quota

    def _call(self, function_name: str, identity: QuotaIdentity) -> DeepStudyQuota:
        if not self.configured:
            raise QuotaConfigurationError("Supabase Deep Study quotas are not configured.")
        if identity.provider.strip().casefold() != "supabase":
            raise QuotaConfigurationError(
                "The legacy Supabase quota adapter cannot serve this identity provider."
            )
        token = self._bearer_token(identity.legacy_authorisation)
        payload = self.transport(self.url, self.publishable_key, token, function_name)
        return DeepStudyQuota.from_payload(payload)

    @staticmethod
    def _bearer_token(value: str | None) -> str:
        scheme, separator, token = str(value or "").strip().partition(" ")
        if separator != " " or scheme.casefold() != "bearer" or not token.strip():
            raise QuotaServiceError("A verified account session is required for Deep Study.")
        token = token.strip()
        if len(token) > 16_384:
            raise QuotaServiceError("The account session is invalid.")
        return token

    @classmethod
    def _request_rpc(
        cls,
        url: str,
        publishable_key: str,
        token: str,
        function_name: str,
    ) -> dict[str, Any]:
        request = Request(
            f"{url}/rest/v1/rpc/{function_name}",
            data=b"{}",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "apikey": publishable_key,
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=12) as response:
                body = response.read(cls.max_response_bytes + 1)
                if len(body) > cls.max_response_bytes:
                    raise QuotaServiceError(
                        "Supabase returned an unexpectedly large quota response."
                    )
                payload = json.loads(body.decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404:
                raise QuotaConfigurationError(
                    "The Supabase Deep Study quota migration has not been installed."
                ) from exc
            if exc.code in {401, 403}:
                raise QuotaServiceError(
                    "Supabase rejected the account session for quota use."
                ) from exc
            raise QuotaServiceError(f"Supabase quota service returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
            raise QuotaServiceError("Supabase could not return a quota decision.") from exc
        if not isinstance(payload, dict):
            raise QuotaServiceError("Supabase returned an invalid quota response.")
        return payload


DatabaseQuotaTransport = Callable[[str, str, str, bool], dict[str, Any]]


class PostgresQuotaClient:
    """Reserve quota with a backend-owned PostgreSQL connection.

    The database receives only the already verified provider and immutable subject.
    Browser bearer tokens never cross this boundary.
    """

    backend_owned = True

    def __init__(
        self,
        database_url: str | None = None,
        transport: DatabaseQuotaTransport | None = None,
    ) -> None:
        self.database_url = (
            database_url
            if database_url is not None
            else os.getenv("FIRSTROLL_DATABASE_URL", "")
        ).strip()
        self.transport = transport or self._request_database

    @property
    def configured(self) -> bool:
        parsed = urlparse(self.database_url)
        return bool(
            parsed.scheme in {"postgres", "postgresql"}
            and parsed.hostname
            and parsed.path not in {"", "/"}
            and parsed.username
        )

    def status(self, identity: QuotaIdentity) -> DeepStudyQuota:
        return self._call(identity, reserve=False)

    def reserve(self, identity: QuotaIdentity) -> DeepStudyQuota:
        quota = self._call(identity, reserve=True)
        if not quota.allowed:
            raise QuotaExceededError(quota)
        return quota

    def _call(self, identity: QuotaIdentity, *, reserve: bool) -> DeepStudyQuota:
        if not self.configured:
            raise QuotaConfigurationError(
                "The backend-owned PostgreSQL Deep Study quota store is not configured."
            )
        verified = identity.validated()
        try:
            payload = self.transport(
                self.database_url,
                verified.provider,
                verified.subject,
                reserve,
            )
        except QuotaServiceError:
            raise
        except (psycopg.Error, OSError, TimeoutError) as exc:
            raise QuotaServiceError(
                "The PostgreSQL quota store could not return a decision."
            ) from exc
        return DeepStudyQuota.from_payload(payload)

    @staticmethod
    def _request_database(
        database_url: str,
        provider: str,
        subject: str,
        reserve: bool,
    ) -> dict[str, Any]:
        try:
            with psycopg.connect(database_url, connect_timeout=10) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        select firstroll_private.deep_study_quota_decision(
                          %s::text,
                          %s::text,
                          %s::boolean
                        )
                        """,
                        (provider, subject, reserve),
                    )
                    row = cursor.fetchone()
        except psycopg.errors.UndefinedFunction as exc:
            raise QuotaConfigurationError(
                "The identity-neutral Deep Study quota migration has not been installed."
            ) from exc
        if row is None or not isinstance(row[0], dict):
            raise QuotaServiceError("The PostgreSQL quota store returned an invalid response.")
        return row[0]


def configured_quota_client() -> SupabaseQuotaClient | PostgresQuotaClient:
    """Select one quota persistence boundary explicitly."""

    provider = os.getenv("FIRSTROLL_QUOTA_PROVIDER", "supabase").strip().casefold()
    if provider == "postgres":
        return PostgresQuotaClient()
    if provider == "supabase":
        return SupabaseQuotaClient()
    raise QuotaConfigurationError(
        "FIRSTROLL_QUOTA_PROVIDER must be either 'postgres' or 'supabase'."
    )
