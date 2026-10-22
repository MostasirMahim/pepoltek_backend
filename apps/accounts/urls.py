from django.urls import path
from . import views

urlpatterns = [
    path('register', views.register, name='auth-register'),
    path('login', views.login, name='auth-login'),
    path('logout', views.logout, name='auth-logout'),
    path('refresh', views.CookieTokenRefreshView.as_view(), name='auth-refresh'),
    path('me', views.me, name='auth-me'),
    path('admin/telemetry', views.admin_telemetry, name='admin-telemetry'),
    path('admin/users', views.admin_users_list, name='admin-users-list'),
    path('admin/roles', views.admin_roles_catalogue, name='admin-roles-catalogue'),
    path('admin/roles/<str:role_code>', views.admin_role_detail, name='admin-role-detail'),
    path('admin/permissions-catalogue', views.admin_permissions_catalogue, name='admin-permissions-catalogue'),
    path('admin/users/<str:user_id>/roles', views.admin_update_user_roles, name='admin-update-user-roles'),
    path('admin/users/<str:user_id>/status', views.admin_update_user_status, name='admin-update-user-status'),
    path('admin/users/<str:user_id>', views.admin_delete_user, name='admin-delete-user'),
    path('admin/invite-staff', views.admin_invite_staff, name='admin-invite-staff'),

    path('resend-otp', views.resend_verification_otp, name='auth-resend-otp'),
    path('verify-otp', views.verify_email_otp, name='auth-verify-otp'),
    path('change-email', views.change_verification_email, name='auth-change-email'),
    path('google/login', views.google_oauth_login, name='google-login'),
    path('google/callback', views.google_oauth_callback, name='google-callback'),
    path('google/verify', views.google_token_verify, name='google-verify'),
]
