"""
Celery background tasks for Mnotify SMS dispatching.
All SMS operations are delegated to these tasks so the web request
returns immediately while the message delivery happens asynchronously
via the Celery/Redis worker.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='common.send_bulk_sms',
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def send_bulk_sms_task(self, phone_numbers, message, sender_id=None, campaign_id=None):
    """
    Background task: Dispatches bulk SMS via Mnotify and updates
    the SMSCampaign record with the result.

    Args:
        phone_numbers (list[str]): List of raw or normalized phone numbers.
        message (str): SMS text body.
        sender_id (str, optional): Mnotify sender ID (max 11 chars).
        campaign_id (str, optional): UUID of the SMSCampaign to update on completion.
    """
    from apps.common.mnotify import send_mnotify_bulk_sms

    logger.info(
        f"[CELERY SMS] Starting bulk dispatch to {len(phone_numbers)} recipients "
        f"(campaign: {campaign_id or 'N/A'})"
    )

    try:
        result = send_mnotify_bulk_sms(phone_numbers, message, sender_id=sender_id)
    except Exception as exc:
        logger.error(f"[CELERY SMS] Mnotify dispatch failed: {exc}")
        # Update campaign as failed if we have an ID
        if campaign_id:
            _update_campaign_status(campaign_id, 'failed', error_message=str(exc))
        raise self.retry(exc=exc)

    # Update the SMSCampaign record with the result
    if campaign_id:
        if result.get('success'):
            status = 'simulated' if result.get('status') == 'simulated' else 'sent'
            _update_campaign_status(
                campaign_id,
                status,
                recipient_count=result.get('total_sent', len(phone_numbers)),
                response_summary=result.get('summary', result.get('details', {})),
            )
        else:
            _update_campaign_status(
                campaign_id,
                'failed',
                error_message=result.get('message', 'Unknown error'),
                response_summary=result.get('details', {}),
            )

    logger.info(
        f"[CELERY SMS] Dispatch complete. Success: {result.get('success')} | "
        f"Sent: {result.get('total_sent', 0)} | Status: {result.get('status')}"
    )

    return {
        'success': result.get('success'),
        'total_sent': result.get('total_sent', 0),
        'status': result.get('status'),
        'message': result.get('message'),
    }


@shared_task(
    bind=True,
    name='common.send_member_id_sms',
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def send_member_id_sms_task(self, member_id):
    """
    Background task: Sends the generated Member ID to a new church member
    via Mnotify SMS.

    Args:
        member_id (int): Primary key of the Members model instance.
    """
    from apps.members.models import Members
    from apps.common.mnotify import dispatch_single_member_sms

    try:
        member = Members.objects.get(pk=member_id)
    except Members.DoesNotExist:
        logger.error(f"[CELERY SMS] Member with pk={member_id} not found. Skipping SMS.")
        return {'success': False, 'message': f'Member {member_id} not found'}

    message = (
        f"Hello {member.name}, your Church Attendance Member ID is: {member.member_id}. "
        f"Present or enter this ID when scanning the check-in QR code. God bless you!"
    )

    try:
        success, resp_msg = dispatch_single_member_sms(member, message)
    except Exception as exc:
        logger.error(f"[CELERY SMS] Failed to send Member ID SMS to {member.phone_number}: {exc}")
        raise self.retry(exc=exc)

    logger.info(
        f"[CELERY SMS] Member ID SMS to {member.phone_number} ({member.member_id}): "
        f"success={success}"
    )

    return {'success': success, 'message': resp_msg}


@shared_task(
    bind=True,
    name='common.send_birthday_wishes_task',
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def send_birthday_wishes_task(self, custom_message=None, sender_id=None, target_date_str=None, campaign_id=None):
    """
    Background task: Finds members whose birthday matches the target date
    (defaults to today) and sends personalized birthday SMS wishes to each.

    Args:
        custom_message (str, optional): Message template. May contain placeholders
                                        like {name}, {first_name}, {member_id}.
        sender_id (str, optional): Mnotify sender ID (max 11 chars).
        target_date_str (str, optional): 'YYYY-MM-DD' formatted date string.
        campaign_id (str, optional): UUID of pre-created SMSCampaign (if triggered from UI).
    """
    from datetime import datetime
    from django.utils import timezone
    from django.conf import settings
    from apps.members.models import Members, SMSCampaign
    from apps.common.mnotify import dispatch_single_member_sms

    if target_date_str:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    else:
        target_date = timezone.localdate()

    celebrants = Members.objects.filter(
        date_of_birth__month=target_date.month,
        date_of_birth__day=target_date.day,
    ).exclude(phone_number='').exclude(phone_number__isnull=True)

    total_celebrants = celebrants.count()
    logger.info(
        f"[CELERY BIRTHDAY SMS] Found {total_celebrants} celebrants for {target_date.strftime('%B %d')} "
        f"(campaign: {campaign_id or 'Auto-Daily'})"
    )

    default_template = (
        "Happy Birthday {first_name}! 🎂 On this blessed day, the church family celebrates you. "
        "May God's favor, joy, and peace overflow in your life this new year. Have a wonderful celebration!"
    )
    template = custom_message.strip() if custom_message and custom_message.strip() else default_template
    sender = sender_id or getattr(settings, 'MNOTIFY_SENDER_ID', 'CHURCH')

    # If triggered automatically without a pre-existing campaign, create a campaign record
    campaign = None
    if campaign_id:
        try:
            campaign = SMSCampaign.objects.get(pk=campaign_id)
        except SMSCampaign.DoesNotExist:
            logger.warning(f"[CELERY BIRTHDAY SMS] Campaign {campaign_id} not found.")
    elif total_celebrants > 0:
        campaign = SMSCampaign.objects.create(
            title=f"Birthday Wishes - {target_date.strftime('%b %d, %Y')}",
            target_type='birthday',
            sender_id=sender[:11],
            message=template,
            recipient_count=total_celebrants,
            status='pending',
        )

    if total_celebrants == 0:
        if campaign:
            _update_campaign_status(
                campaign.id,
                'sent',
                recipient_count=0,
                response_summary={'message': f'No birthdays on {target_date.strftime("%B %d")}'}
            )
        return {
            'success': True,
            'total_sent': 0,
            'message': f'No birthday celebrants for {target_date.strftime("%B %d")}.',
            'celebrants': []
        }

    sent_count = 0
    failed_count = 0
    results_detail = []

    for member in celebrants:
        first_name = member.name.strip().split()[0] if member.name else 'Beloved'
        personalized_msg = template.format(
            name=member.name,
            first_name=first_name,
            member_id=member.member_id,
        )
        try:
            success, resp_msg = dispatch_single_member_sms(member, personalized_msg, sender_id=sender)
            if success:
                sent_count += 1
            else:
                failed_count += 1
            results_detail.append({
                'member_id': member.member_id,
                'name': member.name,
                'phone': member.phone_number,
                'success': success,
                'response': resp_msg,
            })
        except Exception as err:
            failed_count += 1
            logger.error(f"[CELERY BIRTHDAY SMS] Failed for {member.name}: {err}")
            results_detail.append({
                'member_id': member.member_id,
                'name': member.name,
                'phone': member.phone_number,
                'success': False,
                'response': str(err),
            })

    final_status = 'sent' if sent_count > 0 else 'failed'
    if campaign:
        _update_campaign_status(
            campaign.id,
            final_status,
            recipient_count=sent_count,
            response_summary={
                'sent_count': sent_count,
                'failed_count': failed_count,
                'details': results_detail,
                'target_date': str(target_date),
            }
        )

    logger.info(
        f"[CELERY BIRTHDAY SMS] Completed: {sent_count} sent, {failed_count} failed out of {total_celebrants}."
    )

    return {
        'success': sent_count > 0 or failed_count == 0,
        'total_sent': sent_count,
        'failed_count': failed_count,
        'target_date': str(target_date),
        'results': results_detail,
    }


def _update_campaign_status(campaign_id, status, **kwargs):
    """Helper to update an SMSCampaign record after task completion."""
    from apps.members.models import SMSCampaign

    try:
        campaign = SMSCampaign.objects.get(pk=campaign_id)
        campaign.status = status

        if 'recipient_count' in kwargs:
            campaign.recipient_count = kwargs['recipient_count']
        if 'response_summary' in kwargs:
            campaign.response_summary = kwargs['response_summary']
        if 'error_message' in kwargs:
            campaign.error_message = kwargs['error_message']

        campaign.save(update_fields=['status', 'recipient_count', 'response_summary', 'error_message'])
        logger.info(f"[CELERY SMS] Campaign {campaign_id} updated to status='{status}'")
    except SMSCampaign.DoesNotExist:
        logger.warning(f"[CELERY SMS] Campaign {campaign_id} not found for status update.")
    except Exception as e:
        logger.error(f"[CELERY SMS] Error updating campaign {campaign_id}: {e}")
