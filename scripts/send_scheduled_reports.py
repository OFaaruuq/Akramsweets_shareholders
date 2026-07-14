"""Send approved shareholder reports when the configured delivery day is reached."""

from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

from apps import create_app  # noqa: E402
from apps.config import config_dict  # noqa: E402
from apps.services.report_schedule_service import send_due_approved_reports  # noqa: E402


def main():
    app = create_app(config_dict[os.getenv('FLASK_ENV', 'Debug')])
    with app.app_context():
        sent = send_due_approved_reports()
        if sent:
            labels = ', '.join(period.period_label for period in sent)
            print(f'Sent reports for: {labels}')
        else:
            print('No due reports to send.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
