#!/usr/bin/env python3
"""
Import / upsert the Excel shareholder capital register into the app.

Usage (from project root, venv active):

  python scripts/import_shareholder_capital.py data/shareholder_capital.csv
  python scripts/import_shareholder_capital.py data/shareholder_capital.csv --dry-run

CSV columns (header required):
  name, email, shares, capital, ownership_percent, is_owner, phone, country, country_code

Notes:
  - ownership_percent should total 100.0000 across active rows
  - capital / shares are for the capital register & dashboard (reporting)
  - Mudarabah monthly distribution still uses Net Profit × ownership %, not capital totals
  - Company-owned Murabaha assets are set separately in Settings → Shareholder capital register
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _dec(raw, default='0'):
    try:
        return Decimal(str(raw or default).replace(',', '').strip())
    except (InvalidOperation, ValueError):
        return Decimal(default)


def main():
    parser = argparse.ArgumentParser(description='Import shareholder capital CSV')
    parser.add_argument('csv_path', type=Path, help='Path to shareholder_capital.csv')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument(
        '--effective-from',
        default='2026-01-01',
        help='Ownership effective_from date (YYYY-MM-DD)',
    )
    args = parser.parse_args()

    if not args.csv_path.is_file():
        print(f'CSV not found: {args.csv_path}', file=sys.stderr)
        return 1

    from run import app
    from apps import db
    from apps.models.shareholder import OwnershipRecord, Shareholder
    from apps.services.share_value_service import ensure_default_share_settings, save_share_settings

    rows = []
    with args.csv_path.open(newline='', encoding='utf-8-sig') as fh:
        reader = csv.DictReader(fh)
        required = {'name', 'email', 'shares', 'capital', 'ownership_percent'}
        if not reader.fieldnames or not required.issubset({h.strip() for h in reader.fieldnames}):
            print(f'CSV must include columns: {sorted(required)}', file=sys.stderr)
            return 1
        for raw in reader:
            if not (raw.get('name') or '').strip():
                continue
            rows.append({
                'name': raw['name'].strip(),
                'email': (raw.get('email') or '').strip().lower(),
                'shares': _dec(raw.get('shares')),
                'capital': _dec(raw.get('capital')),
                'ownership_percent': _dec(raw.get('ownership_percent')),
                'is_owner': str(raw.get('is_owner') or '').strip().lower() in ('1', 'true', 'yes', 'y'),
                'phone': (raw.get('phone') or '').strip() or None,
                'country': (raw.get('country') or '').strip() or None,
                'country_code': (raw.get('country_code') or '').strip().lower() or None,
            })

    if not rows:
        print('No data rows in CSV.', file=sys.stderr)
        return 1

    total_shares = sum((r['shares'] for r in rows), Decimal('0'))
    total_capital = sum((r['capital'] for r in rows), Decimal('0'))
    total_ownership = sum((r['ownership_percent'] for r in rows), Decimal('0'))

    print(f'Rows: {len(rows)}')
    print(f'Total shares: {total_shares}')
    print(f'Total capital: {total_capital}')
    print(f'Total ownership %: {total_ownership}')

    if abs(total_ownership - Decimal('100')) > Decimal('0.05'):
        print(
            f'WARNING: ownership % totals {total_ownership} (expected ~100). '
            'Fix the CSV before approving periods.',
            file=sys.stderr,
        )

    if args.dry_run:
        print('Dry run — no database changes.')
        return 0

    effective = date.fromisoformat(args.effective_from)

    with app.app_context():
        ensure_default_share_settings()
        save_share_settings(
            share_value=1000,
            total_company_shares=total_shares if total_shares > 0 else 1220,
            company_owned_assets=423000,
        )

        created = updated = 0
        for row in rows:
            if not row['email'] or '@' not in row['email']:
                print(f"Skip (missing email): {row['name']}", file=sys.stderr)
                continue
            sh = Shareholder.query.filter_by(email=row['email']).first()
            if not sh:
                sh = Shareholder(email=row['email'])
                db.session.add(sh)
                created += 1
            else:
                updated += 1
            sh.name = row['name']
            sh.share_count = row['shares']
            sh.investment_amount = row['capital']
            sh.is_owner = row['is_owner']
            sh.is_active = True
            sh.phone = row['phone']
            sh.country = row['country']
            sh.country_code = row['country_code']
            db.session.flush()

            # Close open ownership and write new record
            open_recs = (
                OwnershipRecord.query.filter_by(shareholder_id=sh.id, effective_to=None).all()
            )
            for rec in open_recs:
                if rec.effective_from >= effective:
                    db.session.delete(rec)
                else:
                    from datetime import timedelta

                    rec.effective_to = effective - timedelta(days=1)

            db.session.add(
                OwnershipRecord(
                    shareholder_id=sh.id,
                    ownership_percent=row['ownership_percent'],
                    effective_from=effective,
                )
            )

        db.session.commit()
        print(f'Done. Created {created}, updated {updated}.')
        print('Company-owned assets set to $423,000.00 (Settings).')
        print('Complete the CSV with all 20 shareholders from Excel, then re-run.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
