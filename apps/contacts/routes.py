from flask import redirect, render_template, request, url_for
from flask_login import current_user

from apps.auth.decorators import finance_or_management_required
from apps.contacts import blueprint
from apps.services.contact_service import (
    build_shareholder_contacts,
    build_staff_contacts,
    contact_directory_stats,
)
from apps.services.shareholder_service import COUNTRY_CHOICES


@blueprint.route('/')
@finance_or_management_required
def list_contacts():
    q = (request.args.get('q') or '').strip()
    country = (request.args.get('country') or '').strip().lower() or None
    status = (request.args.get('status') or 'active').strip().lower()
    if status not in ('active', 'inactive', 'all'):
        status = 'active'

    shareholder_rows = build_shareholder_contacts(q=q, country=country, status=status)
    staff_rows = []
    if current_user.can_manage_users():
        staff_rows = build_staff_contacts(q=q)

    stats = contact_directory_stats(shareholder_rows, staff_rows)
    return render_template(
        'contacts/list.html',
        shareholder_rows=shareholder_rows,
        staff_rows=staff_rows,
        stats=stats,
        q=q,
        country_filter=country,
        status_filter=status,
        country_choices=COUNTRY_CHOICES,
        segment='contacts',
        can_edit_shareholders=current_user.can_edit_shareholders(),
        can_manage_users=current_user.can_manage_users(),
    )


@blueprint.route('/legacy')
@finance_or_management_required
def legacy_apps_contacts():
    """Compatibility redirect from theme URL /apps-contacts."""
    return redirect(url_for('contacts.list_contacts', **request.args))
