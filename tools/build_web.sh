#!/usr/bin/env sh

set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
source_dir="$project_root/app/web"
output_dir="$project_root/dist"
api_base=${FIRSTROLL_API_BASE:-}
supabase_url=${FIRSTROLL_SUPABASE_URL:-}
supabase_publishable_key=${FIRSTROLL_SUPABASE_PUBLISHABLE_KEY:-}
auth_provider=${FIRSTROLL_AUTH_PROVIDER:-supabase}
entra_authority=${FIRSTROLL_ENTRA_AUTHORITY:-}
entra_spa_client_id=${FIRSTROLL_ENTRA_SPA_CLIENT_ID:-}
entra_api_scope=${FIRSTROLL_ENTRA_API_SCOPE:-}
build_channel=${FIRSTROLL_BUILD_CHANNEL:-}
build_number=${FIRSTROLL_BUILD_NUMBER:-}
build_commit=${FIRSTROLL_BUILD_COMMIT:-}

# Git commit count gives both local and deployed builds a small, comparable
# number. CI publishes the current number; local builds reserve the next one so
# the working copy is always visibly ahead of the live release.
if [ -z "$build_channel" ]; then
  if [ "${GITHUB_ACTIONS:-}" = "true" ] || [ "${CI:-}" = "true" ]; then
    build_channel=live
  else
    build_channel=local
  fi
fi
case "$build_channel" in
  local|live|preview) ;;
  *)
    echo "FIRSTROLL_BUILD_CHANNEL must be local, live or preview." >&2
    exit 1
    ;;
esac

if [ -z "$build_number" ]; then
  build_number=$(git -C "$project_root" rev-list --count HEAD 2>/dev/null || echo 0)
  if [ "$build_channel" = "local" ]; then
    build_number=$((build_number + 1))
  fi
fi
case "$build_number" in
  ''|*[!0-9]*)
    echo "FIRSTROLL_BUILD_NUMBER must be a non-negative integer." >&2
    exit 1
    ;;
esac

if [ -z "$build_commit" ]; then
  build_commit=$(git -C "$project_root" rev-parse --short=8 HEAD 2>/dev/null || echo unknown)
fi
case "$build_commit" in
  *[!A-Za-z0-9._-]*)
    echo "FIRSTROLL_BUILD_COMMIT contains invalid characters." >&2
    exit 1
    ;;
esac

case "$api_base" in
  https://*) ;;
  *)
    echo "FIRSTROLL_API_BASE must be the backend's https:// URL." >&2
    exit 1
    ;;
esac

if [ -n "$supabase_url" ] || [ -n "$supabase_publishable_key" ]; then
  case "$supabase_url" in
    https://*.supabase.co) ;;
    *)
      echo "FIRSTROLL_SUPABASE_URL must be the project's https://*.supabase.co URL." >&2
      exit 1
      ;;
  esac
  case "$supabase_publishable_key" in
    sb_publishable_*) ;;
    *)
      echo "FIRSTROLL_SUPABASE_PUBLISHABLE_KEY must begin with sb_publishable_." >&2
      exit 1
      ;;
  esac
  case "$supabase_publishable_key" in
    *[!A-Za-z0-9_-]*)
      echo "FIRSTROLL_SUPABASE_PUBLISHABLE_KEY contains invalid characters." >&2
      exit 1
      ;;
  esac
fi

case "$auth_provider" in
  supabase) ;;
  entra)
    case "$entra_authority" in
      https://*.ciamlogin.com/*) ;;
      *)
        echo "FIRSTROLL_ENTRA_AUTHORITY must be the External ID tenant's https://*.ciamlogin.com/... authority." >&2
        exit 1
        ;;
    esac
    if [ -z "$entra_spa_client_id" ] || [ -z "$entra_api_scope" ]; then
      echo "FIRSTROLL_ENTRA_SPA_CLIENT_ID and FIRSTROLL_ENTRA_API_SCOPE are required for Entra authentication." >&2
      exit 1
    fi
    ;;
  *)
    echo "FIRSTROLL_AUTH_PROVIDER must be either supabase or entra." >&2
    exit 1
    ;;
esac

rm -rf "$output_dir"
mkdir -p "$output_dir/assets"

cp "$source_dir/index.html" "$output_dir/index.html"
cp "$source_dir/app.js" "$output_dir/assets/app.js"
cp "$source_dir/integrations.js" "$output_dir/assets/integrations.js"
cp "$source_dir/local-auth.js" "$output_dir/assets/local-auth.js"
cp "$source_dir/closet3d.js" "$output_dir/assets/closet3d.js"
cp "$source_dir/favicon.svg" "$output_dir/assets/favicon.svg"
cp "$source_dir/styles.css" "$output_dir/assets/styles.css"
cp -R "$source_dir/models" "$output_dir/assets/models"
cp -R "$source_dir/vendor" "$output_dir/assets/vendor"

npm ci --include=dev --ignore-scripts --no-audit --no-fund
./node_modules/.bin/esbuild "$source_dir/auth.js" \
  --bundle \
  --minify \
  --format=iife \
  --outfile="$output_dir/assets/auth.js"
./node_modules/.bin/esbuild "$source_dir/entra-auth.js" \
  --bundle \
  --minify \
  --format=iife \
  --outfile="$output_dir/assets/entra-auth.js"

cat > "$output_dir/assets/config.js" <<EOF
window.FIRSTROLL_CONFIG = Object.freeze({
  apiBase: "${api_base}",
  publicMode: true,
  videoAnalysisEnabled: false,
  authProvider: "${auth_provider}",
  supabaseUrl: "${supabase_url}",
  supabasePublishableKey: "${supabase_publishable_key}",
  entraAuthority: "${entra_authority}",
  entraSpaClientId: "${entra_spa_client_id}",
  entraApiScope: "${entra_api_scope}",
  localTestAccountEmail: "",
  buildId: "v${build_number}",
  buildNumber: ${build_number},
  buildChannel: "${build_channel}",
  buildCommit: "${build_commit}",
});
EOF

echo "Built FirstRoll static site in $output_dir"
