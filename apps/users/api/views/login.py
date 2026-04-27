import logging

from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.api.serializers import SendCodeSerializer, VerifyCodeSerializer
from arabica.api_utils import api_error
from apps.users.utils.twilio import send_verification_code, check_verification_code

User = get_user_model()
logger = logging.getLogger(__name__)


@extend_schema(
    summary="Send code to phone number",
    tags=["Authentication"],
    request=SendCodeSerializer,
    responses={200: OpenApiResponse(description="Код отправлен"), 400: SendCodeSerializer},
)
class SendCodeView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = SendCodeSerializer(data=request.data)

        if not serializer.is_valid():
            return api_error(
                code="validation_error",
                message="Ошибка валидации.",
                status_code=status.HTTP_400_BAD_REQUEST,
                details=serializer.errors,
            )

        phone_number = serializer.validated_data["phone_number"]

        user_exists = User.objects.filter(phone_number=phone_number).exists()

        try:
            send_verification_code(phone_number)
        except Exception as exc:
            logger.exception("Twilio send-code failed for %s", phone_number)
            return api_error(
                code="verification_unavailable",
                message=f"Не удалось отправить код подтверждения: {exc}",
                status_code=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "success": True,
                "message": "Код отправлен на номер",
                "is_new_user": not user_exists,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    summary="Verify code for phone number",
    tags=["Authentication"],
    request=VerifyCodeSerializer,
    responses={200: OpenApiResponse(description="Код подтвержден"), 400: OpenApiResponse(description="Ошибка проверки")},
)
class VerifyCodeView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = VerifyCodeSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="validation_error",
                message="Ошибка валидации.",
                status_code=status.HTTP_400_BAD_REQUEST,
                details=serializer.errors,
            )

        phone_number = serializer.validated_data["phone_number"]
        code = serializer.validated_data["code"]

        try:
            is_valid_code = check_verification_code(phone_number, code)
        except Exception as exc:
            logger.exception("Twilio verify-code failed for %s", phone_number)
            return api_error(
                code="verification_unavailable",
                message=f"Сервис проверки кода временно недоступен: {exc}",
                status_code=status.HTTP_502_BAD_GATEWAY,
            )

        if not is_valid_code:
            return api_error(
                code="invalid_code",
                message="Неверный или просроченный код.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        user, created = User.objects.get_or_create(phone_number=phone_number)
        user.mark_phone_as_verified()
        user.save(update_fields=["is_phone_verified", "phone_verified_at"])

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        return Response(
            {
                "success": True,
                "message": "Код успешно подтвержден",
                "is_new_user": created,
                "is_phone_verified": user.is_phone_verified,
                "access": str(access),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )
