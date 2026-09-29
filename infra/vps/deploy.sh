#!/usr/bin/env bash
# Release, roll back or inspect the FirstRoll stack on this server.
#
#   deploy.sh release <commit-sha> <image-digest> <site.tar.gz>
#   deploy.sh rollback
#   deploy.sh status
#
# A release pulls the API image by immutable digest, waits until the container reports the
# expected baked commit, then switches the static site. Any activation failure restores the
# previous site and API; a first-release failure restores the bootstrap site and stops the API.
# Recovery failures remain failures and retain the candidate for investigation. The workflow
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
  tmp=$(mktemp "$root/.env.XXXXXX") || return 1
  if ! awk '!/^FIRSTROLL_IMAGE_DIGEST=/' "$env_file" > "$tmp" \
    || ! printf 'FIRSTROLL_IMAGE_DIGEST=%s\n' "$digest" >> "$tmp" \
    || ! chmod 0600 "$tmp" || ! mv -f "$tmp" "$env_file"; then
    rm -f "$tmp"
    return 1
  fi
}

write_record() {
  local target=$1 sha=$2 digest=$3 site=$4 tmp
  tmp=$(mktemp "$state_dir/.record.XXXXXX") || return 1
  if ! printf '%s %s %s\n' "$sha" "$digest" "$site" > "$tmp" \
    || ! mv -f "$tmp" "$target"; then
    rm -f "$tmp"
    return 1
  fi
}

write_current() { write_record "$current_file" "$@"; }
write_previous() { write_record "$previous_file" "$@"; }

# Switch releases/current atomically to a directory inside releases/.
point_site() {
  local name=$1
  [ -d "$releases/$name" ] || { echo "site directory $name is missing" >&2; return 1; }
  ln -sfn "$name" "$releases/current.tmp" || return 1
  mv -Tf "$releases/current.tmp" "$releases/current"
}

start_api() {
  "${compose[@]}" pull --quiet api || return 1
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
  # Bash disables errexit inside functions used by `if`/`||`. Every step and every
  # multi-command helper must propagate failure explicitly before state is committed.
  set_digest "$digest" || return 1
  start_api || return 1
  wait_for_api "$sha" || return 1
  point_site "$site" || return 1
  reload_caddy || return 1
  write_current "$sha" "$digest" "$site"
}

restore_before_release() {
  local sha=$1 digest=$2 site=$3
  # Restore the site before attempting API recovery; never leave a dangling candidate
  # symlink if the old API cannot start. An empty SHA means no API has been deployed yet.
  point_site "$site" || return 1
  set_digest "$digest" || return 1
  if valid_sha "$sha"; then
    start_api || return 1
    wait_for_api "$sha" || return 1
    reload_caddy || return 1
    write_current "$sha" "$digest" "$site" || return 1
  else
    # The bootstrap digest is a placeholder, not a downloadable rollback image.
    "${compose[@]}" stop api || return 1
  fi
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
  # Each attempt gets a new directory, including retries of the same commit. Never
  # remove a directory that the current or previous release may still reference.
  staging=$(mktemp -d "$releases/site-$sha.XXXXXX")
  site=$(basename "$staging")
  tar --no-same-owner -xzf "$archive" -C "$staging"
  [ -f "$staging/index.html" ] || { rm -rf "$staging"; fail "site archive lacks index.html"; }
  [ -f "$staging/release.json" ] || { rm -rf "$staging"; fail "site archive lacks release.json"; }
  chmod 0755 "$staging"

  if activate "$sha" "$digest" "$site"; then
    if valid_sha "$previous_sha" && valid_digest "$previous_digest" \
      && ! write_previous "$previous_sha" "$previous_digest" "$previous_site"; then
      echo "Could not record the rollback target; recovering the pre-release state." >&2
    else
      # Housekeeping is not activation. A pruning problem must not turn an active
      # release into a failed rollout that skips the runner's live verification.
      prune_sites || echo "Warning: old site cleanup failed." >&2
      docker image prune -f >/dev/null || echo "Warning: unused image cleanup failed." >&2
      echo "Released $sha ($digest)"
      return 0
    fi
  fi

  echo "Release activation failed; restoring the pre-release site and API state." >&2
  if restore_before_release "$previous_sha" "$previous_digest" "$previous_site"; then
    if [ "$(current_site)" != "$site" ]; then
      rm -rf "${releases:?}/${site:?}"
    fi
  else
    echo "Recovery also failed; candidate files retained. Manual recovery is required." >&2
  fi
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
