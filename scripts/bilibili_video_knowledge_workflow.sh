#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <bilibili-url-or-bvid> <workspace> [extractor]" >&2
  echo "Example: $0 'https://www.bilibili.com/video/BV1Z5myBqEGV/' /tmp/bili-work heuristic" >&2
  exit 2
fi

INPUT_REF="$1"
WORKSPACE="$2"
EXTRACTOR="${3:-heuristic}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT_DIR/packages/qa-agent/src${PYTHONPATH:+:$PYTHONPATH}"

FETCH_ARGS=()
if [[ "$INPUT_REF" =~ ^https?:// ]]; then
  FETCH_ARGS+=(--url "$INPUT_REF")
else
  FETCH_ARGS+=(--bvid "$INPUT_REF")
fi

mkdir -p "$WORKSPACE"
BUNDLE_PATH="$WORKSPACE/bilibili-bundle.yaml"

python3 -m qa_agent.app.fetch_bilibili_bundle "${FETCH_ARGS[@]}" --output "$BUNDLE_PATH"
python3 -m qa_agent.app.run_video_pipeline --input "$BUNDLE_PATH" --workspace "$WORKSPACE" --extractor "$EXTRACTOR"
