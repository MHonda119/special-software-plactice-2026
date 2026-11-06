from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient


User = get_user_model()


class AuthApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sample-user",
            password="example-password",
        )
        self.client = APIClient()

    def test_login_returns_user_and_absolute_expiry(self):
        login_time = timezone.now()
        expected_expiry = login_time + timedelta(hours=12)

        with patch("core.authentication.timezone.now", return_value=login_time):
            response = self.client.post(
                "/api/auth/login/",
                {
                    "username": "sample-user",
                    "password": "example-password",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.data,
            {
                "user": {
                    "id": self.user.id,
                    "username": "sample-user",
                },
                "expires_at": expected_expiry.isoformat().replace("+00:00", "Z"),
            },
        )
        self.assertNotIn("password", response.data)
        self.assertNotIn("password", response.data["user"])
        self.assertIn("sessionid", self.client.cookies)

    def test_invalid_credentials_have_the_same_response(self):
        inactive_user = User.objects.create_user(
            username="inactive-user",
            password="example-password",
            is_active=False,
        )

        responses = [
            self.client.post(
                "/api/auth/login/",
                {"username": "sample-user", "password": "wrong-password"},
                format="json",
            ),
            self.client.post(
                "/api/auth/login/",
                {"username": "missing-user", "password": "wrong"},
                format="json",
            ),
            self.client.post(
                "/api/auth/login/",
                {
                    "username": inactive_user.username,
                    "password": "example-password",
                },
                format="json",
            ),
        ]

        self.assertEqual([response.status_code for response in responses], [401] * 3)
        self.assertEqual(responses[0].data, responses[1].data)
        self.assertEqual(responses[1].data, responses[2].data)
        self.assertEqual(
            responses[0].data,
            {"detail": "Invalid username or password."},
        )

    def test_login_requires_csrf_even_for_anonymous_requests(self):
        client = APIClient(enforce_csrf_checks=True)
        payload = {
            "username": "sample-user",
            "password": "example-password",
        }

        rejected = client.post("/api/auth/login/", payload, format="json")
        self.assertEqual(rejected.status_code, 403)

        csrf_response = client.get("/api/csrf/")
        accepted = client.post(
            "/api/auth/login/",
            payload,
            format="json",
            HTTP_X_CSRFTOKEN=csrf_response.data["csrftoken"],
        )
        self.assertEqual(accepted.status_code, 200, accepted.content)

    def test_authenticated_api_writes_require_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        csrf_response = client.get("/api/csrf/")
        login_response = client.post(
            "/api/auth/login/",
            {
                "username": "sample-user",
                "password": "example-password",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf_response.data["csrftoken"],
        )
        self.assertEqual(login_response.status_code, 200, login_response.content)

        rejected = client.post("/api/llms/", {}, format="json")
        self.assertEqual(rejected.status_code, 403)

        refreshed_csrf_response = client.get("/api/csrf/")
        accepted = client.post(
            "/api/llms/",
            {},
            format="json",
            HTTP_X_CSRFTOKEN=refreshed_csrf_response.data["csrftoken"],
        )
        self.assertEqual(accepted.status_code, 400)

    def test_logout_requires_csrf_and_invalidates_the_session(self):
        client = APIClient(enforce_csrf_checks=True)
        csrf_response = client.get("/api/csrf/")
        login_response = client.post(
            "/api/auth/login/",
            {
                "username": "sample-user",
                "password": "example-password",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf_response.data["csrftoken"],
        )
        self.assertEqual(login_response.status_code, 200, login_response.content)

        rejected = client.post("/api/auth/logout/", format="json")
        self.assertEqual(rejected.status_code, 403)

        refreshed_csrf_response = client.get("/api/csrf/")
        logout_response = client.post(
            "/api/auth/logout/",
            format="json",
            HTTP_X_CSRFTOKEN=refreshed_csrf_response.data["csrftoken"],
        )
        self.assertEqual(logout_response.status_code, 204, logout_response.content)
        self.assertEqual(client.get("/api/auth/me/").status_code, 401)

    def test_protected_endpoints_require_login_and_public_endpoints_do_not(self):
        self.assertEqual(self.client.get("/api/health/").status_code, 200)
        self.assertEqual(self.client.get("/api/csrf/").status_code, 200)

        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.assertEqual(
            self.client.post("/api/auth/logout/", format="json").status_code,
            401,
        )

    def test_all_business_api_operations_require_authentication(self):
        operations = [
            ("GET", "/api/"),
            ("HEAD", "/api/"),
            ("OPTIONS", "/api/"),
            ("GET", "/api/llms/"),
            ("POST", "/api/llms/"),
            ("GET", "/api/llms/1/"),
            ("PUT", "/api/llms/1/"),
            ("PATCH", "/api/llms/1/"),
            ("DELETE", "/api/llms/1/"),
            ("GET", "/api/sessions/"),
            ("POST", "/api/sessions/"),
            ("GET", "/api/sessions/00000000-0000-0000-0000-000000000001/"),
            ("PUT", "/api/sessions/00000000-0000-0000-0000-000000000001/"),
            ("PATCH", "/api/sessions/00000000-0000-0000-0000-000000000001/"),
            ("DELETE", "/api/sessions/00000000-0000-0000-0000-000000000001/"),
            ("GET", "/api/sessions/00000000-0000-0000-0000-000000000001/messages/"),
            ("POST", "/api/sessions/00000000-0000-0000-0000-000000000001/chat/"),
            ("GET", "/api/agents/"),
            ("POST", "/api/agents/"),
            ("GET", "/api/agents/1/"),
            ("PUT", "/api/agents/1/"),
            ("PATCH", "/api/agents/1/"),
            ("DELETE", "/api/agents/1/"),
            ("POST", "/api/agents/1/execute/"),
            ("GET", "/api/datasources/"),
            ("POST", "/api/datasources/"),
            ("GET", "/api/datasources/1/"),
            ("PUT", "/api/datasources/1/"),
            ("PATCH", "/api/datasources/1/"),
            ("DELETE", "/api/datasources/1/"),
            ("GET", "/api/datasources/1/chunks/"),
            ("POST", "/api/datasources/1/chunks/"),
            ("DELETE", "/api/datasources/1/chunks/any-chunk/"),
        ]

        for method, path in operations:
            with self.subTest(method=method, path=path):
                response = self.client.generic(method, path)
                self.assertEqual(response.status_code, 401, response.content)

    def test_me_reports_user_and_logout_invalidates_session(self):
        login_response = self.client.post(
            "/api/auth/login/",
            {
                "username": "sample-user",
                "password": "example-password",
            },
            format="json",
        )
        self.assertEqual(login_response.status_code, 200, login_response.content)

        me_response = self.client.get("/api/auth/me/")
        self.assertEqual(me_response.status_code, 200, me_response.content)
        self.assertEqual(me_response.data["user"]["id"], self.user.id)
        self.assertEqual(me_response.data["user"]["username"], "sample-user")
        self.assertNotIn("password", me_response.data)
        self.assertNotIn("password", me_response.data["user"])

        logout_response = self.client.post("/api/auth/logout/", format="json")
        self.assertEqual(logout_response.status_code, 204)
        self.assertEqual(logout_response.content, b"")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.assertEqual(self.client.get("/api/llms/").status_code, 401)

    def test_absolute_expiry_is_not_extended_by_activity(self):
        login_time = timezone.now()
        with patch("core.authentication.timezone.now", return_value=login_time):
            response = self.client.post(
                "/api/auth/login/",
                {
                    "username": "sample-user",
                    "password": "example-password",
                },
                format="json",
            )
        self.assertEqual(response.status_code, 200, response.content)

        with patch(
            "core.authentication.timezone.now",
            return_value=login_time + timedelta(seconds=43199),
        ):
            self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)

        with patch(
            "core.authentication.timezone.now",
            return_value=login_time + timedelta(seconds=43200),
        ):
            self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
            self.assertEqual(self.client.get("/api/llms/").status_code, 401)
