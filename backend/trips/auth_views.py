"""Sign up, current user (profile) and password change. Login and refresh come from simplejwt."""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .auth_serializers import ChangePasswordSerializer, RegisterSerializer, UserSerializer
from .models import Profile


def tokens_for(user):
    """A refresh token and an access token for the user (the same as /api/auth/login/ returns)."""
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


@extend_schema(
    summary="Sign up",
    responses={201: inline_serializer(name="RegisterResponse", fields={
        "user": UserSerializer(),
        "refresh": serializers.CharField(),
        "access": serializers.CharField(),
    })},
)
class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — creates a user and logs them in at once."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({"user": UserSerializer(user).data, **tokens_for(user)}, status=status.HTTP_201_CREATED)


@extend_schema(summary="Current user and profile")
class MeView(generics.RetrieveUpdateAPIView):
    """GET / PATCH /api/auth/me/ — who am I; change username, email, home city, bio."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        # users created before profiles existed (e.g. the admin) get an empty one
        Profile.objects.get_or_create(user=self.request.user)
        return self.request.user


@extend_schema(
    summary="Change password",
    request=ChangePasswordSerializer,
    responses={200: inline_serializer(name="ChangePasswordResponse", fields={"detail": serializers.CharField()})},
)
class ChangePasswordView(APIView):
    """POST /api/auth/change-password/ — {"old_password": "...", "new_password": "..."}."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        return Response({"detail": "Password changed."})