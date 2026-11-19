import base64
import io
import logging
import math
import qrcode
from qrcode.image.pil import PilImage

logger = logging.getLogger(__name__)

EARTH_RADIUS_METERS = 6371000.0  # Earth radius in meters


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Computes the great-circle distance between two GPS coordinates (in decimal degrees)
    using the Haversine formula.

    Returns:
        float: Distance in meters between the two points.
    """
    try:
        lat1_rad = math.radians(float(lat1))
        lon1_rad = math.radians(float(lon1))
        lat2_rad = math.radians(float(lat2))
        lon2_rad = math.radians(float(lon2))

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

        distance = EARTH_RADIUS_METERS * c
        return round(distance, 2)
    except (ValueError, TypeError) as e:
        logger.error(f"Error computing haversine distance: {e}")
        return float('inf')


def verify_geofence(user_lat, user_lon, location):
    """
    Verifies if user's coordinates are inside the church premises geofence.

    Args:
        user_lat: Submitted latitude from user's device
        user_lon: Submitted longitude from user's device
        location: Location model instance with latitude, longitude, radius

    Returns:
        tuple: (is_inside: bool, distance_meters: float, message: str)
    """
    if not location or location.latitude is None or location.longitude is None:
        return False, 0.0, "Church location coordinates are not configured."

    distance = haversine_distance(user_lat, user_lon, location.latitude, location.longitude)
    allowed_radius = float(location.radius or 50.0)

    if distance <= allowed_radius:
        return True, distance, f"Verified within church grounds ({distance:.1f}m from center)."
    else:
        return (
            False,
            distance,
            f"Outside church premises. You are {distance:.1f}m away (maximum allowed radius is {allowed_radius:.0f}m)."
        )


def generate_qr_code_base64(url, box_size=10, border=3):
    """
    Generates a QR code image as a base64 encoded data URI string for embedding directly into HTML.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#1052ba", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_img = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{b64_img}"


def send_member_id_sms(member):
    """
    Dispatches the generated Member ID to the member's phone number
    via Mnotify SMS as a background Celery task. If Celery is unreachable,
    falls back to synchronous dispatch.
    """
    from apps.common.tasks import send_member_id_sms_task

    try:
        send_member_id_sms_task.delay(member.pk)
        logger.info(f"[MNOTIFY] Queued Member ID SMS task for {member.phone_number} ({member.member_id})")
        return True
    except Exception as e:
        logger.warning(f"[MNOTIFY] Celery queue unavailable ({e}). Falling back to direct dispatch...")
        try:
            from apps.common.mnotify import dispatch_single_member_sms
            message = (
                f"Hello {member.name}, your Church Attendance Member ID is: {member.member_id}. "
                f"Present or enter this ID when scanning the check-in QR code. God bless you!"
            )
            success, resp_msg = dispatch_single_member_sms(member, message)
            logger.info(f"[MNOTIFY] Direct dispatch result: {success} - {resp_msg}")
            return success
        except Exception as direct_err:
            logger.error(f"[MNOTIFY] Direct dispatch also failed: {direct_err}")
            return False
