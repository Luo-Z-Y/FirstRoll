"""Tests for single-use authorization capabilities.

Covers: correct approval, wrong repository, wrong environment, wrong run,
wrong SHA, wrong digest, expired token, reused token, changed candidate,
unauthorized user, and rejection semantics.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from tools.release.authorization import (
    AuthorizationCapability,
    NonceStore,
    VerificationResult,
    capability_from_token,
    issue_capability,
    verify_capability,
)


SIGNING_KEY = "test-signing-key-do-not-use-in-production"


def _issue(**overrides):
    defaults = dict(
        signing_key=SIGNING_KEY,
        repository="Luo-Z-Y/FirstRoll",
        environment="production",
        workflow_run_id=123456789,
        commit_sha="a" * 40,
        image_digest="sha256:" + "b" * 64,
        deployment_target="api.firstroll.app",
        manifest_digest="sha256:" + "c" * 64,
        authorizing_user="luo-z-y",
        decision="approve",
    )
    defaults.update(overrides)
    return issue_capability(**defaults)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestCorrectApproval:
    def test_valid_capability_passes_verification(self):
        nonce_store = NonceStore()
        cap = _issue()
        result = verify_capability(
            cap,
            signing_key=SIGNING_KEY,
            nonce_store=nonce_store,
            expected_repository="Luo-Z-Y/FirstRoll",
            expected_environment="production",
        )
        assert result.valid is True
        assert result.error == ""

    def test_token_round_trip(self):
        cap = _issue()
        token = cap.to_token()
        restored = capability_from_token(token)
        assert restored.repository == cap.repository
        assert restored.commit_sha == cap.commit_sha
        assert restored.signature == cap.signature


# ---------------------------------------------------------------------------
# Binding mismatches
# ---------------------------------------------------------------------------


class TestBindingMismatch:
    def test_wrong_repository_rejected(self):
        nonce_store = NonceStore()
        cap = _issue(repository="Wrong/Repo")
        result = verify_capability(
            cap,
            signing_key=SIGNING_KEY,
            nonce_store=nonce_store,
            expected_repository="Luo-Z-Y/FirstRoll",
        )
        assert result.valid is False
        assert "repository" in result.error

    def test_wrong_environment_rejected(self):
        nonce_store = NonceStore()
        cap = _issue(environment="staging")
        result = verify_capability(
            cap,
            signing_key=SIGNING_KEY,
            nonce_store=nonce_store,
            expected_environment="production",
        )
        assert result.valid is False
        assert "environment" in result.error

    def test_wrong_workflow_run_rejected(self):
        nonce_store = NonceStore()
        cap = _issue(workflow_run_id=999)
        result = verify_capability(
            cap,
            signing_key=SIGNING_KEY,
            nonce_store=nonce_store,
            expected_workflow_run_id=123456789,
        )
        assert result.valid is False
        assert "workflow_run_id" in result.error

    def test_wrong_commit_sha_rejected(self):
        nonce_store = NonceStore()
        cap = _issue(commit_sha="f" * 40)
        result = verify_capability(
            cap,
            signing_key=SIGNING_KEY,
            nonce_store=nonce_store,
            expected_commit_sha="a" * 40,
        )
        assert result.valid is False
        assert "commit_sha" in result.error

    def test_wrong_image_digest_rejected(self):
        nonce_store = NonceStore()
        cap = _issue(image_digest="sha256:" + "f" * 64)
        result = verify_capability(
            cap,
            signing_key=SIGNING_KEY,
            nonce_store=nonce_store,
            expected_image_digest="sha256:" + "b" * 64,
        )
        assert result.valid is False
        assert "image_digest" in result.error

    def test_wrong_manifest_digest_rejected(self):
        nonce_store = NonceStore()
        cap = _issue(manifest_digest="sha256:" + "f" * 64)
        result = verify_capability(
            cap,
            signing_key=SIGNING_KEY,
            nonce_store=nonce_store,
            expected_manifest_digest="sha256:" + "c" * 64,
        )
        assert result.valid is False
        assert "manifest_digest" in result.error


# ---------------------------------------------------------------------------
# Expiry
# ---------------------------------------------------------------------------


class TestExpiry:
    def test_expired_authorization_rejected(self):
        nonce_store = NonceStore()
        cap = _issue(expiry_seconds=0)
        # The capability expires immediately; wait a tiny bit to ensure expiry.
        time.sleep(0.1)
        result = verify_capability(
            cap,
            signing_key=SIGNING_KEY,
            nonce_store=nonce_store,
        )
        assert result.valid is False
        assert "expired" in result.error.lower()


# ---------------------------------------------------------------------------
# Replay protection
# ---------------------------------------------------------------------------


class TestReplayProtection:
    def test_reused_authorization_rejected(self):
        nonce_store = NonceStore()
        cap = _issue()
        # First use succeeds
        result1 = verify_capability(
            cap,
            signing_key=SIGNING_KEY,
            nonce_store=nonce_store,
        )
        assert result1.valid is True
        # Second use fails
        result2 = verify_capability(
            cap,
            signing_key=SIGNING_KEY,
            nonce_store=nonce_store,
        )
        assert result2.valid is False
        assert "already been used" in result2.error

    def test_nonce_store_independence(self):
        """Different nonce stores do not share state."""
        cap = _issue()
        store1 = NonceStore()
        store2 = NonceStore()
        result1 = verify_capability(
            cap,
            signing_key=SIGNING_KEY,
            nonce_store=store1,
        )
        assert result1.valid is True
        result2 = verify_capability(
            cap,
            signing_key=SIGNING_KEY,
            nonce_store=store2,
        )
        assert result2.valid is True


# ---------------------------------------------------------------------------
# Signature integrity
# ---------------------------------------------------------------------------


class TestSignatureIntegrity:
    def test_wrong_signing_key_rejected(self):
        nonce_store = NonceStore()
        cap = _issue()
        result = verify_capability(
            cap,
            signing_key="wrong-key",
            nonce_store=nonce_store,
        )
        assert result.valid is False
        assert "signature" in result.error.lower()

    def test_tampered_token_rejected(self):
        nonce_store = NonceStore()
        cap = _issue()
        # Tamper with the commit SHA
        tampered = AuthorizationCapability(
            repository=cap.repository,
            environment=cap.environment,
            workflow_run_id=cap.workflow_run_id,
            commit_sha="f" * 40,  # tampered
            image_digest=cap.image_digest,
            deployment_target=cap.deployment_target,
            manifest_digest=cap.manifest_digest,
            authorizing_user=cap.authorizing_user,
            decision=cap.decision,
            nonce=cap.nonce,
            issued_at=cap.issued_at,
            expires_at=cap.expires_at,
            signature=cap.signature,  # original signature
        )
        result = verify_capability(
            tampered,
            signing_key=SIGNING_KEY,
            nonce_store=nonce_store,
        )
        assert result.valid is False
        assert "signature" in result.error.lower()


# ---------------------------------------------------------------------------
# Decision semantics
# ---------------------------------------------------------------------------


class TestDecisionSemantics:
    def test_reject_decision_not_treated_as_approval(self):
        nonce_store = NonceStore()
        cap = _issue(decision="reject")
        result = verify_capability(
            cap,
            signing_key=SIGNING_KEY,
            nonce_store=nonce_store,
        )
        assert result.valid is False
        assert "reject" in result.error.lower()

    def test_invalid_decision_raises(self):
        with pytest.raises(ValueError, match="decision"):
            _issue(decision="maybe")


# ---------------------------------------------------------------------------
# Changed candidate
# ---------------------------------------------------------------------------


class TestChangedCandidate:
    def test_approval_for_one_candidate_cannot_approve_another(self):
        """An authorization issued for candidate A cannot be used for candidate B."""
        nonce_store = NonceStore()
        cap = _issue(
            commit_sha="a" * 40,
            image_digest="sha256:" + "b" * 64,
        )
        result = verify_capability(
            cap,
            signing_key=SIGNING_KEY,
            nonce_store=nonce_store,
            expected_commit_sha="a" * 40,
            expected_image_digest="sha256:" + "d" * 64,  # different candidate
        )
        assert result.valid is False
        assert "image_digest" in result.error


# ---------------------------------------------------------------------------
# Agent authority constraints
# ---------------------------------------------------------------------------


class TestAgentAuthority:
    def test_agent_cannot_approve_without_signing_key(self):
        """Without the signing key, the agent cannot mint valid capabilities."""
        nonce_store = NonceStore()
        cap = _issue(signing_key="agent-does-not-have-this-key")
        result = verify_capability(
            cap,
            signing_key=SIGNING_KEY,
            nonce_store=nonce_store,
        )
        assert result.valid is False
