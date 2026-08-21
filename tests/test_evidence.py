from app.backend.evidence import EvidencePacket
from app.backend.criticism import CriticalClaim, ReviewSource
from app.backend.study_service import StudyQualityGate
from app.backend.video_sources import FilmVideo, VideoTextTrack


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


def test_evidence_packet_retains_reconciled_crew_and_provenance() -> None:
    packet = EvidencePacket.from_retrieval(
        {
            "title": "Example",
            "year": 2026,
            "credits": {
                "directors": ["Director"],
                "writers": ["Writer"],
                "producers": ["Producer"],
                "cinematographers": ["Cinematographer"],
                "editors": ["Editor"],
            },
            "crew_sources": [{"name": "Wikipedia infobox", "fields": ["editors"]}],
        },
        {"method": "hybrid_rrf", "passages": []},
        None,
    )

    assert packet.film_record["producers"] == ["Producer"]
    assert packet.film_record["editors"] == ["Editor"]
    assert packet.film_record["crew_sources"][0]["name"] == "Wikipedia infobox"


def test_evidence_packet_includes_review_bodies_and_typed_video_text() -> None:
    review = ReviewSource(
        source_id="R1",
        provider="The Guardian public web",
        review_id="review-1",
        title="A spatial argument",
        summary="The critic connects repeated corridors to the characters' constrained choices.",
        author="A Critic",
        url="https://www.theguardian.com/film/review-1",
        language="en",
    )
    video = FilmVideo(
        platform="YouTube",
        video_id="abcdefghijk",
        title="Director interview",
        creator="Festival channel",
        description="A conversation about writing, casting and the production process.",
        url="https://www.youtube.com/watch?v=abcdefghijk",
        embed_url="https://www.youtube-nocookie.com/embed/abcdefghijk",
        category="interview",
        relevance="title_and_director",
        text_tracks=[
            VideoTextTrack(
                kind="auto_captions",
                language="en",
                text="The speaker explains that rehearsal changed how the scene was blocked.",
                source_url="https://www.youtube.com/watch?v=abcdefghijk",
            )
        ],
    )

    packet = EvidencePacket.from_retrieval(
        {"title": "Example", "year": 2024},
        {"passages": []},
        None,
        reviews=[review],
        videos=[video],
    )

    assert [source.evidence_id for source in packet.attributed_sources] == ["E1", "E2", "E3"]
    assert packet.attributed_sources[0].content == review.summary
    assert packet.attributed_sources[1].locator == "YouTube · uploader description · Festival channel"
    assert packet.attributed_sources[2].locator == "YouTube · auto_captions · Festival channel"
    assert packet.attributed_sources[2].evidence_type == "critic_reported"
    assert any("speaker identity" in boundary for boundary in packet.boundaries)
    selection = packet.retrieval["attributed_selection"]
    assert selection["candidate_items"] == 3
    assert selection["selected_items"] == 3
    assert selection["omitted_items"] == 0
    assert selection["truncated_items"] == 0


def test_evidence_packet_reports_bounded_attributed_omissions_without_source_text() -> None:
    reviews = [
        ReviewSource(
            source_id=f"R{index}",
            provider="Synthetic publication",
            review_id=f"review-{index}",
            title=f"Review {index}",
            summary=chr(96 + index) * 7000,
            author="Synthetic critic",
            url=f"https://example.org/review-{index}",
            language="en",
        )
        for index in range(1, 9)
    ]

    packet = EvidencePacket.from_retrieval(
        {"title": "Example", "year": 2024},
        {"passages": []},
        None,
        reviews=reviews,
    )

    selection = packet.retrieval["attributed_selection"]
    assert len(packet.attributed_sources) == 4
    assert selection == {
        "candidate_items": 8,
        "selected_items": 4,
        "omitted_items": 4,
        "truncated_items": 4,
        "input_characters": 56000,
        "selected_characters": 12000,
        "omitted_characters": 44000,
        "maximum_items": 12,
        "maximum_total_characters": 18000,
        "maximum_item_characters": 3000,
        "focus_ranked": True,
        "selected_origin_count": 4,
        "selected_domain_count": 1,
        "omission_reasons": {
            "below_minimum_content": 0,
            "duplicate": 0,
            "source_quota": 4,
            "item_limit": 0,
            "total_budget_exhausted": 0,
        },
    }
    assert "Synthetic critic" not in str(selection)
    assert "x" * 40 not in str(selection)


def test_evidence_packet_enforces_focus_aware_layer_budgets() -> None:
    passages = [
        {
            "title": f"Framework {index}",
            "page": index,
            "language": "en",
            "excerpt": (
                f"Framing framework topic{index} compares position, boundary, depth and "
                "offscreen relations through a distinct synthetic example."
            ),
        }
        for index in range(1, 11)
    ]
    reviews = [
        ReviewSource(
            source_id=f"R{index}",
            provider=f"Synthetic provider {index}",
            review_id=f"review-{index}",
            title=f"Review {index}",
            summary=(
                f"Critic topic{index} argues that framing relation {index} directs attention "
                "through a distinct synthetic interpretation requiring close viewing."
            ),
            author=f"Critic {index}",
            url=f"https://source{index}.example/review",
            language="en",
        )
        for index in range(1, 21)
    ]
    claims = [
        CriticalClaim(
            claim_id=f"C{index}",
            source_id=f"R{index}",
            critic_claim=(
                f"Critic topic{index} proposes a distinct framing relation that should be "
                "verified through close viewing."
            ),
            lens_tags=["cinematography"],
            extraction_confidence="high",
        )
        for index in range(1, 21)
    ]

    packet = EvidencePacket.from_retrieval(
        {"title": "Example", "year": 2024, "directors": ["Director"]},
        {"method": "test", "candidate_count": 100, "passages": passages},
        "framing",
        claims,
        reviews=reviews,
    )

    assert [item.evidence_id for item in packet.theory_sources] == [
        f"S{index}" for index in range(1, 9)
    ]
    assert [claim.claim_id for claim in packet.critical_claims] == [
        f"C{index}" for index in range(1, 13)
    ]
    assert [item.evidence_id for item in packet.attributed_sources] == [
        f"E{index}" for index in range(1, 13)
    ]
    assert packet.retrieval["theory_selection"]["omission_reasons"]["item_limit"] == 2
    assert packet.retrieval["critical_selection"]["omission_reasons"]["item_limit"] == 8
    assert packet.retrieval["attributed_selection"]["omission_reasons"]["item_limit"] == 8


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


def test_quality_gate_scores_generic_language_without_blocking_acceptance() -> None:
    study = {
        "central_argument": (
            "Test whether repeated framings may organise a changing relation between "
            "the characters and their surroundings."
        ),
        "sections": [
            {
                "lens": "Framing",
                "theory_explains": "Framing determines the visible field and offscreen relations.",
                "hypothesis": (
                    "Test whether the repeated framing invites the viewer to compare distance; "
                    "if so, it might organise the surrounding space."
                ),
                "mechanism": "By increasing visible separation, the framing could weaken proximity.",
                "verify": "Log and compare shot scale and figure position in each sequence.",
                "critic_claim_ids": [],
            }
        ],
    }

    report = StudyQualityGate.evaluate(study, has_criticism=False)

    assert report["status"] == "passed"
    assert report["score"] == 0.8
    assert report["sections"][0]["issues"] == ["generic_language"]


def test_quality_gate_scores_a_generic_central_argument_without_blocking() -> None:
    study = {
        "central_argument": (
            "This viewing hypothesis invites the viewer to test whether repeated framing may "
            "organise the characters' changing relation to their surroundings."
        ),
        "sections": [
            {
                "lens": "Framing",
                "theory_explains": "Framing determines the visible field and offscreen relations.",
                "hypothesis": "Test whether wider framings might separate figures across the room.",
                "mechanism": "By increasing visible separation, the framing could weaken proximity.",
                "verify": "Log and compare shot scale and figure position in each sequence.",
                "critic_claim_ids": [],
            }
        ],
    }

    report = StudyQualityGate.evaluate(study, has_criticism=False)

    assert report["status"] == "passed"
    assert report["score"] == 0.95
    assert report["central_issues"] == ["central_argument_generic"]


def test_quality_gate_scores_weak_causal_signalling_without_blocking_acceptance() -> None:
    study = {
        "central_argument": (
            "Test whether repeated framings may organise a changing relation between "
            "the characters and their surroundings."
        ),
        "sections": [
            {
                "lens": "Framing",
                "theory_explains": "Framing determines the visible field and offscreen relations.",
                "hypothesis": "Test whether wider framings might separate figures across the room.",
                "mechanism": (
                    "Greater visible separation makes emotional proximity harder to sustain "
                    "while keeping both figures legible within the surrounding space."
                ),
                "verify": "Log and compare shot scale and figure position in each sequence.",
                "critic_claim_ids": [],
            }
        ],
    }

    report = StudyQualityGate.evaluate(study, has_criticism=False)

    assert report["status"] == "passed"
    assert report["score"] == 0.8
    assert report["sections"][0]["issues"] == ["mechanism_not_causal"]


def test_quality_gate_blocks_an_absent_mechanism() -> None:
    study = {
        "central_argument": (
            "Test whether repeated framings may organise a changing relation between "
            "the characters and their surroundings."
        ),
        "sections": [
            {
                "lens": "Framing",
                "theory_explains": "Framing determines the visible field and offscreen relations.",
                "hypothesis": "Test whether wider framings might separate figures across the room.",
                "mechanism": "Not supplied.",
                "verify": "Log and compare shot scale and figure position in each sequence.",
                "critic_claim_ids": [],
            }
        ],
    }

    report = StudyQualityGate.evaluate(study, has_criticism=False)

    assert report["status"] == "insufficient_evidence"
    assert report["sections"][0]["issues"] == ["mechanism_missing"]


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
