from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from apps.members.models import Members, Department


@receiver(pre_save, sender=Members)
def track_previous_member_department(sender, instance, **kwargs):
    """
    Tracks previous department before saving in case a member moves between departments.
    """
    if instance.pk:
        try:
            old = Members.objects.filter(pk=instance.pk).values('department_id').first()
            instance._old_department_id = old['department_id'] if old else None
        except Exception:
            instance._old_department_id = None
    else:
        instance._old_department_id = None


@receiver(post_save, sender=Members)
def invalidate_member_cache_on_save(sender, instance, **kwargs):
    """
    Invalidates cached member data when a member is added or modified.
    """
    cache.delete("all_members")
    cache.delete(f"member_{instance.id}")

    if instance.department_id:
        cache.delete(f"members_department_{instance.department_id}")

    old_dept = getattr(instance, '_old_department_id', None)
    if old_dept and old_dept != instance.department_id:
        cache.delete(f"members_department_{old_dept}")


@receiver(post_delete, sender=Members)
def invalidate_member_cache_on_delete(sender, instance, **kwargs):
    """
    Invalidates cached member data when a member is deleted.
    """
    cache.delete("all_members")
    cache.delete(f"member_{instance.id}")
    if instance.department_id:
        cache.delete(f"members_department_{instance.department_id}")


@receiver(post_save, sender=Department)
def invalidate_department_cache_on_save(sender, instance, **kwargs):
    """
    Invalidates cached department data when a department is created or updated.
    """
    cache.delete("all_departments")
    cache.delete(f"department_{instance.id}")
    cache.delete(f"members_department_{instance.id}")
    cache.delete("all_members")


@receiver(post_delete, sender=Department)
def invalidate_department_cache_on_delete(sender, instance, **kwargs):
    """
    Invalidates cached department data when a department is deleted.
    """
    cache.delete("all_departments")
    cache.delete(f"department_{instance.id}")
    cache.delete(f"members_department_{instance.id}")
    cache.delete("all_members")
