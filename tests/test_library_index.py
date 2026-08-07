from app.backend.library_index import LocalLibraryIndex, QueryPlanner


def test_excerpt_repairs_common_pdf_extraction_spacing() -> None:
    text = (
        "Th e fi lm contains pas - sages about narrative form. "
        "Narrative guides th e filmmaker's choices and helps y ou understand structure. "
        "Th is formal pattern is visible. "
        "A second sentence supplies enough context for a useful reading card."
    )

    excerpt = LocalLibraryIndex._excerpt(text, "Narrative")

    assert "The film contains passages" in excerpt
    assert "the filmmaker's choices" in excerpt
    assert "you understand" in excerpt
    assert "This formal pattern" in excerpt


def test_excerpt_removes_known_running_heading() -> None:
    text = (
        "198 CHAPTER 5 The Shot: Cinematography Camera distance shapes framing. "
        "The camera can organise visual information for the viewer."
    )

    excerpt = LocalLibraryIndex._excerpt(text, "Cinematography")

    assert excerpt.startswith("Camera distance")
    assert "CHAPTER" not in excerpt


def test_token_chunks_overlap_and_stable_ids() -> None:
    text = "\n\n".join(
        [
            "CAMERA MOVEMENT",
            " ".join(f"Sentence {index} describes camera movement and spatial relation." for index in range(40)),
        ]
    )
    chunks = list(LocalLibraryIndex._chunks(text, target_tokens=80, overlap_tokens=18))

    assert len(chunks) > 2
    assert all(chunk.section == "CAMERA MOVEMENT" for chunk in chunks)
    assert LocalLibraryIndex._chunk_id("book", 12, chunks[0].text) == LocalLibraryIndex._chunk_id(
        "book", 12, chunks[0].text
    )
    first_words = set(chunks[0].text.split())
    second_words = set(chunks[1].text.split())
    assert first_words & second_words


def test_query_planner_uses_focus_instead_of_fixed_generic_lenses() -> None:
    plan = QueryPlanner.plan("How does framing create spatial hierarchy?")

    assert plan[0]["origin"] == "user_focus"
    assert plan[0]["lens"] == "cinematography"
    assert any("lens" in item["query"] for item in plan)
