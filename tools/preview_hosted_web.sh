#!/usr/bin/env sh

set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
preview_port=${PORT:-4173}

# Use the same feature boundary as firstroll.app while serving the frontend and
# API from one localhost origin. Supabase values remain optional environment
# inputs; when supplied, account behaviour matches the deployed site as well.
export FIRSTROLL_PUBLIC_MODE=true
export FIRSTROLL_SERVE_HOSTED_FRONTEND=true
export FIRSTROLL_VIDEO_ANALYSIS_ENABLED=false
export FIRSTROLL_BUILD_CHANNEL=local

cd "$project_root"
exec uv run uvicorn app.backend.main:app --host 127.0.0.1 --port "$preview_port"
