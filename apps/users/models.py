from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.common.models import BaseModel
from .manager import UserManager
from django.utils.translation import gettext_lazy as _


# Create your models here.

class Roles(models.TextChoices):
    ADMIN = 'admin', _('Administrator')
    PASTOR = 'pastor', _('Pastor / Minister')
    USHER = 'usher', _('Usher / Protocol Team')
    STAFF = 'staff', _('Church Staff')
    USER = 'user', _('General Staff')  

# Backwards compatibility alias
Roles.ADMIN_USER = Roles.ADMIN

class User(BaseModel, AbstractUser):
    username = None

    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=255, unique=True, blank=True, null=True)

    role = models.CharField(choices=Roles.choices, default=Roles.USHER, max_length=255)

    objects = UserManager()

    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'phone_number']

    @property
    def is_admin_role(self):
        return self.role == Roles.ADMIN or self.is_superuser or self.is_staff

    @property
    def is_pastor_role(self):
        return self.role == Roles.PASTOR

    @property
    def is_usher_role(self):
        return self.role == Roles.USHER

    @property
    def can_mark_attendance(self):
        """Allows ushers, pastors, staff, and admins to operate the Usher Desk."""
        return self.role in [Roles.ADMIN, Roles.PASTOR, Roles.USHER, Roles.STAFF, Roles.USER] or self.is_staff or self.is_superuser

    @property
    def can_manage_system(self):
        """Allows church admins and superusers to manage settings, departments, users, and locations."""
        return self.role == Roles.ADMIN or self.is_staff or self.is_superuser

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class UserProfile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    date_of_birth = models.DateField(help_text="For birthday wishes")
    avatar = models.ImageField(upload_to='uploads/avatar')
    location = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"