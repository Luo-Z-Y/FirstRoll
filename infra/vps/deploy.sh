#!/usr/bin/env bash
# Release, roll back or inspect the FirstRoll stack on this server.
#
#   deploy.sh release <commit-sha> <image-digest> <site.tar.gz>
#   deploy.sh rollback
#   deploy.sh status
#
# A release pulls the API image by immutable digest, waits until the container reports the
# expected baked commit, then switches the static site. If the API never becomes healthy the
# previous digest is restored and the site is left untouched. The GitHub VPS Release workflow
# uploads this script from the approved commit before running it, so the server always
# executes the reviewed version.
set -euo pipefail

root=${FIRSTROLL_INSTALL_ROOT:-/opt/firstroll}
env_file="$root/.env"
releases="$root/releases"
state_dir="$root/state"
previous_file="$state_dir/previous-release"
current_file="$state_dir/current-release"
compose=(docker compose --project-directory "$root")

fail() {
  echo "deploy.sh: $*" >&2
  exit 1
}

usage() {
  sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
}

valid_sha() { [[ ${1:-} =~ ^[0-9a-f]{40}$ ]]; }
valid_digest() { [[ ${1:-} =~ ^sha256:[0-9a-f]{64}$ ]]; }

current_digest() {
  sed -n 's/^FIRSTROLL_IMAGE_DIGEST=//p' "$env_file" | tail -n 1
}

current_site() {
  local target
  target=$(readlink "$releases/current" 2>/dev/null || true)
  printf '%s\n' "${target:-none}"
}

current_sha() {
  local record
  record=$(cat "$current_file" 2>/dev/null || true)
  printf '%s\n' "${record%% *}"
}

# Rewrite the single digest line without leaving a partially written env file.
set_digest() {
  local digest=$1 tmp
  tmp=$(mktemp "$root/.env.XXXXXX")
  { grep -v '^FIRSTROLL_IMAGE_DIGEST=' "$env_file" || true; printf 'FIRSTROLL_IMAGE_DIGEST=%s\n' "$digest"; } > "$tmp"
  chmod 0600 "$tmp"
  mv -f "$tmp" "$env_file"
}

# Switch releases/current atomically to a directory inside releases/.
point_site() {
  local name=$1
  [ -d "$releases/$name" ] || fail "site directory $name is missing"
  ln -sfn "$name" "$releases/current.tmp"
  mv -Tf "$releases/current.tmp" "$releases/current"
}

start_api() {
  "${compose[@]}" pull --quiet api
  "${compose[@]}" up -d --remove-orphans
}

# The running container must report the expected baked release SHA, not merely "ok".
wait_for_api() {
  local sha=$1
  for _ in $(seq 1 30); do
    if "${compose[@]}" exec -T api python -c '
import json, sys, urllib.request
body = json.load(urllib.request.urlopen("http://127.0.0.1:10000/api/health", timeout=5))
sys.exit(0 if body.get("status") == "ok" and body.get("release_sha") == sys.argv[1] else 1)
' "$sha" >/dev/null 2>&1; then
      return 0
    fi
    sleep 4
  done
  return 1
}

reload_caddy() {
  "${compose[@]}" exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
}

# Keep the current and previous sites plus the two most recent others.
prune_sites() {
  local keep dir name
  keep=" $(current_site) $(cut -d' ' -f3 "$previous_file" 2>/dev/null || true) "
  while IFS= read -r dir; do
    [ -n "$dir" ] || continue
    name=$(basename "$dir")
    case "$keep" in *" $name "*) continue ;; esac
    rm -rf "$dir"
  done < <(find "$releases" -mindepth 1 -maxdepth 1 -type d -name 'site-*' -printf '%T@ %p\n' \
    | sort -rn | tail -n +4 | cut -d' ' -f2-)
}

activate() {
  local sha=$1 digest=$2 site=$3
  set_digest "$digest"
  start_api
  wait_for_api "$sha" || return 1
  point_site "$site"
  reload_caddy
  printf '%s %s %s\n' "$sha" "$digest" "$site" > "$current_file"
}

release() {
  local sha=${1:-} digest=${2:-} archive=${3:-}
  valid_sha "$sha" || fail "release requires a 40-character commit SHA"
  valid_digest "$digest" || fail "release requires an image digest of the form sha256:<64 hex>"
  [ -f "$archive" ] || fail "site archive $archive not found"
  [ -f "$env_file" ] || fail "$env_file is missing; run bootstrap.sh and edit it first"

  local previous_sha previous_digest previous_site site staging
  previous_sha=$(current_sha)
  previous_digest=$(current_digest)
  previous_site=$(current_site)
  site="site-$sha"

  staging=$(mktemp -d "$releases/.staging.XXXXXX")
  tar --no-same-owner -xzf "$archive" -C "$staging"
  [ -f "$staging/index.html" ] || { rm -rf "$staging"; fail "site archive lacks index.html"; }
  [ -f "$staging/release.json" ] || { rm -rf "$staging"; fail "site archive lacks release.json"; }
  chmod 0755 "$staging"
  rm -rf "${releases:?}/${site:?}"
  mv "$staging" "$releases/$site"

  if activate "$sha" "$digest" "$site"; then
    if valid_sha "$previous_sha" && valid_digest "$previous_digest"; then
      printf '%s %s %s\n' "$previous_sha" "$previous_digest" "$previous_site" > "$previous_file"
    fi
    prune_sites
    docker image prune -f >/dev/null
    echo "Released $sha ($digest)"
    return 0
  fi

  echo "The API did not report release $sha; restoring the previous image." >&2
  if valid_digest "$previous_digest"; then
    set_digest "$previous_digest"
    start_api || true
  fi
  rm -rf "${releases:?}/${site:?}"
  exit 1
}

rollback() {
  local record previous_sha previous_digest previous_site current_record
  record=$(cat "$previous_file" 2>/dev/null || true)
  read -r previous_sha previous_digest previous_site <<< "$record"
  valid_sha "${previous_sha:-}" || fail "no previous release is recorded"
  valid_digest "${previous_digest:-}" || fail "the recorded previous release has no valid digest"
  [ -d "$releases/${previous_site:-}" ] || fail "the previous site directory ${previous_site:-} is missing"
  current_record=$(cat "$current_file" 2>/dev/null || true)
  activate "$previous_sha" "$previous_digest" "$previous_site" \
    || fail "the previous image did not become healthy"
  # Record what we rolled away from so a roll-forward stays possible.
  if [ -n "$current_record" ]; then
    printf '%s\n' "$current_record" > "$previous_file"
  fi
  echo "Rolled back to $previous_sha ($previous_digest)"
}

status() {
  echo "Current release:  $(cat "$current_file" 2>/dev/null || echo none)"
  echo "Previous release: $(cat "$previous_file" 2>/dev/null || echo none)"
  echo "Configured digest: $(current_digest)"
  echo "Served site:      $(current_site)"
  "${compose[@]}" ps
}

case ${1:-} in
  release) shift; release "$@" ;;
  rollback) rollback ;;
  status) status ;;
  -h|--help|help) usage ;;
  *) usage >&2; exit 2 ;;
esac
