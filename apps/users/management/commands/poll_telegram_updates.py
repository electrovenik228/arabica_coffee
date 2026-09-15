import logging
import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.users.utils.telegram import get_updates, process_telegram_update

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Long-polling воркер для Telegram-бота с кодами подтверждения.

    Сервер хостится в РФ, и входящие запросы от Telegram (webhook) до него нестабильно
    доходят из-за блокировок Роскомнадзора, поэтому вместо push-модели сервер сам
    исходящими запросами спрашивает Telegram о новых сообщениях (getUpdates).
    Держать этот процесс запущенным постоянно, например через отдельный сервис
    в docker-compose (см. telegram-poller).
    """

    help = "Long-polls Telegram getUpdates and processes bot messages (contact linking, /start)."

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            self.stderr.write(self.style.ERROR("TELEGRAM_BOT_TOKEN is not set, exiting."))
            return

        # getUpdates не работает, пока у бота зарегистрирован webhook — снимаем его,
        # если он вдруг остался с прошлой настройки.
        self._delete_webhook()

        offset = None
        self.stdout.write(self.style.SUCCESS("Telegram long polling started."))

        while True:
            try:
                updates = get_updates(offset=offset, timeout=30)
            except Exception:
                logger.exception("Telegram getUpdates failed, retrying in 5s")
                time.sleep(5)
                continue

            for update in updates:
                offset = update["update_id"] + 1
                try:
                    process_telegram_update(update)
                except Exception:
                    logger.exception(
                        "Failed to process Telegram update %s", update.get("update_id")
                    )

    def _delete_webhook(self):
        try:
            requests.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/deleteWebhook",
                timeout=10,
            )
        except Exception:
            logger.warning("Could not delete Telegram webhook on startup", exc_info=True)
