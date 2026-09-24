from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bonus.api.serializers import AddCoffeeCupSerializer, AddLoyaltyPointsSerializer
from apps.bonus.api.serializers.loyalty import (
    AddLoyaltyPointsResponseSerializer,
    AddCoffeeCupResponseSerializer,
    RedeemFreeCupResponseSerializer,
    RedeemFreeCupSerializer,
)
from apps.bonus.services.wallet import award_order_bonus, redeem_free_cup
from apps.order.models import Order
from apps.users.models import User
from arabica.api_utils import api_error


def _get_own_delivered_order(request, order_id: int) -> Order:
    return get_object_or_404(
        Order, id=order_id, courier_id=request.user.id, status="delivered"
    )


@extend_schema(
    summary="Подтвердить начисление бонусных баллов за доставленный заказ",
    tags=["Courier"],
    request=AddLoyaltyPointsSerializer,
    responses={
        200: AddLoyaltyPointsResponseSerializer,
        400: OpenApiResponse(description="Неверные данные"),
        403: OpenApiResponse(description="Доступ только для курьеров"),
        404: OpenApiResponse(description="Заказ не найден, не ваш или ещё не доставлен"),
    },
    description=(
        "Баллы начисляются автоматически при переводе заказа в статус «доставлен». "
        "Этот эндпоинт — подтверждение того же начисления по QR-коду клиента "
        "(идемпотентно: повторный вызов ничего не изменит, если баллы уже начислены). "
        "Сумма берётся из заказа и не может быть указана произвольно."
    ),
    examples=[
        OpenApiExample(
            "Подтвердить по заказу",
            value={"order_id": 123},
            request_only=True,
        )
    ],
)
class AddLoyaltyPointsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_courier:
            return api_error(code="forbidden", message="Нет прав доступа.", status_code=403)

        serializer = AddLoyaltyPointsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = _get_own_delivered_order(request, serializer.validated_data["order_id"])

        newly_awarded = award_order_bonus(order, created_by=request.user)
        user = order.user
        user.refresh_from_db(fields=["loyalty_points"])

        message = (
            f"Начислено {order.bonus_earned} баллов за заказ #{order.id}."
            if newly_awarded
            else "Баллы за этот заказ уже были начислены."
        )
        return Response(
            AddLoyaltyPointsResponseSerializer({
                "message": message,
                "already_awarded": not newly_awarded,
                "total_loyalty_points": user.loyalty_points,
            }).data
        )


@extend_schema(
    summary="Подтвердить чашку кофе за доставленный заказ",
    tags=["Courier"],
    request=AddCoffeeCupSerializer,
    responses={
        200: AddCoffeeCupResponseSerializer,
        403: OpenApiResponse(description="Доступ только для курьеров"),
        404: OpenApiResponse(description="Заказ не найден, не ваш или ещё не доставлен"),
    },
    description=(
        "Чашка кофе начисляется автоматически при переводе заказа в статус «доставлен» "
        "(после 6 чашек счётчик сбрасывается — бесплатная чашка). Этот эндпоинт — "
        "подтверждение того же начисления по QR-коду клиента, идемпотентно."
    ),
)
class AddCoffeeCupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_courier:
            return api_error(code="forbidden", message="Нет прав доступа.", status_code=403)

        serializer = AddCoffeeCupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = _get_own_delivered_order(request, serializer.validated_data["order_id"])

        newly_awarded = award_order_bonus(order, created_by=request.user)
        user = order.user
        user.refresh_from_db(fields=["coffee_cups", "free_coffee_cups"])

        if not newly_awarded:
            message = "Чашка за этот заказ уже была начислена."
        elif user.coffee_cups == 0 and user.free_coffee_cups > 0:
            message = "Чашка добавлена. Пользователь заработал бесплатную чашку кофе! 🎉"
        else:
            message = f"Чашка кофе добавлена. До бесплатной — {6 - user.coffee_cups}."

        return Response(
            AddCoffeeCupResponseSerializer({
                "message": message,
                "already_awarded": not newly_awarded,
                "current_coffee_cups": user.coffee_cups,
            }).data
        )


@extend_schema(
    summary="Выдать заработанную бесплатную чашку кофе по QR-коду",
    tags=["Courier"],
    request=RedeemFreeCupSerializer,
    responses={
        200: RedeemFreeCupResponseSerializer,
        400: OpenApiResponse(description="У клиента нет бесплатных чашек"),
        403: OpenApiResponse(description="Доступ только для курьеров"),
        404: OpenApiResponse(description="Клиент с таким QR-кодом не найден"),
    },
    description=(
        "Списывает одну бесплатную чашку из free_coffee_cups клиента в момент, когда "
        "она физически выдана (акция «Кофейная миссия»: 6 куплено — 7-я бесплатно). "
        "Баланс бесплатных чашек виден заранее в ответе qr-scan и в GET /bonus/."
    ),
    examples=[
        OpenApiExample(
            "Выдать по QR-коду",
            value={"qr_code_data": "abc123..."},
            request_only=True,
        )
    ],
)
class RedeemFreeCupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_courier:
            return api_error(code="forbidden", message="Нет прав доступа.", status_code=403)

        serializer = RedeemFreeCupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_object_or_404(User, qr_code=serializer.validated_data["qr_code_data"])

        if not redeem_free_cup(user):
            return api_error(
                code="no_free_cups",
                message="У клиента нет бесплатных чашек для выдачи.",
                status_code=400,
            )

        return Response(
            RedeemFreeCupResponseSerializer({
                "message": "Бесплатная чашка выдана.",
                "free_cups_available": user.free_coffee_cups,
            }).data
        )
