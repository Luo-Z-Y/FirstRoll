from __future__ import annotations

import pytest

from app.backend.autonomous_study import (
    FilmmakerCoach,
    StudyClaimAudit,
    audited_claim_paths,
    path_source_ids,
    validate_claim_audit,
    validate_filmmaker_coach,
    weak_claim_paths,
)
from tools.evaluate_agent_repair import synthetic_packet, valid_candidate


def audit_payload(*, weak_path: str | None = None) -> dict:
    study = valid_candidate()
    items = []
    for path in audited_claim_paths(study):
        field = path.rsplit(".", 1)[-1]
        label = (
            "unsupported"
            if path == weak_path
            else "directly_supported"
            if field in {"critic_reports", "theory_explains"}
            else "reasonable_interpretation"
        )
        allowed_ids = path_source_ids(study, path)
        source_id = (
            sorted(source for source in allowed_ids if source.startswith("E"))[0]
            if field == "critic_reports"
            else sorted(source for source in allowed_ids if source.startswith("S"))[0]
            if field == "theory_explains"
            else sorted(allowed_ids)[0]
        )
        items.append(
            {
                "path": path,
                "label": label,
                "source_ids": [source_id],
                "support_note": (
                    "The selected evidence supports this bounded classification while the wording "
                    "retains its stated epistemic status."
                ),
            }
        )
    return {"items": items}


def test_claim_audit_requires_exact_coverage_and_path_local_citations() -> None:
    study = valid_candidate()
    packet = synthetic_packet()
    audit = StudyClaimAudit.model_validate(audit_payload())

    validate_claim_audit(study, audit, packet)

    missing = StudyClaimAudit.model_validate({"items": audit_payload()["items"][:-1]})
    with pytest.raises(ValueError, match="cover every required study path"):
        validate_claim_audit(study, missing, packet)

    wrong_source = audit.model_copy(deep=True)
    wrong_source.items[1].source_ids = ["E999"]
    with pytest.raises(ValueError, match="outside the audited study path"):
        validate_claim_audit(study, wrong_source, packet)


def test_audit_enforces_evidence_class_for_reports_and_theory() -> None:
    study = valid_candidate()
    packet = synthetic_packet()
    payload = audit_payload()
    critic = next(item for item in payload["items"] if item["path"] == "sections.0.critic_reports")
    critic["source_ids"] = ["S1"]
    audit = StudyClaimAudit.model_validate(payload)

    with pytest.raises(ValueError, match="must cite criticism or attributed evidence"):
        validate_claim_audit(study, audit, packet)


def test_interpretive_claim_cannot_be_labelled_directly_supported() -> None:
    study = valid_candidate()
    packet = synthetic_packet()
    payload = audit_payload()
    central = next(item for item in payload["items"] if item["path"] == "central_argument")
    central["label"] = "directly_supported"
    audit = StudyClaimAudit.model_validate(payload)

    with pytest.raises(ValueError, match="cannot be labelled directly supported"):
        validate_claim_audit(study, audit, packet)


def test_weak_claim_paths_are_exact_editor_targets() -> None:
    weak_path = "sections.1.mechanism"
    audit = StudyClaimAudit.model_validate(audit_payload(weak_path=weak_path))

    assert weak_claim_paths(audit) == (weak_path,)


def test_filmmaker_coach_accepts_only_audited_traceable_actions() -> None:
    study = valid_candidate()
    packet = synthetic_packet()
    audit = StudyClaimAudit.model_validate(audit_payload())
    exercises = []
    for action, path in zip(
        ("log", "compare", "track"),
        ("sections.0.hypothesis", "sections.1.mechanism", "sections.2.hypothesis"),
    ):
        exercises.append(
            {
                "title": f"{action.title()} an observable pattern",
                "action": action,
                "instruction": (
                    f"{action.title()} each relevant instance and record where the proposed pattern "
                    "holds or fails before drawing a conclusion."
                ),
                "study_path": path,
                "source_ids": [sorted(path_source_ids(study, path))[0]],
                "success_signal": (
                    "The record contains comparable examples and at least one searched-for "
                    "counterexample."
                ),
                "uncertainty_boundary": (
                    "This exercise tests a viewing hypothesis and does not establish intention or "
                    "a whole-film fact."
                ),
            }
        )
    coach = FilmmakerCoach.model_validate({"exercises": exercises})

    validate_filmmaker_coach(study, audit, coach, packet)

    hidden_action = coach.model_copy(deep=True)
    hidden_action.exercises[
        0
    ].instruction = (
        "Catalogue each relevant instance and retain enough examples for a later comparison."
    )
    with pytest.raises(ValueError, match="state its observable action"):
        validate_filmmaker_coach(study, audit, hidden_action, packet)

    missing_boundary = coach.model_copy(deep=True)
    missing_boundary.exercises[
        0
    ].uncertainty_boundary = (
        "The completed exercise provides a clear and comprehensive production conclusion."
    )
    with pytest.raises(ValueError, match="explicit uncertainty boundary"):
        validate_filmmaker_coach(study, audit, missing_boundary, packet)

    weak_audit = StudyClaimAudit.model_validate(audit_payload(weak_path="sections.1.mechanism"))
    with pytest.raises(ValueError, match="cannot rely on an unaudited or weak claim"):
        validate_filmmaker_coach(study, weak_audit, coach, packet)
