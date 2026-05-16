#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <bilibili-url-or-bvid> <workspace> [extractor]" >&2
  echo "Example: $0 'https://www.bilibili.com/video/BV1Z5myBqEGV/' /tmp/bili-work heuristic" >&2
  echo "Env flags (optional):" >&2
  echo "  WITH_FRAMES=1           Sample video frames alongside subtitles (Plan 2)." >&2
  echo "  FRAME_INTERVAL=30       Seconds between sampled frames." >&2
  echo "  FRAME_MAX_COUNT=10      Cap total frames sampled per video." >&2
  echo "  ENRICH_FRAMES=1         Run ImageExtractor over sampled frames before LLM extraction." >&2
  echo "  FRAMES_PER_SEGMENT=3    Max frames sent to vision per segment." >&2
  exit 2
fi

INPUT_REF="$1"
WORKSPACE="$2"
EXTRACTOR="${3:-heuristic}"
WITH_FRAMES="${WITH_FRAMES:-0}"
FRAME_INTERVAL="${FRAME_INTERVAL:-30}"
FRAME_MAX_COUNT="${FRAME_MAX_COUNT:-10}"
ENRICH_FRAMES="${ENRICH_FRAMES:-0}"
FRAMES_PER_SEGMENT="${FRAMES_PER_SEGMENT:-3}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT_DIR/packages/qa-agent/src${PYTHONPATH:+:$PYTHONPATH}"

FETCH_ARGS=()
if [[ "$INPUT_REF" =~ ^https?:// ]]; then
  FETCH_ARGS+=(--url "$INPUT_REF")
else
  FETCH_ARGS+=(--bvid "$INPUT_REF")
fi

mkdir -p "$WORKSPACE"
# Absolute path — qa-agent CLIs resolve relative paths against the package root
# (packages/qa-agent), not the monorepo root, which causes double-nesting.
WORKSPACE="$(cd "$WORKSPACE" && pwd)"
BUNDLE_PATH="$WORKSPACE/bilibili-bundle.yaml"

ENV_FILE="$ROOT_DIR/packages/qa-agent/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

FETCH_EXTRA=()
if [[ "$WITH_FRAMES" == "1" ]]; then
  FETCH_EXTRA+=(--with-frames --frame-interval "$FRAME_INTERVAL" --frame-max-count "$FRAME_MAX_COUNT" --frame-output-dir "$WORKSPACE/frames")
fi

PIPELINE_EXTRA=()
if [[ "$ENRICH_FRAMES" == "1" ]]; then
  PIPELINE_EXTRA+=(--enrich-frames --frames-per-segment "$FRAMES_PER_SEGMENT")
fi

fetch_cmd=(python3 -m qa_agent.app.fetch_bilibili_bundle "${FETCH_ARGS[@]}" --output "$BUNDLE_PATH" --asr-fallback)
if [[ ${#FETCH_EXTRA[@]} -gt 0 ]]; then
  fetch_cmd+=("${FETCH_EXTRA[@]}")
fi

pipeline_cmd=(python3 -m qa_agent.app.run_video_pipeline --input "$BUNDLE_PATH" --workspace "$WORKSPACE" --extractor "$EXTRACTOR")
if [[ ${#PIPELINE_EXTRA[@]} -gt 0 ]]; then
  pipeline_cmd+=("${PIPELINE_EXTRA[@]}")
fi

"${fetch_cmd[@]}"
"${pipeline_cmd[@]}"
