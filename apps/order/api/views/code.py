from decimal import Decimal, ROUND_DOWN

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bonus.services.wallet import spend_order_points
from apps.cart.models import Cart
from apps.order.api.pagination import OrderPageNumberPagination
from apps.order.api.serializers.code import (
    OrderCreateSerializer,
    OrderSerializer,
)
from apps.order.models.code import Order, OrderItem
from apps.order.models import Cafe
from arabica.api_utils import api_error

User = get_user_model()


@extend_schema(
    summary="Создать заказ из корзины",
    tags=["Order"],
    request=OrderCreateSerializer,
    responses={
        201: OrderSerializer,
        400: OpenApiResponse(description="Корзина пуста или ошибка валидации"),
        404: OpenApiResponse(description="Кафе не найдено или неактивно"),
    },
    description=(
        "Создаёт заказ на основе текущей корзины пользователя. "
        "После создания корзина очищается, а пользователю начисляются бонусные баллы. "
        "Для доставки обязателен параметр `address`."
    ),
)
class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        cafe_id = serializer.validated_data["cafe_id"]
        cafe = get_object_or_404(Cafe, id=cafe_id, is_active=True)

        cart, _ = Cart.objects.get_or_create(user=user)
        if not cart.items.exists():
            return api_error(
                code="cart_empty",
                message="Корзина пуста.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        delivery_type    = serializer.validated_data.get("delivery_type", "pickup")
        address          = serializer.validated_data.get("address")
        delivery_time    = serializer.validated_data.get("delivery_time")
        courier_comment  = serializer.validated_data.get("courier_comment") or ""
        use_bonus_points = serializer.validated_data.get("use_bonus_points", 0)

        with transaction.atomic():
            # Lock user row to safely read/write loyalty_points
            locked_user = User.objects.select_for_update().get(id=user.id)

            # Validate bonus points request upfront
            if use_bonus_points > locked_user.loyalty_points:
                return api_error(
                    code="insufficient_points",
                    message=(
                        f"Недостаточно бонусных баллов. "
                        f"Доступно: {locked_user.loyalty_points}."
                    ),
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            order = Order.objects.create(
                user=user,
                cafe=cafe,
                delivery_type=delivery_type,
                address=address,
                delivery_time=delivery_time,
                courier_comment=courier_comment,
                total_price=Decimal("0.00"),
                bonus_spent=0,
            )

            total_price = Decimal("0.00")
            bonus_earned = Decimal("0.00")

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
                    product_options={"options": options, "comment": cart_item.comment or ""},
                    final_price=item_price,
                )
                total_price += item_price
                bonus_percent = Decimal(str(cart_item.product.bonus_percent or 0))
                bonus_earned += (item_price * bonus_percent) / Decimal("100")

            # Apply bonus discount (1 point = 1 som, cannot exceed total)
            bonus_spent = 0
            if use_bonus_points > 0:
                bonus_spent  = min(use_bonus_points, int(total_price))
                total_price  = max(Decimal("0.00"), total_price - Decimal(str(bonus_spent)))

            # Баллы не начисляются на часть заказа, оплаченную баллами — иначе
            # клиент мог бы бесконечно воспроизводить баллы, оплачивая ими же
            # новые заказы и получая новые баллы с "бесплатной" суммы.
            earned_int = (
                0 if bonus_spent > 0
                else int(bonus_earned.quantize(Decimal("1"), rounding=ROUND_DOWN))
            )
            order.total_price = total_price
            order.bonus_spent = bonus_spent
            order.bonus_earned = earned_int
            order.save(update_fields=["total_price", "bonus_spent", "bonus_earned"])

            spend_order_points(locked_user, order, bonus_spent)

            cart.items.all().delete()
            cache.delete(f"user_cart_{user.id}")

        try:
            from apps.printing.utils import create_and_broadcast_print_job
            create_and_broadcast_print_job(order)
        except Exception:
            pass

        serializer = OrderSerializer(order, context={"request": request})
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
        orders = (
            Order.objects.filter(user=request.user)
            .prefetch_related("items__product")
            .order_by("-created_at")
        )
        paginator = OrderPageNumberPagination()
        page = paginator.paginate_queryset(orders, request, view=self)
        serializer = OrderSerializer(page, many=True, context={"request": request})
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
        order = get_object_or_404(
            Order.objects.prefetch_related("items__product"),
            id=pk,
            user=request.user,
        )
        serializer = OrderSerializer(order, context={"request": request})
        return Response(serializer.data)