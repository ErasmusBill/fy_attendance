from django.db import models
from django.conf import settings
from apps.common.models import BaseModel
from apps.common.utils import generate_member_id

# Create your models here.


class Department(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Members(BaseModel):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='members')
    member_id = models.CharField(max_length=20, unique=True, blank=True, db_index=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, unique=True)
    address = models.TextField()
    date_of_birth = models.DateField()

    def save(self, *args, **kwargs):
        if not self.member_id:
            self.member_id = generate_member_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.member_id})"


class Location(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    radius = models.DecimalField(max_digits=7, decimal_places=2, help_text="Radius in meters")
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.radius}m radius)"


class SMSCampaign(BaseModel):
    TARGET_CHOICES = [
        ('all', 'All Congregants'),
        ('department', 'Specific Department'),
        ('session_present', 'Present Attendees at Service'),
        ('session_absent', 'Absent Members from Service'),
        ('birthday', 'Birthday Celebrants'),
        ('custom', 'Custom Phone Numbers'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending (Queued)'),
        ('sent', 'Delivered / Sent'),
        ('simulated', 'Simulated (Dev Mode)'),
        ('failed', 'Failed'),
    ]

    sender_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_campaigns'
    )
    title = models.CharField(max_length=200, blank=True)
    target_type = models.CharField(max_length=50, choices=TARGET_CHOICES, default='all')
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_campaigns'
    )
    session_title = models.CharField(max_length=255, blank=True)
    sender_id = models.CharField(max_length=11, default='CHURCH')
    message = models.TextField()
    recipient_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='sent')
    response_summary = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'SMS Campaign'
        verbose_name_plural = 'SMS Campaigns'

    def __str__(self):
        return f"{self.title or self.get_target_type_display()} - {self.recipient_count} recipients ({self.created_at.strftime('%b %d, %Y %I:%M %p')})"
