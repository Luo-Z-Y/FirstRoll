#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GUIDELLM_VERSION="0.7.3"
LM_EVAL_VERSION="0.4.12"
PORT="18766"
OUT="$ROOT/.firstroll/benchmarks/tooling-smoke"
GUIDELLM_REPORT="$OUT/guidellm.json"
LM_EVAL_OUT="$OUT/lm-eval"
MOCK_LOG="$OUT/guidellm-mock.log"

umask 077
python - "$ROOT" "$OUT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
candidate = Path(sys.argv[2]).resolve(strict=False)
if candidate != root / ".firstroll" and root / ".firstroll" not in candidate.parents:
    raise SystemExit("Benchmark smoke output must resolve beneath this repository's .firstroll.")
PY
mkdir -p "$OUT"
chmod 700 "$ROOT/.firstroll" "$ROOT/.firstroll/benchmarks" "$OUT" 2>/dev/null || true
rm -f "$GUIDELLM_REPORT" "$MOCK_LOG" "$OUT/summary.json"
rm -rf "$LM_EVAL_OUT"

if ! command -v uvx >/dev/null 2>&1; then
  printf 'uvx is required. Install uv before running the benchmark-tooling smoke test.\n' >&2
  exit 1
fi

if python - "$PORT" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket() as probe:
    raise SystemExit(0 if probe.connect_ex(("127.0.0.1", port)) == 0 else 1)
PY
then
  printf 'Local port %s is already in use; refusing to contact an unknown service.\n' "$PORT" >&2
  exit 1
fi

uvx --from "guidellm==$GUIDELLM_VERSION" guidellm mock-server \
  --host 127.0.0.1 \
  --port "$PORT" \
  --model firstroll-benchmark-mock \
  --ttft-ms 20 \
  --itl-ms 2 \
  --output-tokens 16 \
  >"$MOCK_LOG" 2>&1 &
mock_pid=$!
cleanup() {
  kill "$mock_pid" 2>/dev/null || true
  wait "$mock_pid" 2>/dev/null || true
}
trap cleanup EXIT

ready=0
for _ in $(seq 1 80); do
  if python - "$PORT" <<'PY' >/dev/null 2>&1
import json
import sys
from urllib.request import urlopen

port = int(sys.argv[1])
with urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=0.5) as response:
    payload = json.load(response)
ids = {item.get("id") for item in payload.get("data", [])}
raise SystemExit(0 if "firstroll-benchmark-mock" in ids else 1)
PY
  then
    ready=1
    break
  fi
  sleep 0.25
done
if [[ "$ready" != "1" ]]; then
  printf 'GuideLLM mock server did not become ready. See %s.\n' "$MOCK_LOG" >&2
  exit 1
fi

GUIDELLM__MP_CONTEXT_TYPE=spawn \
GUIDELLM__MAX_WORKER_PROCESSES=1 \
TOKENIZERS_PARALLELISM=false \
uvx --from "guidellm==$GUIDELLM_VERSION" guidellm run \
  --config evals/benchmark_tools/guidellm-tool-calling-smoke.json \
  --disable-console-interactive \
  --disable-console

uvx --from "lm-eval==$LM_EVAL_VERSION" lm_eval validate \
  --tasks firstroll_tooling_smoke,firstroll_claim_support \
  --include_path evals/benchmark_tools/lm_eval

uvx --from "lm-eval[api]==$LM_EVAL_VERSION" lm_eval run \
  --model local-chat-completions \
  --model_args "model=firstroll-benchmark-mock,base_url=http://127.0.0.1:$PORT/v1/chat/completions,tokenized_requests=false,tokenizer_backend=none,num_concurrent=1,max_retries=0,max_gen_toks=16,eos_string=<|endoftext|>" \
  --tasks firstroll_tooling_smoke \
  --include_path evals/benchmark_tools/lm_eval \
  --output_path "$LM_EVAL_OUT" \
  --seed 42 \
  --apply_chat_template \
  >/dev/null

python - "$GUIDELLM_REPORT" "$LM_EVAL_OUT" "$OUT/summary.json" <<'PY'
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

report_path = Path(sys.argv[1])
lm_eval_dir = Path(sys.argv[2])
summary_path = Path(sys.argv[3])

guide = json.loads(report_path.read_text(encoding="utf-8"))
benchmark = guide["benchmarks"][0]
request_totals = benchmark["metrics"]["request_totals"]
tool_calls = benchmark["metrics"]["tool_call"]["count"]["output"]["successful"]
if request_totals != {"successful": 4, "errored": 0, "incomplete": 0, "total": 4}:
    raise SystemExit("GuideLLM did not complete the four-request mock tool-call smoke test.")
if int(tool_calls["total_sum"]) != 2:
    raise SystemExit("GuideLLM did not observe two mock native tool calls.")

result_paths = sorted(lm_eval_dir.rglob("results_*.json"))
if len(result_paths) != 1:
    raise SystemExit("lm-evaluation-harness did not produce exactly one aggregate result.")
lm_eval = json.loads(result_paths[0].read_text(encoding="utf-8"))
samples = lm_eval["n-samples"]["firstroll_tooling_smoke"]
if samples != {"original": 3, "effective": 3}:
    raise SystemExit("lm-evaluation-harness did not process all three mock samples.")

summary = {
    "schema_version": 1,
    "scope": "local_mock_tooling_smoke_only",
    "recorded_at": datetime.now(timezone.utc).isoformat(),
    "external_model_provider_calls": 0,
    "guidellm": {
        "version": guide["metadata"]["guidellm_version"],
        "successful_requests": request_totals["successful"],
        "errored_requests": request_totals["errored"],
        "observed_native_tool_calls": int(tool_calls["total_sum"]),
    },
    "lm_eval": {
        "version": lm_eval["lm_eval_version"],
        "model_adapter": lm_eval["config"]["model"],
        "processed_samples": samples["effective"],
        "quality_score_is_product_evidence": False,
    },
}
summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
summary_path.chmod(0o600)
print(json.dumps(summary, indent=2))
PY

printf 'Private smoke outputs: %s\n' "$OUT"
