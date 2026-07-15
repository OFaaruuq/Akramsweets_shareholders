"""Run integration checks against a temporary SQLite database."""

from __future__ import annotations

import os
import re
import sys
import tempfile
from decimal import Decimal

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

TEST_DB = os.path.join(tempfile.gettempdir(), 'akram_shareholders_verify.sqlite3')
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

# Isolated SQLite for verification — do not touch the Postgres .env settings
os.environ['DB_ENGINE'] = 'sqlite'
os.environ['SQLITE_PATH'] = TEST_DB
os.environ.pop('DATABASE_URL', None)
os.environ['DEBUG'] = 'True'
# Automated checks skip email OTP (production login still requires it)
os.environ['LOGIN_OTP_ENABLED'] = 'false'
os.environ['OTP_TEST_CAPTURE'] = 'false'

from apps.config import config_dict  # noqa: E402
from apps import create_app, db  # noqa: E402
from apps.models import MonthlyPeriod, Shareholder, User  # noqa: E402
from apps.services.calculation_service import (  # noqa: E402
    approve_period,
    calculate_period,
    submit_for_review,
)


def login_client(client, app, email, password):
    csrf = re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"',
        client.get('/auth/login').get_data(as_text=True),
    )
    if not csrf:
        raise RuntimeError('CSRF token missing on login page')
    return client.post('/auth/login', data={
        'email': email,
        'password': password,
        'csrf_token': csrf.group(1),
    }, follow_redirects=False)


def main():
    app = create_app(config_dict['Debug'])
    client = app.test_client()
    errors = []

    with app.app_context():
        if User.query.count() < 5:
            errors.append(f'Expected at least 5 seed users, got {User.query.count()}')
        if Shareholder.query.count() != 3:
            errors.append(f'Expected 3 shareholders, got {Shareholder.query.count()}')

        portal_user = User.query.filter_by(email='shareholder.a@akramsweets.com').first()
        if not portal_user or not portal_user.is_shareholder():
            errors.append('Shareholder A portal user missing or not linked')

    r = client.get('/auth/login')
    if r.status_code != 200:
        errors.append(f'Login page status {r.status_code}')

    r = client.get('/', follow_redirects=False)
    if r.status_code not in (302, 303):
        errors.append('Dashboard should redirect when not logged in')

    r2 = login_client(client, app, 'admin@akramsweets.com', 'admin123')
    if r2.status_code not in (302, 303):
        errors.append(f'Admin login failed status {r2.status_code}')

    with client.session_transaction() as sess:
        with app.app_context():
            user = User.query.filter_by(email='admin@akramsweets.com').first()
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    for path in [
        '/',
        '/shareholders/',
        '/periods/',
        '/periods/create',
        '/settings/arrangements',
        '/settings/system',
        '/settings/images',
        '/auth/account',
        '/settings/audit-log',
        '/users/',
        '/reports/',
        '/analytics',
    ]:
        r = client.get(path)
        if r.status_code != 200:
            errors.append(f'{path} returned {r.status_code}')

    with app.app_context():
        from apps.services.period_service import resolve_period_totals

        net, pnl_fields = resolve_period_totals(
            income=Decimal('500000'),
            gross_profit=Decimal('200000'),
            total_gross_profit=Decimal('210000'),
            total_income=Decimal('520000'),
            total_operating_expenses=Decimal('150000'),
            net_profit=Decimal('100000'),
        )
        if net != Decimal('100000'):
            errors.append(f'P&L net should be entered Net Profit, got {net}')
        if pnl_fields['total_revenues'] != Decimal('500000'):
            errors.append('P&L should mirror Income into total_revenues')
        if pnl_fields['cost_of_goods'] != Decimal('300000'):
            errors.append('P&L cost_of_goods should be Income − Gross Profit')
        if pnl_fields['other_income'] != Decimal('20000'):
            errors.append('P&L other_income should be Total Income − Income')

        period = MonthlyPeriod(
            year=2026,
            month=6,
            total_profit_loss=net,
            income=pnl_fields['income'],
            gross_profit=pnl_fields['gross_profit'],
            total_gross_profit=pnl_fields['total_gross_profit'],
            total_income=pnl_fields['total_income'],
            total_revenues=pnl_fields['total_revenues'],
            cost_of_goods=pnl_fields['cost_of_goods'],
            total_expenses=pnl_fields['total_expenses'],
            other_income=pnl_fields['other_income'],
            entry_mode=pnl_fields['entry_mode'],
        )
        db.session.add(period)
        db.session.commit()
        calculate_period(period)
        results = {c.shareholder.name: float(c.final_amount) for c in period.calculations}
        expected = {
            'Pocly (Owner)': 44000.0,
            'Shareholder A': 32000.0,
            'Shareholder B': 24000.0,
        }
        for name, val in expected.items():
            if abs(results.get(name, 0) - val) > 0.01:
                errors.append(f'Calc mismatch {name}: got {results.get(name)} expected {val}')

        # Selective arrangement: 10% only from Shareholder A → Pocly
        from apps.models.arrangement import SpecialArrangement
        from datetime import date

        pocly = Shareholder.query.filter_by(email='pocly@akramsweets.com').first()
        sh_a = Shareholder.query.filter_by(email='shareholder.a@akramsweets.com').first()
        selective = SpecialArrangement(
            name='Selective test bonus',
            recipient_shareholder_id=pocly.id,
            bonus_percent=Decimal('10'),
            applies_to_all_others=False,
            apply_on_profit=True,
            apply_on_loss=False,
            effective_from=date(2026, 1, 1),
            is_active=True,
        )
        selective.source_shareholders = [sh_a]
        db.session.add(selective)
        db.session.commit()

        selective_period = MonthlyPeriod(year=2026, month=8, total_profit_loss=Decimal('100000'))
        db.session.add(selective_period)
        db.session.commit()
        calculate_period(selective_period)
        selective_results = {
            c.shareholder.name: float(c.final_amount) for c in selective_period.calculations
        }
        # Base: 30k/40k/30k + existing 20% all-others (Pocly +14k, A -8k, B -6k)
        # Plus selective 10% of A's base (4k) → Pocly +4k, A -4k
        # Finals: Pocly 48000, A 28000, B 24000
        selective_expected = {
            'Pocly (Owner)': 48000.0,
            'Shareholder A': 28000.0,
            'Shareholder B': 24000.0,
        }
        for name, val in selective_expected.items():
            if abs(selective_results.get(name, 0) - val) > 0.01:
                errors.append(
                    f'Selective calc mismatch {name}: got {selective_results.get(name)} expected {val}'
                )
        selective.is_active = False
        db.session.commit()

        loss_period = MonthlyPeriod(year=2026, month=7, total_profit_loss=Decimal('-100000'))
        db.session.add(loss_period)
        db.session.commit()
        calculate_period(loss_period)
        loss_results = {c.shareholder.name: float(c.final_amount) for c in loss_period.calculations}
        for name, val in expected.items():
            if abs(loss_results.get(name, 0) + val) > 0.01:
                errors.append(f'Loss calc mismatch {name}: got {loss_results.get(name)} expected {-val}')

        admin = User.query.filter_by(email='admin@akramsweets.com').first()
        submit_for_review(period)
        if period.status != MonthlyPeriod.STATUS_REVIEW:
            errors.append('Period not moved to review')
        approve_period(period, admin)
        if period.status != MonthlyPeriod.STATUS_APPROVED:
            errors.append('Period not approved')

        from apps.models.certificate import ShareholderCertificate
        from apps.services.certificate_service import build_certificate_payload
        from apps.services.pdf_service import generate_shareholder_certificate_pdf
        from apps.services.report_schedule_service import auto_send_period_reports

        auto_send_period_reports(period)
        cert_count = ShareholderCertificate.query.filter_by(period_id=period.id).count()
        if cert_count != 3:
            errors.append(f'Expected 3 shareholder certificates, got {cert_count}')

        calc_a = next(c for c in period.calculations if c.shareholder.name == 'Shareholder A')
        cert_a = ShareholderCertificate.query.filter_by(period_id=period.id, shareholder_id=calc_a.shareholder_id).first()
        if not cert_a:
            errors.append('Shareholder A certificate missing')
        else:
            cert_payload = build_certificate_payload(period, calc_a, cert_a)
            if cert_payload.get('shareholder_name') != 'Shareholder A':
                errors.append('Certificate does not display the current shareholder name')
            if not cert_payload.get('current_shareholders') or len(cert_payload['current_shareholders']) != 3:
                errors.append('Certificate missing current shareholders roster')
            if not cert_payload.get('shareholder_email'):
                errors.append('Certificate missing current shareholder email')
            cert_pdf = generate_shareholder_certificate_pdf(cert_payload)
            if not cert_pdf.startswith(b'%PDF'):
                errors.append('Certificate PDF generation failed')

        total = sum(float(c.final_amount) for c in period.calculations)
        if abs(total - 100000.0) > 0.01:
            errors.append(f'Total distribution {total} != 100000')

        from apps.services.calculation_service import reopen_for_correction
        from apps.services.pdf_service import generate_shareholder_report_pdf
        from apps.services.report_service import build_shareholder_report

        reopen_for_correction(period, 'Correction test: adjusted prior month entry')
        if period.status != MonthlyPeriod.STATUS_REVIEW:
            errors.append('Period not reopened for correction')
        approve_period(period, admin)

        calc_a = next(c for c in period.calculations if c.shareholder.name == 'Shareholder A')
        report = build_shareholder_report(period, calc_a)
        pdf = generate_shareholder_report_pdf(report)
        if not pdf.startswith(b'%PDF'):
            errors.append('PDF report generation failed')

        period_id = period.id

        from apps.services.topbar_service import TOPBAR_EXCLUDED_ACTIONS

        if 'login' not in TOPBAR_EXCLUDED_ACTIONS or 'logout' not in TOPBAR_EXCLUDED_ACTIONS:
            errors.append('Auth noise should be excluded from topbar notifications')

    # Topbar notifications render for staff after workflow
    dash = client.get('/')
    if dash.status_code != 200:
        errors.append('Dashboard after period workflow failed')
    elif 'Notifications' not in dash.get_data(as_text=True):
        errors.append('Topbar notifications dropdown missing')

    client.get('/auth/logout')

    portal_login = login_client(client, app, 'shareholder.a@akramsweets.com', 'shareholder123')
    if portal_login.status_code not in (302, 303):
        errors.append(f'Shareholder login failed status {portal_login.status_code}')
    elif '/portal/' in portal_login.headers.get('Location', ''):
        errors.append('Shareholder should land on main dashboard after login')

    with client.session_transaction() as sess:
        with app.app_context():
            user = User.query.filter_by(email='shareholder.a@akramsweets.com').first()
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    for path in ['/portal/', '/portal/reports', '/portal/ownership', '/auth/account']:
        r = client.get(path)
        if r.status_code != 200:
            errors.append(f'{path} returned {r.status_code}')

    r = client.get('/portal/profile', follow_redirects=False)
    if r.status_code not in (302, 303):
        errors.append(f'/portal/profile should redirect to account, got {r.status_code}')

    r = client.get('/')
    if r.status_code != 200:
        errors.append('Shareholder should access main dashboard')

    r = client.get('/apps-todolist', follow_redirects=False)
    if r.status_code not in (302, 303):
        errors.append('Theme demo pages should redirect away from the app')

    r = client.get('/shareholders/', follow_redirects=False)
    if r.status_code != 302:
        errors.append('Shareholder should be blocked from shareholders list')

    r = client.get(f'/portal/reports/{period_id}')
    if r.status_code != 200:
        errors.append(f'Shareholder report detail returned {r.status_code}')
    elif '32000.00' not in r.get_data(as_text=True):
        errors.append('Shareholder report detail missing expected payout')

    r = client.get(f'/portal/reports/{period_id}/pdf')
    if r.status_code != 200 or r.mimetype != 'application/pdf':
        errors.append('Shareholder PDF download failed')

    r = client.get(f'/portal/reports/{period_id}/certificate')
    if r.status_code != 200 or r.mimetype != 'application/pdf':
        errors.append('Shareholder certificate PDF download failed')

    if errors:
        print('VERIFICATION FAILED:')
        for err in errors:
            print(' -', err)
        return 1

    print('ALL CHECKS PASSED')
    return 0


if __name__ == '__main__':
    code = main()
    try:
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
    except OSError:
        pass
    raise SystemExit(code)
