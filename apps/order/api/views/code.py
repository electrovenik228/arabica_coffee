from decimal import Decimal, ROUND_DOWN

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart.models import Cart
from apps.order.api.pagination import OrderPageNumberPagination
from apps.order.api.serializers.code import (
    OrderCreateSerializer,
    OrderSerializer,
)
from apps.order.models.code import Order, OrderItem


@extend_schema(
    summary="Создать заказ из корзины",
    tags=["Order"],
    request=OrderCreateSerializer,
    responses={
        201: OrderSerializer,
        400: OpenApiResponse(description="Пустая корзина или ошибка валидации."),
    },
)
class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user

        cart, _ = Cart.objects.get_or_create(user=user)
        if not cart.items.exists():
            return Response(
                {"error": "Корзина пуста"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        delivery_type = serializer.validated_data.get("delivery_type", "pickup")
        address = serializer.validated_data.get("address")
        delivery_time = serializer.validated_data.get("delivery_time")

        order = Order.objects.create(
            user=user,
            delivery_type=delivery_type,
            address=address,
            delivery_time=delivery_time,
            total_price=Decimal("0.00"),
        )

        total_price = Decimal("0.00")
        bonus_total = Decimal("0.00")

        # Add items from cart to order
        for cart_item in cart.items.all():
            item_price = Decimal(cart_item.get_total_price())

            options = [
                {"id": opt.option_value.id, "value": str(opt.option_value)}
                for opt in cart_item.options.all()
            ]

            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                quantity=cart_item.quantity,
                product_options={"options": options},
                final_price=item_price,
            )

            total_price += item_price

            bonus_percent = Decimal(str(cart_item.product.bonus_percent or 0))
            bonus_for_item = (item_price * bonus_percent) / Decimal("100")
            bonus_total += bonus_for_item

        order.total_price = total_price
        order.save()

        if bonus_total > 0:
            user.loyalty_points += int(
                bonus_total.quantize(Decimal("1"), rounding=ROUND_DOWN)
            )
            user.save(update_fields=["loyalty_points"])

        # Clear user's cart and cache
        cart.items.all().delete()
        cache.delete(f"user_cart_{user.id}")

        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(
    summary="Список заказов текущего пользователя",
    tags=["Order"],
    parameters=[
        OpenApiParameter(
            name="page",
            type=int,
            location=OpenApiParameter.QUERY,
            description="Номер страницы",
            required=False,
        ),
        OpenApiParameter(
            name="page_size",
            type=int,
            location=OpenApiParameter.QUERY,
            description="Количество элементов на странице (макс. 100)",
            required=False,
        ),
    ],
    responses={
        200: OrderSerializer(many=True),
        400: OpenApiResponse(description="Неверный запрос"),
    }
)
class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user).order_by("-created_at")
        paginator = OrderPageNumberPagination()
        page = paginator.paginate_queryset(orders, request, view=self)
        serializer = OrderSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(
    summary="Детали заказа",
    tags=["Order"],
    responses={
        200: OrderSerializer,
        404: OpenApiResponse(description="Заказ не найден"),
    }
)
class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        order = get_object_or_404(Order, id=pk, user=request.user)
        serializer = OrderSerializer(order)
        return Response(serializer.data)