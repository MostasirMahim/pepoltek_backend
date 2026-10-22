"""
core/permissions.py
Shared base permission classes used across all apps.
App-specific permissions live in their own permissions.py.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsStaff(BasePermission):
    """Any authenticated staff user (Recruiter, BA, Admin, etc.)."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsAdminRole(BasePermission):
    """User holds ADMIN or SUPER_ADMIN role or is_superuser."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'is_superuser', False):
            return True
        return request.user.has_role('ADMIN') or request.user.has_role('SUPER_ADMIN')


class ReadOnly(BasePermission):
    """Allow all safe (GET/HEAD/OPTIONS) methods."""
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
