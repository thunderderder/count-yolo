#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -n "${COUNT_YOLO_PYTHON:-}" && -x "${COUNT_YOLO_PYTHON}" ]]; then
  PYTHON="$COUNT_YOLO_PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="python3"
fi

CMD="${1:-}"
shift || true

case "$CMD" in
  annotate)
    exec "$PYTHON" annotate_line.py "$@"
    ;;
  count)
    exec "$PYTHON" count_traffic.py "$@"
    ;;
  compare)
    exec "$PYTHON" compare_ground_truth.py "$@"
    ;;
  8m)
    MODEL="$ROOT/models/yolov8m.pt"
    ARGS=("$@")
    if [[ ! " ${ARGS[*]} " =~ " --model " && -f "$MODEL" ]]; then
      ARGS+=(--model "$MODEL")
    fi
    exec "$PYTHON" count_traffic.py "${ARGS[@]}"
    ;;
  ebike)
    MODEL="${COUNT_YOLO_EBIKE_MODEL:-$ROOT/models/electri_bike_and_vehicle.pt}"
    if [[ ! -f "$MODEL" ]]; then
      echo "model file missing: $MODEL (set COUNT_YOLO_EBIKE_MODEL)" >&2
      exit 1
    fi
    ARGS=("$@")
    if [[ ! " ${ARGS[*]} " =~ " --model " ]]; then
      ARGS+=(--model "$MODEL")
    fi
    exec "$PYTHON" count_traffic.py "${ARGS[@]}"
    ;;
  "")
    echo "Usage: ./scripts/run.sh <annotate|count|compare|8m|ebike> [args...]"
    echo "Python: $PYTHON"
    exit 1
    ;;
  *)
    echo "unknown command: $CMD" >&2
    exit 1
    ;;
esac
