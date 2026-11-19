from django.core.cache import cache
from apps.members.models import Department, Location
from apps.attendance.models import AttendanceSession
from apps.users.models import Roles


def global_church_context(request):
    """
    Supplies global church system state across all authenticated views:
    - Active church service session (for quick attendance check-in modal)
    - Department choices (for global Add Member modal)
    - Role flags (is_admin, is_usher, is_pastor)
    Cached with automatic signal-driven invalidation.
    """
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}

    role = getattr(request.user, 'role', '')
    is_admin = role == Roles.ADMIN or request.user.is_staff or request.user.is_superuser
    is_usher = role == Roles.USHER
    is_pastor = role == Roles.PASTOR

    # 1. Cached active session
    active_session = cache.get("global_active_session")
    if active_session is None:
        try:
            active_session = AttendanceSession.objects.filter(is_active=True).order_by('-date', '-start_time').first()
            cache.set("global_active_session", active_session, 300)
        except Exception:
            active_session = None

    # 2. Cached departments
    departments = cache.get("global_departments")
    if departments is None:
        try:
            departments = list(Department.objects.all().order_by('name'))
            cache.set("global_departments", departments, 600)
        except Exception:
            departments = []

    return {
        'global_active_session': active_session,
        'global_departments': departments,
        'is_admin': is_admin,
        'is_usher': is_usher,
        'is_pastor': is_pastor,
    }
