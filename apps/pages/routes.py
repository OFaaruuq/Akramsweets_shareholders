# -*- encoding: utf-8 -*-

from apps.pages import blueprint
from flask import Response, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from jinja2 import TemplateNotFound

from apps.services.dashboard_service import get_dashboard_metrics, get_shareholder_dashboard_metrics

# Only real public/error pages remain reachable via the catch-all.
# Theme demos (ui-*, charts-*, forms-*, tables-*, maps-*, widgets, etc.) redirect home.
ALLOWED_STATIC_PAGES = {
    'error-404',
    'error-500',
    'error-503',
    'error-429',
    'offline-page',
    'pages-maintenance',
}


@blueprint.route('/')
@login_required
def dashboard():
    if current_user.is_shareholder():
        metrics = get_shareholder_dashboard_metrics(current_user.shareholder_id)
        return render_template(
            'pages/index.html',
            segment='index',
            can_edit_dashboard=False,
            is_shareholder_view=True,
            **metrics,
        )

    metrics = get_dashboard_metrics()
    return render_template(
        'pages/index.html',
        segment='index',
        can_edit_dashboard=current_user.is_management(),
        is_shareholder_view=False,
        **metrics,
    )


@blueprint.route('/analytics')
@login_required
def analytics():
    year = request.args.get('year', type=int)

    if current_user.is_shareholder():
        metrics = get_shareholder_dashboard_metrics(current_user.shareholder_id, year=year)
        return render_template(
            'pages/analytics.html',
            segment='analytics',
            can_edit_dashboard=False,
            is_shareholder_view=True,
            **metrics,
        )

    metrics = get_dashboard_metrics(year=year)
    return render_template(
        'pages/analytics.html',
        segment='analytics',
        can_edit_dashboard=current_user.is_management(),
        is_shareholder_view=False,
        **metrics,
    )


@blueprint.route('/analytics/export')
@login_required
def analytics_export():
    import csv
    from io import StringIO

    year = request.args.get('year', type=int)
    if current_user.is_shareholder():
        metrics = get_shareholder_dashboard_metrics(current_user.shareholder_id, year=year)
        filename = f'shareholder-analytics-{metrics["selected_year"]}.csv'
        headers = ['Period', 'Ownership %', 'My Payout', 'Reports Sent']
        rows = []
        for trend in reversed(metrics['analytics_table_rows']):
            shareholder = trend['shareholders'][0] if trend['shareholders'] else {}
            rows.append([
                trend['label'],
                f'{shareholder.get("ownership_percent", 0):.2f}',
                f'{shareholder.get("final_amount", 0):.2f}',
                'Yes' if trend['reports_sent'] else 'No',
            ])
    else:
        metrics = get_dashboard_metrics(year=year)
        filename = f'shareholder-analytics-{metrics["selected_year"]}.csv'
        headers = ['Period', 'Company P/L', 'Distributed', 'Type', 'Reports Sent', 'Shareholder Breakdown']
        rows = []
        for trend in reversed(metrics['analytics_table_rows']):
            breakdown = ' | '.join(
                f'{sh["name"]}: {sh["final_amount"]:.2f}' for sh in trend['shareholders']
            )
            rows.append([
                trend['label'],
                f'{trend["company_total"]:.2f}',
                f'{trend["distributed_total"]:.2f}',
                'Profit' if trend['is_profit'] else 'Loss',
                'Yes' if trend['reports_sent'] else 'No',
                breakdown,
            ])

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)

    return Response(
        buffer.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


@blueprint.route('/auth-login')
def legacy_login():
    return redirect(url_for('auth.login'))


@blueprint.route('/auth-register')
def legacy_register():
    """Public registration is disabled — only super admins create users."""
    flash('Registration is disabled. Ask a super admin to create your account.', 'warning')
    return redirect(url_for('auth.login'))


@blueprint.route('/apps-contacts')
@login_required
def legacy_apps_contacts():
    """Theme demo URL → real contacts directory."""
    return redirect(url_for('contacts.list_contacts', **request.args))


@blueprint.route('/<template>')
def route_template(template):
    if template in ('index', 'analytics'):
        return dashboard() if template == 'index' else analytics()

    segment = get_segment(request)

    # Auth / contacts aliases
    if segment == 'auth-login':
        return redirect(url_for('auth.login'))
    if segment == 'auth-register':
        flash('Registration is disabled. Ask a super admin to create your account.', 'warning')
        return redirect(url_for('auth.login'))
    if segment in ('email-verification', 'auth-confirm-mail', 'auth-recoverpw', 'auth-lock-screen', 'auth-logout'):
        return redirect(url_for('auth.login'))
    if segment == 'apps-contacts':
        return redirect(url_for('contacts.list_contacts', **request.args))

    # Theme demo pages are not part of this product — send users to the live app.
    if segment not in ALLOWED_STATIC_PAGES:
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        flash('That demo page is not part of the Akram Sweets shareholders app.', 'info')
        return redirect(url_for(current_user.home_endpoint()))

    if not current_user.is_authenticated and segment not in ALLOWED_STATIC_PAGES:
        return redirect(url_for('auth.login'))

    try:
        if not template.endswith('.html'):
            template += '.html'
        return render_template('pages/' + template, segment=segment)
    except TemplateNotFound:
        return render_template('pages/error-404.html'), 404
    except Exception:
        return render_template('pages/error-500.html'), 500


def get_segment(request):
    try:
        segment = request.path.split('/')[-1]
        if segment == '':
            segment = 'index'
        return segment
    except Exception:
        return None
