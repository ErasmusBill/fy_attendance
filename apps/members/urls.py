from django.urls import path
from . import views

app_name = 'members'

urlpatterns = [
    # Members routes
    path('', views.member_list, name='member_list'),
    path('create/', views.member_create, name='member_create'),
    path('<uuid:member_id>/edit/', views.member_update, name='member_update'),
    path('<uuid:member_id>/delete/', views.member_delete, name='member_delete'),

    # Bulk upload & template download
    path('bulk-upload/', views.bulk_upload_members, name='bulk_upload'),
    path('download-template/', views.download_member_template, name='download_template'),

    # Bulk SMS routes (Mnotify integration for Admin, Clergy, Ushers)
    path('sms/', views.bulk_sms_view, name='bulk_sms'),
    path('sms/recipient-count/', views.sms_recipient_count, name='sms_recipient_count'),

    # Department routes
    path('departments/', views.department_list, name='department_list'),
    path('departments/create/', views.department_create, name='department_create'),
    path('departments/<uuid:department_id>/edit/', views.department_update, name='department_update'),
    path('departments/<uuid:department_id>/delete/', views.department_delete, name='department_delete'),
]
