from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from tools import audit_agent_benchmarks as audit


ROOT = Path(__file__).resolve().parents[1]
COMMITTED = ROOT / "evals" / "results" / "agent-benchmark-audit-2026-08-31.json"
TOOLING = ROOT / "evals" / "results" / "benchmark-tooling-smoke-2026-08-31.json"
GUIDELLM = ROOT / "evals" / "benchmark_tools" / "guidellm-tool-calling-smoke.json"
LM_EVAL_DIR = ROOT / "evals" / "benchmark_tools" / "lm_eval"
SMOKE_SCRIPT = ROOT / "tools" / "run_benchmark_tooling_smoke.sh"


def json_lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_committed_agent_benchmark_audit_is_reproducible() -> None:
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))

    rebuilt = audit.build_audit(
        recorded_at=committed["recorded_at"],
        benchmark_subject_revision=committed["benchmark_subject_revision"],
    )

    assert rebuilt == committed
    assert all(len(item["sha256"]) == 64 for item in committed["input_artefacts"])


def test_benchmark_audit_preserves_failures_and_does_not_overclaim() -> None:
    report = json.loads(COMMITTED.read_text(encoding="utf-8"))
    tooling = json.loads(TOOLING.read_text(encoding="utf-8"))

    assert report["current_benchmark"]["original_local_agent"]["agent_completion_ratio"] == 0.8
    assert report["current_benchmark"]["repeated_synthesis"]["machine_targets_passed"] is False
    assert (
        report["current_benchmark"]["structural_revision"]["evaluation_artefacts_complete"] is False
    )
    assert report["current_benchmark"]["structural_revision"]["repair_samples_observed"] == 0
    assert (
        report["current_benchmark"]["A01_acquisition_ablation"]["machine_targets_passed"] is False
    )
    assert report["current_benchmark"]["A02_repair_ablation"]["targeted_patch_completed"] == 9
    assert report["conclusion"] == {
        "fixed_production_workflow_retained": True,
        "autonomous_agent_value_demonstrated": False,
        "autonomous_agent_reliable": False,
        "native_tool_calling_provider_validated": False,
        "targeted_patch_is_promising": True,
        "third_party_tooling_ready_for_bounded_future_runs": True,
        "new_paid_benchmark_authorised": False,
    }
    assert [item["status"] for item in tooling["tools"]["guidellm"]["attempts"]] == [
        "failed_preflight",
        "failed_startup",
        "passed_mock_transport_smoke",
        "passed_mock_native_tool_call_smoke",
    ]
    assert [item["status"] for item in tooling["tools"]["lm_evaluation_harness"]["attempts"]] == [
        "passed_dummy_model_smoke",
        "failed_setup",
        "passed_mock_openai_compatible_adapter_smoke",
        "passed_claim_support_task_load_smoke",
    ]
    assert tooling["external_model_provider_calls"] == 0
    assert tooling["reproducibility_rerun"] == {
        "recorded_at": "2026-08-31T09:51:13Z",
        "script": "tools/run_benchmark_tooling_smoke.sh",
        "guidellm_successful_requests": 4,
        "guidellm_errored_requests": 0,
        "guidellm_observed_native_tool_calls": 2,
        "lm_eval_completed_samples": 3,
        "external_model_provider_calls": 0,
        "status": "passed",
    }


def test_guidellm_profile_is_local_mock_only_and_bounded() -> None:
    profile = json.loads(GUIDELLM.read_text(encoding="utf-8"))["spec"]
    backend = profile["backend"]
    data = profile["data"][0]

    assert backend["target"] == "http://127.0.0.1:18766"
    assert backend["model"] == "firstroll-benchmark-mock"
    assert profile["constraints"] == [{"kind": "max_requests", "count": 4}]
    assert data["tool_call_turns"] == [0]
    function = data["tools"][0]["function"]
    assert function["name"] == "fetch_crossref_research"
    assert set(function["parameters"]["properties"]) == {"target_gap"}
    assert function["parameters"]["additionalProperties"] is False
    assert profile["outputs"][0]["path"].startswith(".firstroll/")


def test_lm_eval_claim_support_suite_is_public_bounded_and_complete() -> None:
    cases = json_lines(LM_EVAL_DIR / "claim-support.jsonl")
    labels = {
        "directly_supported",
        "reasonable_interpretation",
        "unsupported",
        "stronger_than_evidence",
    }
    serialised = json.dumps(cases)

    assert len(cases) == 12
    assert len({case["case_id"] for case in cases}) == 12
    assert {case["target"] for case in cases} == labels
    assert all(case["prompt"].endswith("Label:") for case in cases)
    assert "PRIVATE_" not in serialised
    task = (LM_EVAL_DIR / "firstroll_claim_support.yaml").read_text(encoding="utf-8")
    assert "output_type: generate_until" in task
    assert "metric: exact_match" in task
    assert "max_gen_toks: 16" in task


def test_tooling_smoke_script_cannot_target_a_paid_provider() -> None:
    script = SMOKE_SCRIPT.read_text(encoding="utf-8")
    mode = os.stat(SMOKE_SCRIPT).st_mode

    assert mode & 0o111
    assert 'PORT="18766"' in script
    assert "firstroll-benchmark-mock" in script
    assert 'GUIDELLM_VERSION="0.7.3"' in script
    assert 'LM_EVAL_VERSION="0.4.12"' in script
    assert "guidellm==$GUIDELLM_VERSION" in script
    assert "lm-eval[api]==$LM_EVAL_VERSION" in script
    assert "api.deepseek.com" not in script
    assert "DEEPSEEK_API_KEY" not in script
    assert "external_model_provider_calls" in script
    assert "must resolve beneath this repository's .firstroll" in script
