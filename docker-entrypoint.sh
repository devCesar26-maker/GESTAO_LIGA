#!/usr/bin/env sh
# Run migrations against the external database, then start Gunicorn.
# Set DIRECT_DATABASE_URL (Neon direct endpoint) to keep schema changes off the
# PgBouncer pooled connection. DATABASE_URL is still used by the application.
set -eu

if [ -n "${DIRECT_DATABASE_URL:-}" ]; then
  DATABASE_URL="$DIRECT_DATABASE_URL" python backend/manage.py migrate --noinput
else
  python backend/manage.py migrate --noinput
fi

exec ./start.sh
