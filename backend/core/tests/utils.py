from django.utils import timezone

from core.authentication import LOGIN_TIMESTAMP_SESSION_KEY


def login_test_client(client, user):
    client.force_login(user)
    session = client.session
    session[LOGIN_TIMESTAMP_SESSION_KEY] = timezone.now().timestamp()
    session.save()
