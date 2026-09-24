from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.order.crm_services import broadcast_cafe_orders
from apps.order.models import Order


@receiver(post_save, sender=Order)
def notify_cafe_order_saved(sender, instance, **kwargs):
    if instance.cafe_id:
        broadcast_cafe_orders(instance.cafe_id)


@receiver(post_delete, sender=Order)
def notify_cafe_order_deleted(sender, instance, **kwargs):
    if instance.cafe_id:
        broadcast_cafe_orders(instance.cafe_id)


@receiver(post_save, sender=Order)
def handle_order_delivered(sender, instance, **kwargs):
    if instance.status != "delivered" or instance.bonus_awarded:
        return

    from apps.bonus.services.wallet import award_order_bonus

    award_order_bonus(instance)
