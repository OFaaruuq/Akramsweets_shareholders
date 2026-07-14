-- Local PostgreSQL setup for AKRAM SWEET Shareholders (no Docker).
-- Run once as the postgres superuser, e.g.:
--   sudo -u postgres psql -f scripts/init_postgres.sql
-- Or:
--   sudo -u postgres python scripts/setup_database.py

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'akram_user') THEN
    CREATE ROLE akram_user LOGIN PASSWORD 'akram_pass';
  ELSE
    ALTER ROLE akram_user WITH LOGIN PASSWORD 'akram_pass';
  END IF;
END
$$;

SELECT 'CREATE DATABASE akram_shareholders OWNER akram_user ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'akram_shareholders')\gexec

GRANT ALL PRIVILEGES ON DATABASE akram_shareholders TO akram_user;

\connect akram_shareholders

GRANT ALL ON SCHEMA public TO akram_user;
ALTER SCHEMA public OWNER TO akram_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO akram_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO akram_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO akram_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO akram_user;
