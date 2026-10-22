"""
accounts/authentication.py
Custom JWT authentication that reads tokens from httpOnly cookies.
Falls back to Bearer header for API integrations and testing.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.conf import settings


class CookieJWTAuthentication(JWTAuthentication):
    """
    Read JWT from httpOnly cookie 'access_token'.
    Falls back to 'Authorization: Bearer ...' header if cookie is absent.
    """

    def authenticate(self, request):
        # Try cookie first
        raw_token = request.COOKIES.get(settings.SIMPLE_JWT.get('AUTH_COOKIE', 'access_token'))

        if raw_token is None:
            # Fall back to header (useful for API clients, CI tests)
            return super().authenticate(request)

        try:
            validated_token = self.get_validated_token(raw_token)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        return self.get_user(validated_token), validated_token
