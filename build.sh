#!/usr/bin/env bash
# Build / deploy prep for Render and similar hosts.
set -o errexit
set -o pipefail

python -m pip install --upgrade pip
pip install -r requirements.txt

# Apply Alembic migrations when DATABASE_URL / DB_* are available at build time.
# If the DB is not reachable during build, the app will migrate on first boot.
if [[ -n "${DATABASE_URL:-}" || -n "${DB_HOST:-}" ]]; then
  echo "> Running flask db upgrade"
  flask --app run.py db upgrade || {
    echo "> WARNING: flask db upgrade failed during build; will retry on startup."
    true
  }
fi
