from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Callable, Sequence, cast

from app.backend.agent_evidence import (
    PlannerMode,
    assess_agent_evidence,
    choose_deterministic_research_tool,
)
from app.backend.criticism import (
    CriticismError,
    CrossrefResearchAdapter,
    DoubanMcpAdapter,
    GuardianPublicWebAdapter,
    LetterboxdApiAdapter,
    LetterboxdPublicWebAdapter,
    ReviewSource,
)
from app.backend.evidence import EvidencePacket
from app.backend.packet_quality import assess_evidence_packet
from app.backend.research_agent_contract import (
    MAX_AGENT_REPAIR_CALLS,
    EvidenceKind,
    EvidenceRef,
    ResearchState,
    ToolName,
    ToolPlan,
)
from app.backend.research_graph.context import (
    DraftResult,
    FilmResolution,
    NoAddressableResearchTool,
    ToolObservation,
    ValidationResult,
)
from app.backend.research_graph.state import ResearchGraphState
from app.backend.study_observability import StudyTrace
from app.backend.study_service import DeepSeekStudyService, StudyGenerationError
from app.backend.video_sources import (
    BilibiliPublicVideoAdapter,
    FilmVideo,
    PublicVideoTextExtractor,
    VideoSourceError,
    YouTubeVideoAdapter,
)


PreparedStudy = dict[str, Any]
FilmDetail = Callable[[str], dict[str, Any]]
StudyPreparation = Callable[..., PreparedStudy]


@dataclass(frozen=True)
class AcquiredSources:
    provider: str
    reviews: tuple[ReviewSource, ...] = ()
    videos: tuple[FilmVideo, ...] = ()


@dataclass
class _RunWorkspace:
    film_id: str
    film: dict[str, Any]
    focus: str
    reading: dict[str, Any]
    claims: list[Any]
    reviews: list[ReviewSource]
    videos: list[FilmVideo]
    packet: EvidencePacket
    initial_packet_quality: dict[str, Any]
    initial_agent_evidence: dict[str, Any]
    initial_packet_fingerprint: str
    trace: StudyTrace
    planner_calls: list[ToolPlan] = field(default_factory=list)
    planning_decisions: list[dict[str, str]] = field(default_factory=list)
    planner_latency_seconds: list[float] = field(default_factory=list)
    tool_attempts: list[dict[str, Any]] = field(default_factory=list)
    acquired_review_count: int = 0
    acquired_video_count: int = 0
    draft: dict[str, Any] | None = None
    last_valid_draft: dict[str, Any] | None = None
    structural_repair_candidate: dict[str, Any] | None = None
    structural_repair_paths: tuple[str, ...] = ()
    study_attempts: list[dict[str, Any]] = field(default_factory=list)
    repair_attempts: int = 0


class LocalAttributedSourceAcquirer:
    """Call existing local provider adapters without writing their results to caches."""

    def __init__(
        self,
        *,
        douban: DoubanMcpAdapter,
        guardian: GuardianPublicWebAdapter,
        letterboxd: LetterboxdApiAdapter,
        letterboxd_web: LetterboxdPublicWebAdapter,
        crossref: CrossrefResearchAdapter,
        youtube: YouTubeVideoAdapter,
        bilibili: BilibiliPublicVideoAdapter,
        video_text: PublicVideoTextExtractor | None = None,
    ) -> None:
        self.douban = douban
        self.guardian = guardian
        self.letterboxd = letterboxd
        self.letterboxd_web = letterboxd_web
        self.crossref = crossref
        self.youtube = youtube
        self.bilibili = bilibili
        self.video_text = video_text or PublicVideoTextExtractor()

    def status(self) -> dict[str, dict[str, Any]]:
        letterboxd_status = self.letterboxd.status()
        if not letterboxd_status.get("configured"):
            letterboxd_status = self.letterboxd_web.status()
        youtube_status = self.youtube.status()
        bilibili_status = self.bilibili.status()
        return {
            ToolName.FETCH_GUARDIAN_REVIEWS.value: self.guardian.status(),
            ToolName.FETCH_DOUBAN_REVIEWS.value: self.douban.status(),
            ToolName.FETCH_LETTERBOXD_REVIEWS.value: letterboxd_status,
            ToolName.FETCH_CROSSREF_RESEARCH.value: self.crossref.status(),
            ToolName.SEARCH_YOUTUBE_RESOURCES.value: {
                "provider": "YouTube or Bilibili",
                "state": (
                    "ready"
                    if youtube_status.get("state") == "ready"
                    or bilibili_status.get("state") == "ready"
                    else "unavailable"
                ),
                "configured": bool(youtube_status.get("configured")),
                "official": bool(youtube_status.get("official")),
            },
        }

    def acquire(self, tool: ToolName, film: dict[str, Any]) -> AcquiredSources:
        if tool is ToolName.FETCH_GUARDIAN_REVIEWS:
            _, _, reviews = self.guardian.fetch_reviews(film)
            return AcquiredSources("The Guardian public web", tuple(reviews))
        if tool is ToolName.FETCH_DOUBAN_REVIEWS:
            _, _, reviews = self._run_douban(film)
            return AcquiredSources("Douban", tuple(reviews))
        if tool is ToolName.FETCH_LETTERBOXD_REVIEWS:
            adapter = (
                self.letterboxd
                if self.letterboxd.status().get("configured")
                else self.letterboxd_web
            )
            _, _, reviews = adapter.fetch_reviews(film)
            return AcquiredSources(
                str(adapter.status().get("provider") or "Letterboxd"),
                tuple(reviews),
            )
        if tool is ToolName.FETCH_CROSSREF_RESEARCH:
            _, _, reviews = self.crossref.fetch_reviews(film)
            return AcquiredSources("Crossref scholarship", tuple(reviews))
        if tool is ToolName.SEARCH_YOUTUBE_RESOURCES:
            return self._acquire_videos(film)
        raise CriticismError("The selected tool has no local attributed-source adapter.")

    def _run_douban(
        self,
        film: dict[str, Any],
    ) -> tuple[str, str, list[ReviewSource]]:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return cast(
                tuple[str, str, list[ReviewSource]],
                asyncio.run(self.douban.fetch_reviews(film)),
            )
        raise CriticismError("The synchronous local Agent cannot run Douban inside an event loop.")

    def _acquire_videos(self, film: dict[str, Any]) -> AcquiredSources:
        found: list[FilmVideo] = []
        failures: list[str] = []
        for name, adapter in (("YouTube", self.youtube), ("Bilibili", self.bilibili)):
            try:
                found.extend(adapter.search(film, limit=8))
            except VideoSourceError as exc:
                failures.append(f"{name}: {exc}")
        unique: dict[tuple[str, str], FilmVideo] = {}
        for video in found:
            unique.setdefault((video.platform.casefold(), video.video_id), video)
        videos = self.video_text.enrich(list(unique.values()), limit=6)
        if not videos:
            detail = f" Provider details: {'; '.join(failures)}" if failures else ""
            raise VideoSourceError(f"No usable attributed video text was found.{detail}")
        return AcquiredSources("YouTube or Bilibili", videos=tuple(videos))


class LocalResearchGraphServices:
    """Default-off local adapter over the fixed packet and synthesis services.

    Provider acquisitions remain ephemeral in this object. Existing caches are read by the
    supplied preparation function, but newly acquired reviews and videos are not persisted.
    """

    def __init__(
        self,
        *,
        detail: FilmDetail,
        prepare: StudyPreparation,
        acquirer: LocalAttributedSourceAcquirer,
        study_service: DeepSeekStudyService,
        packet_override: EvidencePacket | None = None,
        planner_mode: PlannerMode = "model",
    ) -> None:
        self.detail = detail
        self.prepare = prepare
        self.acquirer = acquirer
        self.study_service = study_service
        self.packet_override = packet_override.model_copy(deep=True) if packet_override else None
        if planner_mode not in {"model", "deterministic"}:
            raise ValueError("The local Agent planner mode is invalid.")
        self.planner_mode = planner_mode
        self._workspaces: dict[str, _RunWorkspace] = {}

    def for_frozen_packet(self, packet: EvidencePacket) -> LocalResearchGraphServices:
        """Create an isolated synthesis lane over one already-selected packet."""

        return LocalResearchGraphServices(
            detail=self.detail,
            prepare=self.prepare,
            acquirer=self.acquirer,
            study_service=self.study_service,
            packet_override=packet,
            planner_mode=self.planner_mode,
        )

    def resolve_film(self, state: ResearchGraphState) -> FilmResolution:
        return FilmResolution(film_id=state.get("film_id"))

    def load_existing_evidence(
        self,
        state: ResearchGraphState,
    ) -> tuple[EvidenceRef, ...]:
        film_id = str(state.get("film_id") or "").strip()
        if not film_id:
            return ()
        trace = StudyTrace()
        with trace.stage("film_context"):
            film = self.detail(film_id)["film"]
        if self.packet_override is not None:
            packet = self.packet_override.model_copy(deep=True)
            prepared = {
                "reading": {"passages": []},
                "claims": list(packet.critical_claims),
                "reviews": [],
                "videos": [],
            }
            trace.skip("packet_assembly")
        else:
            prepared = self.prepare(
                film_id,
                film,
                state["question"],
                public_mode=False,
                trace=trace,
            )
            packet = prepared["packet"]
        initial_quality = assess_evidence_packet(packet)
        initial_agent_evidence = assess_agent_evidence(
            packet,
            initial_packet_status=str(initial_quality["status"]),
        )
        workspace = _RunWorkspace(
            film_id=film_id,
            film=film,
            focus=state["question"],
            reading=prepared["reading"],
            claims=list(prepared.get("claims", [])),
            reviews=list(prepared.get("reviews", [])),
            videos=list(prepared.get("videos", [])),
            packet=packet,
            initial_packet_quality=initial_quality,
            initial_agent_evidence=initial_agent_evidence.safe_summary(initial_quality),
            initial_packet_fingerprint=self._packet_fingerprint(packet),
            trace=trace,
        )
        self._workspaces[state["run_id"]] = workspace
        return self._packet_evidence(packet)

    def evidence_is_sufficient(self, state: ResearchGraphState) -> bool:
        workspace = self._workspace(state)
        assessment = assess_agent_evidence(
            workspace.packet,
            initial_packet_status=str(workspace.initial_packet_quality["status"]),
        )
        return assessment.sufficient

    def choose_tool(
        self,
        state: ResearchGraphState,
        allowed_tools: tuple[ToolName, ...],
    ) -> ToolName:
        workspace = self._workspace(state)
        quality = assess_evidence_packet(workspace.packet)
        assessment = assess_agent_evidence(
            workspace.packet,
            initial_packet_status=str(workspace.initial_packet_quality["status"]),
        )
        provider_states = self.acquirer.status()
        started_at = monotonic()
        try:
            if self.planner_mode == "deterministic":
                selected, target_gap = choose_deterministic_research_tool(
                    assessment,
                    allowed_tools,
                    provider_states,
                )
                workspace.planning_decisions.append(
                    {
                        "strategy": "deterministic_gap_router",
                        "tool": selected.value,
                        "target_gap": target_gap.value,
                    }
                )
                return selected
            try:
                plan = self.study_service.plan_research_tool(
                    film=workspace.film,
                    focus=workspace.focus,
                    packet_summary=assessment.safe_summary(quality),
                    allowed_tools=allowed_tools,
                    provider_states=provider_states,
                )
            except StudyGenerationError as exc:
                if exc.category == "no_addressable_research_tool":
                    raise NoAddressableResearchTool(str(exc)) from exc
                raise
        except ValueError as exc:
            if self.planner_mode == "deterministic":
                raise NoAddressableResearchTool(str(exc)) from exc
            raise
        finally:
            workspace.planner_latency_seconds.append(max(0.0, monotonic() - started_at))
        workspace.planner_calls.append(plan)
        workspace.planning_decisions.append(
            {
                "strategy": "model_gap_planner",
                "tool": plan.tool.value,
                "target_gap": plan.target_gap.value
                if plan.target_gap is not None
                else "unspecified",
            }
        )
        workspace.trace.increment_count("model_calls")
        workspace.trace.increment_count("prompt_tokens", plan.prompt_tokens)
        workspace.trace.increment_count("completion_tokens", plan.completion_tokens)
        workspace.trace.increment_count("total_tokens", plan.total_tokens)
        return plan.tool

    def run_tool(self, state: ResearchGraphState, tool: ToolName) -> ToolObservation:
        workspace = self._workspace(state)
        started_at = monotonic()
        try:
            acquired = self.acquirer.acquire(tool, workspace.film)
        except Exception:
            workspace.tool_attempts.append(
                {
                    "tool": tool.value,
                    "status": "failed",
                    "duration_seconds": round(max(0.0, monotonic() - started_at), 3),
                }
            )
            raise
        workspace.tool_attempts.append(
            {
                "tool": tool.value,
                "status": "completed",
                "duration_seconds": round(max(0.0, monotonic() - started_at), 3),
            }
        )
        workspace.reviews = self._merge_reviews(workspace.reviews, acquired.reviews)
        workspace.videos = self._merge_videos(workspace.videos, acquired.videos)
        workspace.acquired_review_count += len(acquired.reviews)
        workspace.acquired_video_count += len(acquired.videos)
        with workspace.trace.stage("packet_assembly"):
            workspace.packet = EvidencePacket.from_retrieval(
                workspace.film,
                workspace.reading,
                workspace.focus,
                workspace.claims,
                reviews=workspace.reviews,
                videos=workspace.videos,
            )
        self._record_packet_counts(workspace.trace, workspace.packet)
        return ToolObservation(evidence=self._packet_evidence(workspace.packet))

    def synthesise(self, state: ResearchGraphState) -> DraftResult:
        workspace = self._workspace(state)
        study = self._run_study_attempt(workspace, kind="initial")
        workspace.draft = study
        if self._is_valid_study(study):
            workspace.last_valid_draft = study
        return DraftResult(study)

    def validate(self, state: ResearchGraphState) -> ValidationResult:
        workspace = self._workspace(state)
        draft = state.get("draft") or workspace.draft or {}
        quality = draft.get("quality") if isinstance(draft, dict) else None
        report = (
            quality
            if isinstance(quality, dict)
            else {
                "status": "invalid",
                "issues": ["missing_quality_report"],
            }
        )
        passed = report.get("status") == "passed"
        if passed:
            workspace.trace.finish("completed")
        elif workspace.repair_attempts >= MAX_AGENT_REPAIR_CALLS:
            workspace.structural_repair_candidate = None
            workspace.structural_repair_paths = ()
            workspace.trace.finish("failed")
        return ValidationResult(passed, report)

    def repair(self, state: ResearchGraphState) -> DraftResult:
        workspace = self._workspace(state)
        workspace.repair_attempts += 1
        workspace.trace.increment_count("repair_attempts")
        study = self._run_study_attempt(workspace, kind="repair")
        workspace.draft = study
        if self._is_valid_study(study):
            workspace.last_valid_draft = study
        return DraftResult(study)

    def _run_study_attempt(
        self,
        workspace: _RunWorkspace,
        *,
        kind: str,
    ) -> dict[str, Any]:
        attempt_trace = StudyTrace()
        started_at = monotonic()
        result: dict[str, Any]
        status = "failed"
        failure_category: str | None = None
        strategy = "initial_generation"
        try:
            if kind == "repair" and workspace.last_valid_draft is not None:
                strategy = "targeted_quality_repair"
                prior_quality = workspace.last_valid_draft.get("quality")
                result = self.study_service.repair_once(
                    workspace.last_valid_draft,
                    prior_quality if isinstance(prior_quality, dict) else {},
                    evidence_packet=workspace.packet,
                    trace=attempt_trace,
                )
            elif kind == "repair" and workspace.structural_repair_candidate is not None:
                strategy = "targeted_structural_repair"
                result = self.study_service.repair_invalid_once(
                    workspace.structural_repair_candidate,
                    workspace.structural_repair_paths,
                    evidence_packet=workspace.packet,
                    trace=attempt_trace,
                )
            else:
                strategy = "full_regeneration" if kind == "repair" else strategy
                result = self.study_service.generate_once(
                    workspace.film,
                    workspace.reading.get("passages", []),
                    workspace.focus,
                    workspace.packet.critical_claims,
                    evidence_packet=workspace.packet,
                    trace=attempt_trace,
                )
            workspace.structural_repair_candidate = None
            workspace.structural_repair_paths = ()
            status = "completed"
        except StudyGenerationError as exc:
            failure_category = exc.category
            workspace.structural_repair_candidate = exc.repair_candidate
            workspace.structural_repair_paths = exc.repair_paths
            result = {
                "quality": {
                    "status": "invalid",
                    "issues": [exc.category],
                }
            }
        snapshot = attempt_trace.snapshot()
        self._merge_study_counts(workspace.trace, snapshot)
        quality = result.get("quality") if isinstance(result, dict) else None
        attempt = {
            "kind": kind,
            "strategy": strategy,
            "status": status,
            "quality_status": quality.get("status") if isinstance(quality, dict) else "invalid",
            "model_calls": int(snapshot.get("counts", {}).get("model_calls", 0)),
            "total_tokens": int(snapshot.get("counts", {}).get("total_tokens", 0)),
            "duration_seconds": round(max(0.0, monotonic() - started_at), 3),
        }
        if failure_category is not None:
            attempt["failure_category"] = failure_category
        workspace.study_attempts.append(attempt)
        return result

    @staticmethod
    def _merge_study_counts(trace: StudyTrace, snapshot: dict[str, Any]) -> None:
        counts = snapshot.get("counts") if isinstance(snapshot, dict) else None
        if not isinstance(counts, dict):
            return
        for name in (
            "model_calls",
            "prompt_characters",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "structural_repair_attempts",
        ):
            value = counts.get(name)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                trace.increment_count(name, value)

    @staticmethod
    def _is_valid_study(study: dict[str, Any]) -> bool:
        return bool(
            isinstance(study.get("sections"), list) and isinstance(study.get("quality"), dict)
        )

    def safe_metrics(self, run_id: str) -> dict[str, Any]:
        workspace = self._workspaces[run_id]
        quality = assess_evidence_packet(workspace.packet)
        agent_evidence = assess_agent_evidence(
            workspace.packet,
            initial_packet_status=str(workspace.initial_packet_quality["status"]),
        )
        return {
            "planner_calls": len(workspace.planner_calls),
            "planning_turns": len(workspace.planning_decisions),
            "planning_decisions": list(workspace.planning_decisions),
            "planner_latency_seconds": [
                round(value, 3) for value in workspace.planner_latency_seconds
            ],
            "planner_prompt_tokens": sum(item.prompt_tokens for item in workspace.planner_calls),
            "planner_completion_tokens": sum(
                item.completion_tokens for item in workspace.planner_calls
            ),
            "planner_total_tokens": sum(item.total_tokens for item in workspace.planner_calls),
            "tool_attempts": list(workspace.tool_attempts),
            "acquired_reviews": workspace.acquired_review_count,
            "acquired_videos": workspace.acquired_video_count,
            "study_attempts": list(workspace.study_attempts),
            "repair_attempts": workspace.repair_attempts,
            "initial_packet_quality": workspace.initial_packet_quality,
            "initial_agent_evidence": workspace.initial_agent_evidence,
            "initial_packet_fingerprint": workspace.initial_packet_fingerprint,
            "packet_quality": quality,
            "agent_evidence": agent_evidence.safe_summary(quality),
            "packet_fingerprint": self._packet_fingerprint(workspace.packet),
            "study_observability": workspace.trace.snapshot(),
        }

    def private_packet(self, run_id: str) -> EvidencePacket:
        """Return a detached packet only to the local private evaluation harness."""

        return self._workspaces[run_id].packet.model_copy(deep=True)

    def _workspace(self, state: ResearchState | ResearchGraphState) -> _RunWorkspace:
        try:
            return self._workspaces[state["run_id"]]
        except KeyError as exc:
            raise RuntimeError("The local Agent run has no prepared workspace.") from exc

    @classmethod
    def _packet_evidence(cls, packet: EvidencePacket) -> tuple[EvidenceRef, ...]:
        records: list[tuple[EvidenceKind, str, str, str]] = []
        for item in packet.attributed_sources:
            kind = {
                "creator_stated": EvidenceKind.CREATOR_STATED,
                "film_observed": EvidenceKind.VIDEO_CONTEXT,
            }.get(item.evidence_type, EvidenceKind.CRITIC_REPORTED)
            records.append(
                (
                    kind,
                    item.locator or item.title,
                    item.source_url or item.locator or item.title,
                    item.content,
                )
            )
        for claim in packet.critical_claims:
            records.append(
                (
                    EvidenceKind.CRITIC_REPORTED,
                    claim.source_id,
                    claim.source_id,
                    claim.critic_claim,
                )
            )
        for item in packet.theory_sources:
            records.append(
                (
                    EvidenceKind.THEORY_FRAMEWORK,
                    item.title,
                    item.locator or item.title,
                    item.content,
                )
            )
        return tuple(
            EvidenceRef(
                evidence_id=cls._stable_evidence_id(kind, provider, locator, content),
                kind=kind,
                provider=provider,
                locator=locator,
                content=content,
            )
            for kind, provider, locator, content in records
        )

    @staticmethod
    def _packet_fingerprint(packet: EvidencePacket) -> str:
        return hashlib.sha256(packet.model_dump_json().encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _stable_evidence_id(
        kind: EvidenceKind,
        provider: str,
        locator: str,
        content: str,
    ) -> str:
        digest = hashlib.sha256(
            f"{kind.value}\0{provider}\0{locator}\0{content}".encode("utf-8")
        ).hexdigest()[:16]
        return f"agent-{digest}"

    @staticmethod
    def _merge_reviews(
        existing: Sequence[ReviewSource],
        acquired: Sequence[ReviewSource],
    ) -> list[ReviewSource]:
        merged: dict[tuple[str, str, str], ReviewSource] = {}
        for review in (*existing, *acquired):
            key = (review.provider.casefold(), review.review_id, review.url)
            merged.setdefault(key, review)
        return list(merged.values())

    @staticmethod
    def _merge_videos(
        existing: Sequence[FilmVideo],
        acquired: Sequence[FilmVideo],
    ) -> list[FilmVideo]:
        merged: dict[tuple[str, str], FilmVideo] = {}
        for video in (*existing, *acquired):
            merged.setdefault((video.platform.casefold(), video.video_id), video)
        return list(merged.values())

    @staticmethod
    def _record_packet_counts(trace: StudyTrace, packet: EvidencePacket) -> None:
        trace.set_count("theory_sources", len(packet.theory_sources))
        trace.set_count("critical_claims", len(packet.critical_claims))
        trace.set_count("attributed_sources", len(packet.attributed_sources))
        theory = packet.retrieval.get("theory_selection", {})
        critical = packet.retrieval.get("critical_selection", {})
        attributed = packet.retrieval.get("attributed_selection", {})
        trace.set_count("theory_candidates", int(theory.get("candidate_items", 0) or 0))
        trace.set_count("theory_omitted", int(theory.get("omitted_items", 0) or 0))
        trace.set_count("critical_candidates", int(critical.get("candidate_items", 0) or 0))
        trace.set_count("critical_omitted", int(critical.get("omitted_items", 0) or 0))
        trace.set_count("attributed_candidates", int(attributed.get("candidate_items", 0) or 0))
        trace.set_count("attributed_omitted", int(attributed.get("omitted_items", 0) or 0))
        trace.set_count("attributed_truncated", int(attributed.get("truncated_items", 0) or 0))
