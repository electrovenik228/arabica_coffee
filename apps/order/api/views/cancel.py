from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bonus.services.wallet import refund_order_points
from apps.order.api.serializers.code import OrderSerializer
from apps.order.models.code import Order
from arabica.api_utils import api_error

CANCELLABLE_STATUSES = ("accepted",)


@extend_schema(
    summary="Отменить заказ",
    tags=["Order"],
    responses={
        200: OrderSerializer,
        400: OpenApiResponse(description="Заказ нельзя отменить (уже готовится или доставляется)"),
        404: OpenApiResponse(description="Заказ не найден"),
    },
    description=(
        "Клиент может отменить заказ только пока он в статусе «Принят». "
        "После перехода в «Готов» или позже — отмена недоступна."
    ),
)
class CancelOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = get_object_or_404(Order, id=pk, user=request.user)

        if order.status == "cancelled":
            return Response(OrderSerializer(order).data)

        if order.status not in CANCELLABLE_STATUSES:
            return api_error(
                code="cannot_cancel",
                message=(
                    f"Нельзя отменить заказ со статусом «{order.get_status_display()}». "
                    "Отмена доступна только для новых заказов."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            order.status = "cancelled"
            order.updated_at = timezone.now()
            order.save(update_fields=["status", "updated_at"])
            refund_order_points(order)

        return Response(OrderSerializer(order).data)
