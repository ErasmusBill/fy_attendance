import re
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def normalize_phone_number(phone_str):
    """
    Cleans and normalizes phone numbers into standard Mnotify format.
    Handles Ghana networks (MTN, Telecel, AT) and international formats.
    Example:
        '+233 24 123 4567' -> '0241234567'
        '233241234567'     -> '0241234567'
        '024-123-4567'     -> '0241234567'
    """
    if not phone_str:
        return ""

    # Remove all non-digit characters except leading plus
    cleaned = re.sub(r'[\s\-\(\)\.]', '', str(phone_str).strip())

    # Handle +233 or 233 prefix for Ghana numbers
    if cleaned.startswith('+233'):
        cleaned = '0' + cleaned[4:]
    elif cleaned.startswith('233') and len(cleaned) == 12:
        cleaned = '0' + cleaned[3:]

    return cleaned


def get_mnotify_balance():
    """
    Queries Mnotify API for current SMS credit balance.
    Endpoint: GET https://api.mnotify.com/api/balance/sms?key=<API_KEY>

    Returns:
        dict: {'success': bool, 'balance': float, 'bonus': float, 'raw': dict}
    """
    api_key = getattr(settings, 'MNOTIFY_API_KEY', '').strip()
    api_url = getattr(settings, 'MNOTIFY_API_URL', 'https://api.mnotify.com/api/').rstrip('/')

    if not api_key:
        return {
            'success': False,
            'simulated': True,
            'balance': 0,
            'message': 'Mnotify API Key is not configured in settings or .env file.'
        }

    url = f"{api_url}/balance/sms?key={api_key}"

    try:
        response = requests.get(url, timeout=8)
        data = response.json()

        if response.status_code == 200 and data.get('status') == 'success':
            return {
                'success': True,
                'balance': float(data.get('balance', 0)),
                'bonus': float(data.get('bonus', 0)),
                'raw': data,
            }
        else:
            return {
                'success': False,
                'message': data.get('message', 'Failed to retrieve balance from Mnotify.'),
                'raw': data,
            }
    except Exception as e:
        logger.error(f"[MNOTIFY] Error checking SMS balance: {e}")
        return {
            'success': False,
            'message': str(e),
        }


def send_mnotify_bulk_sms(recipients, message, sender_id=None):
    """
    Sends bulk SMS via Mnotify Quick SMS endpoint.
    Endpoint: POST https://api.mnotify.com/api/sms/quick?key=<API_KEY>

    Args:
        recipients (list[str]): List of raw or normalized phone numbers.
        message (str): SMS text body.
        sender_id (str, optional): Max 11 characters alphanumeric sender ID.

    Returns:
        dict: Standardized result with keys:
              success (bool), status (str), total_sent (int), message (str), details (dict)
    """
    api_key = getattr(settings, 'MNOTIFY_API_KEY', '').strip()
    api_url = getattr(settings, 'MNOTIFY_API_URL', 'https://api.mnotify.com/api/').rstrip('/')
    default_sender = getattr(settings, 'MNOTIFY_SENDER_ID', 'CHURCH')[:11]
    sender = (sender_id or default_sender).strip()[:11]

    # Normalize and deduplicate recipient phone numbers
    cleaned_numbers = []
    seen = set()
    for num in recipients:
        normalized = normalize_phone_number(num)
        if normalized and len(normalized) >= 9 and normalized not in seen:
            cleaned_numbers.append(normalized)
            seen.add(normalized)

    if not cleaned_numbers:
        return {
            'success': False,
            'status': 'error',
            'total_sent': 0,
            'message': 'No valid phone numbers found among the selected recipients.',
            'details': {}
        }

    # If no API key is provided, simulate successful dispatch gracefully
    if not api_key:
        logger.warning(
            f"[MNOTIFY SIMULATION] MNOTIFY_API_KEY is not configured. "
            f"Simulating dispatch to {len(cleaned_numbers)} recipients. "
            f"Sender: {sender} | Sample Recipient: {cleaned_numbers[0]}"
        )
        print(f"\n=======================================================")
        print(f" [MNOTIFY SMS DISPATCH - SIMULATED / LOCAL DEV]")
        print(f" Sender ID  : {sender}")
        print(f" Recipients : {len(cleaned_numbers)} numbers -> {cleaned_numbers[:5]}...")
        print(f" Message    : {message}")
        print(f"=======================================================\n")

        return {
            'success': True,
            'status': 'simulated',
            'total_sent': len(cleaned_numbers),
            'message': f"Simulated delivery to {len(cleaned_numbers)} recipient(s) (MNOTIFY_API_KEY not configured).",
            'details': {
                'recipients': cleaned_numbers,
                'sender': sender,
                'simulated': True,
            }
        }

    # Real dispatch to Mnotify API
    url = f"{api_url}/sms/quick?key={api_key}"
    payload = {
        "recipient": cleaned_numbers,
        "sender": sender,
        "message": message,
        "is_schedule": False,
        "schedule_date": ""
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        data = response.json()

        # Mnotify code 2000 or status 'success' represents successful dispatch
        is_success = response.status_code in [200, 201] and (
            data.get('status') == 'success' or str(data.get('code')) in ['2000', '200']
        )

        summary = data.get('summary', {})
        total_sent = summary.get('total_sent', len(cleaned_numbers)) if is_success else 0

        logger.info(
            f"[MNOTIFY API] Sent to {len(cleaned_numbers)} recipients. "
            f"Status: {data.get('status')} | Code: {data.get('code')}"
        )

        return {
            'success': is_success,
            'status': data.get('status', 'unknown'),
            'code': data.get('code'),
            'total_sent': total_sent,
            'message': data.get('message', 'SMS processed by Mnotify.'),
            'summary': summary,
            'details': data
        }

    except requests.exceptions.Timeout:
        logger.error("[MNOTIFY] Request timed out while connecting to Mnotify.")
        return {
            'success': False,
            'status': 'timeout',
            'total_sent': 0,
            'message': 'Connection to Mnotify timed out. Please check your internet connection.',
            'details': {}
        }
    except Exception as e:
        logger.error(f"[MNOTIFY] Unexpected error during dispatch: {e}")
        return {
            'success': False,
            'status': 'error',
            'total_sent': 0,
            'message': f"Failed to send SMS via Mnotify: {str(e)}",
            'details': {}
        }


def dispatch_single_member_sms(member, message, sender_id=None):
    """
    Convenience method for sending a single SMS to a congregant.
    """
    if not member or not member.phone_number:
        return False, "Member has no phone number recorded."

    res = send_mnotify_bulk_sms([member.phone_number], message, sender_id=sender_id)
    return res['success'], res.get('message', '')
