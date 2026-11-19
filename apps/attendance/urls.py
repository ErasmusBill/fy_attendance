from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    # Permanent Entrance QR Code Check-in (Print Once for the Entrance Door)
    path('entrance/', views.entrance_check_in, name='entrance_checkin'),
    path('entrance/<uuid:location_id>/', views.entrance_check_in, name='entrance_checkin_loc'),

    # Printable Entrance Door Posters (High-res QR + Instructions)
    path('poster/', views.entrance_poster, name='entrance_poster'),
    path('poster/<uuid:location_id>/', views.entrance_poster, name='entrance_poster_loc'),

    # Public QR Code Scan & Check-in URL (Session-specific fallback)
    path('check-in/<uuid:session_code>/', views.check_in, name='check_in'),

    # Central Attendance Register Dashboard (Filtered by Date, Month, Year, Session, Dept)
    path('dashboard/', views.attendance_dashboard, name='attendance_dashboard'),
    path('dashboard/export/', views.attendance_dashboard_export, name='attendance_dashboard_export'),
    path('quick-checkin/', views.quick_mark_attendance, name='quick_mark_attendance'),

    # Usher Desk - Manual Check-In & Quick Member Registration
    path('usher-desk/', views.usher_desk, name='usher_desk'),
    path('usher-desk/<uuid:session_id>/', views.usher_desk, name='usher_desk_session'),
    path('usher-desk/<uuid:session_id>/checkin/<uuid:member_id>/', views.usher_mark_checkin, name='usher_checkin'),
    path('usher-desk/<uuid:session_id>/undo/<uuid:member_id>/', views.usher_undo_checkin, name='usher_undo_checkin'),
    path('usher-desk/<uuid:session_id>/quick-add/', views.usher_quick_add_member, name='usher_quick_add'),

    # Admin Session Management
    path('sessions/', views.session_list, name='session_list'),
    path('sessions/create/', views.session_create, name='session_create'),
    path('sessions/<uuid:session_id>/', views.session_detail, name='session_detail'),
    path('sessions/<uuid:session_id>/delete/', views.session_delete, name='session_delete'),
    path('sessions/<uuid:session_id>/records/', views.session_records, name='session_records'),
    path('sessions/<uuid:session_id>/toggle/', views.session_toggle_active, name='session_toggle'),
    path('sessions/<uuid:session_id>/export/', views.session_export_excel, name='session_export'),

    # SMS Dispatch
    path('members/<uuid:member_id>/send-sms/', views.send_member_sms, name='send_member_sms'),

    # Location & Geofencing Configuration
    path('locations/', views.location_list, name='location_list'),
    path('locations/create/', views.location_create, name='location_create'),
    path('locations/<uuid:location_id>/edit/', views.location_update, name='location_update'),
    path('locations/<uuid:location_id>/calibrate/', views.location_calibrate, name='location_calibrate'),
]
