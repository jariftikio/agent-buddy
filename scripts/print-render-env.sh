#!/usr/bin/env bash
# Prints the environment variables to set in the Render dashboard, read from .env.
# Run it yourself: the values are secrets and belong in your terminal, not in a file.
#
#   ./scripts/print-render-env.sh
set -euo pipefail

cd "$(dirname "$0")/.."
[ -f .env ] || { echo "no .env here -- copy .env.example and fill it in" >&2; exit 1; }

# Keys Render needs. DATABASE_URL is deliberately absent: this deployment runs on
# SQLite, and a stale value is worse than none. PORT and RENDER_EXTERNAL_URL are
# injected by Render and must not be set by hand.
KEYS=(
  TELEGRAM_BOT_TOKEN
  TELEGRAM_WEBHOOK_SECRET
  OPENROUTER_API_KEY
  HEALTH_TOKEN
  OPENROUTER_MODELS
  OPENROUTER_VISION_MODELS
  OPENROUTER_TIMEOUT
  OPENROUTER_BUDGET
  WEBHOOK_WORKERS
  WEBHOOK_MAX_PENDING
)

echo "Start Command:"
echo "  $(sed -n 's/^web: //p' Procfile)"
echo
echo "Environment variables to set:"
for key in "${KEYS[@]}"; do
  value="$(sed -n "s/^${key}=//p" .env | head -1)"
  if [ -n "$value" ]; then
    printf '  %-26s %s\n' "$key" "$value"
  else
    printf '  %-26s (NOT SET in .env)\n' "$key"
  fi
done
printf '  %-26s %s\n' PYTHON_VERSION 3.11.8

echo
echo "Delete these if present: DATABASE_URL, Database_URL, OPENROUTER_MODEL, PORT"
