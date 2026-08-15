from __future__ import annotations

import html
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlencode, urlparse
from urllib.request import Request, urlopen

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
    claim_status: Literal["pending", "structured"] = "structured"
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
            raise CriticismError(
                f"Douban MCP failed to initialise: {self._mcp_exception_detail(exc)}"
            ) from exc
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
        external_ids = film.get("external_ids")
        imdb_id = (
            str(external_ids.get("imdb") or "").strip()
            if isinstance(external_ids, dict)
            else ""
        )
        # Douban's search accepts IMDb identifiers. Prefer that stable identity key
        # because English, Traditional Chinese and Simplified Chinese titles often
        # cannot be compared reliably as strings.
        search_query = imdb_id or title
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
                    search_text = await self._call_text(
                        session,
                        "search-movie",
                        {"q": search_query},
                    )
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
            nested = self._nested_criticism_error(exc)
            if nested is not None:
                raise CriticismError(str(nested)) from exc
            raise CriticismError(
                f"Douban MCP failed: {self._mcp_exception_detail(exc)}"
            ) from exc
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

    async def fetch_score(self, film: dict[str, Any]) -> dict[str, Any]:
        """Return the matched film's Douban community score without loading reviews."""
        if not self.server_path.is_file():
            raise CriticismError("Douban MCP is not installed.")
        title = str(film.get("title") or "").strip()
        if not title:
            raise CriticismError("The film record has no title for Douban matching.")
        external_ids = film.get("external_ids") or {}
        search_query = str(external_ids.get("imdb") or title).strip()
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
                    search_text = await self._call_text(
                        session,
                        "search-movie",
                        {"q": search_query},
                    )
        except CriticismError:
            raise
        except Exception as exc:
            raise CriticismError(
                f"Douban MCP failed: {self._mcp_exception_detail(exc)}"
            ) from exc
        match = self._choose_match(film, self._markdown_table(search_text))
        score, votes = self._parse_platform_rating(match.get("rating"))
        if score is None:
            raise CriticismError("Douban returned no film rating for this title.")
        return {
            "provider": "Douban",
            "score": score,
            "scale": 10,
            "normalised": round(score * 10, 1),
            "votes": votes,
            "url": f"https://movie.douban.com/subject/{match['id']}/",
        }

    @staticmethod
    def _parse_platform_rating(value: Any) -> tuple[float | None, int | None]:
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:\((\d+)\s*人\))?", str(value or ""))
        if not match:
            return None, None
        score = float(match.group(1))
        if not 0 < score <= 10:
            return None, None
        return score, int(match.group(2)) if match.group(2) else None

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
            return (
                "Douban MCP returned an empty review table for the matched provider record. "
                "This may indicate an identity mismatch or temporary access restriction; it "
                "does not establish that the film has no long-form reviews."
            )

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
    def _nested_criticism_error(exc: BaseException) -> CriticismError | None:
        """Recover a useful adapter error hidden by an AnyIO ExceptionGroup."""
        if isinstance(exc, CriticismError):
            return exc
        for child in getattr(exc, "exceptions", ()):
            nested = DoubanMcpAdapter._nested_criticism_error(child)
            if nested is not None:
                return nested
        return None

    @staticmethod
    def _mcp_exception_detail(exc: BaseException) -> str:
        """Flatten task-group wrappers while keeping provider diagnostics concise."""
        leaves: list[str] = []

        def collect(error: BaseException) -> None:
            children = getattr(error, "exceptions", ())
            if children:
                for child in children:
                    collect(child)
                return
            message = re.sub(r"\s+", " ", str(error)).strip()
            if message:
                leaves.append(message)
            elif type(error).__name__:
                leaves.append(type(error).__name__)

        collect(exc)
        detail = "; ".join(dict.fromkeys(leaves)) or type(exc).__name__
        return DoubanMcpAdapter._safe_response_preview(detail, limit=240)

    @staticmethod
    def _choose_match(film: dict[str, Any], candidates: list[dict[str, str]]) -> dict[str, str]:
        if not candidates:
            raise CriticismError("Douban returned no film matches.")
        target_title = str(film.get("title") or "").casefold()
        original_title = str(film.get("original_title") or "").casefold()
        target_year = str(film.get("year") or "")
        year_matches = [
            candidate
            for candidate in candidates
            if target_year and candidate.get("publish_date") == target_year
        ]
        eligible = year_matches or candidates

        # A stable external-ID search can return a single translated-title row.
        # The exact release year is enough to accept that unique provider result;
        # ambiguous same-year candidates still pass through the stricter scorer.
        if len(candidates) == 1 and year_matches and candidates[0].get("id"):
            return candidates[0]

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

        match = max(eligible, key=score)
        if score(match) < 0.55 or not match.get("id"):
            raise CriticismError("Douban did not return a confident film identity match.")
        return match

    @staticmethod
    def _language(value: str) -> str:
        chinese = len(re.findall(r"[\u3400-\u9fff]", value))
        return "zh" if chinese >= max(2, len(value) // 12) else "und"


class LetterboxdApiAdapter:
    """Read-only adapter for Letterboxd's official OAuth API."""

    api_base = "https://api.letterboxd.com/api/v0"

    def __init__(
        self,
        settings: LocalSettingsStore,
        transport: Callable[[str, str, dict[str, str], bytes | None], dict[str, Any]] | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport or self._request_json

    def status(self) -> dict[str, Any]:
        configured = self.settings.secret_state("letterboxd").configured
        return {
            "provider": "Letterboxd API",
            "state": "ready" if configured else "credentials_required",
            "configured": configured,
            "official": True,
            "content_scope": "public attributed reviews",
        }

    def test_connection(self) -> dict[str, Any]:
        self._access_token()
        return {
            "message": "Letterboxd OAuth credentials accepted.",
            "mode": "official_client_credentials",
        }

    def fetch_reviews(
        self,
        film: dict[str, Any],
        limit: int = 8,
    ) -> tuple[str, str, list[ReviewSource]]:
        token = self._access_token()
        title = str(film.get("title") or "").strip()
        if not title:
            raise CriticismError("The film record has no title for Letterboxd matching.")
        search = self._api_get(
            "/search",
            token,
            {
                "input": title,
                "searchMethod": "Autocomplete",
                "include": "FilmSearchItem",
                "perPage": "10",
                "excludeMemberFilmRelationships": "true",
            },
        )
        candidates = self._search_films(search)
        match = self._choose_match(film, candidates)
        response = self._api_get(
            "/log-entries",
            token,
            {
                "film": match["id"],
                "where": "HasReview",
                "filter": "NoDuplicateMembers",
                "sort": "ReviewPopularity",
                "perPage": str(max(1, min(limit, 20))),
            },
        )
        reviews = self._normalise_reviews(response, match, limit)
        if not reviews:
            raise CriticismError(
                "Letterboxd returned no public attributed reviews for this film."
            )
        return match["id"], match["title"], reviews

    def _access_token(self) -> str:
        client_id = self.settings.effective_credential("letterboxd", "client_id")
        client_secret = self.settings.effective_credential("letterboxd", "client_secret")
        if not client_id or not client_secret:
            raise CriticismError(
                "Letterboxd API credentials are incomplete. Add both fields in Settings."
            )
        body = urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }
        ).encode("utf-8")
        response = self.transport(
            "POST",
            f"{self.api_base}/auth/token",
            {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body,
        )
        token = str(response.get("access_token") or "").strip()
        if not token:
            raise CriticismError("Letterboxd did not return an OAuth access token.")
        return token

    def _api_get(
        self,
        path: str,
        token: str,
        parameters: dict[str, str],
    ) -> dict[str, Any]:
        return self.transport(
            "GET",
            f"{self.api_base}{path}?{urlencode(parameters)}",
            {"Accept": "application/json", "Authorization": f"Bearer {token}"},
            None,
        )

    @staticmethod
    def _search_films(payload: dict[str, Any]) -> list[dict[str, Any]]:
        films: list[dict[str, Any]] = []
        for item in payload.get("items", []):
            if not isinstance(item, dict) or item.get("type") not in {None, "FilmSearchItem"}:
                continue
            film = item.get("film") or item.get("production") or item.get("data")
            if not isinstance(film, dict):
                continue
            identifier = str(film.get("id") or "").strip()
            title = str(film.get("name") or film.get("title") or "").strip()
            if identifier and title:
                films.append(
                    {
                        "id": identifier,
                        "title": title,
                        "year": film.get("releaseYear") or film.get("year"),
                        "link": film.get("link") or "",
                        "score": item.get("score") or 0,
                    }
                )
        return films

    @staticmethod
    def _choose_match(film: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
        if not candidates:
            raise CriticismError("Letterboxd returned no film matches.")
        target_title = str(film.get("title") or "").casefold()
        original_title = str(film.get("original_title") or "").casefold()
        target_year = str(film.get("year") or "")

        def score(candidate: dict[str, Any]) -> float:
            title = str(candidate.get("title") or "").casefold()
            title_score = max(
                SequenceMatcher(None, target_title, title).ratio(),
                SequenceMatcher(None, original_title, title).ratio() if original_title else 0,
            )
            return title_score + (0.25 if target_year == str(candidate.get("year") or "") else 0)

        match = max(candidates, key=score)
        if score(match) < 0.55:
            raise CriticismError("Letterboxd did not return a confident film identity match.")
        return match

    @classmethod
    def _normalise_reviews(
        cls,
        payload: dict[str, Any],
        film: dict[str, Any],
        limit: int,
    ) -> list[ReviewSource]:
        reviews: list[ReviewSource] = []
        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            review = item.get("review")
            owner = item.get("owner") or {}
            if not isinstance(review, dict) or not isinstance(owner, dict):
                continue
            review_id = str(item.get("id") or "").strip()
            text = cls._plain_text(str(review.get("text") or ""))
            if not review_id or not text or review.get("moderated"):
                continue
            username = str(owner.get("username") or "").strip()
            author = str(
                owner.get("displayName")
                or " ".join(
                    part
                    for part in (owner.get("givenName"), owner.get("familyName"))
                    if part
                )
                or username
                or "Letterboxd member"
            )
            reviews.append(
                ReviewSource(
                    source_id=f"L{len(reviews) + 1}",
                    provider="Letterboxd",
                    review_id=review_id,
                    title=str(item.get("name") or f"{author} on {film['title']}"),
                    summary=text[:6000],
                    rating_label=(
                        f"{item['rating']}/5" if item.get("rating") is not None else None
                    ),
                    author=author,
                    url=cls._review_url(username, film.get("link"), review_id),
                    language=str(review.get("languageCode") or "und"),
                )
            )
            if len(reviews) >= limit:
                break
        return reviews

    @staticmethod
    def _plain_text(value: str) -> str:
        value = re.sub(r"(?i)<br\s*/?>|</p>|</blockquote>", "\n", value)
        value = re.sub(r"<[^>]+>", "", value)
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    @staticmethod
    def _review_url(username: str, film_link: Any, review_id: str) -> str:
        path = urlparse(str(film_link or "")).path.strip("/").split("/")
        slug = path[1] if len(path) >= 2 and path[0] == "film" else ""
        if username and slug:
            return f"https://letterboxd.com/{username}/film/{slug}/"
        return f"https://boxd.it/{review_id}"

    @staticmethod
    def _request_json(
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> dict[str, Any]:
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise CriticismError(
                    "Letterboxd rejected the API credentials or has not authorised this client."
                ) from exc
            raise CriticismError(f"Letterboxd API returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise CriticismError(f"Letterboxd API request failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise CriticismError("Letterboxd API returned an invalid response.")
        return payload


class LetterboxdPublicWebAdapter:
    """Bounded importer for attributed reviews on public film pages."""

    web_base = "https://letterboxd.com"
    max_response_bytes = 2_000_000

    def __init__(
        self,
        transport: Callable[[str], tuple[str, str]] | None = None,
    ) -> None:
        self.transport = transport or self._request_html

    def status(self) -> dict[str, Any]:
        return {
            "provider": "Letterboxd public web",
            "state": "ready",
            "configured": True,
            "official": False,
            "local_only": False,
            "content_scope": "public attributed reviews selected from one film page",
        }

    def fetch_reviews(
        self,
        film: dict[str, Any],
        limit: int = 4,
    ) -> tuple[str, str, list[ReviewSource]]:
        title = str(film.get("title") or "").strip()
        if not title:
            raise CriticismError("The film record has no title for Letterboxd matching.")

        film_url, film_html = self._resolve_film_page(film)
        film_slug = urlparse(film_url).path.strip("/").split("/")[-1]
        review_urls = self._review_links(film_html, film_slug)[: max(1, min(limit, 6))]
        if not review_urls:
            raise CriticismError(
                "Letterboxd's public film page returned no attributed review links."
            )

        reviews: list[ReviewSource] = []
        for review_url in review_urls:
            try:
                final_url, review_html = self.transport(review_url)
                self._validate_letterboxd_url(final_url)
                review = self._normalise_review(review_html, final_url, len(reviews) + 1)
            except CriticismError:
                continue
            if review is not None:
                reviews.append(review)

        if not reviews:
            raise CriticismError(
                "Letterboxd's public pages contained no usable attributed review text."
            )
        return film_slug, title, reviews

    def fetch_score(self, film: dict[str, Any]) -> dict[str, Any]:
        """Return Letterboxd's aggregate member rating from the matched public film page."""
        film_url, film_html = self._resolve_film_page(film)
        score, votes = self._aggregate_rating(film_html)
        if score is None:
            raise CriticismError("Letterboxd returned no aggregate film rating.")
        return {
            "provider": "Letterboxd",
            "score": score,
            "scale": 5,
            "normalised": round(score * 20, 1),
            "votes": votes,
            "url": film_url,
        }

    @classmethod
    def _aggregate_rating(cls, body: str) -> tuple[float | None, int | None]:
        scripts = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            body,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for script in scripts:
            try:
                payload = json.loads(html.unescape(script).strip())
            except (json.JSONDecodeError, TypeError):
                continue
            for node in cls._json_nodes(payload):
                aggregate = node.get("aggregateRating") if isinstance(node, dict) else None
                if not isinstance(aggregate, dict):
                    continue
                try:
                    score = float(aggregate.get("ratingValue"))
                except (TypeError, ValueError):
                    continue
                try:
                    votes = int(str(aggregate.get("ratingCount") or "").replace(",", ""))
                except ValueError:
                    votes = None
                if 0 < score <= 5:
                    return score, votes
        fallback = re.search(
            r'([0-5](?:\.\d+)?)\s+(?:out of 5|average rating)',
            html.unescape(body),
            flags=re.IGNORECASE,
        )
        return (float(fallback.group(1)), None) if fallback else (None, None)

    @classmethod
    def _json_nodes(cls, value: Any) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        if isinstance(value, dict):
            nodes.append(value)
            for child in value.values():
                nodes.extend(cls._json_nodes(child))
        elif isinstance(value, list):
            for child in value:
                nodes.extend(cls._json_nodes(child))
        return nodes

    def _resolve_film_page(self, film: dict[str, Any]) -> tuple[str, str]:
        title = str(film.get("title") or "").strip()
        year = str(film.get("year") or "").strip()
        directors = film.get("credits", {}).get("directors") or film.get("directors") or []
        slug = self._slugify(title)
        external_ids = film.get("external_ids") or {}
        imdb_id = str(external_ids.get("imdb") or "").strip()
        candidates = []
        if re.fullmatch(r"tt\d+", imdb_id):
            candidates.append(f"{self.web_base}/imdb/{imdb_id}/")
        candidates.append(f"{self.web_base}/film/{slug}/")
        if year:
            candidates.append(f"{self.web_base}/film/{slug}-{year}/")

        for candidate in candidates:
            try:
                final_url, body = self.transport(candidate)
                self._validate_letterboxd_url(final_url)
            except CriticismError:
                continue
            if self._film_page_matches(body, title, year, directors):
                return final_url, body
        raise CriticismError(
            "Letterboxd did not resolve a public film page confidently from the verified "
            "film identity."
        )

    @staticmethod
    def _slugify(value: str) -> str:
        normalised = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
        normalised = re.sub(r"['’]", "", normalised.casefold())
        return re.sub(r"[^a-z0-9]+", "-", normalised).strip("-")

    @staticmethod
    def _film_page_matches(
        body: str,
        title: str,
        year: str,
        directors: list[Any] | tuple[Any, ...] = (),
    ) -> bool:
        match = re.search(
            r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)',
            body,
            re.IGNORECASE,
        )
        if not match:
            return False
        page_title = html.unescape(match.group(1)).casefold()
        title_score = SequenceMatcher(None, title.casefold(), page_title.split(" (")[0]).ratio()
        year_matches = not year or f"({year})" in page_title
        if title_score < 0.75 or not year_matches:
            return False
        page_directors = LetterboxdPublicWebAdapter._film_page_directors(body)
        target_directors = [
            LetterboxdPublicWebAdapter._slugify(str(director)).replace("-", " ")
            for director in directors
            if str(director).strip()
        ]
        if page_directors and target_directors:
            return any(
                SequenceMatcher(None, target, page_director).ratio() >= 0.72
                for target in target_directors
                for page_director in page_directors
            )
        return True

    @staticmethod
    def _film_page_directors(body: str) -> list[str]:
        payloads = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            body,
            re.IGNORECASE | re.DOTALL,
        )
        for payload in payloads:
            try:
                value = json.loads(html.unescape(payload).strip())
            except json.JSONDecodeError:
                continue
            values = value if isinstance(value, list) else [value]
            for item in values:
                if not isinstance(item, dict) or item.get("@type") != "Movie":
                    continue
                directors = item.get("director") or []
                if isinstance(directors, dict):
                    directors = [directors]
                return [
                    LetterboxdPublicWebAdapter._slugify(str(director.get("name") or "")).replace("-", " ")
                    for director in directors
                    if isinstance(director, dict) and director.get("name")
                ]
        return []

    @classmethod
    def _review_links(cls, body: str, film_slug: str) -> list[str]:
        pattern = re.compile(
            rf'href=["\'](/[^/"\']+/film/{re.escape(film_slug)}/)(?:#[^"\']*)?["\']',
            re.IGNORECASE,
        )
        links: list[str] = []
        seen: set[str] = set()
        for path in pattern.findall(body):
            url = f"{cls.web_base}{html.unescape(path)}"
            if url not in seen:
                seen.add(url)
                links.append(url)
        return links

    @staticmethod
    def _normalise_review(body: str, url: str, index: int) -> ReviewSource | None:
        payloads = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            body,
            re.IGNORECASE | re.DOTALL,
        )
        review: dict[str, Any] | None = None
        for payload in payloads:
            try:
                clean_payload = re.sub(
                    r"/\*\s*(?:<!\[CDATA\[|\]\]>)\s*\*/",
                    "",
                    html.unescape(payload),
                ).strip()
                value = json.loads(clean_payload)
            except json.JSONDecodeError:
                continue
            values = value if isinstance(value, list) else [value]
            review = next(
                (
                    item
                    for item in values
                    if isinstance(item, dict) and item.get("@type") == "Review"
                ),
                None,
            )
            if review:
                break
        if not review:
            return None

        text = LetterboxdApiAdapter._plain_text(str(review.get("reviewBody") or ""))
        if len(text) < 40:
            return None
        authors = review.get("author") or []
        if isinstance(authors, dict):
            authors = [authors]
        author = next(
            (
                str(item.get("name") or "").strip()
                for item in authors
                if isinstance(item, dict) and item.get("name")
            ),
            "Letterboxd member",
        )
        item = review.get("itemReviewed") if isinstance(review.get("itemReviewed"), dict) else {}
        film_title = str(item.get("name") or "Film").strip()
        rating = review.get("reviewRating")
        rating_value = rating.get("ratingValue") if isinstance(rating, dict) else None
        identifier = urlparse(url).path.strip("/").replace("/", "-")
        return ReviewSource(
            source_id=f"W{index}",
            provider="Letterboxd public web",
            review_id=identifier,
            title=f"{author} on {film_title}",
            summary=text[:12_000],
            rating_label=f"{rating_value}/5" if rating_value is not None else None,
            author=author,
            url=url,
            language="und",
        )

    @classmethod
    def _request_html(cls, url: str) -> tuple[str, str]:
        cls._validate_letterboxd_url(url)
        request = Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-GB,en;q=0.8",
                "User-Agent": "Mozilla/5.0 FirstRoll/0.1 local-public-review-import",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=20) as response:
                final_url = response.geturl()
                cls._validate_letterboxd_url(final_url)
                payload = response.read(cls.max_response_bytes + 1)
                if len(payload) > cls.max_response_bytes:
                    raise CriticismError("Letterboxd returned an unexpectedly large page.")
                charset = response.headers.get_content_charset() or "utf-8"
                return final_url, payload.decode(charset, errors="replace")
        except HTTPError as exc:
            raise CriticismError(f"Letterboxd public web returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, UnicodeError) as exc:
            raise CriticismError(f"Letterboxd public web request failed: {exc}") from exc

    @staticmethod
    def _validate_letterboxd_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in {"letterboxd.com", "www.letterboxd.com"}:
            raise CriticismError("Only public HTTPS pages on letterboxd.com may be imported.")


class _GuardianBodyParser(HTMLParser):
    """Collect paragraph text only from the Guardian article-body container."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.body_depth: int | None = None
        self.depth = 0
        self.paragraph_depth: int | None = None
        self.current: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self.depth += 1
        if self.body_depth is None and attributes.get("data-gu-name") == "body":
            self.body_depth = self.depth
        if self.body_depth is not None and tag == "p" and self.paragraph_depth is None:
            self.paragraph_depth = self.depth
            self.current = []

    def handle_endtag(self, tag: str) -> None:
        if self.paragraph_depth == self.depth and tag == "p":
            paragraph = re.sub(r"\s+", " ", " ".join(self.current)).strip()
            if paragraph:
                self.paragraphs.append(paragraph)
            self.paragraph_depth = None
            self.current = []
        if self.body_depth == self.depth:
            self.body_depth = None
        self.depth = max(0, self.depth - 1)

    def handle_data(self, data: str) -> None:
        if self.paragraph_depth is not None:
            value = data.strip()
            if value:
                self.current.append(value)


class GuardianPublicWebAdapter:
    """Bounded importer for public Guardian film reviews."""

    search_base = "https://content.guardianapis.com/search"
    max_response_bytes = 3_000_000

    def __init__(
        self,
        search_transport: Callable[[str], dict[str, Any]] | None = None,
        html_transport: Callable[[str], tuple[str, str]] | None = None,
    ) -> None:
        self.search_transport = search_transport or self._request_json
        self.html_transport = html_transport or self._request_html

    def status(self) -> dict[str, Any]:
        return {
            "provider": "The Guardian public web",
            "state": "ready",
            "configured": True,
            "official": False,
            "local_only": False,
            "content_scope": "public film-review articles selected for one film",
        }

    def fetch_reviews(
        self,
        film: dict[str, Any],
        limit: int = 4,
    ) -> tuple[str, str, list[ReviewSource]]:
        title = str(film.get("title") or "").strip()
        if not title:
            raise CriticismError("The film record has no title for Guardian matching.")
        quoted_title = quote_plus(f'"{title}"')
        url = (
            f"{self.search_base}?q={quoted_title}"
            "&query-fields=headline&section=film&order-by=relevance&page-size=20&api-key=test"
        )
        response = self.search_transport(url).get("response") or {}
        results = response.get("results") if isinstance(response, dict) else []
        if not isinstance(results, list):
            results = []
        candidates = self._choose_matches(title, results)[: max(1, min(limit, 6))]
        if not candidates:
            raise CriticismError("The Guardian returned no confident film-review matches.")

        reviews: list[ReviewSource] = []
        for candidate in candidates:
            article_url = str(candidate.get("webUrl") or "")
            try:
                final_url, body = self.html_transport(article_url)
                self._validate_article_url(final_url)
                review = self._normalise_article(body, final_url, len(reviews) + 1)
            except CriticismError:
                continue
            if review is not None:
                reviews.append(review)
        if not reviews:
            raise CriticismError(
                "The Guardian's public pages contained no usable attributed review text."
            )
        provider_id = str(candidates[0].get("id") or urlparse(reviews[0].url).path.strip("/"))
        return provider_id, title, reviews

    @staticmethod
    def _choose_matches(title: str, results: list[Any]) -> list[dict[str, Any]]:
        target = title.casefold()

        def score(item: dict[str, Any]) -> float:
            headline = str(item.get("webTitle") or "").casefold()
            simplified = re.split(r"\s+[–—:-]\s+", headline, maxsplit=1)[0]
            similarity = max(
                SequenceMatcher(None, target, headline).ratio(),
                SequenceMatcher(None, target, simplified).ratio(),
            )
            if headline == target:
                similarity += 0.5
            elif target in headline:
                similarity += 0.25
            if "review" in headline:
                similarity += 0.1
            return similarity

        valid = [
            item
            for item in results
            if isinstance(item, dict)
            and item.get("webUrl")
            and str(item.get("sectionId") or "") == "film"
        ]
        ranked = sorted(valid, key=score, reverse=True)
        return [item for item in ranked if score(item) >= 0.65]

    @staticmethod
    def _normalise_article(body: str, url: str, index: int) -> ReviewSource | None:
        payloads = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            body,
            re.IGNORECASE | re.DOTALL,
        )
        article: dict[str, Any] | None = None
        for payload in payloads:
            try:
                value = json.loads(html.unescape(payload).strip())
            except json.JSONDecodeError:
                continue
            values = value if isinstance(value, list) else [value]
            article = next(
                (
                    item
                    for item in values
                    if isinstance(item, dict)
                    and item.get("@type") in {"Article", "NewsArticle", "Review"}
                ),
                None,
            )
            if article:
                break
        if not article:
            return None

        parser = _GuardianBodyParser()
        parser.feed(body)
        text = "\n\n".join(parser.paragraphs).strip()
        if len(text) < 80:
            return None
        authors = article.get("author") or []
        if isinstance(authors, dict):
            authors = [authors]
        author = next(
            (
                str(item.get("name") or "").strip()
                for item in authors
                if isinstance(item, dict) and item.get("name")
            ),
            "Guardian critic",
        )
        headline = str(article.get("headline") or "Guardian film review").strip()
        rating_match = re.search(
            r'aria-label=["\']([0-5](?:\.5)?)\s+out\s+of\s+5\s+stars?["\']',
            body,
            re.IGNORECASE,
        )
        identifier = urlparse(url).path.strip("/")
        return ReviewSource(
            source_id=f"G{index}",
            provider="The Guardian public web",
            review_id=identifier,
            title=headline,
            summary=text[:12_000],
            rating_label=f"{rating_match.group(1)}/5" if rating_match else None,
            author=author,
            url=url,
            language="en",
        )

    @classmethod
    def _request_json(cls, url: str) -> dict[str, Any]:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "content.guardianapis.com":
            raise CriticismError("Only the Guardian public search index may resolve reviews.")
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read(cls.max_response_bytes).decode("utf-8"))
        except HTTPError as exc:
            raise CriticismError(f"Guardian search returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
            raise CriticismError(f"Guardian search failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise CriticismError("Guardian search returned an invalid response.")
        return payload

    @classmethod
    def _request_html(cls, url: str) -> tuple[str, str]:
        cls._validate_article_url(url)
        request = Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-GB,en;q=0.8",
                "User-Agent": "Mozilla/5.0 FirstRoll/0.1 local-public-review-import",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=20) as response:
                final_url = response.geturl()
                cls._validate_article_url(final_url)
                payload = response.read(cls.max_response_bytes + 1)
                if len(payload) > cls.max_response_bytes:
                    raise CriticismError("The Guardian returned an unexpectedly large page.")
                charset = response.headers.get_content_charset() or "utf-8"
                return final_url, payload.decode(charset, errors="replace")
        except HTTPError as exc:
            raise CriticismError(f"Guardian public web returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, UnicodeError) as exc:
            raise CriticismError(f"Guardian public web request failed: {exc}") from exc

    @staticmethod
    def _validate_article_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in {
            "theguardian.com",
            "www.theguardian.com",
        }:
            raise CriticismError("Only public HTTPS articles on theguardian.com may be imported.")


class CrossrefResearchAdapter:
    """Retrieve attributed scholarly abstracts from Crossref's public metadata API."""

    api_base = "https://api.crossref.org/works"
    max_response_bytes = 3_000_000

    def __init__(
        self,
        transport: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self.transport = transport or self._request_json

    def status(self) -> dict[str, Any]:
        return {
            "provider": "Crossref scholarship",
            "state": "ready",
            "configured": True,
            "official": True,
            "content_scope": "attributed scholarly abstracts from registered publications",
        }

    def fetch_reviews(
        self,
        film: dict[str, Any],
        limit: int = 6,
    ) -> tuple[str, str, list[ReviewSource]]:
        title = str(film.get("title") or "").strip()
        if not title:
            raise CriticismError("The film record has no title for scholarly research.")
        directors = film.get("credits", {}).get("directors") or film.get("directors") or []
        director = str(directors[0]).strip() if directors else ""
        query = " ".join(part for part in (f'"{title}"', director, "film cinema") if part)
        url = f"{self.api_base}?{urlencode({'query.bibliographic': query, 'filter': 'has-abstract:true', 'rows': '24'})}"
        payload = self.transport(url)
        message = payload.get("message") if isinstance(payload, dict) else None
        items = message.get("items") if isinstance(message, dict) else None
        reviews = self._normalise_items(
            items if isinstance(items, list) else [],
            film,
            max(1, min(limit, 8)),
        )
        if not reviews:
            raise CriticismError(
                "Crossref found no confidently matched scholarly abstracts for this film."
            )
        slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")
        return f"crossref:{slug}", title, reviews

    @classmethod
    def _normalise_items(
        cls,
        items: list[Any],
        film: dict[str, Any],
        limit: int,
    ) -> list[ReviewSource]:
        aliases = [
            cls._normalise(str(value))
            for value in (film.get("title"), film.get("original_title"))
            if value
        ]
        directors = film.get("credits", {}).get("directors") or film.get("directors") or []
        director_surnames = {
            cls._normalise(str(director)).split()[-1]
            for director in directors
            if cls._normalise(str(director))
        }
        reviews: list[ReviewSource] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            work_title = cls._first_text(item.get("title"))
            abstract = LetterboxdApiAdapter._plain_text(str(item.get("abstract") or ""))
            if len(abstract) < 80:
                continue
            normalised_title = cls._normalise(work_title)
            normalised_body = cls._normalise(f"{work_title} {abstract}")
            matched_alias = next((alias for alias in aliases if alias in normalised_body), "")
            if not matched_alias:
                continue
            short_title = len(matched_alias.split()) <= 2
            has_director = any(name in normalised_body for name in director_surnames)
            has_film_context = any(
                term in normalised_title.split()
                for term in ("film", "cinema", "cinematic", "movie")
            )
            if short_title and director_surnames and not (has_director or has_film_context):
                continue

            doi = str(item.get("DOI") or "").strip()
            source_url = f"https://doi.org/{quote_plus(doi, safe='/')}" if doi else str(item.get("URL") or "")
            parsed = urlparse(source_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                continue
            author = cls._authors(item.get("author"))
            venue = cls._first_text(item.get("container-title")) or str(item.get("publisher") or "Scholarly publication")
            year = cls._published_year(item.get("published"))
            work_type = str(item.get("type") or "research work").replace("-", " ")
            label = " · ".join(part for part in (work_type.title(), venue, year) if part)
            identifier = doi or source_url
            reviews.append(
                ReviewSource(
                    source_id=f"S{len(reviews) + 1}",
                    provider="Crossref scholarship",
                    review_id=identifier,
                    title=work_title or f"Research on {film.get('title') or 'the film'}",
                    summary=abstract[:6000],
                    rating_label=label or None,
                    author=author or venue,
                    url=source_url,
                    language=str(item.get("language") or "und"),
                )
            )
            if len(reviews) >= limit:
                break
        return reviews

    @staticmethod
    def _normalise(value: str) -> str:
        value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()

    @staticmethod
    def _first_text(value: Any) -> str:
        if isinstance(value, list):
            return str(value[0]).strip() if value else ""
        return str(value or "").strip()

    @staticmethod
    def _authors(value: Any) -> str:
        if not isinstance(value, list):
            return ""
        names = []
        for author in value[:4]:
            if not isinstance(author, dict):
                continue
            name = " ".join(
                part for part in (str(author.get("given") or "").strip(), str(author.get("family") or "").strip()) if part
            )
            if name:
                names.append(name)
        return ", ".join(names)

    @staticmethod
    def _published_year(value: Any) -> str:
        if not isinstance(value, dict):
            return ""
        parts = value.get("date-parts")
        if not isinstance(parts, list) or not parts or not isinstance(parts[0], list) or not parts[0]:
            return ""
        return str(parts[0][0])

    @classmethod
    def _request_json(cls, url: str) -> dict[str, Any]:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "api.crossref.org":
            raise CriticismError("Only Crossref's public HTTPS metadata API may be queried.")
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "FirstRoll/0.1 (local film-research client)",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=20) as response:
                payload = response.read(cls.max_response_bytes + 1)
                if len(payload) > cls.max_response_bytes:
                    raise CriticismError("Crossref returned an unexpectedly large response.")
                value = json.loads(payload.decode("utf-8"))
        except HTTPError as exc:
            raise CriticismError(f"Crossref returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
            raise CriticismError(f"Crossref research failed: {exc}") from exc
        if not isinstance(value, dict):
            raise CriticismError("Crossref returned an invalid response.")
        return value


class CriticismStore:
    """Private cache for attributed, structured criticism."""

    def __init__(self, directory: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.directory = directory or project_root / ".firstroll" / "criticism"

    def save(self, bundle: CriticalResearchBundle) -> None:
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self._path(bundle.film_id, bundle.provider)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(path)
        os.chmod(path, 0o600)

    def load(self, film_id: str, provider: str | None = None) -> CriticalResearchBundle | None:
        if provider is None:
            bundles = self.load_all(film_id)
            return bundles[0] if bundles else None
        path = self._path(film_id, provider)
        if not path.is_file() and provider.casefold() == "douban":
            path = self._path(film_id)
        if not path.is_file():
            return None
        try:
            return CriticalResearchBundle.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def load_all(self, film_id: str) -> list[CriticalResearchBundle]:
        safe = self._safe_name(film_id)
        paths = list(self.directory.glob(f"{safe}--*.json")) if self.directory.is_dir() else []
        legacy = self._path(film_id)
        if legacy.is_file():
            paths.append(legacy)
        bundles: dict[str, CriticalResearchBundle] = {}
        for path in paths:
            try:
                bundle = CriticalResearchBundle.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError):
                continue
            bundles[bundle.provider.casefold()] = bundle
        return [bundles[key] for key in sorted(bundles)]

    def _path(self, film_id: str, provider: str | None = None) -> Path:
        safe = self._safe_name(film_id)
        if provider:
            safe_provider = self._safe_name(provider).casefold()
            return self.directory / f"{safe}--{safe_provider}.json"
        return self.directory / f"{safe}.json"

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-") or "film"


def build_bundle(
    film_id: str,
    provider_film_id: str,
    provider_film_title: str,
    reviews: list[ReviewSource],
    claims: list[CriticalClaim],
    *,
    provider: str = "Douban",
    notice: str | None = None,
    claim_status: Literal["pending", "structured"] = "structured",
) -> CriticalResearchBundle:
    return CriticalResearchBundle(
        film_id=film_id,
        provider=provider,
        provider_film_id=provider_film_id,
        provider_film_title=provider_film_title,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        reviews=reviews,
        claims=claims,
        claim_status=claim_status,
        notice=notice
        or (
            f"These are model-structured claims from attributed {provider} reviews. "
            "They are secondary criticism, not verified observations or creator statements."
        ),
    )
