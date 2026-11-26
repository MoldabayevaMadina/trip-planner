"""Serializers for sign up, the current user with the profile, and password change."""
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Profile, User


def check_password_rules(password, user=None):
    """Django's password rules from AUTH_PASSWORD_VALIDATORS (length, too common, only digits...)."""
    try:
        password_validation.validate_password(password, user)
    except DjangoValidationError as error:
        raise serializers.ValidationError(list(error.messages))
    return password


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["home_city", "bio", "updated_at"]
        read_only_fields = ["updated_at"]


class UserSerializer(serializers.ModelSerializer):
    """The current user: GET and PATCH /api/auth/me/. The profile is nested (one-to-one)."""

    profile = ProfileSerializer(required=False)
    trips_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "date_joined", "profile", "trips_count"]
        read_only_fields = ["id", "date_joined"]

    def get_trips_count(self, obj) -> int:
        return obj.trips.count()

    def update(self, instance, validated_data):
        # DRF can't save a nested object by itself: take the profile part out and save it separately
        profile_data = validated_data.pop("profile", None)
        instance = super().update(instance, validated_data)      # username, email
        if profile_data:
            profile, _ = Profile.objects.get_or_create(user=instance)
            for field, value in profile_data.items():
                setattr(profile, field, value)
            profile.save()
        return instance


class RegisterSerializer(serializers.ModelSerializer):
    """POST /api/auth/register/ — a new user and an empty profile."""

    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]
        read_only_fields = ["id"]

    def validate_password(self, value):
        return check_password_rules(value)

    def create(self, validated_data):
        # create_user stores a hash of the password, never the password itself
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )
        Profile.objects.create(user=user)
        return user


class ChangePasswordSerializer(serializers.Serializer):
    """POST /api/auth/change-password/ — the old password is required."""

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("The current password is wrong.")
        return value

    def validate_new_password(self, value):
        return check_password_rules(value, self.context["request"].user)

    def validate(self, attrs):
        if attrs["old_password"] == attrs["new_password"]:
            raise serializers.ValidationError({"new_password": "The new password must be different."})
        return attrs