from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import authenticate


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(email=data["email"], password=data["password"])
        if not user:
            raise AuthenticationFailed("Invalid credentials")
        if user.status != "ACTIVE":
            raise AuthenticationFailed("Account inactive")
        data["user"] = user
        return data


class MFAVerifySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=8)
