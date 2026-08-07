from __future__ import annotations

import html
import os
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, ConfigDict, Field

from app.backend.settings import LocalSettingsStore


class CriticismError(RuntimeError):
    """Raised when an optional criticism provider cannot produce usable evidence."""


class ReviewSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    provider: str
    review_id: str
    title: str
    summary: str
    rating_label: str | None = None
    author: str | None = None
    url: str
    language: str
    content_scope: Literal["provider_summary"] = "provider_summary"


class CriticalClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    source_id: str
    critic_claim: str = Field(min_length=20, max_length=1200)
    scene_or_sequence: str | None = Field(default=None, max_length=300)
    described_observation: str | None = Field(default=None, max_length=900)
    techniques: list[str] = Field(default_factory=list, max_length=8)
    interpretation: str | None = Field(default=None, max_length=1000)
    alternative_reading: str | None = Field(default=None, max_length=700)
    lens_tags: list[str] = Field(min_length=1, max_length=4)
    short_source_excerpt: str | None = Field(default=None, max_length=240)
    evidence_status: Literal["critic_reported"] = "critic_reported"
    extraction_confidence: Literal["high", "medium", "low"]
    missing_fields: list[str] = Field(default_factory=list)


class CriticalClaimPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[CriticalClaim] = Field(default_factory=list, max_length=12)


class CriticalResearchBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    film_id: str
    provider: str
    provider_film_id: str
    provider_film_title: str
    fetched_at: str
    reviews: list[ReviewSource]
    claims: list[CriticalClaim]
    notice: str


class DoubanMcpAdapter:
    """Optional stdio adapter for moria97/douban-mcp."""

    def __init__(self, settings: LocalSettingsStore, server_path: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        configured = os.getenv("FIRSTROLL_DOUBAN_MCP_PATH", "").strip()
        self.server_path = server_path or (
            Path(configured)
            if configured
            else project_root / ".firstroll" / "connectors" / "douban-mcp" / "dist" / "index.js"
        )
        self.settings = settings

    def status(self) -> dict[str, Any]:
        return {
            "provider": "Douban MCP",
            "state": "ready" if self.server_path.is_file() else "not_installed",
            "installed": self.server_path.is_file(),
            "cookie_configured": self.settings.secret_state("douban").configured,
            "content_scope": "review summaries",
            "unofficial": True,
        }

    async def test_connection(self) -> dict[str, Any]:
        if not self.server_path.is_file():
            raise CriticismError("Douban MCP is not installed.")
        environment = {"PATH": os.getenv("PATH", "")}
        cookie = self.settings.effective_secret("douban")
        if cookie:
            environment["COOKIE"] = cookie
        parameters = StdioServerParameters(
            command="node",
            args=[str(self.server_path)],
            env=environment,
            cwd=self.server_path.parent.parent,
        )
        try:
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
        except Exception as exc:
            raise CriticismError(f"Douban MCP failed to initialise: {exc}") from exc
        names = [tool.name for tool in tools.tools]
        required = {"search-movie", "list-movie-reviews"}
        if not required.issubset(names):
            raise CriticismError("Douban MCP is missing the required movie-review tools.")
        return {
            "message": "Douban MCP started successfully.",
            "tools": sorted(required),
            "cookie_configured": bool(cookie),
        }

    async def fetch_reviews(
        self,
        film: dict[str, Any],
        limit: int = 8,
    ) -> tuple[str, str, list[ReviewSource]]:
        if not self.server_path.is_file():
            raise CriticismError(
                "Douban MCP is not installed. Follow the optional connector setup guide."
            )
        title = str(film.get("title") or "").strip()
        if not title:
            raise CriticismError("The film record has no title for Douban matching.")
        environment = {"PATH": os.getenv("PATH", "")}
        cookie = self.settings.effective_secret("douban")
        if cookie:
            environment["COOKIE"] = cookie
        parameters = StdioServerParameters(
            command="node",
            args=[str(self.server_path)],
            env=environment,
            cwd=self.server_path.parent.parent,
        )
        try:
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    search_text = await self._call_text(session, "search-movie", {"q": title})
                    candidates = self._markdown_table(search_text)
                    match = self._choose_match(film, candidates)
                    review_text = await self._call_text(
                        session,
                        "list-movie-reviews",
                        {"id": match["id"]},
                    )
        except CriticismError:
            raise
        except Exception as exc:
            raise CriticismError(f"Douban MCP failed: {exc}") from exc
        rows = self._markdown_table(review_text)[:limit]
        reviews = [
            ReviewSource(
                source_id=f"R{index}",
                provider="Douban",
                review_id=row.get("id", ""),
                title=row.get("title") or "Untitled review",
                summary=row.get("summary") or "",
                rating_label=row.get("rating") or None,
                author=None,
                url=f"https://movie.douban.com/review/{row.get('id', '')}/",
                language=self._language(row.get("summary", "")),
            )
            for index, row in enumerate(rows, 1)
            if row.get("id") and row.get("summary")
        ]
        if not reviews:
            raise CriticismError(
                self._review_response_error(
                    review_text,
                    rows,
                    cookie_configured=bool(cookie),
                )
            )
        return match["id"], match.get("title") or title, reviews

    @staticmethod
    async def _call_text(
        session: ClientSession,
        tool: str,
        arguments: dict[str, Any],
    ) -> str:
        result = await session.call_tool(tool, arguments=arguments)
        if result.isError:
            raise CriticismError(f"Douban MCP tool {tool} returned an error.")
        parts = [getattr(item, "text", "") for item in result.content]
        return "\n".join(part for part in parts if part)

    @staticmethod
    def _markdown_table(value: str) -> list[dict[str, str]]:
        lines = value.splitlines()
        table_start = next(
            (index for index, line in enumerate(lines) if line.strip().startswith("|")),
            None,
        )
        if table_start is None:
            return []
        headers = DoubanMcpAdapter._table_cells(lines[table_start].strip())
        if not headers:
            return []
        separator_index = next(
            (
                index
                for index in range(table_start + 1, len(lines))
                if DoubanMcpAdapter._is_table_separator(lines[index])
            ),
            None,
        )
        if separator_index is None:
            return []

        logical_rows: list[str] = []
        current: list[str] = []
        for line in lines[separator_index + 1 :]:
            stripped = line.strip()
            cells = (
                DoubanMcpAdapter._table_cells(stripped)
                if stripped.startswith("|")
                else []
            )
            if DoubanMcpAdapter._is_table_row_start(headers, cells):
                if current:
                    logical_rows.append(" ".join(current))
                current = [stripped]
            elif current and stripped:
                current.append(stripped)
        if current:
            logical_rows.append(" ".join(current))

        rows: list[dict[str, str]] = []
        for line in logical_rows:
            cells = DoubanMcpAdapter._table_cells(line)
            cells = DoubanMcpAdapter._merge_summary_cells(headers, cells)
            if len(cells) != len(headers):
                continue
            rows.append(dict(zip(headers, cells)))
        return rows

    @staticmethod
    def _is_table_separator(line: str) -> bool:
        cells = DoubanMcpAdapter._table_cells(line.strip())
        return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)

    @staticmethod
    def _is_table_row_start(headers: list[str], cells: list[str]) -> bool:
        if not cells:
            return False
        if "rating" in headers:
            rating_index = headers.index("rating")
            if rating_index >= len(cells):
                return False
            return bool(re.match(r"^\d+(?:\.\d+)?\s*\(", cells[rating_index]))
        if len(cells) != len(headers):
            return False
        if "id" in headers:
            return bool(cells[headers.index("id")])
        return True

    @staticmethod
    def _merge_summary_cells(headers: list[str], cells: list[str]) -> list[str]:
        if len(cells) <= len(headers) or "summary" not in headers:
            return cells
        summary_index = headers.index("summary")
        trailing_count = len(headers) - summary_index - 1
        if trailing_count <= 0:
            return cells[:summary_index] + [" | ".join(cells[summary_index:])]
        summary_end = len(cells) - trailing_count
        return (
            cells[:summary_index]
            + [" | ".join(cells[summary_index:summary_end])]
            + cells[summary_end:]
        )

    @staticmethod
    def _table_cells(line: str) -> list[str]:
        cells = re.split(r"(?<!\\)\|", line.strip().strip("|"))
        return [
            html.unescape(cell.replace("\\|", "|").replace("<br>", " ").strip())
            for cell in cells
        ]

    @staticmethod
    def _review_response_error(
        value: str,
        rows: list[dict[str, str]],
        *,
        cookie_configured: bool,
    ) -> str:
        """Classify an unusable provider response without exposing credentials or full text."""
        normalised = re.sub(r"\s+", " ", html.unescape(value)).strip()
        folded = normalised.casefold()
        authentication_markers = (
            "captcha",
            "forbidden",
            "log in",
            "login",
            "sign in",
            "unauthorised",
            "unauthorized",
            "verify you are human",
            "异常请求",
            "登录",
            "验证码",
            "访问受限",
        )
        empty_markers = (
            "0 reviews",
            "no reviews",
            "no movie reviews",
            "暂无影评",
            "没有影评",
            "还没有影评",
        )

        if any(marker in folded for marker in authentication_markers):
            credential_guidance = (
                "The configured cookie may have expired; replace it in Settings and try again."
                if cookie_configured
                else "Add your personal Douban cookie in Settings and try again."
            )
            return f"Douban blocked the review request or requires authentication. {credential_guidance}"

        if any(marker in folded for marker in empty_markers) or DoubanMcpAdapter._empty_table(value):
            return "Douban returned a valid response, but no long-form review summaries were available for this film."

        if rows:
            columns = sorted({column for row in rows for column in row})
            missing = sorted({"id", "summary"} - set(columns))
            if missing:
                return (
                    "Douban MCP returned a review table in an unsupported format "
                    f"(missing columns: {', '.join(missing)}; received: {', '.join(columns)}). "
                    "The connector or FirstRoll adapter may need updating."
                )
            return (
                "Douban returned review rows, but none contained both an attributed review ID "
                "and a non-empty summary."
            )

        preview = DoubanMcpAdapter._safe_response_preview(normalised)
        suffix = f' Provider response preview: "{preview}"' if preview else ""
        return (
            "Douban MCP returned an unsupported response instead of a review table. "
            "The connector or FirstRoll adapter may need updating."
            f"{suffix}"
        )

    @staticmethod
    def _empty_table(value: str) -> bool:
        table_lines = [line.strip() for line in value.splitlines() if line.strip().startswith("|")]
        return len(table_lines) == 2 and bool(DoubanMcpAdapter._markdown_table(value) == [])

    @staticmethod
    def _safe_response_preview(value: str, limit: int = 180) -> str:
        if not value:
            return ""
        redacted = re.sub(
            r"(?i)\b(cookie|authorization|token|api[-_ ]?key)\s*[:=]\s*[^\s,;]+",
            r"\1=[redacted]",
            value,
        )
        redacted = re.sub(r"https?://\S+", "[link]", redacted)
        return redacted if len(redacted) <= limit else f"{redacted[: limit - 1].rstrip()}…"

    @staticmethod
    def _choose_match(film: dict[str, Any], candidates: list[dict[str, str]]) -> dict[str, str]:
        if not candidates:
            raise CriticismError("Douban returned no film matches.")
        target_title = str(film.get("title") or "").casefold()
        original_title = str(film.get("original_title") or "").casefold()
        target_year = str(film.get("year") or "")

        def score(candidate: dict[str, str]) -> float:
            title = candidate.get("title", "").casefold()
            subtitle = candidate.get("subtitle", "").casefold()
            title_score = max(
                SequenceMatcher(None, target_title, title).ratio(),
                SequenceMatcher(None, original_title, title).ratio() if original_title else 0,
            )
            year_score = 0.25 if target_year and candidate.get("publish_date") == target_year else 0
            subtitle_score = 0.1 if target_year and target_year in subtitle else 0
            return title_score + year_score + subtitle_score

        match = max(candidates, key=score)
        if score(match) < 0.55 or not match.get("id"):
            raise CriticismError("Douban did not return a confident film identity match.")
        return match

    @staticmethod
    def _language(value: str) -> str:
        chinese = len(re.findall(r"[\u3400-\u9fff]", value))
        return "zh" if chinese >= max(2, len(value) // 12) else "und"


class CriticismStore:
    """Private cache for attributed, structured criticism."""

    def __init__(self, directory: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.directory = directory or project_root / ".firstroll" / "criticism"

    def save(self, bundle: CriticalResearchBundle) -> None:
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self._path(bundle.film_id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(path)
        os.chmod(path, 0o600)

    def load(self, film_id: str) -> CriticalResearchBundle | None:
        path = self._path(film_id)
        if not path.is_file():
            return None
        try:
            return CriticalResearchBundle.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _path(self, film_id: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", film_id).strip("-") or "film"
        return self.directory / f"{safe}.json"


def build_bundle(
    film_id: str,
    provider_film_id: str,
    provider_film_title: str,
    reviews: list[ReviewSource],
    claims: list[CriticalClaim],
) -> CriticalResearchBundle:
    return CriticalResearchBundle(
        film_id=film_id,
        provider="Douban",
        provider_film_id=provider_film_id,
        provider_film_title=provider_film_title,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        reviews=reviews,
        claims=claims,
        notice=(
            "These are model-structured claims from attributed Douban review summaries. "
            "They are secondary criticism, not verified observations or creator statements."
        ),
    )
