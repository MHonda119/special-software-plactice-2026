from base64 import b64encode
from datetime import datetime, timezone as datetime_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.authentication import LOGIN_TIMESTAMP_SESSION_KEY
from core.tests.utils import login_test_client


User = get_user_model()


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="sample-user",
            password="correct-password",
        )

    def test_login_returns_user_and_absolute_expiration(self):
        login_time = datetime(2026, 10, 26, 12, tzinfo=datetime_timezone.utc)
        with patch("core.auth_views.timezone.now", return_value=login_time):
            response = self.client.post(
                "/api/auth/login/",
                {"username": "sample-user", "password": "correct-password"},
                format="json",
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.data,
            {
                "user": {"id": self.user.id, "username": "sample-user"},
                "expires_at": "2026-10-27T00:00:00+00:00",
            },
        )
        self.assertNotIn("password", response.data)
        self.assertIn("sessionid", response.cookies)
        self.assertEqual(
            float(self.client.session[LOGIN_TIMESTAMP_SESSION_KEY]),
            login_time.timestamp(),
        )

    def test_unknown_username_and_wrong_password_have_same_error(self):
        unknown_user = self.client.post(
            "/api/auth/login/",
            {"username": "missing-user", "password": "incorrect-password"},
            format="json",
        )
        wrong_password = self.client.post(
            "/api/auth/login/",
            {"username": "sample-user", "password": "incorrect-password"},
            format="json",
        )

        self.assertEqual(unknown_user.status_code, 400)
        self.assertEqual(wrong_password.status_code, 400)
        self.assertEqual(unknown_user.data, wrong_password.data)
        self.assertEqual(
            unknown_user.data,
            {"detail": "Invalid username or password."},
        )

    def test_inactive_user_has_same_authentication_error(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.post(
            "/api/auth/login/",
            {"username": "sample-user", "password": "correct-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {"detail": "Invalid username or password."},
        )

    def test_me_requires_authentication_and_does_not_expose_secrets(self):
        anonymous_response = self.client.get("/api/auth/me/")
        self.assertEqual(anonymous_response.status_code, 403)

        login_test_client(self.client, self.user)
        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(set(response.data), {"user", "expires_at"})
        self.assertEqual(
            response.data["user"],
            {"id": self.user.id, "username": "sample-user"},
        )
        self.assertNotIn("password", response.data)
        self.assertNotIn("sessionid", response.data)

    def test_session_without_login_timestamp_is_invalidated(self):
        self.client.force_login(self.user)

        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, 403)

    def test_logout_returns_empty_204_and_invalidates_session(self):
        login_test_client(self.client, self.user)

        response = self.client.post("/api/auth/logout/", {}, format="json")

        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(response.content, b"")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 403)

    def test_login_requires_csrf_token(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post(
            "/api/auth/login/",
            {"username": "sample-user", "password": "correct-password"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_login_succeeds_with_csrf_token(self):
        client = APIClient(enforce_csrf_checks=True)
        csrf_response = client.get("/api/csrf/")
        token = csrf_response.data["csrftoken"]

        response = client.post(
            "/api/auth/login/",
            {"username": "sample-user", "password": "correct-password"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 200, response.content)

    def test_authenticated_unsafe_requests_still_require_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        login_test_client(client, self.user)

        response = client.post("/api/auth/logout/", {}, format="json")

        self.assertEqual(response.status_code, 403)

    def test_logout_succeeds_with_csrf_token(self):
        client = APIClient(enforce_csrf_checks=True)
        csrf_response = client.get("/api/csrf/")
        token = csrf_response.data["csrftoken"]
        login_response = client.post(
            "/api/auth/login/",
            {"username": "sample-user", "password": "correct-password"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(login_response.status_code, 200)

        refreshed_csrf_response = client.get("/api/csrf/")
        refreshed_token = refreshed_csrf_response.data["csrftoken"]
        response = client.post(
            "/api/auth/logout/",
            {},
            format="json",
            HTTP_X_CSRFTOKEN=refreshed_token,
        )

        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(response.content, b"")

    def test_absolute_session_expiration_boundary_and_no_extension(self):
        login_time = datetime(2026, 10, 26, 12, tzinfo=datetime_timezone.utc)
        with patch("core.auth_views.timezone.now", return_value=login_time):
            login_response = self.client.post(
                "/api/auth/login/",
                {"username": "sample-user", "password": "correct-password"},
                format="json",
            )
        self.assertEqual(login_response.status_code, 200)
        expiry = login_time.timestamp() + 43_200

        with patch(
            "core.authentication.timezone.now",
            return_value=datetime.fromtimestamp(expiry - 1, tz=datetime_timezone.utc),
        ):
            before_expiry = self.client.get("/api/auth/me/")
        self.assertEqual(before_expiry.status_code, 200)
        self.assertEqual(before_expiry.data["expires_at"], "2026-10-27T00:00:00+00:00")
        self.assertEqual(
            float(self.client.session[LOGIN_TIMESTAMP_SESSION_KEY]),
            login_time.timestamp(),
        )

        with patch(
            "core.authentication.timezone.now",
            return_value=datetime.fromtimestamp(expiry, tz=datetime_timezone.utc),
        ):
            at_expiry = self.client.get("/api/auth/me/")
        self.assertEqual(at_expiry.status_code, 403)
        self.assertNotIn(LOGIN_TIMESTAMP_SESSION_KEY, self.client.session)

    def test_expiration_is_enforced_for_admin_sessions(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        login_time = datetime(2026, 10, 26, 12, tzinfo=datetime_timezone.utc)
        with patch(
            "core.authentication.timezone.now", return_value=login_time
        ):
            login_response = self.client.post(
                "/admin/login/",
                {"username": "sample-user", "password": "correct-password"},
            )

        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(
            float(self.client.session[LOGIN_TIMESTAMP_SESSION_KEY]),
            login_time.timestamp(),
        )

        with patch(
            "core.authentication.timezone.now",
            return_value=datetime.fromtimestamp(
                login_time.timestamp() + 43_199, tz=datetime_timezone.utc
            ),
        ):
            before_expiry = self.client.get("/admin/")
        self.assertEqual(before_expiry.status_code, 200)

        with patch(
            "core.authentication.timezone.now",
            return_value=datetime.fromtimestamp(
                login_time.timestamp() + 43_200, tz=datetime_timezone.utc
            ),
        ):
            at_expiry = self.client.get("/admin/")
        self.assertEqual(at_expiry.status_code, 302)
        self.assertIn("/admin/login/", at_expiry["Location"])

    def test_only_health_csrf_and_login_are_public(self):
        public_responses = (
            self.client.get("/api/health/"),
            self.client.get("/api/csrf/"),
            self.client.post(
                "/api/auth/login/",
                {"username": "unknown", "password": "wrong"},
                format="json",
            ),
        )
        self.assertEqual(
            [response.status_code for response in public_responses],
            [200, 200, 400],
        )

        protected_requests = (
            ("get", "/api/"),
            ("get", "/api/llms/"),
            ("post", "/api/llms/"),
            ("get", "/api/sessions/"),
            ("post", "/api/sessions/"),
            ("get", "/api/agents/"),
            ("post", "/api/agents/"),
            ("post", "/api/agents/1/execute/"),
            ("get", "/api/datasources/"),
            ("post", "/api/datasources/"),
            ("get", "/api/datasources/1/chunks/"),
            ("post", "/api/datasources/1/chunks/"),
            ("get", "/api/auth/me/"),
            ("post", "/api/auth/logout/"),
        )
        for method, path in protected_requests:
            with self.subTest(method=method, path=path):
                if method == "get":
                    response = self.client.get(path)
                else:
                    response = self.client.post(path, {}, format="json")
                self.assertEqual(response.status_code, 403, response.content)

    def test_basic_authentication_is_disabled(self):
        credentials = b64encode(b"sample-user:correct-password").decode("ascii")

        response = self.client.get(
            "/api/llms/",
            HTTP_AUTHORIZATION=f"Basic {credentials}",
        )

        self.assertEqual(response.status_code, 403)
