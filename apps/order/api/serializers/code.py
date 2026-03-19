from rest_framework import serializers
from apps.order.models import Cafe
from apps.order.models.code import Order, OrderItem


class OrderCreateSerializer(serializers.Serializer):
    """
    Request payload for order creation.
    """

    cafe_id = serializers.IntegerField(required=True)
    delivery_type = serializers.ChoiceField(
        choices=Order.DELIVERY_TYPE_CHOICES, default="pickup"
    )
    address = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=500
    )
    delivery_time = serializers.TimeField(required=False, allow_null=True)

    def validate_cafe_id(self, value):
        if not Cafe.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError(
                "Кафе не найдено или не активно."
            )
        return value

    def validate(self, attrs):
        # Require address when delivery is selected
        if attrs.get("delivery_type") == "delivery" and not attrs.get("address"):
            raise serializers.ValidationError(
                {"address": "Адрес обязателен для доставки."}
            )
        return attrs


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product",
            "quantity",
            "product_options",
            "final_price",
        )


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "delivery_type",
            "address",
            "delivery_time",
            "total_price",
            "created_at",
            "items",
        )


class OrderItemCourierSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source="product.title", read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "product_title", "quantity", "product_options")


class CourierOrderSerializer(serializers.ModelSerializer):
    items = OrderItemCourierSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "delivery_type",
            "address",
            "delivery_time",
            "items",
        )


class CafeOrderSerializer(serializers.ModelSerializer):
    items = OrderItemCourierSerializer(many=True, read_only=True)
    courier_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "delivery_type",
            "address",
            "delivery_time",
            "total_price",
            "courier_id",
            "items",
        )
