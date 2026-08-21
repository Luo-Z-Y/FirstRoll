from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, RLock, Thread
from time import perf_counter
from typing import Any, Iterable, Protocol, Sequence

import numpy as np

from app.backend.library import LocalLibraryCatalogue
from app.backend.study_observability import StudyTrace


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
SCHEMA_VERSION = "2"
CHUNKING_VERSION = "token-v1"


class Encoder(Protocol):
    model_name: str

    def encode(self, texts: Sequence[str]) -> np.ndarray: ...


class SentenceTransformerEncoder:
    """Lazy local encoder. No passage text is sent to an embedding API."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv(
            "FIRSTROLL_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL
        )
        self._model: Any = None
        self._model_lock = Lock()
        self._encode_lock = Lock()

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(self.model_name)
        with self._encode_lock:
            values = self._model.encode(
                list(texts),
                batch_size=32,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=len(texts) > 100,
            )
        return np.asarray(values, dtype=np.float32)


@dataclass(frozen=True)
class TextChunk:
    text: str
    section: str | None
    token_count: int


class QueryPlanner:
    """Expands a study focus and attributed criticism into craft-specific searches."""

    LENSES: dict[str, tuple[str, ...]] = {
        "cinematography": (
            "cinematography framing composition lens camera movement depth focus shot scale",
            "spatial relations camera position viewpoint visual field",
        ),
        "mise-en-scene": (
            "mise en scene staging blocking setting costume performance",
            "screen space movement composition visual hierarchy",
        ),
        "editing": (
            "editing cutting montage duration rhythm continuity discontinuity",
            "shot relation temporal order pacing graphic match",
        ),
        "narrative": (
            "narrative form narration plot story causality time point of view",
            "restricted knowledge repetition parallelism structure",
        ),
        "sound": (
            "film sound dialogue music noise silence diegetic perspective",
            "sound bridge rhythm acoustic space point of audition",
        ),
        "colour-light": (
            "colour color lighting contrast tonality exposure composition",
            "light shadow palette saturation visual emphasis",
        ),
    }

    @classmethod
    def plan(
        cls,
        focus: str | None,
        critical_claims: Sequence[Any] | None = None,
    ) -> list[dict[str, str]]:
        raw = (focus or "").strip()
        lowered = raw.casefold()
        aliases = {
            "cinematography": ("camera", "cinematograph", "framing", "lens", "shot"),
            "mise-en-scene": ("mise", "staging", "blocking", "performance", "space"),
            "editing": ("edit", "cut", "montage", "rhythm", "pace"),
            "narrative": ("narrative", "story", "plot", "structure", "point of view"),
            "sound": ("sound", "music", "silence", "dialogue", "noise"),
            "colour-light": ("colour", "color", "light", "shadow", "palette"),
        }
        selected = [name for name, terms in aliases.items() if any(term in lowered for term in terms)]
        if not selected:
            selected = ["narrative", "cinematography", "editing", "mise-en-scene", "sound"]

        plan: list[dict[str, str]] = []
        if raw:
            plan.append({"origin": "user_focus", "lens": selected[0], "query": raw})
        for lens in selected:
            for query in cls.LENSES[lens]:
                plan.append({"origin": "craft_taxonomy", "lens": lens, "query": query})
        for claim in critical_claims or []:
            claim_text = str(getattr(claim, "critic_claim", "") or "").strip()
            tags = getattr(claim, "lens_tags", []) or []
            if claim_text:
                plan.append(
                    {
                        "origin": f"critic_claim:{getattr(claim, 'claim_id', '?')}",
                        "lens": str(tags[0] if tags else selected[0]),
                        "query": claim_text[:320],
                    }
                )
        unique: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in plan:
            key = re.sub(r"\W+", " ", item["query"].casefold()).strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(item)
        return unique[:10]


class LocalLibraryIndex:
    """Private hybrid FTS/vector index with stable page-level citations."""

    def __init__(self, path: Path | None = None, encoder: Encoder | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.path = path or Path(
            os.getenv("FIRSTROLL_LIBRARY_INDEX", project_root / ".firstroll/library.sqlite3")
        )
        self.encoder = encoder or SentenceTransformerEncoder()
        self._warmup_lock = RLock()
        self._warmup_complete = Event()
        self._warmup_state = "idle"
        self._warmup_duration_ms: float | None = None

    def status(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "state": "not_built",
                "chunk_count": 0,
                "document_count": 0,
                "warmup": self.embedding_warmup_status(),
            }
        try:
            with sqlite3.connect(self.path) as connection:
                chunk_count = connection.execute("SELECT count(*) FROM chunk_records").fetchone()[0]
                document_count = connection.execute(
                    "SELECT count(DISTINCT document_id) FROM chunk_records"
                ).fetchone()[0]
                meta = dict(connection.execute("SELECT key, value FROM index_meta").fetchall())
                embedding_count = connection.execute("SELECT count(*) FROM embeddings").fetchone()[0]
        except (sqlite3.Error, TypeError):
            return {
                "state": "outdated",
                "chunk_count": 0,
                "document_count": 0,
                "warmup": self.embedding_warmup_status(),
            }
        return {
            "state": "ready" if meta.get("schema_version") == SCHEMA_VERSION else "outdated",
            "chunk_count": chunk_count,
            "document_count": document_count,
            "built_at": meta.get("built_at"),
            "schema_version": meta.get("schema_version"),
            "chunking_version": meta.get("chunking_version"),
            "embedding": {
                "state": "ready" if embedding_count == chunk_count and chunk_count else "unavailable",
                "count": embedding_count,
                "model": meta.get("embedding_model"),
                "local": True,
            },
            "warmup": self.embedding_warmup_status(),
        }

    def embedding_warmup_status(self) -> dict[str, Any]:
        with self._warmup_lock:
            return {
                "state": self._warmup_state,
                "duration_ms": (
                    round(self._warmup_duration_ms, 3)
                    if self._warmup_duration_ms is not None
                    else None
                ),
                "background": True,
            }

    def start_embedding_warmup(self) -> dict[str, Any]:
        """Load the local query encoder once without delaying API startup."""

        index_status = self.status()
        if (
            index_status.get("state") != "ready"
            or index_status.get("embedding", {}).get("state") != "ready"
        ):
            with self._warmup_lock:
                self._warmup_state = "unavailable"
                self._warmup_duration_ms = None
                self._warmup_complete.set()
            return self.embedding_warmup_status()
        with self._warmup_lock:
            if self._warmup_state in {"warming", "ready"}:
                return self.embedding_warmup_status()
            self._warmup_state = "warming"
            self._warmup_duration_ms = None
            self._warmup_complete.clear()
        Thread(
            target=self._run_embedding_warmup,
            name="firstroll-embedding-warmup",
            daemon=True,
        ).start()
        return self.embedding_warmup_status()

    def wait_for_embedding_warmup(self, timeout: float | None = None) -> dict[str, Any]:
        status = self.start_embedding_warmup()
        if status["state"] == "warming":
            self._warmup_complete.wait(timeout)
        return self.embedding_warmup_status()

    def _run_embedding_warmup(self) -> None:
        started = perf_counter()
        state = "ready"
        try:
            self.encoder.encode(("FirstRoll local film-form retrieval warm-up.",))
        except Exception:
            state = "failed"
        duration_ms = (perf_counter() - started) * 1000
        with self._warmup_lock:
            self._warmup_state = state
            self._warmup_duration_ms = duration_ms
            self._warmup_complete.set()

    def build(
        self,
        catalogue: LocalLibraryCatalogue | None = None,
        include_embeddings: bool | None = None,
    ) -> dict[str, Any]:
        from pypdf import PdfReader

        catalogue = catalogue or LocalLibraryCatalogue()
        records = catalogue.index_records()
        include_embeddings = (
            os.getenv("FIRSTROLL_EMBEDDINGS", "1").casefold() not in {"0", "false", "no"}
            if include_embeddings is None
            else include_embeddings
        )
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".building.sqlite3")
        if temporary.exists():
            temporary.unlink()

        connection = sqlite3.connect(temporary)
        pending_ids: list[str] = []
        pending_texts: list[str] = []
        try:
            self._create_schema(connection)
            for number, record in enumerate(records, start=1):
                path = record["path"]
                if path.suffix.casefold() != ".pdf":
                    continue
                print(f"[{number}/{len(records)}] Indexing {record['title']}", flush=True)
                reader = PdfReader(path)
                topics = " | ".join(record["topics"])
                for page_number, page in enumerate(reader.pages, start=1):
                    text = self._normalise_text(page.extract_text() or "")
                    for chunk in self._chunks(text):
                        chunk_id = self._chunk_id(record["id"], page_number, chunk.text)
                        language = self._language(chunk.text)
                        values = (
                            chunk_id,
                            record["id"],
                            record["title"],
                            page_number,
                            chunk.section,
                            topics,
                            language,
                            chunk.token_count,
                            chunk.text,
                        )
                        connection.execute(
                            "INSERT OR IGNORE INTO chunk_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            values,
                        )
                        if connection.total_changes:
                            connection.execute(
                                "INSERT INTO chunks(chunk_id, document_id, title, page, section, topics, text) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (chunk_id, *values[1:6], chunk.text),
                            )
                            pending_ids.append(chunk_id)
                            pending_texts.append(chunk.text)
                connection.commit()
            embedding_model = ""
            if include_embeddings and pending_texts:
                print(f"Embedding {len(pending_texts)} passages locally…", flush=True)
                self._store_embeddings(connection, pending_ids, pending_texts)
                embedding_model = self.encoder.model_name
            meta = {
                "built_at": datetime.now(timezone.utc).isoformat(),
                "schema_version": SCHEMA_VERSION,
                "chunking_version": CHUNKING_VERSION,
                "embedding_model": embedding_model,
            }
            connection.executemany("INSERT INTO index_meta VALUES (?, ?)", meta.items())
            connection.commit()
        finally:
            connection.close()
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)
        os.chmod(self.path, 0o600)
        return self.status()

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            "CREATE TABLE chunk_records (chunk_id TEXT PRIMARY KEY, document_id TEXT, title TEXT, "
            "page INTEGER, section TEXT, topics TEXT, language TEXT, token_count INTEGER, text TEXT)"
        )
        connection.execute(
            "CREATE VIRTUAL TABLE chunks USING fts5(chunk_id UNINDEXED, document_id UNINDEXED, "
            "title UNINDEXED, page UNINDEXED, section UNINDEXED, topics UNINDEXED, text, "
            "tokenize='porter unicode61')"
        )
        connection.execute(
            "CREATE TABLE embeddings (chunk_id TEXT PRIMARY KEY, dimension INTEGER, vector BLOB, "
            "FOREIGN KEY(chunk_id) REFERENCES chunk_records(chunk_id))"
        )
        connection.execute("CREATE TABLE index_meta (key TEXT PRIMARY KEY, value TEXT)")

    def _store_embeddings(
        self, connection: sqlite3.Connection, chunk_ids: Sequence[str], texts: Sequence[str]
    ) -> None:
        for start in range(0, len(texts), 256):
            vectors = self.encoder.encode(texts[start : start + 256])
            rows = [
                (chunk_id, int(vector.shape[0]), vector.astype(np.float32).tobytes())
                for chunk_id, vector in zip(chunk_ids[start : start + 256], vectors, strict=True)
            ]
            connection.executemany("INSERT INTO embeddings VALUES (?, ?, ?)", rows)
            connection.commit()

    def retrieve_for_film(
        self,
        film: dict[str, Any],
        focus: str | None = None,
        critical_claims: Sequence[Any] | None = None,
        limit: int = 8,
        *,
        trace: StudyTrace | None = None,
    ) -> dict[str, Any]:
        with trace.stage("retrieval_planning") if trace else nullcontext():
            status = self.status()
            plan = (
                QueryPlanner.plan(focus, critical_claims)
                if status["state"] == "ready"
                else []
            )
        if status["state"] != "ready":
            if trace:
                trace.skip("lexical_retrieval")
                trace.skip("semantic_retrieval")
                trace.skip("fusion_and_selection")
            return {"status": status, "passages": [], "plan": plan, "method": "unavailable"}
        fused: dict[str, dict[str, Any]] = {}
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            with trace.stage("lexical_retrieval") if trace else nullcontext():
                for item in plan:
                    rows = self._fts_candidates(connection, item["query"], 25)
                    for rank, row in enumerate(rows, start=1):
                        candidate = fused.setdefault(str(row["chunk_id"]), self._candidate(row))
                        candidate["score"] += 1 / (60 + rank)
                        candidate["lexical_rank"] = min(candidate.get("lexical_rank", 999), rank)
                        candidate["reasons"].append(
                            f"lexical · {item['origin']} · {item['lens']}"
                        )
            dense_ready = status.get("embedding", {}).get("state") == "ready"
            if dense_ready:
                try:
                    with trace.stage("semantic_retrieval") if trace else nullcontext():
                        self._add_dense_candidates(connection, plan, fused)
                except (ImportError, OSError, RuntimeError, ValueError):
                    dense_ready = False
            elif trace:
                trace.skip("semantic_retrieval")
            with trace.stage("fusion_and_selection") if trace else nullcontext():
                candidates = sorted(
                    fused.values(), key=lambda item: item["score"], reverse=True
                )
                selected = self._diverse(candidates, limit)
                passages = []
                for candidate in selected:
                    concept = self._concept(f"{candidate['section'] or ''} {candidate['text']}")
                    passages.append(
                        {
                            "chunk_id": candidate["chunk_id"],
                            "document_id": candidate["document_id"],
                            "title": candidate["title"],
                            "page": candidate["page"],
                            "section": candidate["section"],
                            "topics": str(candidate["topics"]).split(" | "),
                            "language": candidate["language"],
                            "concept": concept,
                            "excerpt": self._excerpt(candidate["text"], concept),
                            "source_kind": "private_local_document",
                            "retrieval_score": round(candidate["score"], 6),
                            "retrieval_reason": list(dict.fromkeys(candidate["reasons"]))[:3],
                        }
                    )
        return {
            "status": status,
            "passages": passages,
            "plan": plan,
            "method": "hybrid_rrf" if dense_ready else "fts_rrf",
            "candidate_count": len(candidates),
            "embedding": status.get("embedding", {}),
        }

    def _fts_candidates(
        self, connection: sqlite3.Connection, query: str, limit: int
    ) -> list[sqlite3.Row]:
        terms = [term for term in re.findall(r"[\w]+", query.casefold()) if len(term) > 2]
        if not terms:
            return []
        expression = " OR ".join(f'"{term}"' for term in terms[:16])
        return connection.execute(
            "SELECT c.*, bm25(chunks) AS rank FROM chunks "
            "JOIN chunk_records c ON c.chunk_id = chunks.chunk_id "
            "WHERE chunks MATCH ? ORDER BY rank LIMIT ?",
            (expression, limit),
        ).fetchall()

    def _add_dense_candidates(
        self,
        connection: sqlite3.Connection,
        plan: Sequence[dict[str, str]],
        fused: dict[str, dict[str, Any]],
    ) -> None:
        rows = connection.execute(
            "SELECT c.*, e.dimension, e.vector FROM embeddings e "
            "JOIN chunk_records c ON c.chunk_id = e.chunk_id"
        ).fetchall()
        if not rows:
            return
        matrix = np.vstack(
            [np.frombuffer(row["vector"], dtype=np.float32, count=row["dimension"]) for row in rows]
        )
        queries = self.encoder.encode([item["query"] for item in plan])
        for item, query_vector in zip(plan, queries, strict=True):
            # ``einsum`` avoids spurious Accelerate/BLAS overflow warnings observed on
            # some Apple Silicon builds even though both normalised operands are finite.
            similarities = np.einsum("ij,j->i", matrix, query_vector, optimize=False)
            best = np.argsort(similarities)[-25:][::-1]
            for rank, index in enumerate(best, start=1):
                row = rows[int(index)]
                candidate = fused.setdefault(str(row["chunk_id"]), self._candidate(row))
                candidate["score"] += 1 / (60 + rank)
                candidate["vector_rank"] = min(candidate.get("vector_rank", 999), rank)
                candidate["reasons"].append(f"semantic · {item['origin']} · {item['lens']}")

    @staticmethod
    def _candidate(row: sqlite3.Row) -> dict[str, Any]:
        return {
            key: row[key]
            for key in (
                "chunk_id",
                "document_id",
                "title",
                "page",
                "section",
                "topics",
                "language",
                "text",
            )
        } | {"score": 0.0, "reasons": []}

    @classmethod
    def _diverse(cls, candidates: Sequence[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        document_counts: dict[str, int] = {}
        page_counts: dict[tuple[str, int], int] = {}
        fingerprints: list[set[str]] = []
        for candidate in candidates:
            document_id = str(candidate["document_id"])
            page_key = (document_id, int(candidate["page"]))
            if document_counts.get(document_id, 0) >= 4 or page_counts.get(page_key, 0) >= 2:
                continue
            words = set(re.findall(r"\w+", str(candidate["text"]).casefold()))
            if any(len(words & prior) / max(1, len(words | prior)) > 0.72 for prior in fingerprints):
                continue
            if not cls._usable_text(str(candidate["text"])):
                continue
            selected.append(candidate)
            fingerprints.append(words)
            document_counts[document_id] = document_counts.get(document_id, 0) + 1
            page_counts[page_key] = page_counts.get(page_key, 0) + 1
            if len(selected) >= limit:
                break
        return selected

    @staticmethod
    def _usable_text(text: str) -> bool:
        compact = " ".join(text.split())
        if len(compact) < 240:
            return False
        lowered = compact.casefold()
        if any(
            label in lowered
            for label in (
                "additional resources",
                "table of contents",
                "contents sight sound motion",
            )
        ):
            return False
        standalone_numbers = re.findall(r"(?<!\w)\d{1,3}(?!\w)", compact)
        chapter_labels = len(re.findall(r"\b(chapter|summary)\b", lowered))
        if len(standalone_numbers) > 14 and chapter_labels > 2:
            return False
        return True

    @staticmethod
    def _normalise_text(value: str) -> str:
        value = value.replace("\u00ad", "").replace("\x00", " ")
        value = re.sub(r"(?<=\w)-\s+(?=\w)", "", value)
        value = re.sub(r"[ \t]+", " ", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()

    @classmethod
    def _chunks(
        cls, text: str, target_tokens: int = 420, overlap_tokens: int = 70
    ) -> Iterable[TextChunk]:
        paragraphs = [" ".join(item.split()) for item in re.split(r"\n\s*\n", text)]
        units: list[tuple[str, str | None]] = []
        section: str | None = None
        for paragraph in paragraphs:
            if not paragraph:
                continue
            if len(paragraph) < 120 and cls._looks_like_heading(paragraph):
                section = paragraph[:180]
                continue
            sentences = re.split(r"(?<=[.!?。！？])\s+", paragraph)
            units.extend((sentence, section) for sentence in sentences if sentence.strip())
        current: list[tuple[str, str | None]] = []
        count = 0
        for sentence, sentence_section in units:
            tokens = cls._token_count(sentence)
            if current and count + tokens > target_tokens:
                yield cls._make_chunk(current)
                overlap: list[tuple[str, str | None]] = []
                overlap_count = 0
                for prior in reversed(current):
                    overlap.insert(0, prior)
                    overlap_count += cls._token_count(prior[0])
                    if overlap_count >= overlap_tokens:
                        break
                current = overlap
                count = overlap_count
            current.append((sentence, sentence_section))
            count += tokens
        if current:
            yield cls._make_chunk(current)

    @classmethod
    def _make_chunk(cls, units: Sequence[tuple[str, str | None]]) -> TextChunk:
        text = " ".join(unit[0].strip() for unit in units).strip()
        section = next((unit[1] for unit in reversed(units) if unit[1]), None)
        return TextChunk(text=text, section=section, token_count=cls._token_count(text))

    @staticmethod
    def _looks_like_heading(value: str) -> bool:
        words = value.split()
        return bool(words) and (
            value.isupper()
            or len(words) <= 9 and not value.endswith((".", "?", "!", "。", "？", "！"))
        )

    @staticmethod
    def _token_count(value: str) -> int:
        return len(re.findall(r"[\u3400-\u9fff]|[\w]+|[^\w\s]", value))

    @staticmethod
    def _chunk_id(document_id: str, page: int, text: str) -> str:
        normalised = re.sub(r"\s+", " ", text).strip().casefold()
        digest = hashlib.sha256(f"{document_id}\0{page}\0{normalised}".encode()).hexdigest()[:24]
        return f"ch_{digest}"

    @staticmethod
    def _language(text: str) -> str:
        cjk = len(re.findall(r"[\u3400-\u9fff]", text))
        letters = len(re.findall(r"[A-Za-z]", text))
        if cjk > letters * 0.25:
            return "zh"
        return "en" if letters else "und"

    @staticmethod
    def _excerpt(text: str, concept: str, limit: int = 760) -> str:
        compact = LocalLibraryIndex._clean_display_text(" ".join(text.split()))
        keywords = {
            "Narrative": ("narrative", "narration", "point of view"),
            "Mise-en-scène": ("mise-en-scene", "mise-en-scène", "staging", "blocking"),
            "Cinematography": ("camera", "cinematography", "framing", "lens"),
            "Editing and rhythm": ("editing", "montage", "cutting", "rhythm"),
            "Sound": ("film sound", "sound", "speech", "music"),
            "Colour and light": ("color", "colour", "lighting"),
        }.get(concept, ())
        sentences = re.split(r"(?<=[.!?。！？])\s+", compact)
        start = next(
            (i for i, sentence in enumerate(sentences) if any(k in sentence.casefold() for k in keywords)),
            0,
        )
        excerpt = ""
        for sentence in sentences[start:]:
            if excerpt and len(excerpt) + len(sentence) > limit:
                break
            excerpt = f"{excerpt} {sentence}".strip()
        if len(excerpt) <= limit:
            return excerpt
        return f"{excerpt[:limit].rsplit(' ', 1)[0]}…"

    @staticmethod
    def _clean_display_text(value: str) -> str:
        value = re.sub(r"(?<=\w)\s+-\s+(?=\w)", "", value)
        repairs = {
            r"\bTh e\b": "The",
            r"\bTh is\b": "This",
            r"\bth e\b": "the",
            r"\bth is\b": "this",
            r"\bY ou\b": "You",
            r"\by ou\b": "you",
            r"\bfi lm\b": "film",
            r"\bfi lms\b": "films",
            r"\bfi lmic\b": "filmic",
            r"\bfi lmmaker\b": "filmmaker",
            r"\bfi lmmakers\b": "filmmakers",
            r"\bdefi ne\b": "define",
            r"\bdefi ned\b": "defined",
            r"\bfl ashed\b": "flashed",
        }
        for pattern, replacement in repairs.items():
            value = re.sub(pattern, replacement, value)
        headings = (
            r"^\d+\s+CHAPTER\s+\d+\s+The Shot:\s*Cinematography\s*",
            r"^Fundamentals of Film Sound\s+\d+\s+Fundamentals of Film Sound\s*",
            r"^STRUCTURING COLOR:\s*FUNCTION AND COMPOSITION\s+\d+\s+"
            r"Compositional Function of Color\s*",
        )
        for pattern in headings:
            value = re.sub(pattern, "", value, flags=re.IGNORECASE)
        return re.sub(r"\s{2,}", " ", value).strip()

    @staticmethod
    def _concept(text: str) -> str:
        lowered = text.casefold()
        rules = (
            (("edit", "cutting", "montage"), "Editing and rhythm"),
            (("mise-en-scène", "mise en scene", "staging", "blocking"), "Mise-en-scène"),
            (("camera", "cinematograph", "lens", "framing"), "Cinematography"),
            (("sound", "music", "dialogue"), "Sound"),
            (("narrative", "story", "plot", "point of view"), "Narrative"),
            (("colour", "color", "light"), "Colour and light"),
        )
        return next((concept for needles, concept in rules if any(n in lowered for n in needles)), "Film form")


def main() -> None:
    result = LocalLibraryIndex().build()
    print(
        f"Indexed {result['document_count']} documents into {result['chunk_count']} cited passages "
        f"({result['embedding']['state']} local embeddings).",
        flush=True,
    )


if __name__ == "__main__":
    main()
