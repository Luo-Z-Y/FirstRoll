from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "app" / "web"


def test_blender_closet_glb_is_packaged_as_a_web_asset() -> None:
    model = WEB / "models" / "firstroll-closet.glb"

    assert model.is_file()
    assert model.stat().st_size > 100_000
    assert model.read_bytes()[:4] == b"glTF"


def test_webgl_runtime_is_local_and_loaded_by_the_discovery_page() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    runtime = (WEB / "closet3d.js").read_text(encoding="utf-8")

    assert 'type="importmap"' in index
    assert 'src="/assets/closet3d.js' in index
    assert 'from "three"' in runtime
    assert "firstroll-closet.glb" in runtime
    assert "firstroll:select-film" in runtime
    assert "waitForShelfReveal" in runtime
    assert 'textContent = "Shelf ready"' in runtime
    assert "window.setTimeout(resolve, 420)" in runtime
    assert "window.FirstRollCloset.update(detail)" in (WEB / "app.js").read_text(
        encoding="utf-8"
    )
    assert (WEB / "vendor" / "three" / "LICENSE").is_file()


def test_supabase_auth_is_bundled_and_deep_study_sends_bearer_tokens() -> None:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    auth = (WEB / "auth.js").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")
    build = (ROOT / "tools" / "build_web.sh").read_text(encoding="utf-8")
    integrations = (WEB / "integrations.js").read_text(encoding="utf-8")

    assert 'id="authDialog"' in index
    assert '"/assets/auth.js?v=20260820-4"' in index
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
    assert '"/assets/local-auth.js?v=20260820-2"' in index
    assert '["localhost", "127.0.0.1", "::1"]' in index
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
    assert "account studies remain today" in app
    assert 'src="/assets/integrations.js?v=20260820-6"' in index
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

    assert "/assets/styles.css?v=20260821-2" in index
    assert "/assets/app.js?v=20260821-2" in index
    assert "/assets/closet3d.js?v=20260821-1" in index
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


def test_supabase_dialog_hides_the_unused_entra_form() -> None:
    styles = (WEB / "styles.css").read_text(encoding="utf-8")

    assert ".auth-dialog form.auth-provider-entra { display: none; }" in styles
    assert 'body[data-auth-provider="entra"] form.auth-provider-entra { display: grid; }' in styles


def test_director_shelf_uses_front_facing_poster_cases() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")
    runtime = (WEB / "closet3d.js").read_text(encoding="utf-8")
    styles = (WEB / "styles.css").read_text(encoding="utf-8")
    discovery = (ROOT / "app" / "backend" / "discovery.py").read_text(encoding="utf-8")
    blender_builder = (ROOT / "tools" / "build_closet_blender.py").read_text(
        encoding="utf-8"
    )

    assert "displayableFilms" in app
    assert "related?limit=12&fast=false&director_only=true" in app
    assert "buildShelfCollections(primary, directorWorks, director)" in app
    director_shelf = app[app.index("function buildShelfCollections"):app.index("function displayableFilms")]
    assert "const films = displayableFilms(directorWorks)" in director_shelf
    assert "shared_cast" not in director_shelf
    assert "candidate_cap = min(168, max(40, limit * 5))" in discovery
    assert "candidate_cap = min(48, max(limit * 2, limit))" in discovery
    assert "if cast_ids and not director_only:" in discovery
    assert "self._get_shelf_entities(selected_ids)" in discovery
    assert "RELATED_POSTER_FALLBACK_LIMIT = 8" in discovery
    assert "fetchRelatedFilms" in app
    assert "28000" in app
    assert "Still checking verified films" in app
    assert "searchFallbackShelfCollections" not in app
    assert "Live relations delayed · showing verified search matches" not in app
    assert "clearLiveCollections" in runtime
    assert "this.shelfPlaques" not in runtime
    assert "hydrateFilmShelf" in app
    assert "collections: []" in app
    assert "window.FirstRollCloset.update(detail)" in app
    assert "showFilmShelfError" in app
    assert "No other verified films by this director were returned" in app
    assert "collections.some((collection) => collection.films.length < 10)" not in app
    assert "videoProviderStatusMarkup" in app
    assert "Douban is not connected on this hosted server yet" in app
    assert "renderFilmArchive(primary, [], uniqueFilms(nearby" not in app
    assert "!/^Q\\d+$/i.test(text)" in app
    assert "closet-help" not in app
    assert app.count('wall: "back"') == 1
    assert 'wall: "left"' not in app
    assert 'wall: "right"' not in app
    assert 'shelf: "middle",\n    label: `${director} films`' in app
    assert "Shared cast & related works" not in app
    assert "const SHELF_ROW_SIZE = 12" in runtime
    assert "const DISPLAY_COLUMNS = 4" in runtime
    assert "SHELF_VERTICAL_CENTRE = 2.27" in runtime
    assert "DEFAULT_CAMERA_POSITION = new THREE.Vector3(0, SHELF_VERTICAL_CENTRE, 0.12)" in runtime
    assert "DEFAULT_CAMERA_PITCH = 0" in runtime
    assert runtime.count("this.camera.position.copy(DEFAULT_CAMERA_POSITION)") == 2
    assert "this.camera.getWorldDirection(forward)" in runtime
    assert "crossVectors(forward, this.camera.up)" in runtime
    assert "const { forward } = this.movementBasis()" in runtime
    assert "const { right } = this.movementBasis()" in runtime
    assert "placeholder: true" not in runtime
    assert "FirstRoll Archive" not in runtime
    assert "selectableCase: true" in runtime
    assert "bottom: 0.61" in runtime
    assert "top: 3.93" in runtime
    assert "middle: 2.27" in runtime
    assert "upper: 3.10" in runtime
    assert "lower: 1.44" in runtime
    assert "new THREE.Vector3(offset, rowHeights[rowIndex], -3.52)" in runtime
    assert "const gap = 0.085" in runtime
    assert "const depth = 0.095" in runtime
    assert "amount * 0.035" in runtime
    assert "wireframe: true" not in runtime
    assert "firstroll_ambient_case" not in runtime
    assert "updateCaseCaption" in runtime
    assert "uniqueFilmCount" in runtime
    assert "canvas.height = 1152" in runtime
    assert "closet-loading-cases" in app
    assert "closet-loading-case" in styles
    assert "hasShelfCollections" in runtime
    assert "finishLoading" in runtime
    assert runtime.count('if (this.hasShelfCollections()) {') == 2
    assert "const faceAspect = faceWidth / faceHeight" in runtime
    assert "loadPosterTexture" in runtime
    assert 'textContent = "Loading film artwork"' not in runtime
    assert "this.loadPosterTexture(film.poster_url, faceAspect).then" in runtime
    assert "posterPromise" in runtime
    assert "loadedPosterCount" in runtime
    assert "createCoverBaseTexture" in runtime
    assert "createCoverLabelTexture" in runtime
    assert "createSpineTexture" not in runtime
    assert "async update(payload)" in runtime
    assert 'setCrossOrigin("anonymous")' in runtime
    assert "texture.repeat.set(targetAspect / imageAspect, 1)" in runtime
    assert "All five rows remain empty in the asset" in blender_builder
    assert "firstroll_ambient_case" not in blender_builder
    assert 'build_side_shelves("left", materials)' not in blender_builder
    assert 'build_side_shelves("right", materials)' not in blender_builder
