from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers

from core.exceptions import AppError

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name", "team_name", "is_staff", "date_joined"]
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    name = serializers.CharField(max_length=120)
    team_name = serializers.CharField(max_length=60)

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise AppError("EMAIL_TAKEN", 400)
        return email

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise AppError(
                "WEAK_PASSWORD", 400, {"errors": {"password": list(exc.messages)}}
            )
        return value

    def validate(self, attrs):
        attrs["name"] = attrs["name"].strip()
        attrs["team_name"] = attrs["team_name"].strip()
        if not attrs["name"]:
            raise AppError("INVALID_DATA", 400, {"errors": {"name": ["Informe seu nome."]}})
        if not attrs["team_name"]:
            raise AppError(
                "INVALID_DATA", 400, {"errors": {"team_name": ["Informe o nome do seu time."]}}
            )
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return User.objects.create_user(**validated_data)
        except IntegrityError:
            raise AppError("EMAIL_TAKEN", 400)


class ProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "name", "team_name", "is_staff"]
        read_only_fields = ["id", "email", "is_staff"]
        extra_kwargs = {
            "name": {"allow_blank": False, "max_length": 120},
            "team_name": {"allow_blank": False, "max_length": 60},
        }
