from rest_framework import serializers

from apps.users.utils.phone import normalize_phone_number

class SendCodeSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        max_length=20,
        required=True,
        allow_blank=False,
        help_text="Номер телефона для отправки кода.",
    )

    def validate_phone_number(self, value):
        return normalize_phone_number(value)


class VerifyCodeSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=10)

    def validate_phone_number(self, value):
        return normalize_phone_number(value)
