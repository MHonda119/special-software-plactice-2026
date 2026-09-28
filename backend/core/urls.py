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

router = DefaultRouter()
router.register(r"llms", LLMViewSet, basename="llm")
router.register(r"sessions", ChatSessionViewSet, basename="session")
router.register(r"agents", AgentViewSet, basename="agent")
router.register(r"datasources", DatasourceViewSet, basename="datasource")

urlpatterns = [
    path("health/", health, name="health"),
    path("csrf/", csrf_token, name="csrf-token"),
    path("", include(router.urls)),
]
