import sqlite3
import tempfile
from pathlib import Path

import numpy as np

from app.backend.library_index import SCHEMA_VERSION, LocalLibraryIndex, QueryPlanner
from app.backend.study_observability import StudyTrace


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


def test_unavailable_index_records_planning_and_skips_retrieval_work() -> None:
    with tempfile.TemporaryDirectory() as directory:
        trace = StudyTrace()
        result = LocalLibraryIndex(Path(directory) / "missing.sqlite3").retrieve_for_film(
            {"title": "Example"},
            focus="Framing",
            trace=trace,
        )

    stages = {stage["name"]: stage for stage in trace.snapshot()["stages"]}
    assert result["method"] == "unavailable"
    assert stages["retrieval_planning"]["status"] == "completed"
    assert stages["lexical_retrieval"]["status"] == "skipped"
    assert stages["semantic_retrieval"]["status"] == "skipped"
    assert stages["fusion_and_selection"]["status"] == "skipped"


def test_hybrid_retrieval_records_each_applicable_stage() -> None:
    class FakeEncoder:
        model_name = "test-encoder"

        @staticmethod
        def encode(texts):
            return np.tile(np.asarray([[1.0, 0.0]], dtype=np.float32), (len(texts), 1))

    text = " ".join(
        [
            "Framing and camera position organise spatial relations through depth and viewpoint."
            for _ in range(8)
        ]
    )
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "library.sqlite3"
        index = LocalLibraryIndex(path, encoder=FakeEncoder())
        with sqlite3.connect(path) as connection:
            index._create_schema(connection)
            row = (
                "chunk-1",
                "document-1",
                "Synthetic film-form source",
                12,
                "Framing",
                "cinematography | space",
                "en",
                80,
                text,
            )
            connection.execute("INSERT INTO chunk_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", row)
            connection.execute(
                "INSERT INTO chunks(chunk_id, document_id, title, page, section, topics, text) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (row[0], *row[1:6], text),
            )
            vector = np.asarray([1.0, 0.0], dtype=np.float32)
            connection.execute(
                "INSERT INTO embeddings VALUES (?, ?, ?)",
                (row[0], len(vector), vector.tobytes()),
            )
            connection.executemany(
                "INSERT INTO index_meta VALUES (?, ?)",
                (
                    ("schema_version", SCHEMA_VERSION),
                    ("built_at", "2026-08-21T00:00:00+00:00"),
                    ("chunking_version", "test"),
                    ("embedding_model", "test-encoder"),
                ),
            )
            connection.commit()

        trace = StudyTrace()
        result = index.retrieve_for_film(
            {"title": "Example"},
            focus="How does framing organise space?",
            limit=1,
            trace=trace,
        )

    stages = {stage["name"]: stage for stage in trace.snapshot()["stages"]}
    assert result["method"] == "hybrid_rrf"
    assert len(result["passages"]) == 1
    assert stages["retrieval_planning"]["status"] == "completed"
    assert stages["lexical_retrieval"]["status"] == "completed"
    assert stages["semantic_retrieval"]["status"] == "completed"
    assert stages["fusion_and_selection"]["status"] == "completed"
