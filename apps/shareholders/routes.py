from datetime import datetime
from decimal import Decimal

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from apps import db
from apps.auth.decorators import finance_or_management_required, management_required, owner_required
from apps.auth.forms import ShareholderPortalAccountForm
from apps.forms import PurgeShareholderRegisterForm, ShareholderCapitalUploadForm, ShareholderForm
from apps.models.shareholder import OwnershipRecord, Shareholder
from apps.services.audit_service import log_action
from apps.services.portal_service import (
    create_shareholder_portal_user,
    deactivate_shareholder_portal_user,
    portal_email_available,
    reactivate_shareholder_portal_user,
    sync_portal_profile,
)
from apps.services.shareholder_service import (
    COUNTRY_CHOICES,
    country_flag_filename,
    country_label,
    effective_shares_and_capital,
    get_ownership_history,
    get_ownership_percent,
    normalize_email,
    ownership_fits_or_error,
    proposed_ownership_total,
    registration_stats,
    shareholder_email_taken,
    validate_capital_against_ownership,
    validate_ownership_totals,
)
from apps.shareholders import blueprint


def _prepare_shareholder_form(form, is_create=False, ownership_ctx=None, share_settings=None):
    form.country_code.choices = list(COUNTRY_CHOICES)
    if not form.country_code.data:
        form.country_code.data = 'so'
    if is_create and request.method == 'GET':
        form.effective_from.data = datetime.utcnow().date()
        form.is_active.data = True
        form.investment_date.data = datetime.utcnow().date()
        # Suggest remaining ownership so totals stay near 100%.
        if ownership_ctx and ownership_ctx.get('remaining', 0) > 0.01:
            form.ownership_percent.data = round(Decimal(str(ownership_ctx['remaining'])), 4)
            if share_settings and share_settings.get('has_total_shares'):
                from apps.services.share_value_service import capital_for_ownership, shares_for_ownership

                units = shares_for_ownership(form.ownership_percent.data)
                capital = capital_for_ownership(form.ownership_percent.data)
                if units is not None:
                    form.share_count.data = units
                if capital is not None:
                    form.investment_amount.data = capital


def _apply_country(shareholder, country_code):
    code = (country_code or 'so').lower()
    shareholder.country_code = code
    shareholder.country = country_label(code)


def _ownership_context(as_of_date=None, exclude_shareholder_id=None, proposed_percent=None):
    as_of = as_of_date or datetime.utcnow().date()
    total, shareholders = validate_ownership_totals(as_of)
    rows = []
    for shareholder in shareholders:
        if exclude_shareholder_id and shareholder.id == exclude_shareholder_id:
            continue
        percent = get_ownership_percent(shareholder, as_of)
        rows.append({
            'id': shareholder.id,
            'name': shareholder.name,
            'country': shareholder.country,
            'country_code': shareholder.country_code,
            'flag': country_flag_filename(shareholder.country_code),
            'ownership_percent': float(percent),
            'is_owner': shareholder.is_owner,
        })
    allocated = float(sum(Decimal(str(row['ownership_percent'])) for row in rows))
    remaining = float(Decimal('100') - Decimal(str(allocated)))
    proposed = None
    if proposed_percent is not None:
        proposed = float(
            proposed_ownership_total(proposed_percent, as_of, exclude_shareholder_id)
        )
    return {
        'as_of': as_of,
        'rows': rows,
        'allocated': allocated,
        'remaining': remaining,
        'proposed_total': proposed,
        'valid': abs(Decimal(str(allocated)) - Decimal('100')) <= Decimal('0.01')
        if exclude_shareholder_id
        else abs(total - Decimal('100')) <= Decimal('0.01'),
        'total_with_all': float(total),
    }


def _share_settings():
    from apps.services.share_value_service import get_share_settings

    return get_share_settings()


def _apply_share_suggestions(form):
    if not form.suggest_shares.data or not form.ownership_percent.data:
        return
    from apps.services.share_value_service import capital_for_ownership, shares_for_ownership

    units = shares_for_ownership(form.ownership_percent.data)
    capital = capital_for_ownership(form.ownership_percent.data)
    if units is not None:
        form.share_count.data = units
    if capital is not None:
        form.investment_amount.data = capital


def _validate_registration(form, *, exclude_id=None, require_active_ownership=True):
    """Validate email uniqueness, ownership cap, and portal fields. Mutates form errors."""
    email = normalize_email(form.email.data)
    ok = True

    if shareholder_email_taken(email, exclude_id=exclude_id):
        form.email.errors.append('A shareholder with this email already exists.')
        ok = False

    as_of = form.effective_from.data or datetime.utcnow().date()
    if require_active_ownership and form.is_active.data and form.ownership_percent.data is not None:
        ownership_error = ownership_fits_or_error(
            form.ownership_percent.data,
            as_of,
            exclude_shareholder_id=exclude_id,
        )
        if ownership_error:
            form.ownership_percent.errors.append(ownership_error)
            ok = False

        for msg in validate_capital_against_ownership(
            form.ownership_percent.data,
            share_count=form.share_count.data,
            investment_amount=form.investment_amount.data,
        ):
            form.share_count.errors.append(msg)
            ok = False

    if getattr(form, 'create_portal', None) and form.create_portal.data:
        if not form.portal_password.data:
            form.portal_password.errors.append('Portal password is required when creating portal login.')
            ok = False
        portal_email = normalize_email(form.portal_email.data) or email
        if not portal_email_available(portal_email, shareholder_id=exclude_id):
            form.portal_email.errors.append('That portal email is already used by another account.')
            ok = False

    return ok


@blueprint.route('/import', methods=['GET', 'POST'])
@management_required
def import_capital_register():
    """Authoritative upload — always replaces existing shareholders and capital assets."""
    from apps.services.capital_import_service import import_from_upload, preview_import
    from apps.services.register_reset_service import register_counts
    from apps.services.share_value_service import get_company_owned_assets

    form = ShareholderCapitalUploadForm()
    purge_form = PurgeShareholderRegisterForm()
    if request.method == 'GET':
        form.effective_from.data = datetime.utcnow().date().replace(day=1)
        form.company_owned_assets.data = get_company_owned_assets()

    preview = None
    result = None

    if form.validate_on_submit():
        try:
            upload = form.file.data
            if form.preview_only.data:
                preview = preview_import(upload)
                assets = preview['meta'].get('company_owned_assets')
                flash(
                    f'Preview (not saved): {preview["meta"]["row_count"]} shareholders will REPLACE '
                    f'the active register. Capital ${preview["meta"]["total_capital"]:,.2f}, '
                    f'ownership {preview["meta"]["total_ownership"]:.4f}%'
                    + (
                        f', Murabaha ${assets:,.2f}'
                        if assets is not None
                        else ''
                    )
                    + '.',
                    'info',
                )
            else:
                result = import_from_upload(
                    upload,
                    effective_from=form.effective_from.data,
                    company_owned_assets=form.company_owned_assets.data,
                    actor=current_user,
                )
                flash(
                    f'Register replaced with {result["total_rows"]} shareholders '
                    f'({result["created"]} new, {result["updated"]} updated, '
                    f'{result.get("deactivated", 0)} removed from active register). '
                    f'Total capital ${result["total_capital"]:,.2f} · '
                    f'{result["total_shares"]:,.0f} shares.',
                    'success',
                )
                for warning in result.get('warnings') or []:
                    flash(warning, 'warning')
                return redirect(url_for('shareholders.list_shareholders', status='active'))
        except ValueError as exc:
            flash(str(exc), 'danger')
        except Exception as exc:
            db.session.rollback()
            flash(f'Import failed: {exc}', 'danger')

    return render_template(
        'shareholders/import.html',
        form=form,
        purge_form=purge_form,
        register_stats=register_counts(),
        can_purge=current_user.is_superadmin(),
        preview=preview,
        result=result,
        segment='shareholders',
    )


@blueprint.route('/purge', methods=['POST'])
@owner_required
def purge_shareholder_register():
    """Owner-only: delete all shareholders and capital-register related data."""
    from apps.services.register_reset_service import CONFIRM_PHRASE, purge_all_shareholders_and_assets

    form = PurgeShareholderRegisterForm()
    if not form.validate_on_submit():
        flash('Purge cancelled — confirmation was incomplete.', 'warning')
        return redirect(url_for('shareholders.import_capital_register'))

    phrase = (form.confirm_phrase.data or '').strip().upper()
    if phrase != CONFIRM_PHRASE:
        flash(f'Type exactly {CONFIRM_PHRASE} to confirm the purge.', 'danger')
        return redirect(url_for('shareholders.import_capital_register'))

    try:
        result = purge_all_shareholders_and_assets(actor=current_user, reset_capital_settings=True)
    except Exception as exc:
        db.session.rollback()
        flash(f'Purge failed: {exc}', 'danger')
        return redirect(url_for('shareholders.import_capital_register'))

    deleted = result['deleted']
    flash(
        f'Everything shareholder-related cleared: '
        f'{deleted["shareholders"]} shareholders, '
        f'{deleted.get("periods", 0)} periods, '
        f'{deleted["calculations"]} calculations, '
        f'{deleted["certificates"]} certificates, '
        f'{deleted["arrangements"]} arrangements, '
        f'{deleted["portal_users"]} portal users. '
        f'Company assets reset to $0. Upload a clean Excel now.',
        'success',
    )
    return redirect(url_for('shareholders.import_capital_register'))


@blueprint.route('/import/template.csv')
@finance_or_management_required
def download_capital_template():
    from flask import Response

    from apps.services.capital_import_service import build_template_csv

    return Response(
        build_template_csv(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': 'attachment; filename=shareholder_capital_template.csv',
        },
    )


@blueprint.route('/')
@finance_or_management_required
def list_shareholders():
    from apps.services.certificate_service import get_latest_approved_period, get_shareholder_certificate

    shareholders = Shareholder.query.order_by(Shareholder.name).all()
    latest_period = get_latest_approved_period()
    q = (request.args.get('q') or '').strip().lower()
    country_filter = (request.args.get('country') or '').strip().lower() or None
    status_filter = (request.args.get('status') or 'active').strip().lower()
    portal_filter = (request.args.get('portal') or '').strip().lower() or None
    as_of = datetime.utcnow().date()
    stats = registration_stats(as_of)
    share_settings = _share_settings()

    rows = []
    for shareholder in shareholders:
        if status_filter == 'active' and not shareholder.is_active:
            continue
        if status_filter == 'inactive' and shareholder.is_active:
            continue
        if country_filter and (shareholder.country_code or '').lower() != country_filter:
            continue
        portal = shareholder.user_account
        portal_active = bool(portal and portal.is_active)
        if portal_filter == 'yes' and not portal_active:
            continue
        if portal_filter == 'no' and portal_active:
            continue
        haystack = ' '.join([
            shareholder.name or '',
            shareholder.email or '',
            shareholder.phone or '',
            shareholder.country or '',
            shareholder.country_code or '',
        ]).lower()
        if q and q not in haystack:
            continue

        ownership = get_ownership_percent(shareholder, as_of) if shareholder.is_active else Decimal('0')
        certificate = (
            get_shareholder_certificate(latest_period.id, shareholder.id) if latest_period else None
        )
        capital_info = effective_shares_and_capital(shareholder, ownership)
        rows.append({
            'shareholder': shareholder,
            'ownership_percent': float(ownership),
            'share_units': capital_info['shares'] or None,
            'registered_shares': capital_info['registered_shares'],
            'registered_investment': capital_info['registered_investment'],
            'capital': capital_info['investment'] or None,
            'derived_shares': capital_info['shares'] if capital_info['source'] == 'derived' else None,
            'derived_capital': capital_info['investment'] if capital_info['source'] == 'derived' else None,
            'capital_source': capital_info['source'],
            'capital_mismatch': capital_info['mismatch'],
            'flag': country_flag_filename(shareholder.country_code),
            'country_name': shareholder.country or country_label(shareholder.country_code),
            'latest_period': latest_period,
            'latest_certificate': certificate,
            'portal_active': portal_active,
            'portal_email': portal.email if portal else None,
        })

    return render_template(
        'shareholders/list.html',
        rows=rows,
        q=request.args.get('q') or '',
        country_filter=country_filter,
        status_filter=status_filter,
        portal_filter=portal_filter,
        country_choices=COUNTRY_CHOICES,
        stats=stats,
        share_settings=share_settings,
        share_value_label=share_settings.get('label'),
        segment='shareholders',
    )


@blueprint.route('/create', methods=['GET', 'POST'])
@management_required
def create_shareholder():
    form = ShareholderForm()
    share_settings = _share_settings()
    ownership_ctx = _ownership_context()
    _prepare_shareholder_form(
        form, is_create=True, ownership_ctx=ownership_ctx, share_settings=share_settings
    )
    if form.effective_from.data:
        ownership_ctx = _ownership_context(
            form.effective_from.data,
            proposed_percent=form.ownership_percent.data,
        )

    if form.validate_on_submit():
        _apply_share_suggestions(form)
        if not _validate_registration(form, exclude_id=None):
            flash('Please fix the highlighted fields.', 'danger')
            ownership_ctx = _ownership_context(
                form.effective_from.data,
                proposed_percent=form.ownership_percent.data,
            )
        else:
            email = normalize_email(form.email.data)
            shareholder = Shareholder(
                name=form.name.data.strip(),
                email=email,
                phone=(form.phone.data or '').strip() or None,
                is_owner=form.is_owner.data,
                is_active=True if form.is_active.data else False,
                notes=form.notes.data,
                investment_amount=form.investment_amount.data or 0,
                share_count=form.share_count.data or 0,
                investment_date=form.investment_date.data,
            )
            _apply_country(shareholder, form.country_code.data)
            db.session.add(shareholder)
            db.session.flush()

            ownership = OwnershipRecord(
                shareholder_id=shareholder.id,
                ownership_percent=form.ownership_percent.data,
                effective_from=form.effective_from.data,
                created_by_id=current_user.id,
            )
            db.session.add(ownership)
            db.session.commit()

            if form.create_portal.data:
                portal_email = normalize_email(form.portal_email.data) or email
                try:
                    create_shareholder_portal_user(
                        shareholder,
                        portal_email,
                        form.name.data.strip(),
                        form.portal_password.data,
                        current_user.id,
                    )
                except ValueError as exc:
                    flash(f'Shareholder saved, but portal account failed: {exc}', 'warning')

            total, _ = validate_ownership_totals(form.effective_from.data)
            if abs(total - Decimal('100')) > Decimal('0.01'):
                flash(
                    f'Shareholder created. Active ownership now totals {total:.2f}% '
                    f'(remaining to allocate: {100 - float(total):.2f}%).',
                    'warning',
                )
            else:
                flash('Shareholder created successfully. Ownership totals 100%.', 'success')
            log_action('create', 'shareholder', shareholder.id, shareholder.name)
            return redirect(url_for('shareholders.edit_shareholder', shareholder_id=shareholder.id))
    elif request.method == 'POST':
        flash('Please fix the highlighted fields.', 'danger')
        ownership_ctx = _ownership_context(
            form.effective_from.data,
            proposed_percent=form.ownership_percent.data,
        )

    return render_template(
        'shareholders/form.html',
        form=form,
        title='Register Shareholder',
        ownership_ctx=ownership_ctx,
        share_settings=share_settings,
        ownership_history=[],
        is_create=True,
        segment='shareholders',
    )


@blueprint.route('/<int:shareholder_id>/edit', methods=['GET', 'POST'])
@management_required
def edit_shareholder(shareholder_id):
    shareholder = Shareholder.query.get_or_404(shareholder_id)
    form = ShareholderForm(obj=shareholder)
    share_settings = _share_settings()
    _prepare_shareholder_form(form)
    latest_ownership = shareholder.ownership_records.first()
    if latest_ownership and request.method == 'GET':
        form.ownership_percent.data = latest_ownership.ownership_percent
        form.effective_from.data = latest_ownership.effective_from
        form.country_code.data = shareholder.country_code or 'so'

    ownership_ctx = _ownership_context(
        form.effective_from.data or datetime.utcnow().date(),
        exclude_shareholder_id=shareholder.id,
        proposed_percent=form.ownership_percent.data,
    )

    if form.validate_on_submit():
        _apply_share_suggestions(form)
        if not _validate_registration(
            form,
            exclude_id=shareholder.id,
            require_active_ownership=bool(form.is_active.data),
        ):
            flash('Please fix the highlighted fields.', 'danger')
            ownership_ctx = _ownership_context(
                form.effective_from.data or datetime.utcnow().date(),
                exclude_shareholder_id=shareholder.id,
                proposed_percent=form.ownership_percent.data,
            )
        else:
            email = normalize_email(form.email.data)
            previous_email = shareholder.email
            was_active = shareholder.is_active
            shareholder.name = form.name.data.strip()
            shareholder.email = email
            shareholder.phone = (form.phone.data or '').strip() or None
            shareholder.is_owner = form.is_owner.data
            shareholder.is_active = form.is_active.data
            shareholder.notes = form.notes.data
            shareholder.investment_amount = form.investment_amount.data or 0
            shareholder.share_count = form.share_count.data or 0
            shareholder.investment_date = form.investment_date.data
            _apply_country(shareholder, form.country_code.data)

            if form.is_active.data and (
                not latest_ownership
                or latest_ownership.ownership_percent != form.ownership_percent.data
                or latest_ownership.effective_from != form.effective_from.data
            ):
                if latest_ownership and latest_ownership.effective_from == form.effective_from.data:
                    latest_ownership.ownership_percent = form.ownership_percent.data
                    if latest_ownership.effective_to is not None and form.is_active.data:
                        latest_ownership.effective_to = None
                else:
                    if latest_ownership and latest_ownership.effective_to is None:
                        latest_ownership.effective_to = form.effective_from.data
                    db.session.add(
                        OwnershipRecord(
                            shareholder_id=shareholder.id,
                            ownership_percent=form.ownership_percent.data,
                            effective_from=form.effective_from.data,
                            created_by_id=current_user.id,
                        )
                    )

            # Deactivating via edit: close open ownership like deactivate endpoint.
            if was_active and not form.is_active.data:
                open_rec = shareholder.ownership_records.filter(
                    OwnershipRecord.effective_to.is_(None)
                ).first()
                if open_rec:
                    open_rec.effective_to = datetime.utcnow().date()
                if shareholder.user_account:
                    shareholder.user_account.is_active = False

            db.session.commit()

            try:
                sync_email = bool(form.sync_portal_email.data) or (
                    previous_email == (shareholder.user_account.email if shareholder.user_account else None)
                    and previous_email != email
                )
                sync_portal_profile(shareholder, sync_email=sync_email)
            except ValueError as exc:
                flash(str(exc), 'warning')

            total, _ = validate_ownership_totals(form.effective_from.data)
            if form.is_active.data and abs(total - Decimal('100')) > Decimal('0.01'):
                flash(f'Shareholder updated. Active ownership totals {total:.2f}% (expected 100%).', 'warning')
            else:
                flash('Shareholder updated successfully.', 'success')
            log_action('update', 'shareholder', shareholder.id, shareholder.name)
            return redirect(url_for('shareholders.list_shareholders'))
    elif request.method == 'POST':
        flash('Please fix the highlighted fields.', 'danger')
        ownership_ctx = _ownership_context(
            form.effective_from.data or datetime.utcnow().date(),
            exclude_shareholder_id=shareholder.id,
            proposed_percent=form.ownership_percent.data,
        )

    portal_form = ShareholderPortalAccountForm()
    if request.method == 'GET':
        portal_form.email.data = shareholder.user_account.email if shareholder.user_account else shareholder.email
        portal_form.full_name.data = (
            shareholder.user_account.full_name if shareholder.user_account else shareholder.name
        )

    return render_template(
        'shareholders/form.html',
        form=form,
        title='Edit Shareholder',
        shareholder=shareholder,
        portal_form=portal_form,
        ownership_ctx=ownership_ctx,
        share_settings=share_settings,
        ownership_history=get_ownership_history(shareholder),
        is_create=False,
        segment='shareholders',
    )


@blueprint.route('/<int:shareholder_id>/portal-account', methods=['POST'])
@management_required
def save_portal_account(shareholder_id):
    shareholder = Shareholder.query.get_or_404(shareholder_id)
    portal_form = ShareholderPortalAccountForm()
    if portal_form.validate_on_submit():
        try:
            create_shareholder_portal_user(
                shareholder,
                portal_form.email.data,
                portal_form.full_name.data,
                portal_form.password.data,
                current_user.id,
            )
            flash('Shareholder portal access saved.', 'success')
        except ValueError as exc:
            flash(str(exc), 'danger')
    else:
        flash('Could not save portal access. Check the form fields.', 'danger')

    return redirect(url_for('shareholders.edit_shareholder', shareholder_id=shareholder.id))


@blueprint.route('/<int:shareholder_id>/portal-account/deactivate', methods=['POST'])
@management_required
def deactivate_portal_account(shareholder_id):
    shareholder = Shareholder.query.get_or_404(shareholder_id)
    deactivate_shareholder_portal_user(shareholder, current_user.id)
    flash('Shareholder portal access deactivated.', 'success')
    return redirect(url_for('shareholders.edit_shareholder', shareholder_id=shareholder.id))


@blueprint.route('/<int:shareholder_id>/portal-account/reactivate', methods=['POST'])
@management_required
def reactivate_portal_account(shareholder_id):
    shareholder = Shareholder.query.get_or_404(shareholder_id)
    if not shareholder.is_active:
        flash('Reactivate the shareholder before restoring portal access.', 'warning')
        return redirect(url_for('shareholders.edit_shareholder', shareholder_id=shareholder.id))
    user = reactivate_shareholder_portal_user(shareholder, current_user.id)
    if not user:
        flash('No portal account exists for this shareholder. Create one below.', 'warning')
    else:
        flash('Shareholder portal access reactivated.', 'success')
    return redirect(url_for('shareholders.edit_shareholder', shareholder_id=shareholder.id))


@blueprint.route('/<int:shareholder_id>/deactivate', methods=['POST'])
@management_required
def deactivate_shareholder(shareholder_id):
    shareholder = Shareholder.query.get_or_404(shareholder_id)
    if shareholder.is_owner:
        flash('The company owner shareholder cannot be deactivated.', 'danger')
        return redirect(url_for('shareholders.edit_shareholder', shareholder_id=shareholder.id))

    shareholder.is_active = False
    latest_ownership = shareholder.ownership_records.filter(
        OwnershipRecord.effective_to.is_(None)
    ).first()
    if latest_ownership:
        latest_ownership.effective_to = datetime.utcnow().date()
    if shareholder.user_account:
        shareholder.user_account.is_active = False
    db.session.commit()
    log_action('deactivate', 'shareholder', shareholder.id, shareholder.name)
    flash('Shareholder deactivated. Ownership ended and portal access disabled.', 'success')
    return redirect(url_for('shareholders.list_shareholders'))


@blueprint.route('/<int:shareholder_id>/reactivate', methods=['POST'])
@management_required
def reactivate_shareholder(shareholder_id):
    shareholder = Shareholder.query.get_or_404(shareholder_id)
    if shareholder.is_active:
        flash('Shareholder is already active.', 'info')
        return redirect(url_for('shareholders.edit_shareholder', shareholder_id=shareholder.id))

    # Use last known ownership %, or require edit if none.
    last = shareholder.ownership_records.first()
    if not last:
        flash('Set an ownership % on the edit form before reactivating.', 'warning')
        return redirect(url_for('shareholders.edit_shareholder', shareholder_id=shareholder.id))

    as_of = datetime.utcnow().date()
    ownership_error = ownership_fits_or_error(last.ownership_percent, as_of, exclude_shareholder_id=None)
    if ownership_error:
        flash(
            f'Cannot reactivate yet: restoring {last.ownership_percent}% would exceed 100%. '
            f'Adjust other shareholders first, or edit this record with a lower %.',
            'danger',
        )
        return redirect(url_for('shareholders.edit_shareholder', shareholder_id=shareholder.id))

    shareholder.is_active = True
    if last.effective_to is not None:
        db.session.add(
            OwnershipRecord(
                shareholder_id=shareholder.id,
                ownership_percent=last.ownership_percent,
                effective_from=as_of,
                created_by_id=current_user.id,
            )
        )
    db.session.commit()
    log_action('reactivate', 'shareholder', shareholder.id, shareholder.name)
    flash('Shareholder reactivated with previous ownership %. Review the edit form if needed.', 'success')
    return redirect(url_for('shareholders.edit_shareholder', shareholder_id=shareholder.id))


@blueprint.route('/withdrawals')
@finance_or_management_required
def list_withdrawals():
    from apps.services.capital_withdrawal_service import list_withdrawal_requests

    status = (request.args.get('status') or '').strip() or None
    requests = list_withdrawal_requests(status=status)
    return render_template(
        'shareholders/withdrawals.html',
        requests=requests,
        status_filter=status,
        segment='withdrawals',
    )


@blueprint.route('/withdrawals/<int:request_id>', methods=['GET', 'POST'])
@finance_or_management_required
def review_withdrawal(request_id):
    from apps.forms import CapitalWithdrawalReviewForm
    from apps.models.shareholder import CapitalWithdrawalRequest
    from apps.services.capital_withdrawal_service import (
        approve_withdrawal,
        cancel_withdrawal,
        complete_withdrawal,
        reject_withdrawal,
    )

    withdrawal = CapitalWithdrawalRequest.query.get_or_404(request_id)
    form = CapitalWithdrawalReviewForm()
    can_act = current_user.is_management()

    if request.method == 'GET':
        form.review_notes.data = withdrawal.review_notes
        form.capital_return_date.data = withdrawal.capital_return_date or datetime.utcnow().date()

    if request.method == 'POST' and not can_act:
        flash('Only owners/admins can approve or update capital withdrawal requests.', 'danger')
        return redirect(url_for('shareholders.review_withdrawal', request_id=withdrawal.id))

    if can_act and form.validate_on_submit():
        try:
            if form.submit_approve.data:
                approve_withdrawal(withdrawal.id, current_user, form.review_notes.data)
                from apps.services.capital_withdrawal_service import get_capital_return_deadline_months_label

                deadline_meta = get_capital_return_deadline_months_label()
                flash(
                    f'Capital withdrawal approved. Company has {deadline_meta["label"]} to return capital.',
                    'success',
                )
            elif form.submit_reject.data:
                reject_withdrawal(withdrawal.id, current_user, form.review_notes.data)
                flash('Capital withdrawal rejected.', 'warning')
            elif form.submit_complete.data:
                complete_withdrawal(
                    withdrawal.id,
                    current_user,
                    capital_return_date=form.capital_return_date.data,
                    review_notes=form.review_notes.data,
                )
                flash('Capital return recorded as completed.', 'success')
            elif form.submit_cancel.data:
                cancel_withdrawal(withdrawal.id, current_user, form.review_notes.data)
                flash('Capital withdrawal cancelled.', 'info')
            return redirect(url_for('periods.approvals_inbox'))
        except ValueError as exc:
            flash(str(exc), 'danger')

    return render_template(
        'shareholders/withdrawal_detail.html',
        withdrawal=withdrawal,
        form=form,
        can_act=can_act,
        segment='approvals',
    )
