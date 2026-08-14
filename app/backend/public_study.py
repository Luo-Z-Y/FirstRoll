from __future__ import annotations

from typing import Any


PUBLIC_STUDY_PASSAGES = (
    {
        "title": "FirstRoll formal-analysis protocol — framing and space",
        "concept": "Composition and spatial organisation",
        "page": 1,
        "language": "en",
        "excerpt": (
            "Treat framing as a set of relationships rather than a decorative quality. Track how "
            "figures, objects, depth layers, boundaries, empty areas and off-screen space distribute "
            "attention. Compare repeated compositions before inferring a pattern. A credible claim "
            "should name the visible relation, propose what it may organise for a viewer, and state "
            "what contrary example would weaken the interpretation."
        ),
    },
    {
        "title": "FirstRoll formal-analysis protocol — duration and editing",
        "concept": "Temporal pattern and transition",
        "page": 2,
        "language": "en",
        "excerpt": (
            "Study time through observable contrasts: shot duration, repetition, omission, transition, "
            "event density and the relation between screen time and story information. Do not call a "
            "film slow or fragmented without a comparison. Form a viewing hypothesis, then log several "
            "sequences and test whether the proposed rhythm persists, changes at a threshold, or is "
            "better explained by performance, sound or narrative structure."
        ),
    },
    {
        "title": "FirstRoll formal-analysis protocol — movement and sound",
        "concept": "Audiovisual relation",
        "page": 3,
        "language": "en",
        "excerpt": (
            "Separate camera movement, movement within the frame and changes created by editing before "
            "describing their combined effect. Treat dialogue, ambience, music and silence as relations "
            "to image and duration, not as automatic mood labels. Mark entrances, exits, overlaps and "
            "withheld sounds. Use these observations to ask whether attention is being directed, delayed "
            "or divided, while preserving alternative explanations."
        ),
    },
    {
        "title": "FirstRoll formal-analysis protocol — performance and viewpoint",
        "concept": "Performance, narration and access",
        "page": 4,
        "language": "en",
        "excerpt": (
            "Analyse performance through specific, repeatable features such as posture, gesture, gaze, "
            "timing, vocal delivery and interaction with the setting. Distinguish what the narration "
            "shows, tells, delays and restricts from what a character appears to know. Any interpretation "
            "of interiority or intention should remain conditional until several moments can be compared "
            "and competing readings have been considered."
        ),
    },
)


def build_public_study_retrieval(film: dict[str, Any], focus: str | None) -> dict[str, Any]:
    """Return a bounded first-party framework for the hosted, clip-free study demo."""

    title = str(film.get("title") or "the selected film")
    question = (focus or "formal organisation and viewing hypotheses").strip()
    return {
        "passages": [dict(passage) for passage in PUBLIC_STUDY_PASSAGES],
        "method": "firstroll_public_framework",
        "candidate_count": len(PUBLIC_STUDY_PASSAGES),
        "plan": [
            {
                "origin": "FirstRoll public framework",
                "lens": passage["concept"],
                "query": f"{title}: {question}",
            }
            for passage in PUBLIC_STUDY_PASSAGES
        ],
        "embedding": {
            "state": "first_party_framework",
            "model": None,
        },
    }
