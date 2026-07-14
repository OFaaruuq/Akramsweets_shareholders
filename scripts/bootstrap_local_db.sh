#!/usr/bin/env bash
# Bootstrap local PostgreSQL for AKRAM SWEET Shareholders (no Docker).
# Requires postgres superuser via peer auth:
#   ./scripts/bootstrap_local_db.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SQL_FILE="$ROOT_DIR/scripts/init_postgres.sql"

echo "Creating role/database with: sudo -u postgres psql -f $SQL_FILE"
sudo -u postgres psql -v ON_ERROR_STOP=1 -f "$SQL_FILE"

echo
echo "Verifying app login..."
cd "$ROOT_DIR"
# shellcheck disable=SC1091
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PGPASSWORD="${DB_PASS:-akram_pass}" psql \
  -h "${DB_HOST:-127.0.0.1}" \
  -p "${DB_PORT:-5432}" \
  -U "${DB_USERNAME:-akram_user}" \
  -d "${DB_NAME:-akram_shareholders}" \
  -c "SELECT current_user AS user, current_database() AS database;"

echo
echo "Done. Start the app with:"
echo "  cd $ROOT_DIR && source venv/bin/activate && flask --app run.py run --debug"
