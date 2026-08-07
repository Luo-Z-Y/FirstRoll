from app.backend.evidence import EvidencePacket
from app.backend.study_service import StudyQualityGate


def test_evidence_packet_types_theory_as_framework_not_observation() -> None:
    packet = EvidencePacket.from_retrieval(
        {"title": "Example", "year": 2020, "directors": ["Director"]},
        {
            "method": "hybrid_rrf",
            "candidate_count": 25,
            "passages": [
                {
                    "title": "Film Form",
                    "page": 12,
                    "excerpt": "Framing selects and organises visible information.",
                    "language": "en",
                }
            ],
        },
        "framing",
    )

    assert packet.theory_sources[0].evidence_type == "theory_framework"
    assert "analytical concept" in packet.theory_sources[0].permitted_claims[0]
    assert packet.retrieval["method"] == "hybrid_rrf"


def test_quality_gate_rejects_generic_unobservable_prose() -> None:
    study = {
        "sections": [
            {
                "lens": "Cinematography",
                "theory_explains": "The visual approach invites the viewer into a meditative space.",
                "hypothesis": "The film creates a sense of ambiguity.",
                "mechanism": "It feels ambiguous and meaningful to an audience.",
                "verify": "Watch the imagery carefully.",
                "critic_claim_ids": [],
            }
        ]
    }

    report = StudyQualityGate.evaluate(study, has_criticism=False)

    assert report["status"] == "insufficient_evidence"
    assert "generic_language" in report["sections"][0]["issues"]
    assert "verification_not_observable" in report["sections"][0]["issues"]


def test_quality_gate_rejects_overconfident_thesis_before_clip_evidence() -> None:
    study = {
        "central_argument": "The film employs deliberate framing that isolates every character.",
        "sections": [
            {
                "lens": "Framing",
                "theory_explains": "Framing determines the visible field and offscreen relations.",
                "hypothesis": "Test whether wider framings might separate figures across the room.",
                "mechanism": "By increasing visible distance, the composition could weaken proximity.",
                "verify": "Log and compare shot scale and figure position in each sequence.",
                "critic_claim_ids": [],
            }
        ],
    }

    report = StudyQualityGate.evaluate(study, has_criticism=False)

    assert report["status"] == "insufficient_evidence"
    assert report["central_issues"] == ["central_argument_overclaims_unseen_form"]
