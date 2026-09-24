"""Единая точка изменения User.loyalty_points/coffee_cups/free_coffee_cups.

Любое начисление или списание баллов обязано идти через adjust_points, чтобы
баланс всегда был объясним записями в LoyaltyTransaction. Прямое присваивание
user.loyalty_points += N в вьюхах/сигналах запрещено — иначе теряется журнал
и идемпотентность.
"""
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.bonus.models import LoyaltyTransaction

User = get_user_model()

COFFEE_CUP_THRESHOLD = 6
GUEST_PHONE_PREFIX = "+00000"  # общий POS-аккаунт кафе для заказов без клиента


def is_guest_user(user) -> bool:
    return user.phone_number.startswith(GUEST_PHONE_PREFIX)


def adjust_points(
    user,
    delta: int,
    reason: str,
    *,
    order=None,
    created_by=None,
) -> LoyaltyTransaction:
    """Атомарно меняет баланс пользователя и пишет запись в журнал.

    Вызывающий код должен сам оборачивать серию вызовов в transaction.atomic(),
    если баланс читался заранее (select_for_update) — здесь дополнительно
    блокируется строка пользователя, поэтому вызов безопасен и в одиночку.
    """
    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        new_balance = locked_user.loyalty_points + delta
        if new_balance < 0:
            raise ValueError(
                f"Недостаточно баллов: баланс {locked_user.loyalty_points}, попытка списать {-delta}."
            )

        locked_user.loyalty_points = new_balance
        locked_user.save(update_fields=["loyalty_points"])

        entry = LoyaltyTransaction.objects.create(
            user=locked_user,
            delta=delta,
            reason=reason,
            order=order,
            created_by=created_by,
            balance_after=new_balance,
        )

    user.loyalty_points = new_balance
    return entry


def spend_order_points(user, order, points: int) -> None:
    if points <= 0:
        return
    adjust_points(user, -points, LoyaltyTransaction.Reason.ORDER_SPENT, order=order)


def refund_order_points(order) -> bool:
    """Возвращает бонусы, списанные на отменённый заказ. Идемпотентно."""
    if order.bonus_spent <= 0:
        return False
    if LoyaltyTransaction.objects.filter(
        order=order, reason=LoyaltyTransaction.Reason.ORDER_REFUNDED
    ).exists():
        return False

    adjust_points(order.user, order.bonus_spent, LoyaltyTransaction.Reason.ORDER_REFUNDED, order=order)
    return True


def award_order_bonus(order, *, created_by=None) -> bool:
    """Начисляет баллы и чашку кофе за заказ. Идемпотентно (Order.bonus_awarded)."""
    from apps.order.models import Order

    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        if locked_order.bonus_awarded:
            return False

        user = User.objects.select_for_update().get(pk=locked_order.user_id)
        if is_guest_user(user):
            locked_order.bonus_awarded = True
            locked_order.save(update_fields=["bonus_awarded"])
            return False

        if locked_order.bonus_earned > 0:
            adjust_points(
                user,
                locked_order.bonus_earned,
                LoyaltyTransaction.Reason.ORDER_EARNED,
                order=locked_order,
                created_by=created_by,
            )

        user.coffee_cups += 1
        if user.coffee_cups >= COFFEE_CUP_THRESHOLD:
            user.coffee_cups = 0
            user.free_coffee_cups += 1
        user.save(update_fields=["coffee_cups", "free_coffee_cups"])

        locked_order.bonus_awarded = True
        locked_order.save(update_fields=["bonus_awarded"])

    order.bonus_awarded = True
    return True


def redeem_free_cup(user) -> bool:
    """Списывает одну заработанную бесплатную чашку при выдаче. Возвращает False, если нечего списывать."""
    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if locked_user.free_coffee_cups <= 0:
            return False

        locked_user.free_coffee_cups -= 1
        locked_user.save(update_fields=["free_coffee_cups"])

    user.free_coffee_cups = locked_user.free_coffee_cups
    return True


def coffee_mission_progress(user) -> dict:
    """Единая форма данных о прогрессе "Кофейной миссии" для клиентов API."""
    return {
        "cups_collected": user.coffee_cups,
        "cups_required": COFFEE_CUP_THRESHOLD,
        "cups_remaining": COFFEE_CUP_THRESHOLD - user.coffee_cups,
        "free_cups_available": user.free_coffee_cups,
    }
