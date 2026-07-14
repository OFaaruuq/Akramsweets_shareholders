#!/usr/bin/env python3
"""Create or update a super admin (owner) user.

Examples:
  python scripts/create_super_admin.py
  python scripts/create_super_admin.py --email admin@example.com --name "Super Admin"
  python scripts/create_super_admin.py --email admin@example.com --password 'StrongPass123!' --force

Role defaults to owner (full privileges). Use --role admin for system admin.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT_DIR, '.env'))
load_dotenv(os.path.join(os.path.dirname(ROOT_DIR), '.env'))

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Create or update a super admin user for Akram Sweets Shareholders.',
    )
    parser.add_argument('--email', help='Login email (unique)')
    parser.add_argument('--name', '--full-name', dest='full_name', help='Display full name')
    parser.add_argument('--password', help='Login password (prompted if omitted)')
    parser.add_argument(
        '--role',
        choices=('owner', 'admin'),
        default='owner',
        help='owner = super admin (default), admin = system admin',
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='If the email already exists, upgrade role / reset password / activate',
    )
    parser.add_argument(
        '--inactive',
        action='store_true',
        help='Create the account as inactive (default is active)',
    )
    return parser.parse_args()


def prompt_email(default: str | None = None) -> str:
    while True:
        hint = f' [{default}]' if default else ''
        value = input(f'Email{hint}: ').strip() or (default or '')
        value = value.lower()
        if EMAIL_RE.match(value):
            return value
        print('Enter a valid email address.')


def prompt_name(default: str = 'Super Administrator') -> str:
    value = input(f'Full name [{default}]: ').strip()
    return value or default


def prompt_password() -> str:
    while True:
        password = getpass.getpass('Password (min 6 chars): ')
        if len(password) < 6:
            print('Password must be at least 6 characters.')
            continue
        confirm = getpass.getpass('Confirm password: ')
        if password != confirm:
            print('Passwords do not match.')
            continue
        return password


def main() -> int:
    args = parse_args()

    # Import after dotenv so DB settings apply
    from apps.config import config_dict
    from apps import create_app, db
    from apps.models.user import User
    from apps.services.audit_service import log_action

    email = (args.email or '').strip().lower() or prompt_email('OmarFaaruuq32@gmail.com')
    full_name = (args.full_name or '').strip() or prompt_name()
    password = args.password or prompt_password()

    if len(password) < 6:
        print('Error: password must be at least 6 characters.')
        return 1
    if not EMAIL_RE.match(email):
        print('Error: invalid email address.')
        return 1

    role = User.ROLE_OWNER if args.role == 'owner' else User.ROLE_ADMIN
    debug = (os.getenv('DEBUG', 'False') == 'True')
    app = create_app(config_dict['Debug' if debug else 'Production'])

    with app.app_context():
        existing = User.query.filter_by(email=email).first()
        if existing and not args.force:
            print(f'User already exists: {email} (role={existing.role}, active={existing.is_active})')
            print('Re-run with --force to upgrade/reset this account.')
            return 1

        if existing:
            existing.full_name = full_name
            existing.role = role
            existing.is_active = not args.inactive
            existing.shareholder_id = None
            existing.set_password(password)
            db.session.commit()
            log_action(
                'update',
                'staff_user',
                existing.id,
                f'Super admin updated via script: {email} ({role})',
                user=existing,
            )
            action = 'updated'
            user = existing
        else:
            user = User(
                email=email,
                full_name=full_name,
                role=role,
                is_active=not args.inactive,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            log_action(
                'create',
                'staff_user',
                user.id,
                f'Super admin created via script: {email} ({role})',
                user=user,
            )
            action = 'created'

        # Snapshot before leaving the app/session context
        summary = {
            'id': user.id,
            'email': user.email,
            'full_name': user.full_name,
            'role': user.role,
            'is_active': user.is_active,
        }

    print()
    print(f'Super admin {action} successfully.')
    print(f'  ID:     {summary["id"]}')
    print(f'  Email:  {summary["email"]}')
    print(f'  Name:   {summary["full_name"]}')
    print(f'  Role:   {summary["role"]}')
    print(f'  Active: {summary["is_active"]}')
    print()
    print('Sign in at /auth/login — you will receive an email OTP if LOGIN_OTP_ENABLED=true.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
