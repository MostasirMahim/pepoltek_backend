"""
accounts/serializers.py
Request validation only. No business logic here - delegate to services.py.
"""
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import User, ConsentRecord


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=4)
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    referral_code = serializers.CharField(max_length=12, required=False, allow_blank=True)
    consents = serializers.ListField(child=serializers.DictField(), required=False)

    def validate_password(self, value):
        validate_password(value)
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'full_name', 'auth_provider', 'status',
            'mfa_enabled', 'referral_code', 'roles', 'created_at', 'last_login_at',
        ]
        read_only_fields = ['id', 'email', 'auth_provider', 'referral_code',
                            'created_at', 'last_login_at']

    def get_roles(self, obj) -> list[str]:
        return obj.get_roles()


class ConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsentRecord
        fields = ['policy_type', 'policy_version', 'agreed', 'agreed_at']
        read_only_fields = ['agreed_at']
