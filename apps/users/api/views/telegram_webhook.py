import logging

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import TelegramLink
from apps.users.utils.phone import normalize_phone_number
from apps.users.utils.telegram import send_telegram_message

logger = logging.getLogger(__name__)

CONTACT_KEYBOARD = {
    "keyboard": [[{"text": "Поделиться номером телефона", "request_contact": True}]],
    "resize_keyboard": True,
    "one_time_keyboard": True,
}


@extend_schema(exclude=True)
class TelegramWebhookView(APIView):
    """Принимает обновления от Telegram-бота, используемого для доставки кодов подтверждения."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        if settings.TELEGRAM_WEBHOOK_SECRET:
            secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if secret != settings.TELEGRAM_WEBHOOK_SECRET:
                return Response(status=403)

        message = request.data.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return Response({"ok": True})

        contact = message.get("contact")
        if contact and contact.get("phone_number"):
            self._link_contact(chat_id, contact["phone_number"])
            return Response({"ok": True})

        text = (message.get("text") or "").strip()
        if text.startswith("/start"):
            send_telegram_message(
                chat_id,
                "Здравствуйте! Чтобы получать коды подтверждения Arabica Coffee, "
                "поделитесь своим номером телефона кнопкой ниже.",
                reply_markup=CONTACT_KEYBOARD,
            )

        return Response({"ok": True})

    def _link_contact(self, chat_id, raw_phone_number):
        try:
            phone_number = normalize_phone_number(raw_phone_number)
        except Exception:
            logger.warning("Telegram webhook: unparsable phone number %r", raw_phone_number)
            send_telegram_message(chat_id, "Не удалось распознать номер телефона.")
            return

        TelegramLink.objects.update_or_create(
            phone_number=phone_number, defaults={"chat_id": chat_id}
        )
        send_telegram_message(
            chat_id,
            "Номер привязан. Коды подтверждения Arabica Coffee теперь будут приходить сюда.",
        )
