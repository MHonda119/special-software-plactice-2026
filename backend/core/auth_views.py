from datetime import datetime, timezone as datetime_timezone

from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import (
    LOGIN_TIMESTAMP_SESSION_KEY,
    SESSION_LIFETIME_SECONDS,
)
from .serializers import AuthLoginSerializer


def _auth_response(user, login_timestamp):
    expires_at = datetime.fromtimestamp(
        login_timestamp + SESSION_LIFETIME_SECONDS,
        tz=datetime_timezone.utc,
    )
    return {
        "user": {"id": user.pk, "username": user.get_username()},
        "expires_at": expires_at.isoformat(),
    }


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AuthLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        login(request, user)
        login_timestamp = timezone.now().timestamp()
        request.session[LOGIN_TIMESTAMP_SESSION_KEY] = login_timestamp
        return Response(_auth_response(user, login_timestamp), status=status.HTTP_200_OK)


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    def get(self, request):
        login_timestamp = request.session[LOGIN_TIMESTAMP_SESSION_KEY]
        return Response(
            _auth_response(request.user, login_timestamp),
            status=status.HTTP_200_OK,
        )
