from django.db import models


class TelegramLink(models.Model):
    """Связывает номер телефона с личным чатом клиента с ботом.

    Заполняется вебхуком бота, когда клиент делится контактом. Используется
    вместо Twilio для доставки кода подтверждения, пока её подписка не оплачена.
    """

    phone_number = models.CharField(max_length=20, unique=True)
    chat_id = models.BigIntegerField()
    linked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.phone_number} -> {self.chat_id}"
