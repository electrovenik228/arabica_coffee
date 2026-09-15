import logging

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.utils.telegram import process_telegram_update

logger = logging.getLogger(__name__)


@extend_schema(exclude=True)
class TelegramWebhookView(APIView):
    """Резервный канал приёма апдейтов от Telegram-бота.

    Сервер хостится в РФ, и серверы Telegram не могут стабильно достучаться до него
    входящими запросами, поэтому основной канал — long polling (см.
    apps/users/management/commands/poll_telegram_updates.py). Этот вебхук оставлен
    на случай переезда на хостинг вне РФ: тогда достаточно зарегистрировать
    setWebhook и остановить поллер.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        if settings.TELEGRAM_WEBHOOK_SECRET:
            secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if secret != settings.TELEGRAM_WEBHOOK_SECRET:
                return Response(status=403)

        process_telegram_update(request.data)
        return Response({"ok": True})
