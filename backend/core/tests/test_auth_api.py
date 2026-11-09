from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient


class AuthApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="student", password="test-password"
        )

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.start = timezone.now().replace(microsecond=0)

    def login(self, **credentials):
        token = self.client.get("/api/csrf/").json()["csrftoken"]
        return self.client.post(
            "/api/auth/login/",
            credentials or {"username": "student", "password": "test-password"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

    def test_login_and_me_only_expose_user_and_expiry(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {"user", "expires_at"})
        self.assertEqual(
            response.data["user"], {"id": self.user.pk, "username": "student"}
        )
        self.assertNotIn("password", str(response.data))
        self.assertNotEqual(self.user.password, "test-password")
        self.assertTrue(self.user.check_password("test-password"))
        current = self.client.get("/api/auth/me/")
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.data, response.data)
        self.assertIn("no-store", current["Cache-Control"])
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")

    def test_invalid_credentials_and_inactive_user_have_identical_errors(self):
        responses = [
            self.login(username="missing", password="test-password"),
            self.login(username="student", password="wrong"),
        ]
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        responses.append(self.login())
        for response in responses:
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.data, responses[0].data)

    def test_login_validates_required_fields(self):
        for payload in (
            {"username": "student"},
            {"password": "test-password"},
            {"username": "", "password": "test-password"},
            {"username": "student", "password": []},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.login(**payload).status_code, 400)

    def test_login_requires_csrf_even_for_anonymous_user(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": "student", "password": "test-password"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("CSRF", response.json()["detail"])

    def test_csrf_is_rotated_on_login_and_required_for_writes(self):
        old_token = self.client.get("/api/csrf/").json()["csrftoken"]
        self.assertEqual(self.login().status_code, 200)
        for token in (None, old_token):
            headers = {"HTTP_X_CSRFTOKEN": token} if token else {}
            response = self.client.post("/api/sessions/", {}, **headers)
            self.assertEqual(response.status_code, 403)
            self.assertIn("CSRF", response.json()["detail"])
        token = self.client.get("/api/csrf/").json()["csrftoken"]
        response = self.client.post("/api/sessions/", {}, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 400)

    def test_every_business_route_requires_authentication(self):
        session_id = "00000000-0000-0000-0000-000000000001"
        routes = [
            "/api/",
            "/api/llms/",
            "/api/llms/1/",
            "/api/sessions/",
            f"/api/sessions/{session_id}/",
            f"/api/sessions/{session_id}/messages/",
            f"/api/sessions/{session_id}/chat/",
            "/api/agents/",
            "/api/agents/1/",
            "/api/agents/1/execute/",
            "/api/datasources/",
            "/api/datasources/1/",
            "/api/datasources/1/chunks/",
            "/api/datasources/1/chunks/chunk-1/",
            "/api/auth/me/",
            "/api/auth/logout/",
        ]
        for route in routes:
            for method in ("get", "post", "put", "patch", "delete", "options"):
                with self.subTest(route=route, method=method):
                    response = getattr(self.client, method)(route)
                    self.assertEqual(response.status_code, 401)

    def test_health_and_csrf_are_public(self):
        for route in ("/api/health/", "/api/csrf/"):
            self.assertEqual(self.client.get(route).status_code, 200)

    def test_basic_credentials_do_not_bypass_session_authentication(self):
        response = self.client.get(
            "/api/llms/", HTTP_AUTHORIZATION="Basic c3R1ZGVudDp0ZXN0LXBhc3N3b3Jk"
        )
        self.assertEqual(response.status_code, 401)

    def test_fixed_expiry_boundary_and_replayed_cookie(self):
        with patch("django.utils.timezone.now", return_value=self.start):
            response = self.login()
        self.assertEqual(response.status_code, 200)
        deadline = self.start + timedelta(seconds=43200)
        self.assertEqual(response.data["expires_at"], deadline.isoformat())
        cookie_value = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        session = Session.objects.get(session_key=cookie_value)
        self.assertEqual(session.expire_date, deadline)
        for elapsed in (1, 21600, 43199):
            with patch(
                "django.utils.timezone.now",
                return_value=self.start + timedelta(seconds=elapsed),
            ):
                current = self.client.get("/api/auth/me/")
                self.assertEqual(current.status_code, 200)
                self.assertEqual(current.data["expires_at"], deadline.isoformat())
                self.assertEqual(self.client.get("/api/llms/").status_code, 200)
        with patch("django.utils.timezone.now", return_value=deadline):
            self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
            self.client.cookies[settings.SESSION_COOKIE_NAME] = cookie_value
            self.assertEqual(self.client.get("/api/llms/").status_code, 401)

    def test_server_checks_deadline_even_if_session_storage_lives_longer(self):
        with patch("django.utils.timezone.now", return_value=self.start):
            self.assertEqual(self.login().status_code, 200)
        key = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        Session.objects.filter(session_key=key).update(
            expire_date=self.start + timedelta(days=2)
        )
        with patch(
            "django.utils.timezone.now", return_value=self.start + timedelta(hours=12)
        ):
            self.assertEqual(self.client.get("/api/llms/").status_code, 401)
        self.assertFalse(Session.objects.filter(session_key=key).exists())

    def test_session_without_login_deadline_is_rejected(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/api/llms/").status_code, 401)

    def test_logout_invalidates_server_session_and_replayed_cookie(self):
        self.assertEqual(self.login().status_code, 200)
        cookie_value = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        token = self.client.get("/api/csrf/").json()["csrftoken"]
        response = self.client.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Session.objects.filter(session_key=cookie_value).exists())
        self.client.cookies[settings.SESSION_COOKIE_NAME] = cookie_value
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.assertEqual(self.client.get("/api/llms/").status_code, 401)
