from django.contrib.auth import authenticate, login, logout
from django.utils.dateparse import parse_datetime
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .authentication import (
    AUTH_SESSION_EXPIRES_AT_KEY,
    format_auth_session_expiry,
    set_auth_session_expiry,
)
from .permissions import IsAuthenticated


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=150,
        trim_whitespace=False,
    )
    password = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=False,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    SessionAuthentication().enforce_csrf(request)
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = authenticate(
        request=request._request,
        username=serializer.validated_data["username"],
        password=serializer.validated_data["password"],
    )
    if user is None:
        return Response(
            {"detail": "Invalid username or password."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    login(request._request, user)
    expires_at = set_auth_session_expiry(request._request.session)
    return Response(
        {
            "user": {
                "id": user.pk,
                "username": user.get_username(),
            },
            "expires_at": format_auth_session_expiry(expires_at),
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request._request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    expires_at = parse_datetime(
        request._request.session[AUTH_SESSION_EXPIRES_AT_KEY]
    )
    return Response(
        {
            "user": {
                "id": request.user.pk,
                "username": request.user.get_username(),
            },
            "expires_at": format_auth_session_expiry(expires_at),
        },
        status=status.HTTP_200_OK,
    )
