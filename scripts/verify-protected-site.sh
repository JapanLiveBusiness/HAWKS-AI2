#!/usr/bin/env bash
set -euo pipefail

SITE_URL="${SITE_URL:-https://ai-baseball.f-polaris.jp/}"
CF_ACCESS_CLIENT_ID="${CF_ACCESS_CLIENT_ID:-}"
CF_ACCESS_CLIENT_SECRET="${CF_ACCESS_CLIENT_SECRET:-}"

if [ -z "$CF_ACCESS_CLIENT_ID" ] || [ -z "$CF_ACCESS_CLIENT_SECRET" ]; then
  echo "Cloudflare Access service token is not configured; verifying that anonymous access is blocked"
  headers="$(mktemp)"
  trap 'rm -f "$headers"' EXIT

  status="$(curl \
    --silent \
    --show-error \
    --output /dev/null \
    --dump-header "$headers" \
    --max-time 15 \
    --write-out '%{http_code}' \
    "$SITE_URL")"

  location="$(awk 'BEGIN{IGNORECASE=1} /^location:/ {sub(/^[^:]+:[[:space:]]*/, ""); gsub(/\r/, ""); print; exit}' "$headers")"
  echo "Anonymous HTTP status: $status"

  if [[ "$status" =~ ^30[12378]$ ]] && [[ "$location" == *"cloudflareaccess.com"* || "$location" == *"/cdn-cgi/access/"* ]]; then
    echo "Cloudflare Access is enforcing authentication with a login redirect"
    exit 0
  fi

  if [ "$status" = "401" ] || [ "$status" = "403" ]; then
    echo "Anonymous access is blocked (HTTP $status)"
    exit 0
  fi

  if [ "$status" = "200" ]; then
    echo "::error::Anonymous request reached the production site with HTTP 200; access protection is not enforcing authentication"
  else
    echo "::error::Anonymous access returned an unexpected status: $status"
  fi
  exit 1
fi

SITE_ROOT="${SITE_URL%/}"
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

verify_page() {
  local path="$1"
  local page_url="${SITE_ROOT}${path}"
  for attempt in $(seq 1 5); do
    if curl \
      --fail \
      --silent \
      --show-error \
      --location \
      --max-time 15 \
      --header "CF-Access-Client-Id: $CF_ACCESS_CLIENT_ID" \
      --header "CF-Access-Client-Secret: $CF_ACCESS_CLIENT_SECRET" \
      "$page_url" >/dev/null; then
      echo "Protected page OK: $path"
      return 0
    fi
    sleep 3
  done
  echo "::error::Protected production page failed: $path"
  return 1
}

for path in "${PAGE_PATHS[@]}"; do
  verify_page "$path"
done

echo "All protected production pages are responding through Cloudflare Access"
