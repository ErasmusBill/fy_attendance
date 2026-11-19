import uuid
from django.db import models
from django.utils import timezone
from django.urls import reverse
from apps.common.models import BaseModel
from apps.members.models import Members, Location
from .utils import generate_qr_code_base64


class AttendanceSession(BaseModel):
    title = models.CharField(max_length=200, help_text="e.g. Sunday Celebration Service, Youth Encounter")
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='attendance_sessions',
        help_text="Church sanctuary location and geofence boundary"
    )
    date = models.DateField(default=timezone.now)
    start_time = models.TimeField(default=timezone.now)
    end_time = models.TimeField(blank=True, null=True)
    session_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    is_active = models.BooleanField(default=True, help_text="Turn off to close check-in for this service")

    class Meta:
        ordering = ('-date', '-start_time')

    def __str__(self):
        return f"{self.title} - {self.date.strftime('%b %d, %Y')}"

    def get_checkin_url(self, request=None):
        path = reverse('attendance:check_in', kwargs={'session_code': self.session_code})
        if request:
            return request.build_absolute_uri(path)
        return path

    def get_qr_code_base64(self, request=None):
        url = self.get_checkin_url(request=request)
        return generate_qr_code_base64(url)

    @property
    def total_attendees(self):
        return self.records.count()


class AttendanceRecord(BaseModel):
    session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name='records'
    )
    member = models.ForeignKey(
        Members,
        on_delete=models.CASCADE,
        related_name='attendances'
    )
    check_in_time = models.DateTimeField(auto_now_add=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, help_text="GPS Latitude at check-in")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, help_text="GPS Longitude at check-in")
    distance_meters = models.DecimalField(max_digits=8, decimal_places=2, help_text="Distance from church center")
    status = models.CharField(
        max_length=20,
        choices=[('present', 'Present'), ('late', 'Late')],
        default='present'
    )
    device_info = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ('-check_in_time',)
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'member'],
                name='unique_member_session_checkin'
            )
        ]

    def __str__(self):
        return f"{self.member.name} ({self.member.member_id}) - {self.session.title}"
