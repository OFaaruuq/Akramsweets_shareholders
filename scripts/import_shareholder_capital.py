#!/usr/bin/env python3
"""
CLI import of the shareholder capital register (CSV or Excel).

Prefer the in-app upload: Shareholders → Upload Excel / CSV

Usage:
  python scripts/import_shareholder_capital.py data/shareholder_capital.csv
  python scripts/import_shareholder_capital.py register.xlsx --dry-run
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description='Import shareholder capital CSV/XLSX')
    parser.add_argument('path', type=Path, help='Path to .csv or .xlsx')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--effective-from', default=None, help='YYYY-MM-DD')
    parser.add_argument(
        '--company-owned-assets',
        type=str,
        default=None,
        help='Murabaha / company-owned assets amount (e.g. 423000)',
    )
    args = parser.parse_args()

    if not args.path.is_file():
        print(f'File not found: {args.path}', file=sys.stderr)
        return 1

    from run import app
    from apps.services.capital_import_service import import_from_upload, preview_import

    class _Upload:
        def __init__(self, path: Path):
            self.filename = path.name
            self._data = path.read_bytes()

        def read(self):
            return self._data

    upload = _Upload(args.path)
    effective = date.fromisoformat(args.effective_from) if args.effective_from else None
    assets = Decimal(args.company_owned_assets) if args.company_owned_assets else None

    with app.app_context():
        if args.dry_run:
            preview = preview_import(upload)
            print(f"Rows: {preview['meta']['row_count']}")
            print(f"Shares: {preview['meta']['total_shares']}")
            print(f"Capital: {preview['meta']['total_capital']}")
            print(f"Ownership %: {preview['meta']['total_ownership']}")
            for w in preview['warnings']:
                print(f'WARNING: {w}')
            print('Dry run — no database changes.')
            return 0

        # re-read after preview consumed bytes
        upload = _Upload(args.path)
        result = import_from_upload(
            upload,
            effective_from=effective,
            company_owned_assets=assets,
            actor=SimpleNamespace(id=None, full_name='cli'),
        )
        print(
            f"Register replaced: {result['total_rows']} "
            f"({result['created']} new, {result['updated']} updated, "
            f"{result.get('deactivated', 0)} deactivated)"
        )
        print(f"Capital: {result['total_capital']} · Shares: {result['total_shares']}")
        for w in result.get('warnings') or []:
            print(f'WARNING: {w}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
