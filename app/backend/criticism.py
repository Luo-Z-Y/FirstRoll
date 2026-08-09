from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
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
) -> CriticalResearchBundle:
    return CriticalResearchBundle(
        film_id=film_id,
        provider=provider,
        provider_film_id=provider_film_id,
        provider_film_title=provider_film_title,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        reviews=reviews,
        claims=claims,
        notice=notice
        or (
            f"These are model-structured claims from attributed {provider} reviews. "
            "They are secondary criticism, not verified observations or creator statements."
        ),
    )
