from django.conf import settings
from django.db import models


class LoyaltyTransaction(models.Model):
    """Неизменяемый журнал начислений/списаний бонусных баллов.

    User.loyalty_points остаётся денормализованным текущим балансом для быстрого
    чтения, но каждое его изменение обязано проходить через
    apps.bonus.services.wallet и одновременно писать сюда — иначе баланс
    необъясним (нельзя понять, откуда взялось конкретное число).
    """

    class Reason(models.TextChoices):
        ORDER_EARNED = "order_earned", "Начислено за заказ"
        ORDER_SPENT = "order_spent", "Списано на заказ"
        ORDER_REFUNDED = "order_refunded", "Возврат баллов за отменённый заказ"
        ADMIN_ADJUSTMENT = "admin_adjustment", "Корректировка администратором"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loyalty_transactions",
    )
    delta = models.IntegerField(
        help_text="Положительное значение — начисление, отрицательное — списание."
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    order = models.ForeignKey(
        "order.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loyalty_transactions",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Кто инициировал операцию (курьер/админ). Пусто для автоматических начислений.",
    )
    balance_after = models.IntegerField(help_text="Баланс пользователя сразу после этой операции.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]
        constraints = [
            # На один заказ не может быть больше одной записи с данной причиной —
            # это дополнительная страховка от двойного начисления/списания/возврата
            # поверх идемпотентности на уровне Order.bonus_awarded.
            models.UniqueConstraint(
                fields=["order", "reason"],
                condition=models.Q(order__isnull=False),
                name="bonus_one_ledger_entry_per_order_reason",
            )
        ]

    def __str__(self):
        return f"user={self.user_id} {self.delta:+d} ({self.reason})"
