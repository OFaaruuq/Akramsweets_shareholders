"""One-time local PostgreSQL setup for AKRAM SWEET Shareholders Project.

Preferred (peer auth, no Docker):
  sudo -u postgres python scripts/setup_database.py

Or with a password:
  POSTGRES_ADMIN_PASSWORD=... python scripts/setup_database.py

Or apply SQL:
  sudo -u postgres psql -f scripts/init_postgres.sql
"""

from __future__ import annotations

import getpass
import os
import sys

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT_DIR)

load_dotenv(os.path.join(ROOT_DIR, '.env'))

DB_NAME = os.getenv('DB_NAME', 'akram_shareholders')
DB_USER = os.getenv('DB_USERNAME', 'akram_user')
DB_PASS = os.getenv('DB_PASS', 'akram_pass')
DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = os.getenv('DB_PORT', '5432')
ADMIN_USER = os.getenv('POSTGRES_ADMIN_USER', 'postgres')


def get_admin_password() -> str | None:
    """Return admin password, or None to try peer/trust (unix socket, no password)."""
    if os.getenv('POSTGRES_ADMIN_PASSWORD'):
        return os.getenv('POSTGRES_ADMIN_PASSWORD')
    # Running as the postgres OS user → peer auth on local socket
    if os.name == 'posix' and (os.geteuid() == 0 or getpass.getuser() == 'postgres'):
        return None
    # Interactive fallback for TCP auth
    return getpass.getpass(
        f'Enter PostgreSQL admin password for user "{ADMIN_USER}" '
        f'(leave empty to try local peer/socket auth): '
    ) or None


def connect_admin(password: str | None, dbname: str = 'postgres'):
    kwargs = {
        'dbname': dbname,
        'user': ADMIN_USER,
    }
    if password is None:
        # Peer/trust via unix socket (sudo -u postgres ...)
        kwargs['host'] = '/var/run/postgresql'
    else:
        kwargs['host'] = DB_HOST
        kwargs['port'] = DB_PORT
        kwargs['password'] = password
    return psycopg2.connect(**kwargs)


def user_exists(cursor, username: str) -> bool:
    cursor.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', (username,))
    return cursor.fetchone() is not None


def database_exists(cursor, dbname: str) -> bool:
    cursor.execute('SELECT 1 FROM pg_database WHERE datname = %s', (dbname,))
    return cursor.fetchone() is not None


def grant_schema_privileges(cursor, dbname: str, username: str) -> None:
    cursor.execute(f'GRANT ALL PRIVILEGES ON DATABASE {dbname} TO {username}')
    cursor.execute(f'GRANT ALL ON SCHEMA public TO {username}')
    cursor.execute(f'ALTER SCHEMA public OWNER TO {username}')
    cursor.execute(
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {username}'
    )
    cursor.execute(
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {username}'
    )


def main() -> int:
    print('Setting up local PostgreSQL for AKRAM SWEET Shareholders Project...')
    print(f'  App target: {DB_HOST}:{DB_PORT}/{DB_NAME} as {DB_USER}')
    print(f'  Admin user: {ADMIN_USER}')

    try:
        admin_password = get_admin_password()
        conn = connect_admin(admin_password)
    except psycopg2.Error as exc:
        print(f'\nCould not connect as admin user "{ADMIN_USER}".')
        print(f'Error: {exc}')
        print('\nTips:')
        print('  1. Ensure PostgreSQL is running: pg_isready -h 127.0.0.1 -p 5432')
        print('  2. Run with peer auth: sudo -u postgres python scripts/setup_database.py')
        print('  3. Or: sudo -u postgres psql -f scripts/init_postgres.sql')
        print('  4. Or set POSTGRES_ADMIN_PASSWORD in .env')
        return 1
    except Exception as exc:
        print(f'\nCould not connect as admin user "{ADMIN_USER}".')
        print(f'Error: {exc}')
        print('Try: sudo -u postgres python scripts/setup_database.py')
        return 1

    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    if not user_exists(cursor, DB_USER):
        cursor.execute(
            f"CREATE USER {DB_USER} WITH PASSWORD %s",
            (DB_PASS,),
        )
        print(f'Created user: {DB_USER}')
    else:
        cursor.execute(
            f"ALTER USER {DB_USER} WITH PASSWORD %s",
            (DB_PASS,),
        )
        print(f'Updated password for user: {DB_USER}')

    if not database_exists(cursor, DB_NAME):
        cursor.execute(f'CREATE DATABASE {DB_NAME} OWNER {DB_USER}')
        print(f'Created database: {DB_NAME}')
    else:
        print(f'Database already exists: {DB_NAME}')
        cursor.execute(f'ALTER DATABASE {DB_NAME} OWNER TO {DB_USER}')

    cursor.close()
    conn.close()

    try:
        db_conn = connect_admin(admin_password, dbname=DB_NAME)
    except psycopg2.Error as exc:
        print(f'\nCould not open {DB_NAME} as admin to grant schema rights: {exc}')
        return 1

    db_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    db_cursor = db_conn.cursor()
    grant_schema_privileges(db_cursor, DB_NAME, DB_USER)
    db_cursor.close()
    db_conn.close()
    print(f'Granted public schema privileges to {DB_USER} on {DB_NAME}')

    try:
        app_conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
        )
        app_conn.close()
    except psycopg2.Error as exc:
        print(f'\nDatabase created, but app user login failed: {exc}')
        print('Check pg_hba.conf allows md5/scram for 127.0.0.1 connections.')
        return 1

    print('\nPostgreSQL setup complete (local, no Docker).')
    print('You can now run: flask --app run.py run --debug')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
