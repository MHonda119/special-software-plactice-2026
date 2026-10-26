import math

from django.contrib.auth import logout
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone


LOGIN_TIMESTAMP_SESSION_KEY = "auth_login_timestamp"
SESSION_LIFETIME_SECONDS = 43_200


class AbsoluteSessionExpiryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            self._ensure_valid_session(request)

        response = self.get_response(request)

        if request.user.is_authenticated:
            self._record_login_timestamp(request)

        return response

    def _ensure_valid_session(self, request):
        login_timestamp = request.session.get(LOGIN_TIMESTAMP_SESSION_KEY)
        now_timestamp = timezone.now().timestamp()

        try:
            valid_timestamp = (
                not isinstance(login_timestamp, bool)
                and isinstance(login_timestamp, (int, float))
                and math.isfinite(login_timestamp)
                and login_timestamp >= 0
            )
        except OverflowError:
            valid_timestamp = False

        if (
            not valid_timestamp
            or now_timestamp >= login_timestamp + SESSION_LIFETIME_SECONDS
        ):
            logout(request)
            request.user = AnonymousUser()

    def _record_login_timestamp(self, request):
        if LOGIN_TIMESTAMP_SESSION_KEY not in request.session:
            request.session[LOGIN_TIMESTAMP_SESSION_KEY] = timezone.now().timestamp()
