from datetime import datetime, timezone as datetime_timezone
import math

from django.contrib.auth import logout
from django.utils import timezone
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed

LOGIN_TIMESTAMP_SESSION_KEY = "core_auth_login_timestamp"
AUTH_SESSION_MAX_AGE_SECONDS = 43_200


def expires_at_for(login_timestamp: float) -> datetime:
    return datetime.fromtimestamp(
        login_timestamp + AUTH_SESSION_MAX_AGE_SECONDS,
        tz=datetime_timezone.utc,
    )


def format_datetime(value: datetime) -> str:
    return (
        value.astimezone(datetime_timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


class FixedExpirySessionAuthentication(SessionAuthentication):
    """Django session authentication with a non-sliding 12-hour login limit."""

    def authenticate(self, request):
        authenticated = super().authenticate(request)
        if authenticated is None:
            return None

        user, auth = authenticated
        login_timestamp = request.session.get(LOGIN_TIMESTAMP_SESSION_KEY)
        if (
            isinstance(login_timestamp, bool)
            or not isinstance(login_timestamp, (int, float))
            or not math.isfinite(login_timestamp)
        ):
            raise AuthenticationFailed("Authentication session is invalid.")

        expires_at = login_timestamp + AUTH_SESSION_MAX_AGE_SECONDS
        if timezone.now().timestamp() >= expires_at:
            logout(request._request)
            raise AuthenticationFailed("Authentication expired.")

        return user, auth

    def authenticate_header(self, request):
        return "Session"
