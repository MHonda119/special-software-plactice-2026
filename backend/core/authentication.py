from django.contrib.auth import logout
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed

AUTH_SESSION_SECONDS = 43200
AUTH_EXPIRES_AT = "auth_expires_at"


class FixedExpirySessionAuthentication(SessionAuthentication):
    def authenticate(self, request):
        user = getattr(request._request, "user", None)
        if not user or not user.is_active:
            return None
        raw_expiry = request.session.get(AUTH_EXPIRES_AT)
        try:
            expiry = parse_datetime(raw_expiry) if isinstance(raw_expiry, str) else None
        except ValueError:
            expiry = None
        if expiry is None or timezone.is_naive(expiry) or timezone.now() >= expiry:
            logout(request._request)
            raise AuthenticationFailed("Authentication session has expired.")
        self.enforce_csrf(request)
        return user, None

    def authenticate_header(self, request):
        return "Session"
