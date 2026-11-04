from datetime import timedelta, timezone as datetime_timezone

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.authentication import SessionAuthentication


AUTH_SESSION_EXPIRES_AT_KEY = "auth_session_expires_at"
AUTH_SESSION_DURATION = timedelta(seconds=43200)


def set_auth_session_expiry(session):
    expires_at = timezone.now() + AUTH_SESSION_DURATION
    expires_at = expires_at.astimezone(datetime_timezone.utc)
    session[AUTH_SESSION_EXPIRES_AT_KEY] = expires_at.isoformat()
    return expires_at


def format_auth_session_expiry(expires_at):
    return (
        expires_at.astimezone(datetime_timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


class AbsoluteExpirySessionAuthentication(SessionAuthentication):
    def authenticate(self, request):
        authenticated = super().authenticate(request)
        if authenticated is None:
            return None

        session = request._request.session
        expiry_value = session.get(AUTH_SESSION_EXPIRES_AT_KEY)
        if expiry_value is None:
            return None

        expires_at = parse_datetime(expiry_value)
        if expires_at is None or timezone.is_naive(expires_at):
            session.flush()
            return None

        expires_at = expires_at.astimezone(datetime_timezone.utc)
        if timezone.now() >= expires_at:
            session.flush()
            return None

        return authenticated

    def authenticate_header(self, request):
        return "Session"
