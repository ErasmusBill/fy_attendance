from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('', views.login_user, name='home'),
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),

    # Password Reset Flow
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('password-reset/done/', views.password_reset_done, name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('password-reset-complete/', views.password_reset_complete, name='password_reset_complete'),

    # Dashboard & User Management
    path('dashboard/', views.main_dashboard, name='admin_dashboard'),
    path('staff-accounts/', views.staff_users_dashboard, name='staff_users_dashboard'),
    path('change-password/', views.change_password, name='change_password'),
    path('users/create/', views.admin_create_user, name='admin_create_user'),
    path('users/<uuid:user_id>/update/', views.admin_update_user, name='admin_update_user'),
    path('users/<uuid:user_id>/delete/', views.admin_delete_user, name='admin_delete_user'),
]
