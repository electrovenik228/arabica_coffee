from .information import InformationSerializer


from rest_framework import serializers


class AddLoyaltyPointsSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(
        help_text="Заказ, за который курьер подтверждает начисление бонусов клиенту.",
    )


class AddCoffeeCupSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(
        help_text="Заказ, за который курьер подтверждает начисление чашки кофе клиенту.",
    )


class ScanQRCodeSerializer(serializers.Serializer):
    qr_code_data = serializers.CharField()





