#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ai-baseball2026}"
DATA_DIR="${DATA_DIR:-/opt/hawks-ai/data}"
BRANCH="${BRANCH:-main-AI-BASEBALL}"
CONTAINER_NAME="${CONTAINER_NAME:-ai-baseball-app}"
IMAGE_NAME="${IMAGE_NAME:-ai-baseball-app}"
PORT="${PORT:-8502}"
DEPLOY_SHA="${DEPLOY_SHA:-}"

cd "$APP_DIR"
mkdir -p "$DATA_DIR"

echo "[deploy] fetching $BRANCH"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

if [ -n "$DEPLOY_SHA" ]; then
  ACTUAL_SHA="$(git rev-parse HEAD)"
  if [ "$ACTUAL_SHA" != "$DEPLOY_SHA" ]; then
    echo "[deploy] expected $DEPLOY_SHA but checked out $ACTUAL_SHA"
    exit 1
  fi
fi

SHORT_SHA="$(git rev-parse --short=12 HEAD)"
NEW_IMAGE="$IMAGE_NAME:$SHORT_SHA"
PREVIOUS_IMAGE="$(docker inspect -f '{{.Config.Image}}' "$CONTAINER_NAME" 2>/dev/null || true)"

echo "[deploy] building $NEW_IMAGE"
docker build -t "$NEW_IMAGE" .

if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  docker rm -f "$CONTAINER_NAME"
fi

start_container() {
  local image="$1"
  docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -p "$PORT:8501" \
    -v "$DATA_DIR:/app/data" \
    -e DATA_DIR=/app/data \
    -e TZ=Asia/Tokyo \
    "$image"
}

rollback() {
  echo "[deploy] health check failed"
  docker logs --tail 100 "$CONTAINER_NAME" || true
  docker rm -f "$CONTAINER_NAME" || true
  if [ -n "$PREVIOUS_IMAGE" ] && docker image inspect "$PREVIOUS_IMAGE" >/dev/null 2>&1; then
    echo "[deploy] rolling back to $PREVIOUS_IMAGE"
    start_container "$PREVIOUS_IMAGE"
  fi
  exit 1
}

start_container "$NEW_IMAGE"

for attempt in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$PORT/_stcore/health" >/dev/null; then
    echo "[deploy] healthy: $NEW_IMAGE"
    docker tag "$NEW_IMAGE" "$IMAGE_NAME:latest"
    exit 0
  fi
  sleep 2
done

rollback
