"""One-time local PostgreSQL setup for AKRAM SWEET Shareholders Project."""

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


def connect_admin():
    admin_password = os.getenv('POSTGRES_ADMIN_PASSWORD')
    if not admin_password:
        admin_password = getpass.getpass(
            f'Enter PostgreSQL admin password for user "{ADMIN_USER}": '
        )

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname='postgres',
        user=ADMIN_USER,
        password=admin_password,
    )


def user_exists(cursor, username: str) -> bool:
    cursor.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', (username,))
    return cursor.fetchone() is not None


def database_exists(cursor, dbname: str) -> bool:
    cursor.execute('SELECT 1 FROM pg_database WHERE datname = %s', (dbname,))
    return cursor.fetchone() is not None


def main() -> int:
    print('Setting up PostgreSQL for AKRAM SWEET Shareholders Project...')
    print(f'  Host: {DB_HOST}:{DB_PORT}')
    print(f'  Database: {DB_NAME}')
    print(f'  App user: {DB_USER}')

    try:
        conn = connect_admin()
    except psycopg2.Error as exc:
        print(f'\nCould not connect as admin user "{ADMIN_USER}".')
        print(f'Error: {exc}')
        print('\nTips:')
        print('  1. Confirm PostgreSQL is running on this machine.')
        print('  2. Set POSTGRES_ADMIN_USER / POSTGRES_ADMIN_PASSWORD in .env if needed.')
        print('  3. Or run scripts/init_postgres.sql manually in pgAdmin.')
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

    cursor.close()
    conn.close()

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
        return 1

    print('\nPostgreSQL setup complete.')
    print('You can now run: flask run')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
