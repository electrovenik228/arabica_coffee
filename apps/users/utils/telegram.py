"""Временная замена apps.users.utils.twilio на период, пока подписка Twilio не оплачена.

Код подтверждения доставляется в личный чат клиента с Telegram-ботом вместо SMS.
Чтобы вернуться на Twilio, поменяйте импорт в apps/users/api/views/login.py обратно
на apps.users.utils.twilio — сам модуль twilio.py не менялся и продолжит работать.
"""
import requests
from django.conf import settings


class TelegramNotLinkedError(Exception):
    """Номер телефона ещё не привязан к боту (клиент не поделился контактом)."""


def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"


def send_telegram_message(chat_id: int, text: str, reply_markup: dict | None = None) -> None:
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    response = requests.post(_api_url("sendMessage"), json=payload, timeout=5)
    response.raise_for_status()


def send_verification_code(phone_number: str) -> bool:
    from apps.users.models import PhoneConfirmationCode, TelegramLink

    link = TelegramLink.objects.filter(phone_number=phone_number).first()
    if not link:
        raise TelegramNotLinkedError(phone_number)

    code = PhoneConfirmationCode.generate_code()
    PhoneConfirmationCode.objects.create(phone_number=phone_number, code=code)

    send_telegram_message(
        link.chat_id,
        f"Ваш код подтверждения Arabica Coffee: {code}\nКод действителен 5 минут.",
    )
    return True


def check_verification_code(phone_number: str, code: str) -> bool:
    from apps.users.models import PhoneConfirmationCode

    confirmation = (
        PhoneConfirmationCode.objects.filter(
            phone_number=phone_number, code=code, is_used=False
        )
        .order_by("-created_at")
        .first()
    )
    if not confirmation or confirmation.is_expired():
        return False

    confirmation.is_used = True
    confirmation.save(update_fields=["is_used"])
    return True
