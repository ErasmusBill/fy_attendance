import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import AttendanceSession, AttendanceRecord
from apps.members.models import Location

logger = logging.getLogger(__name__)


def invalidate_attendance_dashboard_caches():
    """
    Clears all cached dashboard statistics, metrics, and trend charts.
    """
    keys_to_clear = [
        "dashboard_metrics_data",
        "att_dashboard_stats",
        "att_dashboard_all",
        "global_active_session",
        "active_session_obj",
        "active_sessions_list",
    ]
    for key in keys_to_clear:
        cache.delete(key)
    logger.debug("[CACHE INVALIDATION] Cleared attendance dashboard metrics caches.")


@receiver(post_save, sender=AttendanceRecord)
def on_attendance_record_saved(sender, instance, created, **kwargs):
    """
    Triggered when an attendee checks in or is updated.
    Invalidates session attendee counts, dashboard metrics, and member history.
    """
    if instance.session_id:
        cache.delete(f"session_stats_{instance.session_id}")
        cache.delete(f"session_records_{instance.session_id}")
        cache.delete(f"session_attendee_ids_{instance.session_id}")

    if instance.member_id:
        cache.delete(f"member_att_{instance.member_id}")

    invalidate_attendance_dashboard_caches()
    logger.info(f"[CACHE INVALIDATION] Invalidated caches for check-in record {instance.id} (Session: {instance.session_id}).")


@receiver(post_delete, sender=AttendanceRecord)
def on_attendance_record_deleted(sender, instance, **kwargs):
    """
    Triggered when an attendance record is removed.
    """
    if instance.session_id:
        cache.delete(f"session_stats_{instance.session_id}")
        cache.delete(f"session_records_{instance.session_id}")
        cache.delete(f"session_attendee_ids_{instance.session_id}")

    if instance.member_id:
        cache.delete(f"member_att_{instance.member_id}")

    invalidate_attendance_dashboard_caches()
    logger.info(f"[CACHE INVALIDATION] Invalidated caches after deleting check-in record {instance.id}.")


@receiver(post_save, sender=AttendanceSession)
def on_session_saved(sender, instance, created, **kwargs):
    """
    Triggered when an attendance service session is created, updated, or toggled active/closed.
    """
    cache.delete("global_active_session")
    cache.delete("active_session_obj")
    cache.delete("active_sessions_list")
    cache.delete(f"session_stats_{instance.id}")
    cache.delete(f"session_records_{instance.id}")
    cache.delete(f"session_attendee_ids_{instance.id}")
    invalidate_attendance_dashboard_caches()
    logger.info(f"[CACHE INVALIDATION] Invalidated caches for session {instance.id} ({instance.title}).")


@receiver(post_delete, sender=AttendanceSession)
def on_session_deleted(sender, instance, **kwargs):
    """
    Triggered when an attendance service session is removed.
    """
    cache.delete("global_active_session")
    cache.delete("active_session_obj")
    cache.delete("active_sessions_list")
    cache.delete(f"session_stats_{instance.id}")
    cache.delete(f"session_records_{instance.id}")
    cache.delete(f"session_attendee_ids_{instance.id}")
    invalidate_attendance_dashboard_caches()
    logger.info(f"[CACHE INVALIDATION] Invalidated caches after deleting session {instance.id}.")


@receiver(post_save, sender=Location)
def on_location_saved(sender, instance, created, **kwargs):
    cache.delete("all_locations")
    logger.info(f"[CACHE INVALIDATION] Invalidated all_locations after saving location {instance.id}.")


@receiver(post_delete, sender=Location)
def on_location_deleted(sender, instance, **kwargs):
    cache.delete("all_locations")
    logger.info(f"[CACHE INVALIDATION] Invalidated all_locations after deleting location {instance.id}.")
