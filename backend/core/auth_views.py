from datetime import timedelta

from django.contrib.auth import login, logout
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import AUTH_EXPIRES_AT, AUTH_SESSION_SECONDS
from .auth_serializers import LoginSerializer


def csrf_failure(request, reason=""):
    response = JsonResponse({"detail": "CSRF verification failed."}, status=403)
    response["Cache-Control"] = "no-store"
    return response


def session_info(request):
    return {
        "user": {"id": request.user.pk, "username": request.user.username},
        "expires_at": request.session[AUTH_EXPIRES_AT],
    }


@method_decorator(never_cache, name="dispatch")
@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        login(request._request, serializer.validated_data["user"])
        request.user = serializer.validated_data["user"]
        expires_at = timezone.now() + timedelta(seconds=AUTH_SESSION_SECONDS)
        request.session[AUTH_EXPIRES_AT] = expires_at.isoformat()
        request.session.set_expiry(expires_at)
        return Response(session_info(request))

    def get_authenticate_header(self, request):
        return "Session"


@method_decorator(never_cache, name="dispatch")
class LogoutView(APIView):
    def post(self, request):
        logout(request._request)
        return Response(status=204)


@method_decorator(never_cache, name="dispatch")
class MeView(APIView):
    def get(self, request):
        return Response(session_info(request))
