from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import LoginSerializer, MFAVerifySerializer
from .services import generate_totp_secret, get_totp_uri, verify_totp


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        roles = list(user.roles.values_list("role__code", flat=True))
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "mfa_enabled": user.mfa_enabled,
            "roles": roles,
        })


class MFASetupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.totp_secret:
            user.totp_secret = generate_totp_secret()
            user.save(update_fields=["totp_secret"])
        uri = get_totp_uri(user.totp_secret, user.email)
        return Response({"totp_uri": uri, "secret": user.totp_secret})


class MFAVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MFAVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.totp_secret:
            return Response({"error": "MFA not set up"}, status=status.HTTP_400_BAD_REQUEST)
        if not verify_totp(user.totp_secret, serializer.validated_data["code"]):
            return Response({"error": "Invalid TOTP code"}, status=status.HTTP_401_UNAUTHORIZED)
        user.mfa_enabled = True
        user.save(update_fields=["mfa_enabled"])
        return Response({"status": "MFA verified"})
