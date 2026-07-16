from datetime import datetime
from io import BytesIO

from flask import flash, redirect, render_template, send_file, url_for

from apps.app_settings import blueprint
from apps.auth.decorators import management_required
from apps.forms import (
    ArrangementForm,
    BrandLogoForm,
    CertificateSignatureImageForm,
    DashboardSettingsForm,
    MediaLibraryUploadForm,
    SystemSettingsForm,
)
from apps.models.arrangement import SpecialArrangement
from apps.models.audit import AuditLog
from apps.models.settings import SystemSetting
from apps.models.shareholder import Shareholder
from apps import db
from apps.services.audit_service import log_action
from apps.services.dashboard_service import get_dashboard_manual_kpis, save_dashboard_manual_kpis


@blueprint.route('/')
@management_required
def settings_home():
    return redirect(url_for('app_settings.arrangements'))


def _shareholder_choices(include_ids=None):
    """Active shareholders for arrangement pickers; keep current IDs selectable when editing."""
    include_ids = {int(i) for i in (include_ids or []) if i}
    query = Shareholder.query
    if include_ids:
        from sqlalchemy import or_

        query = query.filter(
            or_(Shareholder.is_active.is_(True), Shareholder.id.in_(include_ids))
        )
    else:
        query = query.filter_by(is_active=True)
    rows = query.order_by(Shareholder.name).all()
    choices = []
    for sh in rows:
        label = sh.name if sh.is_active else f'{sh.name} (inactive)'
        choices.append((sh.id, label))
    return choices


def _sync_arrangement_sources(arrangement, form):
    if form.applies_to_all_others.data:
        arrangement.source_shareholders = []
        return
    selected_ids = set(form.source_shareholder_ids.data or [])
    selected_ids.discard(form.recipient_shareholder_id.data)
    arrangement.source_shareholders = Shareholder.query.filter(
        Shareholder.id.in_(selected_ids),
        Shareholder.is_active.is_(True),
    ).all() if selected_ids else []


@blueprint.route('/arrangements', methods=['GET', 'POST'])
@management_required
def arrangements():
    form = ArrangementForm()
    choices = _shareholder_choices()
    form.recipient_shareholder_id.choices = choices
    form.source_shareholder_ids.choices = choices

    if form.validate_on_submit():
        recipient = Shareholder.query.get(form.recipient_shareholder_id.data)
        if not recipient or not recipient.is_active:
            flash('Recipient must be an active shareholder.', 'danger')
        else:
            arrangement = SpecialArrangement(
                name=form.name.data.strip(),
                recipient_shareholder_id=form.recipient_shareholder_id.data,
                bonus_percent=form.bonus_percent.data,
                applies_to_all_others=form.applies_to_all_others.data,
                apply_on_profit=form.apply_on_profit.data,
                apply_on_loss=form.apply_on_loss.data,
                effective_from=form.effective_from.data,
                effective_to=form.effective_to.data,
                notes=form.notes.data,
            )
            db.session.add(arrangement)
            db.session.flush()
            _sync_arrangement_sources(arrangement, form)
            db.session.commit()
            log_action('create', 'special_arrangement', arrangement.id, arrangement.name)
            flash('Special arrangement saved. It will apply on the next period calculation.', 'success')
            return redirect(url_for('app_settings.arrangements'))

    rows = SpecialArrangement.query.order_by(SpecialArrangement.effective_from.desc()).all()
    return render_template(
        'settings/arrangements.html',
        form=form,
        rows=rows,
        segment='settings',
    )


@blueprint.route('/arrangements/<int:arrangement_id>/edit', methods=['GET', 'POST'])
@management_required
def edit_arrangement(arrangement_id):
    arrangement = SpecialArrangement.query.get_or_404(arrangement_id)
    form = ArrangementForm(obj=arrangement)
    include_ids = [arrangement.recipient_shareholder_id] + [s.id for s in arrangement.source_shareholders]
    choices = _shareholder_choices(include_ids=include_ids)
    form.recipient_shareholder_id.choices = choices
    form.source_shareholder_ids.choices = choices
    if not form.is_submitted():
        form.source_shareholder_ids.data = [s.id for s in arrangement.source_shareholders]

    if form.validate_on_submit():
        recipient = Shareholder.query.get(form.recipient_shareholder_id.data)
        if not recipient or not recipient.is_active:
            flash('Recipient must be an active shareholder.', 'danger')
        else:
            arrangement.name = form.name.data.strip()
            arrangement.recipient_shareholder_id = form.recipient_shareholder_id.data
            arrangement.bonus_percent = form.bonus_percent.data
            arrangement.applies_to_all_others = form.applies_to_all_others.data
            arrangement.apply_on_profit = form.apply_on_profit.data
            arrangement.apply_on_loss = form.apply_on_loss.data
            arrangement.effective_from = form.effective_from.data
            arrangement.effective_to = form.effective_to.data
            arrangement.notes = form.notes.data
            _sync_arrangement_sources(arrangement, form)
            db.session.commit()
            log_action('update', 'special_arrangement', arrangement.id, arrangement.name)
            flash('Special arrangement updated.', 'success')
            return redirect(url_for('app_settings.arrangements'))

    return render_template(
        'settings/arrangement_form.html',
        form=form,
        title='Edit Special Arrangement',
        arrangement=arrangement,
        segment='settings',
    )


@blueprint.route('/arrangements/<int:arrangement_id>/deactivate', methods=['POST'])
@management_required
def deactivate_arrangement(arrangement_id):
    arrangement = SpecialArrangement.query.get_or_404(arrangement_id)
    arrangement.is_active = False
    db.session.commit()
    log_action('deactivate', 'special_arrangement', arrangement.id, arrangement.name)
    flash('Special arrangement deactivated. It will no longer apply to new calculations.', 'success')
    return redirect(url_for('app_settings.arrangements'))


@blueprint.route('/arrangements/<int:arrangement_id>/activate', methods=['POST'])
@management_required
def activate_arrangement(arrangement_id):
    arrangement = SpecialArrangement.query.get_or_404(arrangement_id)
    if not arrangement.recipient or not arrangement.recipient.is_active:
        flash('Cannot activate: recipient shareholder is inactive.', 'danger')
        return redirect(url_for('app_settings.arrangements'))
    if not arrangement.applies_to_all_others and not arrangement.source_ids():
        flash('Cannot activate: select at least one source shareholder first.', 'danger')
        return redirect(url_for('app_settings.edit_arrangement', arrangement_id=arrangement.id))
    arrangement.is_active = True
    db.session.commit()
    log_action('activate', 'special_arrangement', arrangement.id, arrangement.name)
    flash('Special arrangement activated.', 'success')
    return redirect(url_for('app_settings.arrangements'))


@blueprint.route('/dashboard', methods=['GET', 'POST'])
@management_required
def dashboard_settings():
    manual = get_dashboard_manual_kpis()
    form = DashboardSettingsForm(
        total_revenues=manual['total_revenues'],
        total_expenses=manual['total_expenses'],
        cost_of_goods=manual['cost_of_goods'],
        other_income=manual['other_income'],
        operating_notes=manual['operating_notes'],
    )

    if form.validate_on_submit():
        save_dashboard_manual_kpis(form)
        log_action('update', 'dashboard_settings', None, 'Updated dashboard KPI figures')
        flash('Dashboard figures saved. The main dashboard will reflect these values.', 'success')
        return redirect(url_for('app_settings.dashboard_settings'))

    return render_template('settings/dashboard.html', form=form, segment='dashboard-settings')


@blueprint.route('/system', methods=['GET', 'POST'])
@management_required
def system_settings():
    from apps.services.brand_service import ensure_default_brand_settings, get_brand_settings, save_brand_settings
    from apps.services.certificate_settings_service import (
        ensure_default_certificate_settings,
        get_certificate_settings,
        save_certificate_settings,
    )
    from apps.services.share_value_service import (
        ensure_default_share_settings,
        get_share_settings,
        save_share_settings,
    )
    from apps.services.mudarabah_service import (
        ensure_default_mudarabah_settings,
        get_mudarabah_settings,
        save_mudarabah_settings,
    )
    from apps.services.capital_withdrawal_service import (
        ensure_default_withdrawal_settings,
        get_capital_return_deadline_days,
        get_capital_return_deadline_months_label,
        save_capital_return_deadline_days,
    )

    ensure_default_brand_settings()
    ensure_default_certificate_settings()
    ensure_default_share_settings()
    ensure_default_mudarabah_settings()
    ensure_default_withdrawal_settings()
    from apps.services.twilio_whatsapp_service import get_whatsapp_delivery_status

    brand = get_brand_settings()
    cert = get_certificate_settings()
    share = get_share_settings()
    mudarabah = get_mudarabah_settings()
    capital_return = get_capital_return_deadline_months_label()
    whatsapp_status = get_whatsapp_delivery_status()
    form = SystemSettingsForm(
        auto_email_on_approval=str(SystemSetting.get('auto_email_on_approval', 'true')).lower() in ('1', 'true', 'yes', 'on'),
        sms_notifications_enabled=str(SystemSetting.get('sms_notifications_enabled', 'false')).lower() in ('1', 'true', 'yes', 'on'),
        notify_management_on_review=str(SystemSetting.get('notify_management_on_review', 'true')).lower() in ('1', 'true', 'yes', 'on'),
        email_portal_credentials=str(SystemSetting.get('email_portal_credentials', 'true')).lower() in ('1', 'true', 'yes', 'on'),
        email_staff_invite=str(SystemSetting.get('email_staff_invite', 'true')).lower() in ('1', 'true', 'yes', 'on'),
        email_password_change=str(SystemSetting.get('email_password_change', 'true')).lower() in ('1', 'true', 'yes', 'on'),
        notify_shareholders_on_profit_update=str(
            SystemSetting.get('notify_shareholders_on_profit_update', 'true')
        ).lower()
        in ('1', 'true', 'yes', 'on'),
        share_value=share['share_value'],
        total_company_shares=share['total_company_shares'] if share['has_total_shares'] else None,
        mudarabah_shareholder_percent=mudarabah['shareholder_percent'],
        capital_return_deadline_days=get_capital_return_deadline_days(),
        report_delivery_day=SystemSetting.get('report_delivery_day'),
        mail_from=SystemSetting.get('mail_from'),
        mail_server=SystemSetting.get('mail_server'),
        mail_port=SystemSetting.get('mail_port') or 587,
        mail_username=SystemSetting.get('mail_username'),
        mail_password=SystemSetting.get('mail_password'),
        brand_company_name=brand['company_name'],
        brand_primary_color=brand['primary_color'],
        brand_secondary_color=brand['secondary_color'],
        brand_accent_color=brand['accent_color'],
        cert_subtitle=cert['subtitle'],
        cert_title=cert['title'],
        cert_intro_text=cert['intro_text'],
        cert_allocation_text=cert['allocation_text'],
        cert_profit_label=cert['profit_label'],
        cert_loss_label=cert['loss_label'],
        cert_currency_symbol=cert['currency_symbol'],
        cert_number_prefix=cert['number_prefix'],
        cert_approver_fallback=cert['approver_fallback'],
        cert_owner_label=cert['owner_label'],
        cert_roster_title=cert['roster_title'],
        cert_label_company_pl=cert['label_company_pl'],
        cert_label_base_share=cert['label_base_share'],
        cert_label_ytd=cert['label_ytd'],
        cert_label_odoo=cert['label_odoo'],
        cert_footer_disclaimer=cert['footer_disclaimer'],
        cert_footer_confidential=cert['footer_confidential'],
        cert_legal_text=cert['legal_text'],
        cert_show_roster=cert['show_roster'],
        cert_show_odoo_reference=cert['show_odoo_reference'],
        cert_signature_name=cert['signature_name'],
        cert_signature_title=cert['signature_title'],
    )

    if form.validate_on_submit():
        SystemSetting.set('auto_email_on_approval', 'true' if form.auto_email_on_approval.data else 'false')
        SystemSetting.set('sms_notifications_enabled', 'true' if form.sms_notifications_enabled.data else 'false')
        SystemSetting.set('notify_management_on_review', 'true' if form.notify_management_on_review.data else 'false')
        SystemSetting.set('email_portal_credentials', 'true' if form.email_portal_credentials.data else 'false')
        SystemSetting.set('email_staff_invite', 'true' if form.email_staff_invite.data else 'false')
        SystemSetting.set('email_password_change', 'true' if form.email_password_change.data else 'false')
        SystemSetting.set(
            'notify_shareholders_on_profit_update',
            'true' if form.notify_shareholders_on_profit_update.data else 'false',
        )
        try:
            save_share_settings(form.share_value.data, form.total_company_shares.data)
            save_mudarabah_settings(form.mudarabah_shareholder_percent.data)
            save_capital_return_deadline_days(form.capital_return_deadline_days.data)
        except ValueError as exc:
            flash(str(exc), 'danger')
            return render_template(
                'settings/system.html',
                form=form,
                brand=brand,
                cert=cert,
                mudarabah=mudarabah,
                capital_return=capital_return,
                whatsapp_status=whatsapp_status,
                segment='settings',
            )
        for key in (
            'report_delivery_day',
            'mail_from',
            'mail_server',
            'mail_port',
            'mail_username',
            'mail_password',
        ):
            value = getattr(form, key).data
            SystemSetting.set(key, '' if value is None else str(value))
        try:
            save_brand_settings(
                form.brand_company_name.data,
                form.brand_primary_color.data,
                form.brand_secondary_color.data,
                form.brand_accent_color.data,
                logo_file=form.brand_logo.data,
                remove_logo=form.remove_brand_logo.data,
            )
            save_certificate_settings(
                {
                    'subtitle': form.cert_subtitle.data,
                    'title': form.cert_title.data,
                    'intro_text': form.cert_intro_text.data,
                    'allocation_text': form.cert_allocation_text.data,
                    'profit_label': form.cert_profit_label.data,
                    'loss_label': form.cert_loss_label.data,
                    'currency_symbol': form.cert_currency_symbol.data,
                    'number_prefix': form.cert_number_prefix.data,
                    'approver_fallback': form.cert_approver_fallback.data,
                    'owner_label': form.cert_owner_label.data,
                    'roster_title': form.cert_roster_title.data,
                    'label_company_pl': form.cert_label_company_pl.data,
                    'label_base_share': form.cert_label_base_share.data,
                    'label_ytd': form.cert_label_ytd.data,
                    'label_odoo': form.cert_label_odoo.data,
                    'footer_disclaimer': form.cert_footer_disclaimer.data,
                    'footer_confidential': form.cert_footer_confidential.data,
                    'legal_text': form.cert_legal_text.data,
                    'show_roster': form.cert_show_roster.data,
                    'show_odoo_reference': form.cert_show_odoo_reference.data,
                    'signature_name': form.cert_signature_name.data,
                    'signature_title': form.cert_signature_title.data,
                },
                signature_file=form.cert_signature_image.data,
                remove_signature=form.remove_cert_signature.data,
            )
        except ValueError as exc:
            flash(str(exc), 'danger')
            return render_template(
                'settings/system.html',
                form=form,
                brand=get_brand_settings(),
                cert=get_certificate_settings(),
                mudarabah=get_mudarabah_settings(),
                capital_return=get_capital_return_deadline_months_label(),
                whatsapp_status=whatsapp_status,
                segment='settings',
            )

        log_action('update', 'system_settings', None, 'Updated system, brand, and certificate settings')
        flash('Settings saved. New certificates will use the updated brand and certificate content.', 'success')
        return redirect(url_for('app_settings.system_settings'))

    return render_template(
        'settings/system.html',
        form=form,
        brand=brand,
        cert=cert,
        mudarabah=mudarabah,
        capital_return=capital_return,
        whatsapp_status=whatsapp_status,
        segment='settings',
    )


@blueprint.route('/system/preview-certificate')
@management_required
def preview_certificate():
    """Download a sample branded certificate using current logo, colors, and certificate text."""
    from apps.services.brand_service import ensure_default_brand_settings, get_brand_settings
    from apps.services.certificate_settings_service import (
        ensure_default_certificate_settings,
        format_certificate_text,
        get_certificate_settings,
    )
    from apps.services.pdf_service import certificate_pdf_filename, generate_shareholder_certificate_pdf

    ensure_default_brand_settings()
    ensure_default_certificate_settings()
    brand = get_brand_settings()
    cert = get_certificate_settings()
    now = datetime.utcnow()
    period_label = now.strftime('%B %Y')
    sample = {
        'period_label': period_label,
        'generated_at': now,
        'company_total': 100000,
        'shareholder_name': 'Sample Shareholder',
        'shareholder_email': 'shareholder@example.com',
        'shareholder_phone': '+252 61 0000000',
        'shareholder_id': 0,
        'shareholder_is_owner': False,
        'ownership_percent': 40,
        'base_share': 40000,
        'final_amount': 40000,
        'ytd_total': 120000,
        'certificate_number': f"{cert['number_prefix']}-PREVIEW-{now.strftime('%Y%m')}",
        'certificate_issued_at': now,
        'approved_at': now,
        'approved_by': cert['approver_fallback'],
        'company_name': brand['company_name'],
        'brand_primary_color': brand['primary_color'],
        'brand_secondary_color': brand['secondary_color'],
        'brand_accent_color': brand['accent_color'],
        'brand_logo_path': brand['logo_filesystem_path'],
        'current_shareholders': (
            [
                {'id': 1, 'name': 'Pocly (Owner)', 'ownership_percent': 30, 'is_owner': True},
                {'id': 0, 'name': 'Sample Shareholder', 'ownership_percent': 40, 'is_owner': False},
                {'id': 2, 'name': 'Shareholder B', 'ownership_percent': 30, 'is_owner': False},
            ]
            if cert['show_roster']
            else []
        ),
        'odoo_reference': 'PREVIEW' if cert['show_odoo_reference'] else None,
        'cert_subtitle': cert['subtitle'],
        'cert_title': cert['title'],
        'cert_intro_text': cert['intro_text'],
        'cert_allocation_text': format_certificate_text(
            cert['allocation_text'],
            period_label=period_label,
            company_name=brand['company_name'],
        ),
        'cert_profit_label': cert['profit_label'],
        'cert_loss_label': cert['loss_label'],
        'cert_currency_symbol': cert['currency_symbol'],
        'cert_owner_label': cert['owner_label'],
        'cert_roster_title': cert['roster_title'],
        'cert_label_company_pl': cert['label_company_pl'],
        'cert_label_base_share': cert['label_base_share'],
        'cert_label_ytd': cert['label_ytd'],
        'cert_label_odoo': cert['label_odoo'],
        'cert_footer_disclaimer': cert['footer_disclaimer'],
        'cert_footer_confidential': format_certificate_text(
            cert['footer_confidential'],
            company_name=brand['company_name'],
            period_label=period_label,
        ),
        'cert_legal_text': cert['legal_text'],
        'cert_show_odoo_reference': cert['show_odoo_reference'],
        'cert_signature_name': cert['signature_name'],
        'cert_signature_title': cert['signature_title'],
        'cert_signature_image_path': cert['signature_filesystem_path'],
    }
    pdf_bytes = generate_shareholder_certificate_pdf(sample)
    return send_file(
        BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=certificate_pdf_filename(sample).replace(
            sample['certificate_number'].replace('/', '-'),
            'Preview',
        ),
    )


@blueprint.route('/audit-log')
@management_required
def audit_log():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template('settings/audit_log.html', logs=logs, segment='audit-log')


@blueprint.route('/images', methods=['GET', 'POST'])
@management_required
def manage_images():
    """Central admin page for all application images."""
    from apps.services.brand_service import clear_brand_logo, ensure_default_logo, save_brand_logo
    from apps.services.certificate_settings_service import clear_signature_image, save_signature_image
    from apps.services.media_service import (
        get_application_images,
        upload_library_image,
    )

    logo_form = BrandLogoForm(prefix='logo')
    signature_form = CertificateSignatureImageForm(prefix='sig')
    upload_form = MediaLibraryUploadForm(prefix='upload')

    action = None
    if logo_form.validate_on_submit() and logo_form.submit.data:
        action = 'logo'
    elif signature_form.validate_on_submit() and signature_form.submit.data:
        action = 'signature'
    elif upload_form.validate_on_submit() and upload_form.submit.data:
        action = 'upload'

    try:
        if action == 'logo':
            if logo_form.remove_brand_logo.data:
                clear_brand_logo()
                flash('Brand logo cleared. Default logo restored.', 'success')
            elif logo_form.brand_logo.data:
                save_brand_logo(logo_form.brand_logo.data)
                flash('Brand logo updated. It now appears across login, emails, and certificates.', 'success')
            else:
                flash('Choose a logo file or tick remove.', 'warning')
                return redirect(url_for('app_settings.manage_images'))
            log_action('update', 'media_image', None, 'Updated brand logo')
            return redirect(url_for('app_settings.manage_images'))

        if action == 'signature':
            if signature_form.remove_cert_signature.data:
                clear_signature_image()
                flash('Certificate signature image removed.', 'success')
            elif signature_form.cert_signature_image.data:
                save_signature_image(signature_form.cert_signature_image.data)
                flash('Certificate signature image updated.', 'success')
            else:
                flash('Choose a signature file or tick remove.', 'warning')
                return redirect(url_for('app_settings.manage_images'))
            log_action('update', 'media_image', None, 'Updated certificate signature image')
            return redirect(url_for('app_settings.manage_images'))

        if action == 'upload':
            item = upload_library_image(
                upload_form.image.data,
                title=upload_form.title.data,
                slot=(upload_form.slot.data or None) or None,
            )
            log_action('create', 'media_image', None, f'Uploaded {item.get("title")}')
            flash(f'Image “{item.get("title")}” uploaded.', 'success')
            return redirect(url_for('app_settings.manage_images'))
    except ValueError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('app_settings.manage_images'))

    ensure_default_logo()
    images = get_application_images()
    return render_template(
        'settings/images.html',
        segment='images',
        images=images,
        logo_form=logo_form,
        signature_form=signature_form,
        upload_form=upload_form,
    )


@blueprint.route('/images/library/<image_id>/assign', methods=['POST'])
@management_required
def assign_media_image(image_id):
    from apps.services.media_service import IMAGE_SLOTS, assign_slot
    from flask import request

    slot = (request.form.get('slot') or '').strip()
    if slot not in IMAGE_SLOTS or IMAGE_SLOTS[slot]['managed'] != 'library':
        flash('Choose a valid application image slot.', 'danger')
        return redirect(url_for('app_settings.manage_images'))
    try:
        item = assign_slot(slot, image_id)
        log_action('update', 'media_image', None, f'Assigned {item.get("title")} to {slot}')
        flash('Image assigned to application slot.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('app_settings.manage_images'))


@blueprint.route('/images/library/<image_id>/delete', methods=['POST'])
@management_required
def delete_media_image(image_id):
    from apps.services.media_service import delete_library_image

    try:
        deleted = delete_library_image(image_id)
        log_action('delete', 'media_image', None, f'Deleted {deleted.get("title")}')
        flash('Image deleted from the media library.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('app_settings.manage_images'))


@blueprint.route('/images/slots/<slot>/clear', methods=['POST'])
@management_required
def clear_media_slot(slot):
    from apps.services.media_service import IMAGE_SLOTS, clear_slot

    if slot not in IMAGE_SLOTS or IMAGE_SLOTS[slot]['managed'] != 'library':
        flash('That image slot cannot be cleared here.', 'danger')
        return redirect(url_for('app_settings.manage_images'))
    clear_slot(slot)
    log_action('update', 'media_image', None, f'Cleared slot {slot}')
    flash('Image slot cleared.', 'success')
    return redirect(url_for('app_settings.manage_images'))
