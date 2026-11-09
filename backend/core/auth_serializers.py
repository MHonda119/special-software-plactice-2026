from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate(self, attrs):
        for field in ("username", "password"):
            if not isinstance(self.initial_data.get(field), str):
                raise serializers.ValidationError({field: ["Expected a string."]})
        user = authenticate(
            request=self.context["request"]._request,
            username=attrs["username"],
            password=attrs["password"],
        )
        if user is None:
            raise AuthenticationFailed("Invalid username or password.")
        return {"user": user}
