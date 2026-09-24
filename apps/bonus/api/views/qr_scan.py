from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from apps.bonus.api.serializers import ScanQRCodeSerializer
from apps.bonus.api.serializers.qr_scan import ScanQRCodeResponseSerializer
from apps.users.models import User
from arabica.api_utils import api_error

@extend_schema(
    summary="Сканирование qr-code для курьера",
    tags=["Courier"],
    request=ScanQRCodeSerializer,
    responses={
        200: ScanQRCodeResponseSerializer,
        400: OpenApiResponse(description="Неверные данные запроса"),
        403: OpenApiResponse(description="Нет прав доступа (не курьер)"),
        404: OpenApiResponse(description="Пользователь с таким QR-кодом не найден"),
    }
)
class ScanQRCodeView(APIView):
    """
    Курьер сканирует QR-код.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_courier:
            return api_error(
                code="forbidden",
                message="Нет прав доступа.",
                status_code=403,
            )

        serializer = ScanQRCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        qr_code_data = serializer.validated_data["qr_code_data"]

        user = get_object_or_404(User, qr_code=qr_code_data)

        response_serializer = ScanQRCodeResponseSerializer({
            "user_id": user.id,
            "name": f"{user.first_name} {user.last_name}",
            "loyalty_points": user.loyalty_points,
            "coffee_cups": user.coffee_cups,
            "free_cups_available": user.free_coffee_cups,
        })

        return Response(response_serializer.data)
