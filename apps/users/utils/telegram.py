"""Временная замена apps.users.utils.twilio на период, пока подписка Twilio не оплачена.

Код подтверждения доставляется в личный чат клиента с Telegram-ботом вместо SMS.
Чтобы вернуться на Twilio, поменяйте импорт в apps/users/api/views/login.py обратно
на apps.users.utils.twilio — сам модуль twilio.py не менялся и продолжит работать.

Сервер хостится в РФ, а серверы Telegram не могут стабильно достучаться до него
входящими запросами (последствия блокировок Роскомнадзора), поэтому вебхук
(TelegramWebhookView) ненадёжен. Основной канал получения апдейтов — long polling
через management-команду poll_telegram_updates (apps/users/management/commands),
которая сама ходит к Telegram исходящими запросами. process_telegram_update ниже
используется и поллером, и вебхуком (оставлен как резерв на случай переезда хостинга).
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

CONTACT_KEYBOARD = {
    "keyboard": [[{"text": "Поделиться номером телефона", "request_contact": True}]],
    "resize_keyboard": True,
    "one_time_keyboard": True,
}


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


def get_updates(offset: int | None = None, timeout: int = 30) -> list[dict]:
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    response = requests.get(_api_url("getUpdates"), params=params, timeout=timeout + 5)
    response.raise_for_status()
    return response.json().get("result", [])


def process_telegram_update(update: dict) -> None:
    """Обрабатывает один апдейт от Telegram: /start или отправку контакта."""
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return

    contact = message.get("contact")
    if contact and contact.get("phone_number"):
        _link_contact(chat_id, contact["phone_number"])
        return

    text = (message.get("text") or "").strip()
    if text.startswith("/start"):
        send_telegram_message(
            chat_id,
            "Здравствуйте! Чтобы получать коды подтверждения Arabica Coffee, "
            "поделитесь своим номером телефона кнопкой ниже.",
            reply_markup=CONTACT_KEYBOARD,
        )


def _link_contact(chat_id: int, raw_phone_number: str) -> None:
    from apps.users.models import TelegramLink
    from apps.users.utils.phone import normalize_phone_number

    try:
        phone_number = normalize_phone_number(raw_phone_number)
    except Exception:
        logger.warning("Telegram: unparsable phone number %r", raw_phone_number)
        send_telegram_message(chat_id, "Не удалось распознать номер телефона.")
        return

    TelegramLink.objects.update_or_create(
        phone_number=phone_number, defaults={"chat_id": chat_id}
    )
    send_telegram_message(
        chat_id,
        "Номер привязан. Коды подтверждения Arabica Coffee теперь будут приходить сюда.",
    )


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
