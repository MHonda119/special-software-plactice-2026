from datetime import datetime, timezone as datetime_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.authentication import (
    AUTH_SESSION_MAX_AGE_SECONDS,
    LOGIN_TIMESTAMP_SESSION_KEY,
)


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = get_user_model().objects.create_user(
            username="student01",
            password="example-password",
        )

    def csrf_token(self):
        response = self.client.get("/api/csrf/")
        self.assertEqual(response.status_code, 200)
        return response.data["csrftoken"]

    def login(self):
        token = self.csrf_token()
        return self.client.post(
            "/api/auth/login/",
            {"username": "student01", "password": "example-password"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

    def test_login_requires_csrf_and_returns_public_user_and_expiry(self):
        denied = self.client.post(
            "/api/auth/login/",
            {"username": "student01", "password": "example-password"},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)

        response = self.login()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.data["user"],
            {"id": self.user.pk, "username": "student01"},
        )
        self.assertIn("expires_at", response.data)
        self.assertNotIn("password", response.data)
        self.assertNotIn("password_hash", response.data)
        self.assertIn("sessionid", self.client.cookies)

    def test_invalid_credentials_have_same_response(self):
        unknown_user = self.client.post(
            "/api/auth/login/",
            {"username": "not-a-user", "password": "wrong"},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )
        wrong_password = self.client.post(
            "/api/auth/login/",
            {"username": "student01", "password": "wrong"},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )
        self.assertEqual(unknown_user.status_code, 401)
        self.assertEqual(unknown_user.status_code, wrong_password.status_code)
        self.assertEqual(unknown_user.data, wrong_password.data)

    def test_login_rejects_missing_or_empty_credentials(self):
        token = self.csrf_token()
        for payload in (
            {},
            [],
            {"username": "student01"},
            {"username": "", "password": "x"},
            {"username": "student01", "password": ""},
        ):
            with self.subTest(payload=payload):
                response = self.client.post(
                    "/api/auth/login/",
                    payload,
                    format="json",
                    HTTP_X_CSRFTOKEN=token,
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data, {"detail": "Invalid request."})

    def test_login_rejects_non_json_content_type(self):
        response = self.client.post(
            "/api/auth/login/",
            "username=student01&password=example-password",
            content_type="application/x-www-form-urlencoded",
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )
        self.assertEqual(response.status_code, 415)

    def test_me_requires_authenticated_session(self):
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 401)

    def test_business_api_requires_auth_but_health_and_csrf_are_public(self):
        denied = self.client.get("/api/llms/")
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(self.client.get("/api/health/").status_code, 200)
        self.assertEqual(self.client.get("/api/csrf/").status_code, 200)

        login_response = self.login()
        self.assertEqual(
            login_response.status_code,
            200,
            login_response.content,
        )
        self.assertEqual(self.client.get("/api/llms/").status_code, 200)

    def test_me_returns_fixed_expiry_without_extending_it(self):
        login_response = self.login()
        self.assertEqual(
            login_response.status_code,
            200,
            login_response.content,
        )
        login_timestamp = self.client.session[LOGIN_TIMESTAMP_SESSION_KEY]

        first = self.client.get("/api/auth/me/")
        second = self.client.get("/api/auth/me/")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data, second.data)
        self.assertEqual(first.data["user"]["username"], self.user.username)
        expiry = datetime.fromisoformat(
            first.data["expires_at"].replace("Z", "+00:00")
        )
        expected_expiry = datetime.fromtimestamp(
            login_timestamp + AUTH_SESSION_MAX_AGE_SECONDS,
            tz=datetime_timezone.utc,
        )
        self.assertEqual(expiry, expected_expiry)
        self.assertEqual(
            self.client.session[LOGIN_TIMESTAMP_SESSION_KEY],
            login_timestamp,
        )

    def test_logout_requires_csrf_and_invalidates_session(self):
        login_response = self.login()
        self.assertEqual(
            login_response.status_code,
            200,
            login_response.content,
        )

        denied = self.client.post("/api/auth/logout/", format="json")
        self.assertEqual(denied.status_code, 403)

        response = self.client.post(
            "/api/auth/logout/",
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(response.content)
        me_response = self.client.get("/api/auth/me/")
        self.assertEqual(me_response.status_code, 401)

    def test_expired_session_is_rejected_at_exact_boundary(self):
        login_response = self.login()
        self.assertEqual(
            login_response.status_code,
            200,
            login_response.content,
        )
        session = self.client.session
        login_timestamp = session[LOGIN_TIMESTAMP_SESSION_KEY]
        # Keep the backing session available so the authentication expiry check
        # itself is exercised at the exact 12-hour boundary.
        session.set_expiry(AUTH_SESSION_MAX_AGE_SECONDS + 60)
        session.save()

        before_expiry = datetime.fromtimestamp(
            login_timestamp + AUTH_SESSION_MAX_AGE_SECONDS - 1,
            tz=datetime_timezone.utc,
        )
        with patch(
            "core.authentication.timezone.now",
            return_value=before_expiry,
        ):
            response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 200)

        at_expiry = datetime.fromtimestamp(
            login_timestamp + AUTH_SESSION_MAX_AGE_SECONDS,
            tz=datetime_timezone.utc,
        )
        with patch("core.authentication.timezone.now", return_value=at_expiry):
            expired = self.client.get("/api/auth/me/")
        self.assertEqual(expired.status_code, 401)
        self.assertIn("expired", expired.data["detail"].lower())
