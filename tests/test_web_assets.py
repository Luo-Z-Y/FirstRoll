from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "app" / "web"


def test_director_shelf_uses_native_browser_assets_only() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")
    build = (ROOT / "tools" / "build_web.sh").read_text(encoding="utf-8")

    assert 'type="importmap"' not in index
    assert "closet3d.js" not in index
    assert "three.module" not in index
    assert "directorShelfMarkup" in app
    assert "directorShelfFilmsMarkup" in app
    assert "data-director-shelf" in app
    assert "closet3d.js" not in build
    assert 'cp -R "$source_dir/models"' not in build
    assert 'cp -R "$source_dir/vendor"' not in build
    assert not (WEB / "closet3d.js").exists()
    assert not (WEB / "models").exists()
    assert not (WEB / "vendor" / "three").exists()


def test_dossier_attributes_tmdb_without_mislabelling_its_overview() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")

    assert "overviewSourceName" in app
    assert "overviewSourceLicence" in app
    assert "This product uses the TMDB API but is not endorsed or certified by TMDB." in app
    assert "Wikipedia · CC BY-SA ↗" not in app


def test_supabase_auth_is_bundled_and_deep_study_sends_bearer_tokens() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    auth = (WEB / "auth.js").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")

    assert 'id="authDialog"' in index
    assert '"/assets/auth.js?v=20260821-5"' in index
    assert 'from "@supabase/supabase-js"' in auth
    assert 'flowType: "pkce"' in auth
    assert "signInWithPassword" in auth
    assert "client.auth.signUp" in auth
    assert "resetPasswordForEmail" in auth
    assert "If this is a new account, check your email to confirm it." in auth
    assert "Already used FirstRoll?" in auth
    assert "signInWithOtp" not in auth
    assert "emailRedirectTo" in auth
    assert "persistSession: true" in auth
    assert "authorisationHeaders" in auth
    assert "authorisation.Authorization" in app
    assert 'headers: { "Content-Type": "application/json", ...authorisation, ...integration }' in app
    assert "deepStudyQuotaMarkup(data.quota)" in app


def test_loopback_preview_uses_a_separate_persistent_unlimited_test_account() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    local_auth = (WEB / "local-auth.js").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")
    main = (ROOT / "app" / "backend" / "main.py").read_text(encoding="utf-8")
    integrations = (WEB / "integrations.js").read_text(encoding="utf-8")
    build = (ROOT / "tools" / "build_web.sh").read_text(encoding="utf-8")

    assert "localTestAccountEmail" in index
    assert '"/assets/local-auth.js?v=20260821-3"' in index
    assert '["localhost", "127.0.0.1", "::1"]' in index
    assert "if (localTestReady || (window.FIRSTROLL_CONFIG?.publicMode" in index
    assert 'localTestAccountEmail: ""' in build
    assert 'cp "$source_dir/local-auth.js"' in build
    assert "firstroll.local-test" in local_auth
    assert "firstroll-local-test-account" in local_auth
    assert "window.localStorage" in local_auth
    assert "saveFilm" in local_auth
    assert "updateDisplayName" in local_auth
    assert "updatePreferences" in local_auth
    assert "local_test_request" in main
    assert "ipaddress.ip_address(host).is_loopback" in main
    assert '"unlimited": True' in main
    assert "Unlimited studies on this local test account" in integrations
    assert "Local development account" in integrations
    assert "This loopback test account has no FirstRoll daily quota" in integrations
    assert "window.FIRSTROLL_CONFIG?.localTestAccountEmail" in app
    assert 'document.body.classList.toggle("public-mode", runtimeConfig.accountUi)' in app
    assert 'runtimeConfig.accountUi ? \'<button class="detail-action"' in app
    assert "account studies remain today" in app
    assert 'src="/assets/integrations.js?v=20260821-7"' in index
    assert 'src="/assets/app.js?v=20260821-13"' in index
    assert '"X-FirstRoll-DeepSeek-Key"' in integrations
    assert '"X-FirstRoll-YouTube-Key"' in integrations
    assert "localStorage" not in integrations
    assert 'cp "$source_dir/integrations.js"' in build
    assert "FIRSTROLL_SUPABASE_URL" in build
    assert "FIRSTROLL_SUPABASE_PUBLISHABLE_KEY" in build


def test_frontend_build_identity_distinguishes_local_and_live_releases() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")
    build = (ROOT / "tools" / "build_web.sh").read_text(encoding="utf-8")
    preview = (ROOT / "tools" / "preview_hosted_web.sh").read_text(encoding="utf-8")
    deployment = (
        ROOT
        / ".github"
        / "workflows"
        / "azure-static-web-apps-salmon-field-03695a010.yml"
    ).read_text(encoding="utf-8")

    assert 'id="buildIdentity"' in index
    assert "renderBuildIdentity" in app
    assert 'build_channel=live' in build
    assert 'build_channel=local' in build
    assert 'build_number=$((build_number + 1))' in build
    assert 'buildId: "v${build_number}"' in build
    assert "FIRSTROLL_SERVE_HOSTED_FRONTEND=true" in preview
    assert "FIRSTROLL_PUBLIC_MODE=true" in preview
    assert "fetch-depth: 0" in deployment


def test_account_saved_films_are_persistent_and_user_scoped() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    auth = (WEB / "auth.js").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")
    migration = (
        ROOT
        / "supabase"
        / "migrations"
        / "202608200002_persistent_accounts.sql"
    ).read_text(encoding="utf-8")

    assert 'id="accountSavedFilms"' in index
    assert 'data-save-film' in app
    assert 'data-remove-saved-film' in app
    assert '.from("firstroll_saved_films")' in auth
    assert 'onConflict: "user_id,film_id"' in auth
    assert "firstroll_profiles" in migration
    assert "firstroll_preferences" in migration
    assert "firstroll_saved_films" in migration
    assert migration.count("enable row level security") == 3
    assert migration.count("(select auth.uid()) = user_id") >= 10
    assert "references auth.users(id) on delete cascade" in migration
    assert "revoke all on public.firstroll_saved_films from public, anon" in migration
    assert "grant select, insert, update, delete on public.firstroll_saved_films to authenticated" in migration
    assert "security definer" in migration
    assert "firstroll_on_auth_user_created" in migration
    assert "Passwords, provider API keys, prompts, evidence and generated studies do not" in migration


def test_entra_external_id_account_auth_is_staged_without_breaking_supabase() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    auth = (WEB / "entra-auth.js").read_text(encoding="utf-8")
    build = (ROOT / "tools" / "build_web.sh").read_text(encoding="utf-8")

    assert 'from "@azure/msal-browser"' in auth
    assert "PublicClientApplication" in auth
    assert "loginRedirect" in auth
    assert "acquireTokenSilent" in auth
    assert "knownAuthorities" in auth
    assert 'cacheLocation: "localStorage"' in auth
    assert 'id="entraAuthForm"' in index
    assert "Sign in or create an account" in index
    assert 'authProvider === "entra"' in index
    assert '"$source_dir/entra-auth.js"' in build
    assert "FIRSTROLL_ENTRA_AUTHORITY" in build
    assert "FIRSTROLL_ENTRA_SPA_CLIENT_ID" in build
    assert "FIRSTROLL_ENTRA_API_SCOPE" in build


def test_public_deep_study_consumes_authenticated_safe_sse_progress() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")

    assert "/study/stream" in app
    assert "consumeResearchProgress" in app
    assert "RESEARCH_PROGRESS_KINDS" in app
    assert "progress.run_id !== expectedRunId" in app
    assert "progress.sequence !== lastSequence + 1" in app
    assert 'streamResponse.headers.get("X-FirstRoll-Run-ID")' in app
    assert "/api/research/runs/" in app
    assert 'eventName !== "progress"' in app
    assert 'progress.kind === "run_failed"' in app
    assert 'progress.kind === "run_completed"' in app


def test_public_video_preview_uses_neutral_product_copy() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")

    assert "Online video analysis is coming soon." in index
    assert "available only in the local edition" in index
    assert "your own machine" not in index


def test_public_settings_explains_session_keys_and_hosted_douban_boundary() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")
    styles = (WEB / "styles.css").read_text(encoding="utf-8")

    assert 'id="product-settings"' in index
    assert 'data-product-view="settings"' in index
    assert 'data-settings-section="account"' in index
    assert 'data-settings-section="system"' in index
    assert 'id="accountProfileForm"' in index
    assert 'id="accountPasswordForm"' in index
    assert 'name="accountTheme"' in index
    assert "updateDisplayName" in (WEB / "auth.js").read_text(encoding="utf-8")
    assert "updatePassword" in (WEB / "auth.js").read_text(encoding="utf-8")
    assert "updatePreferences" in (WEB / "auth.js").read_text(encoding="utf-8")
    assert "firstroll_profiles" in (WEB / "auth.js").read_text(encoding="utf-8")
    assert "firstroll_preferences" in (WEB / "auth.js").read_text(encoding="utf-8")
    assert "cleared on refresh or sign-out" in index
    assert "that study uses your DeepSeek account and provider balance" in index
    assert "FirstRoll’s three-study daily safety limit still applies" in index
    assert "search with your Google Cloud quota" in index
    assert "broader, fresher interviews, trailers and film-study videos" in index
    assert "never saved to your FirstRoll account" in index
    assert "Hosted MCP" in index
    assert "Visitors are never asked for a Douban cookie" in index
    assert "No visitor credential is accepted" in index
    assert "https://github.com/moria97/douban-mcp" in index
    assert 'requestHeaders?.("deepseek")' in app
    assert 'requestHeaders?.("youtube")' in app
    assert ".public-mode .public-settings-nav" in styles


def test_public_criticism_fetches_reviews_without_automatic_local_structuring() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")

    assert "if (!runtimeConfig.publicMode)" in app
    assert "Attributed reviews are ready. Deep Study can develop a separate" in app
    assert "route && canStructure" in app


def test_production_image_pins_and_bundles_douban_mcp() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM node:22-bookworm-slim AS douban-mcp-builder" in dockerfile
    assert "DOUBAN_MCP_REF=1adc26d39532db893616ceb7ea851733948ae69e" in dockerfile
    assert "npm ci --ignore-scripts --audit=false" in dockerfile
    assert "dependencies.@modelcontextprotocol/sdk=1.30.0" in dockerfile
    assert "overrides.path-to-regexp=8.4.2" in dockerfile
    assert "overrides.qs=6.15.3" in dockerfile
    assert "npm audit --omit=dev --audit-level=high" in dockerfile
    assert "FIRSTROLL_DOUBAN_MCP_PATH=/opt/douban-mcp/dist/index.js" in dockerfile
    assert "COPY --from=douban-mcp-builder /usr/local/bin/node" in dockerfile


def test_archive_pullout_collapses_before_zoom_can_clip_its_copy() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    styles = (WEB / "styles.css").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")

    assert "/assets/styles.css?v=20260821-8" in index
    assert "/assets/app.js?v=20260821-13" in index
    assert "closet3d.js" not in index
    assert 'class="archive-pullout-shell"' in app
    assert "container-type: inline-size" in styles
    assert "@container (max-width: 520px)" in styles
    assert "grid-template-columns: minmax(0, 0.9fr) minmax(0, 0.85fr)" in styles
    assert "flex: 0 0 100%" in styles
    assert "overflow-wrap: anywhere" in styles
    assert ".archive-pullout-label" in styles
    assert "flex-wrap: wrap" in styles
    assert ".archive-pullout-copy h3" in styles
    assert "overflow-wrap: break-word" in styles
    assert ".archive-pullout-copy button" in styles
    assert "max-width: 100%" in styles


def test_recent_searches_can_be_removed_individually_or_cleared() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")
    styles = (WEB / "styles.css").read_text(encoding="utf-8")

    assert "persistRecentSearches" in app
    assert "window.localStorage.removeItem(RECENT_SEARCHES_KEY)" in app
    assert 'data-remove-recent-search="${index}"' in app
    assert "data-clear-recent-searches" in app
    assert "Remove ${escapeHtml(search.title)} from recent searches" in app
    assert "state.discovery.recentSearches.filter" in app
    assert ".recent-search-item" in styles
    assert ".recent-search-dismiss" in styles
    assert ".recent-search-clear" in styles


def test_interface_states_are_actionable_and_keyboard_navigable() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    styles = (WEB / "styles.css").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")
    integrations = (WEB / "integrations.js").read_text(encoding="utf-8")
    auth = (WEB / "auth.js").read_text(encoding="utf-8")
    local_auth = (WEB / "local-auth.js").read_text(encoding="utf-8")

    assert 'aria-labelledby="resultsTitle" aria-busy="false"' in index
    assert 'id="filmDetail" class="film-detail hidden" aria-busy="false"' in index
    assert index.count('role="tabpanel" aria-labelledby="analysisTab') == 4
    assert index.count('role="tab" aria-selected=') >= 6
    assert "interface-state" in styles
    assert "study-cancel" in styles
    assert "cancelDeepStudyRequest" in app
    assert ".casefold(" not in app
    assert "new AbortController()" in app
    assert app.count("signal: controller.signal") >= 3
    assert "currentRequest" in app
    assert "A provider request already in progress may still finish and consume external quota" in app
    assert "data-cancel-study" in app
    assert "data-retry-study" in app
    assert "data-retry-film-detail" in app
    assert "data-retry-film-videos" in app
    assert "data-retry-criticism" in app
    assert "data-relax-discovery-filters" in app
    assert "focusInterfaceState" in app
    assert "onFilmDetailKeydown" in app
    assert "onAnalysisTabKeydown" in app
    navigation_keys = ("ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End")
    assert all(key in integrations for key in navigation_keys)
    assert all(key in auth for key in navigation_keys)
    assert all(key in local_auth for key in navigation_keys)
    assert "button.tabIndex = active ? 0 : -1" in auth
    assert "button.tabIndex = active ? 0 : -1" in local_auth
    assert "--action-text: #fff7ed" in styles
    assert "--action-text: #11120f" in styles


def test_deep_study_keeps_progress_packet_gaps_and_citations_inspectable() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")
    styles = (WEB / "styles.css").read_text(encoding="utf-8")
    study_service = (ROOT / "app" / "backend" / "study_service.py").read_text(
        encoding="utf-8"
    )

    assert "researchProgressMarkup" in app
    assert "studyProgress.push(progress)" in app
    assert "packetTransparencyMarkup" in app
    assert "Why evidence was left out" in app
    assert "Evidence gaps" in app
    assert "Study timing and stages" in app
    assert "data-study-citation-target" in app
    assert "data-study-evidence" in app
    assert "studyEvidenceTarget" in app
    assert "study-progress-history" in styles
    assert "packet-transparency" in styles
    assert "packet-layer-grid" in styles
    assert 'class="packet-metrics" role="group" aria-label="Packet quality metrics"' in app
    assert 'result["packet_quality"] = assess_evidence_packet(packet)' in study_service


def test_discovery_and_dossier_expose_a_clear_task_hierarchy() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    styles = (WEB / "styles.css").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")

    assert 'class="discovery-hero"' in index
    assert 'id="discoveryTitle"' in index
    assert "Find the film." in index
    assert "Required</small>" in index
    assert index.count("Optional</small>") == 2
    assert ".discovery-hero" in styles
    assert 'class="study-paths" aria-label="Film dossier sections"' in app
    assert 'href="#dossier-watch"' in app
    assert 'href="#dossier-criticism"' in app
    assert 'href="#dossier-study"' in app
    assert "detailOverviewMarkup" in app
    assert "Read the full attributed synopsis" in app
    assert '<details class="detail-facts"${factsOpen}>' in app
    assert 'summary>Credits &amp; film facts</summary>' in app
    assert 'window.requestAnimationFrame(() => {' in app
    assert 'refs.filmDetail.scrollIntoView({ behavior: "smooth", block: "start" })' in app


def test_discovery_workspace_survives_refresh_and_product_navigation() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")
    index = (WEB / "index.html").read_text(encoding="utf-8")

    assert "/assets/app.js?v=20260821-13" in index
    assert 'const DISCOVERY_SESSION_KEY = "firstroll.discovery-session"' in app
    assert 'const PRODUCT_SESSION_KEY = "firstroll.product-session"' in app
    assert "window.sessionStorage.setItem(DISCOVERY_SESSION_KEY" in app
    assert ".map(discoverySessionFilm)" in app
    session_film = app[
        app.index("function discoverySessionFilm"):
        app.index("function clearDiscoverySession")
    ]
    assert "critical_research" not in session_film
    assert "reviews" not in session_film
    assert "study" not in session_film
    assert "sessionByteLength(serialised) > DISCOVERY_SESSION_MAX_BYTES" in app
    assert "restoreDiscoverySession();" in app
    assert 'window.addEventListener("pagehide", persistCurrentSession)' in app
    assert 'snapshot.stage === "archive"' in app
    assert "renderFilmArchive(" in app
    assert "void loadFilmDetail(snapshot.detailFilmId, { scroll: false })" in app
    assert "state.viewScroll[state.productView]" in app
    assert "persistProductSession();" in app
    assert 'window.scrollTo({ top: scrollTop, behavior: "auto" })' in app


def test_new_discovery_search_aborts_stale_search_and_shelf_work() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")

    assert "searchRequestId: 0" in app
    assert "searchController: null" in app
    assert "shelfRequestControllers: new Set()" in app
    assert "state.discovery.searchController?.abort()" in app
    assert "cancelShelfRequests();" in app
    assert "{ signal: controller.signal }" in app
    assert "requestId !== state.discovery.searchRequestId" in app
    assert 'err?.name === "AbortError"' in app
    assert "state.discovery.shelfRequestControllers.add(controller)" in app
    assert "state.discovery.shelfRequestControllers.delete(controller)" in app
    assert "refs.discoverySubmit.disabled = true" not in app


def test_supabase_dialog_hides_the_unused_entra_form() -> None:
    styles = (WEB / "styles.css").read_text(encoding="utf-8")

    assert ".auth-dialog form.auth-provider-entra { display: none; }" in styles
    assert 'body[data-auth-provider="entra"] form.auth-provider-entra { display: grid; }' in styles


def test_director_shelf_renders_immediately_then_enriches_posters() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")
    styles = (WEB / "styles.css").read_text(encoding="utf-8")
    discovery = (ROOT / "app" / "backend" / "discovery.py").read_text(encoding="utf-8")

    assert "displayableFilms" in app
    assert "displayableFilms([primary, ...directorWorks])" in app
    assert "directorShelfMarkup(primary, directorWorks, director, loading)" in app
    assert "directorShelfFilmsMarkup(primary, films, loading)" in app
    assert "data-film-shelf-status" in app
    assert "data-retry-director-shelf" in app
    assert "retryDirectorShelf" in app
    assert "showFilmShelfFallback" in app
    partial = app[app.index("function markDirectorShelfPartial"):app.index("function retryDirectorShelf")]
    fallback = app[app.index("function showFilmShelfFallback"):app.index("function retryDirectorShelf")]
    assert "directorShelfFilmsMarkup(primary, films, false)" in fallback
    assert "markDirectorShelfPartial(primaryId)" in fallback
    assert "Showing the selected film." in partial
    assert "shelfRequestId: 0" in app
    assert "requestId !== state.discovery.shelfRequestId" in app
    assert "window.setTimeout(() => controller.abort(), fast ? 25000 : 90000)" in app
    assert 'fast ? 25000 : 90000' in app
    assert 'fast=${fast ? "true" : "false"}&director_only=true' in app
    assert "enrichDirectorFilmography" in app
    assert '`${filmId}:${fast ? "fast" : "enriched"}`' in app
    assert "Director poster enrichment did not complete" in app
    enrichment = app[
        app.index("async function enrichDirectorFilmography"):
        app.index("function applyDirectorShelf")
    ]
    assert "requestId !== state.discovery.shelfRequestId" in enrichment
    assert "state.discovery.archiveSelectionId !== primary.id" in enrichment
    assert "hydrateDirectorShelf(primary.id" in enrichment
    assert "FirstRollCloset" not in app
    assert "WebGL" not in app
    assert "Blender" not in app
    assert "!/^Q\\d+$/i.test(text)" in app
    assert "candidate_cap = min(48, max(limit * 2, limit))" in discovery
    assert "if cast_ids and not director_only:" in discovery
    assert "self._get_shelf_entities(selected_ids)" in discovery
    assert ".director-shelf" in styles
    assert ".director-film-list" in styles
    assert ".director-film-card.is-selected" in styles
    assert ".director-film-slot.is-skeleton" in styles
    assert 'loading="eager" decoding="async"' in app
    assert "padding: 0 2px 34px" in styles
    assert "@container (min-width: 660px)" in styles
    assert ".film-closet" not in styles
    assert ".closet-webgl" not in styles
