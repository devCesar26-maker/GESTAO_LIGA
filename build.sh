#!/usr/bin/env bash
# Single build for Render / Railway / any PaaS (run from the repository root).
#
# One service serves both the API and the React build, which is what makes the
# session cookie first-party (no CORS, no token in localStorage).
set -o errexit
set -o pipefail

pip install -r backend/requirements.txt

# Frontend build (output goes to frontend/dist, served by Django/WhiteNoise).
if [ -f frontend/package-lock.json ]; then
  npm --prefix frontend ci
else
  npm --prefix frontend install
fi
npm --prefix frontend run build

python backend/manage.py collectstatic --noinput

# Use the direct Neon endpoint for migrations when available: PgBouncer
# transaction pooling is not the recommended place for schema changes.
if [ -n "${DIRECT_DATABASE_URL:-}" ]; then
  DATABASE_URL="$DIRECT_DATABASE_URL" python backend/manage.py migrate --noinput
else
  python backend/manage.py migrate --noinput
fi
