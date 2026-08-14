from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class QuotaConfigurationError(RuntimeError):
    """Raised when the hosted quota boundary is not installed or configured."""


class QuotaServiceError(RuntimeError):
    """Raised when Supabase cannot return a trustworthy quota decision."""


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
            raise QuotaServiceError("Supabase returned an invalid quota response.") from exc
        counts = (
            quota.user_limit,
            quota.user_used,
            quota.user_remaining,
            quota.global_limit,
            quota.global_used,
            quota.global_remaining,
        )
        if any(value < 0 for value in counts) or not quota.reset_at:
            raise QuotaServiceError("Supabase returned an invalid quota response.")
        return quota


QuotaTransport = Callable[[str, str, str, str], dict[str, Any]]


class SupabaseQuotaClient:
    """Reserve one atomic Deep Study allowance through an authenticated Supabase RPC."""

    max_response_bytes = 128_000

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

    def status(self, authorisation: str | None) -> DeepStudyQuota:
        return self._call("deep_study_quota_status", authorisation)

    def reserve(self, authorisation: str | None) -> DeepStudyQuota:
        quota = self._call("reserve_deep_study_quota", authorisation)
        if not quota.allowed:
            raise QuotaExceededError(quota)
        return quota

    def _call(self, function_name: str, authorisation: str | None) -> DeepStudyQuota:
        if not self.configured:
            raise QuotaConfigurationError("Supabase Deep Study quotas are not configured.")
        token = self._bearer_token(authorisation)
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
