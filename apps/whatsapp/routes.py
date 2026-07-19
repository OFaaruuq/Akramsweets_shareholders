"""Public Twilio webhooks and temporary media downloads for WhatsApp."""

from flask import Response, abort, current_app, send_file

from apps import csrf
from apps.whatsapp import blueprint


@blueprint.route('/media/<token>/<path:filename>')
def media_file(token, filename):
    """Twilio fetches certificate/report PDFs from this URL."""
    from apps.services.whatsapp_media_service import resolve_media

    resolved = resolve_media(token, filename)
    if not resolved:
        abort(404)
    path, name = resolved
    return send_file(
        path,
        mimetype='application/pdf',
        as_attachment=False,
        download_name=name or filename,
    )


@blueprint.route('/webhook/status', methods=['POST'])
@csrf.exempt
def status_callback():
    from flask import request

    from apps.services.twilio_whatsapp_service import (
        update_message_status_from_webhook,
        validate_twilio_request,
    )

    if not validate_twilio_request():
        current_app.logger.warning('Rejected Twilio status callback (bad signature)')
        return Response('invalid signature', status=403)
    update_message_status_from_webhook(request.form.to_dict())
    return Response('ok', status=200)


@blueprint.route('/webhook/inbound', methods=['POST'])
@csrf.exempt
def inbound_webhook():
    from flask import request

    from apps.services.twilio_whatsapp_service import (
        record_inbound_message,
        validate_twilio_request,
    )

    if not validate_twilio_request():
        current_app.logger.warning('Rejected Twilio inbound webhook (bad signature)')
        return Response('invalid signature', status=403)
    record_inbound_message(request.form.to_dict())
    # Empty TwiML — we reply via REST API (auto-reply) instead of TwiML body
    return Response(
        '<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        status=200,
        mimetype='text/xml',
    )
