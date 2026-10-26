from django.contrib.auth import authenticate, get_user_model, login, logout
from django.utils import timezone
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .authentication import (
    AUTH_SESSION_MAX_AGE_SECONDS,
    LOGIN_TIMESTAMP_SESSION_KEY,
    FixedExpirySessionAuthentication,
    expires_at_for,
    format_datetime,
)


def _public_user(user):
    return {"id": user.pk, "username": user.get_username()}


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login_view(request):
    csrf_response = CsrfViewMiddleware(lambda _: None).process_view(
        request._request,
        lambda _: None,
        (),
        {},
    )
    if csrf_response is not None:
        return csrf_response

    if request.content_type != "application/json":
        return Response(
            {"detail": "Unsupported media type."},
            status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )

    data = request.data
    if not isinstance(data, dict):
        return Response(
            {"detail": "Invalid request."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    username = data.get("username")
    password = data.get("password")
    user_model = get_user_model()
    username_field = user_model._meta.get_field(user_model.USERNAME_FIELD)
    if (
        not isinstance(username, str)
        or not username
        or (
            username_field.max_length is not None
            and len(username) > username_field.max_length
        )
        or not isinstance(password, str)
        or not password
    ):
        return Response(
            {"detail": "Invalid request."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {"detail": "Invalid username or password."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    login(request, user)
    login_timestamp = timezone.now().timestamp()
    request.session[LOGIN_TIMESTAMP_SESSION_KEY] = login_timestamp
    request.session.set_expiry(AUTH_SESSION_MAX_AGE_SECONDS)
    expires_at = expires_at_for(login_timestamp)
    return Response(
        {
            "user": _public_user(user),
            "expires_at": format_datetime(expires_at),
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@authentication_classes([FixedExpirySessionAuthentication])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@authentication_classes([FixedExpirySessionAuthentication])
@permission_classes([IsAuthenticated])
def me_view(request):
    login_timestamp = request.session[LOGIN_TIMESTAMP_SESSION_KEY]
    return Response(
        {
            "user": _public_user(request.user),
            "expires_at": format_datetime(expires_at_for(login_timestamp)),
        },
        status=status.HTTP_200_OK,
    )
