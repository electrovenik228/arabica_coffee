from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from apps.order.models import Cafe
from apps.order.models.code import Order, OrderItem


class OrderCreateSerializer(serializers.Serializer):
    cafe_id = serializers.IntegerField()
    delivery_type = serializers.ChoiceField(choices=Order.DELIVERY_TYPE_CHOICES, default="pickup")
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=500)
    delivery_time = serializers.TimeField(required=False, allow_null=True)
    courier_comment = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=500,
        help_text="Комментарий для курьера (подъезд, этаж, код домофона и т.п.).",
    )
    use_bonus_points = serializers.IntegerField(
        required=False, default=0, min_value=0,
        help_text="Количество бонусных баллов для списания (1 балл = 1 сом скидки).",
    )

    def validate_cafe_id(self, value):
        if not Cafe.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Кафе не найдено или не активно.")
        return value

    def validate(self, attrs):
        if attrs.get("delivery_type") == "delivery" and not attrs.get("address"):
            raise serializers.ValidationError({"address": "Адрес обязателен для доставки."})
        return attrs


class OrderItemProductSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField()
    price = serializers.IntegerField()
    image = serializers.CharField(allow_null=True)


class OrderItemSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product",
            "quantity",
            "product_options",
            "final_price",
        )

    @extend_schema_field(OrderItemProductSerializer)
    def get_product(self, obj):
        product = obj.product
        image = None
        if product.image:
            request = self.context.get("request")
            image = (
                request.build_absolute_uri(product.image.url)
                if request
                else product.image.url
            )
        return {
            "id": product.id,
            "title": product.title,
            "description": product.description,
            "price": product.price,
            "image": image,
        }


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
            "courier_comment",
            "total_price",
            "bonus_spent",
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
            "courier_comment",
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
            "courier_comment",
            "total_price",
            "courier_id",
            "items",
        )
