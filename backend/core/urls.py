from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    health,
    csrf_token,
    LLMViewSet,
    ChatSessionViewSet,
    AgentViewSet,
    DatasourceViewSet,
)
from .auth_views import login_view, logout_view, me_view

router = DefaultRouter()
router.register(r"llms", LLMViewSet, basename="llm")
router.register(r"sessions", ChatSessionViewSet, basename="session")
router.register(r"agents", AgentViewSet, basename="agent")
router.register(r"datasources", DatasourceViewSet, basename="datasource")

urlpatterns = [
    path("auth/login/", login_view, name="auth-login"),
    path("auth/logout/", logout_view, name="auth-logout"),
    path("auth/me/", me_view, name="auth-me"),
    path("health/", health, name="health"),
    path("csrf/", csrf_token, name="csrf-token"),
    path("", include(router.urls)),
]
