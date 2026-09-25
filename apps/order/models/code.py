from decimal import Decimal

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Order(models.Model):
    ORDER_STATUS = [
        ("accepted", "Ваш заказ принят"),
        ("ready", "Заказ готов"),
        ("on_the_way", "Курьер в пути"),
        ("delivered", "Заказ доставлен"),
        ("cancelled", "Заказ отменён"),
    ]

    DELIVERY_TYPE_CHOICES = [
        ("delivery", "Доставка"),
        ("pickup", "Самовывоз"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    cafe = models.ForeignKey(
        "order.Cafe",
        on_delete=models.PROTECT,
        related_name="orders",
        null=True,
        blank=True,
    )
    courier = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="courier_orders",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default="accepted")
    delivery_type = models.CharField(max_length=10, choices=DELIVERY_TYPE_CHOICES)
    address = models.TextField(blank=True, null=True)  # Только для доставки
    delivery_time = models.TimeField(blank=True, null=True)  # Время доставки
    courier_comment = models.TextField(blank=True, default="")  # Комментарий клиента для курьера
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    bonus_spent = models.PositiveIntegerField(default=0)
    bonus_earned = models.PositiveIntegerField(default=0)
    bonus_awarded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    ready_at = models.DateTimeField(blank=True, null=True)
    on_the_way_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} ({self.user.phone_number}, cafe={self.cafe_id})"

    class Meta:
        app_label = "order"
        indexes = [
            models.Index(fields=["status"], name="order_status_idx"),
            models.Index(fields=["user"], name="order_user_idx"),
            models.Index(fields=["cafe"], name="order_cafe_idx"),
            models.Index(fields=["courier"], name="order_courier_idx"),
            models.Index(fields=["status", "cafe"], name="order_status_cafe_idx"),
        ]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "menu.Product", on_delete=models.CASCADE
    )  # Use string reference to avoid circular import
    quantity = models.IntegerField(default=1)
    product_options = models.JSONField(default=dict, blank=True)  # Информация о выбранных опциях
    final_price = models.DecimalField(max_digits=10, decimal_places=2)  # Цена за всю позицию (кол-во * цена)

    def save(self, *args, **kwargs):
        if self.final_price is None:
            from apps.menu.models.option import OptionValue
            base_price = Decimal(str(self.product.price))
            option_ids = [
                opt["id"]
                for opt in (self.product_options or {}).get("options", [])
                if "id" in opt
            ]
            extra_cost = Decimal("0")
            if option_ids:
                total = OptionValue.objects.filter(id__in=option_ids).aggregate(
                    total=models.Sum("additional_cost")
                )["total"]
                extra_cost = Decimal(str(total or 0))
            self.final_price = (base_price + extra_cost) * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} x {self.product.title} ({self.order.id})"

    class Meta:
        app_label = "order"
