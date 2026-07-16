#!/usr/bin/env python3
"""
Wipe ALL shareholder-related data (register, periods, certificates, portal users).

Usage (from project root, venv active):

  python scripts/purge_shareholders.py --yes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description='Purge all shareholder data')
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Required. Confirm irreversible delete of all shareholder data.',
    )
    args = parser.parse_args()
    if not args.yes:
        print('Refusing to run without --yes', file=sys.stderr)
        return 1

    from run import app
    from apps.services.register_reset_service import purge_all_shareholders_and_assets, register_counts

    with app.app_context():
        before = register_counts()
        print('Before:', {k: v for k, v in before.items() if k != 'confirm_phrase'})
        result = purge_all_shareholders_and_assets(actor=None, wipe_periods=True)
        print('Deleted:', result['deleted'])
        print('Done. Upload a clean Excel via Shareholders → Replace from Excel / CSV.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
