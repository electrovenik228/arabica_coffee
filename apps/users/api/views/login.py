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

        # Создаем пользователя или ищем существующего
        user, created = User.objects.get_or_create(phone_number=phone_number)

        # Генерируем код (пока заглушка)
        send_verification_code(phone_number)

        return Response(
            {
                "success": True,
                "message": "Код отправлен на номер",
                "is_new_user": created,
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
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"]
        code = serializer.validated_data["code"]

        if not check_verification_code(phone_number, code):
            return api_error(
                code="invalid_code",
                message="Неверный или просроченный код.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return api_error(
                code="user_not_found",
                message="Пользователь не найден.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Генерация токенов
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        return Response(
            {
                "success": True,
                "message": "Код успешно подтвержден",
                "access": str(access),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )
