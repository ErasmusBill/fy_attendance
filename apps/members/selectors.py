from django.shortcuts import get_object_or_404
from apps.members.models import Members, Department, Location
from django.core.cache import cache

CACHE_TTL = 60 * 5  # 5 minutes


def get_all_members():
    cache_key = "all_members"
    members = cache.get(cache_key)
    if members is None:
        members = list(Members.objects.select_related('department').all().order_by('-created_at'))
        cache.set(cache_key, members, CACHE_TTL)
    return members


def get_member_by_id(member_id):
    cache_key = f"member_{member_id}"
    member = cache.get(cache_key)
    if member is None:
        member = get_object_or_404(Members.objects.select_related('department'), id=member_id)
        cache.set(cache_key, member, CACHE_TTL)
    return member


def get_all_members_by_department(department_id):
    cache_key = f"members_department_{department_id}"
    members = cache.get(cache_key)
    if members is None:
        members = list(Members.objects.filter(department_id=department_id).order_by('-created_at'))
        cache.set(cache_key, members, CACHE_TTL)
    return members


def get_all_departments():
    cache_key = "all_departments"
    departments = cache.get(cache_key)
    if departments is None:
        departments = list(Department.objects.all().order_by('name'))
        cache.set(cache_key, departments, CACHE_TTL)
    return departments


def get_department_by_id(department_id):
    cache_key = f"department_{department_id}"
    department = cache.get(cache_key)
    if department is None:
        department = get_object_or_404(Department, id=department_id)
        cache.set(cache_key, department, CACHE_TTL)
    return department
