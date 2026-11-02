#!/usr/bin/env bash
# Start the web process on Render / Railway / Docker / bare metal.
# Migrations are handled by build.sh (PaaS) or docker-entrypoint.sh (Docker).
set -o errexit
set -o pipefail

# Declarative admin promotion (ADMIN_EMAILS). No-op when the variable is empty.
python backend/manage.py sync_admins

exec gunicorn --chdir backend config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-120}"
