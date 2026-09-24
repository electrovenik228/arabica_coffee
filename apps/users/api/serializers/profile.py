from rest_framework import serializers

from apps.users.models import User


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "phone_number",
            "first_name",
            "last_name",
            "gender",
            "birth_date",
            "avatar",
            "qr_code",
            "loyalty_points",
            "coffee_cups",
            "free_coffee_cups",
            "is_courier",
            "is_phone_verified",
            "phone_verified_at",
        )
        read_only_fields = (
            "id",
            "phone_number",
            "qr_code",
            "loyalty_points",
            "coffee_cups",
            "free_coffee_cups",
            "is_courier",
            "is_phone_verified",
            "phone_verified_at",
        )
