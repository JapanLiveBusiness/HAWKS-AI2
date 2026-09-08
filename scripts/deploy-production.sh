#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ai-baseball2026}"
DATA_DIR="${DATA_DIR:-/opt/hawks-ai/data}"
SHARED_DATA_DIR="${SHARED_DATA_DIR:-}"
BRANCH="${BRANCH:-main-AI-BASEBALL}"
CONTAINER_NAME="${CONTAINER_NAME:-ai-baseball-app}"
IMAGE_NAME="${IMAGE_NAME:-ai-baseball-app}"
PORT="${PORT:-8502}"
DEPLOY_SHA="${DEPLOY_SHA:-}"
SKIP_GIT_FETCH="${SKIP_GIT_FETCH:-0}"
TRAEFIK_NETWORK="${TRAEFIK_NETWORK:-miki-stack_miki-net}"
TRAEFIK_HOST="${TRAEFIK_HOST:-ai-baseball-studio.f-polaris.jp}"
TRAEFIK_LEGACY_HOST="${TRAEFIK_LEGACY_HOST:-ai-baseball.f-polaris.jp}"
TRAEFIK_CONTAINER="${TRAEFIK_CONTAINER:-miki-traefik}"
AUTH_SECRETS_FILE="${AUTH_SECRETS_FILE:-/opt/hawks-ai/auth0/secrets.toml}"
HANDENOMORI_CREDENTIALS_FILE="${HANDENOMORI_CREDENTIALS_FILE:-/opt/hawks-ai/handenomori/credentials.json}"

cd "$APP_DIR"
mkdir -p "$DATA_DIR"

if [ "$SKIP_GIT_FETCH" = "1" ]; then
  echo "[deploy] using preloaded $BRANCH revision"
else
  echo "[deploy] fetching $BRANCH"
  git fetch origin "$BRANCH"
fi
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

# Publish the versioned historical audit artifacts into the mounted production
# data directory without replacing any live schedule, prediction, BET, or
# result files maintained by the running service.
mkdir -p "$DATA_DIR"
for artifact in \
  historical_backtest_report.json \
  historical_backtest_predictions.csv; do
  install -m 0644 "$APP_DIR/data/$artifact" "$DATA_DIR/$artifact"
done

# Refresh the live schedule and predictions before validating the new release.
# The server timer normally runs this every two minutes; deployment also runs it
# so the first page load after a release cannot use a stale daily slate.
if [ -x /usr/local/bin/hawks-data-sync ]; then
  echo "[deploy] refreshing live baseball data"
  if ! /usr/local/bin/hawks-data-sync; then
    echo "[deploy] live refresh failed; validating the most recent timer-produced data"
  fi
fi

if [ -n "$DEPLOY_SHA" ]; then
  ACTUAL_SHA="$(git rev-parse HEAD)"
  if [ "$ACTUAL_SHA" != "$DEPLOY_SHA" ]; then
    echo "[deploy] expected $DEPLOY_SHA but checked out $ACTUAL_SHA"
    exit 1
  fi
fi

if ! docker network inspect "$TRAEFIK_NETWORK" >/dev/null 2>&1; then
  echo "[deploy] required Traefik network not found: $TRAEFIK_NETWORK"
  exit 1
fi

TRAEFIK_IP="$(docker inspect "$TRAEFIK_CONTAINER" --format "{{with index .NetworkSettings.Networks \"$TRAEFIK_NETWORK\"}}{{.IPAddress}}{{end}}" 2>/dev/null || true)"
if [ -z "$TRAEFIK_IP" ]; then
  echo "[deploy] Traefik container is not attached to $TRAEFIK_NETWORK: $TRAEFIK_CONTAINER"
  exit 1
fi

echo "[deploy] primary route: $TRAEFIK_HOST"
echo "[deploy] legacy route: $TRAEFIK_LEGACY_HOST"

SHORT_SHA="$(git rev-parse --short=12 HEAD)"
NEW_IMAGE="$IMAGE_NAME:$SHORT_SHA"
PREVIOUS_IMAGE="$(docker inspect -f '{{.Config.Image}}' "$CONTAINER_NAME" 2>/dev/null || true)"

echo "[deploy] building $NEW_IMAGE"
docker build -t "$NEW_IMAGE" .

# Validate configuration before stopping the currently running service.
if [ ! -f "$AUTH_SECRETS_FILE" ]; then
  echo "[deploy] Auth0 configuration required; existing container retained"
  exit 1
fi
docker run --rm --network none \
  --security-opt no-new-privileges:true \
  --cap-drop ALL --cap-add DAC_OVERRIDE \
  -v "$AUTH_SECRETS_FILE:/run/auth0-secrets.toml:ro" \
  "$NEW_IMAGE" python scripts/validate_auth_config.py /run/auth0-secrets.toml

if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  docker rm -f "$CONTAINER_NAME"
fi

start_container() {
  local image="$1"
  local shared_mount=()
  local auth_mount=()
  local auth_env=()
  local handicap_mount=()
  if [ -f "$HANDENOMORI_CREDENTIALS_FILE" ]; then
    handicap_mount=(-v "$HANDENOMORI_CREDENTIALS_FILE:/run/handenomori/credentials.json:ro")
  fi
  if [ -n "$SHARED_DATA_DIR" ] && [ -d "$SHARED_DATA_DIR" ]; then
    shared_mount=(-v "$SHARED_DATA_DIR:/app/shared-data:ro")
  fi
  if [ -f "$AUTH_SECRETS_FILE" ]; then
    auth_mount=(-v "$AUTH_SECRETS_FILE:/app/.streamlit/secrets.toml:ro")
    auth_env=(-e "AI_BASEBALL_AUTH_ENABLED=1")
    echo "[deploy] Auth0 configuration mounted"
  else
    echo "[deploy] Auth0 configuration required"
    return 1
  fi
  docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    --network "$TRAEFIK_NETWORK" \
    --dns 1.1.1.1 \
    --dns 8.8.8.8 \
    -p "127.0.0.1:$PORT:8501" \
    --security-opt no-new-privileges:true \
    --cap-drop ALL \
    --cap-add DAC_OVERRIDE \
    -v "$DATA_DIR:/app/data" \
    -e "AI_BASEBALL_SHARED_DATA_DIR=/app/shared-data" \
    "${shared_mount[@]}" \
    "${auth_mount[@]}" \
    "${auth_env[@]}" \
    "${handicap_mount[@]}" \
    --label "traefik.enable=true" \
    --label "traefik.docker.network=$TRAEFIK_NETWORK" \
    --label "traefik.http.routers.ai-baseball-production.rule=Host(\`$TRAEFIK_HOST\`) || Host(\`$TRAEFIK_LEGACY_HOST\`)" \
    --label "traefik.http.routers.ai-baseball-production.entrypoints=websecure" \
    --label "traefik.http.routers.ai-baseball-production.priority=10000" \
    --label "traefik.http.routers.ai-baseball-production.tls=true" \
    --label "traefik.http.routers.ai-baseball-production.tls.certresolver=letsencrypt" \
    --label "traefik.http.routers.ai-baseball-production.service=ai-baseball-production" \
    --label "traefik.http.routers.ai-baseball-production.middlewares=ai-baseball-deploy-marker,ai-baseball-security" \
    --label "traefik.http.middlewares.ai-baseball-security.headers.contenttypenosniff=true" \
    --label "traefik.http.middlewares.ai-baseball-security.headers.framedeny=true" \
    --label "traefik.http.middlewares.ai-baseball-security.headers.referrerpolicy=no-referrer" \
    --label "traefik.http.middlewares.ai-baseball-security.headers.stsseconds=31536000" \
    --label "traefik.http.middlewares.ai-baseball-security.headers.customresponseheaders.Cache-Control=no-store, no-cache, must-revalidate" \
    --label "traefik.http.middlewares.ai-baseball-security.headers.customresponseheaders.Pragma=no-cache" \
    --label "traefik.http.middlewares.ai-baseball-security.headers.customresponseheaders.Expires=0" \
    --label "traefik.http.middlewares.ai-baseball-deploy-marker.headers.customresponseheaders.X-AI-Baseball-Deploy=$SHORT_SHA" \
    --label "traefik.http.services.ai-baseball-production.loadbalancer.server.port=8501" \
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

PAGE_PATHS=(
  "/"
  "/%E8%A9%A6%E5%90%88"
  "/%E6%9C%AC%E6%97%A5%E3%81%AEAI%E4%BA%88%E6%83%B3"
  "/%E4%BA%88%E6%83%B3%E7%B5%90%E6%9E%9C"
  "/BET%E5%85%A5%E5%8A%9B"
  "/%E5%8F%8E%E6%94%AF%E3%83%9E%E3%83%83%E3%83%97"
  "/AI%E8%A9%B3%E7%B4%B0"
  "/%E7%90%83%E5%9B%A3%E5%88%A5%E8%A9%B3%E7%B4%B0"
)

verify_internal_pages() {
  local host="$1"
  local path
  for path in "${PAGE_PATHS[@]}"; do
    if ! curl -k -fsS \
      --noproxy "*" \
      --max-time 15 \
      --resolve "$host:443:$TRAEFIK_IP" \
      "https://$host$path" >/dev/null; then
      echo "[deploy] page route failed: https://$host$path"
      return 1
    fi
    echo "[deploy] page route healthy: https://$host$path"
  done
}

wait_for_traefik_route() {
  local host="$1"
  local attempt
  for attempt in $(seq 1 15); do
    if curl -k -fsSI \
      --noproxy "*" \
      --max-time 15 \
      --resolve "$host:443:$TRAEFIK_IP" \
      "https://$host/_stcore/health" | grep -Fqi "x-ai-baseball-deploy: $SHORT_SHA"; then
      return 0
    fi
    sleep 2
  done
  return 1
}

for attempt in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$PORT/_stcore/health" >/dev/null; then
    echo "[deploy] app healthy: $NEW_IMAGE"
    if ! docker exec "$CONTAINER_NAME" python /app/scripts/validate_runtime_data.py \
      --data-dir /app/data \
      --shared-data-dir /app/shared-data; then
      echo "[deploy] production data validation failed"
      rollback
    fi
    if wait_for_traefik_route "$TRAEFIK_HOST"; then
      echo "[deploy] primary Traefik route healthy: https://$TRAEFIK_HOST/ -> $CONTAINER_NAME:8501"
      verify_internal_pages "$TRAEFIK_HOST" || echo "[deploy] internal page sweep deferred to protected public verification"
    else
      echo "[deploy] primary internal Traefik probe unavailable; deferring to protected public verification"
    fi
    if wait_for_traefik_route "$TRAEFIK_LEGACY_HOST"; then
      echo "[deploy] legacy Traefik route healthy: https://$TRAEFIK_LEGACY_HOST/ -> $CONTAINER_NAME:8501"
      verify_internal_pages "$TRAEFIK_LEGACY_HOST" || echo "[deploy] legacy page sweep deferred to protected public verification"
    else
      echo "[deploy] legacy internal Traefik probe unavailable; deferring to protected public verification"
    fi
    docker tag "$NEW_IMAGE" "$IMAGE_NAME:latest"
    exit 0
  fi
  sleep 2
done

rollback
