#!/usr/bin/env bash
set -e

echo "Waiting for PostgreSQL..."
until python -c "
import os, sys
import psycopg2
try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'postgres'),
        port=os.getenv('DB_PORT', '5432'),
        dbname=os.getenv('DB_NAME', 'akram_shareholders'),
        user=os.getenv('DB_USERNAME', 'akram_user'),
        password=os.getenv('DB_PASS', 'akram_pass'),
    )
    conn.close()
except Exception:
    sys.exit(1)
"; do
  sleep 2
done

echo "Running database migrations..."
flask db upgrade || true

exec gunicorn --config gunicorn-cfg.py run:app
