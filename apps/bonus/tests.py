from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.bonus.models import LoyaltyTransaction
from apps.bonus.services.wallet import (
    COFFEE_CUP_THRESHOLD,
    adjust_points,
    award_order_bonus,
    coffee_mission_progress,
    redeem_free_cup,
    refund_order_points,
    spend_order_points,
)
from apps.order.models import Cafe
from apps.order.models.code import Order

User = get_user_model()


def _make_order(user, cafe, **kwargs):
    defaults = dict(delivery_type="pickup", total_price=100, status="accepted")
    defaults.update(kwargs)
    return Order.objects.create(user=user, cafe=cafe, **defaults)


class WalletServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number="+996700000010")
        self.cafe = Cafe.objects.create(name="Test Cafe", is_active=True)

    def test_adjust_points_updates_balance_and_writes_ledger(self):
        entry = adjust_points(self.user, 50, LoyaltyTransaction.Reason.ADMIN_ADJUSTMENT)

        self.user.refresh_from_db()
        self.assertEqual(self.user.loyalty_points, 50)
        self.assertEqual(entry.balance_after, 50)
        self.assertEqual(entry.delta, 50)

    def test_adjust_points_rejects_going_negative(self):
        with self.assertRaises(ValueError):
            adjust_points(self.user, -10, LoyaltyTransaction.Reason.ORDER_SPENT)

        self.user.refresh_from_db()
        self.assertEqual(self.user.loyalty_points, 0)

    def test_award_order_bonus_credits_points_and_cup_once(self):
        # status="accepted" на create(), затем отдельный переход в delivered —
        # так же, как это делают реальные вьюхи (CourierDeliverView и т.п.),
        # чтобы сигнал handle_order_delivered сработал ровно один раз, как в проде.
        order = _make_order(
            self.user, self.cafe, status="accepted", bonus_earned=30, total_price=200
        )

        order.status = "delivered"
        order.save(update_fields=["status"])  # сигнал уже начислил бонус здесь
        self.user.refresh_from_db()
        self.assertEqual(self.user.loyalty_points, 30)
        self.assertEqual(self.user.coffee_cups, 1)

        second = award_order_bonus(order)
        self.user.refresh_from_db()
        self.assertFalse(second)
        self.assertEqual(self.user.loyalty_points, 30)  # не начислено повторно

    def test_award_order_bonus_skips_guest_pos_accounts(self):
        guest = User.objects.create_user(phone_number="+00000000001")
        order = _make_order(
            guest, self.cafe, status="delivered", bonus_earned=30, total_price=200
        )

        awarded = award_order_bonus(order)

        self.assertFalse(awarded)
        guest.refresh_from_db()
        self.assertEqual(guest.loyalty_points, 0)
        self.assertEqual(guest.coffee_cups, 0)

    def test_refund_order_points_is_idempotent(self):
        adjust_points(self.user, 100, LoyaltyTransaction.Reason.ADMIN_ADJUSTMENT)
        order = _make_order(self.user, self.cafe, bonus_spent=40, total_price=60)
        spend_order_points(self.user, order, 40)
        self.user.refresh_from_db()
        self.assertEqual(self.user.loyalty_points, 60)

        self.assertTrue(refund_order_points(order))
        self.user.refresh_from_db()
        self.assertEqual(self.user.loyalty_points, 100)

        self.assertFalse(refund_order_points(order))
        self.user.refresh_from_db()
        self.assertEqual(self.user.loyalty_points, 100)

    def _deliver_new_order(self):
        # status="accepted" на create(), затем отдельный переход в delivered,
        # чтобы сигнал handle_order_delivered сработал ровно один раз на заказ.
        order = _make_order(self.user, self.cafe, status="accepted", total_price=100)
        order.status = "delivered"
        order.save(update_fields=["status"])

    def test_coffee_mission_completes_cycle_and_grants_free_cup(self):
        for _ in range(COFFEE_CUP_THRESHOLD - 1):
            self._deliver_new_order()

        self.user.refresh_from_db()
        self.assertEqual(self.user.coffee_cups, COFFEE_CUP_THRESHOLD - 1)
        self.assertEqual(self.user.free_coffee_cups, 0)

        self._deliver_new_order()

        self.user.refresh_from_db()
        self.assertEqual(self.user.coffee_cups, 0)  # цикл сброшен
        self.assertEqual(self.user.free_coffee_cups, 1)  # заработана бесплатная чашка

    def test_coffee_mission_progress_shape(self):
        self.user.coffee_cups = 4
        self.user.free_coffee_cups = 2
        self.user.save(update_fields=["coffee_cups", "free_coffee_cups"])

        progress = coffee_mission_progress(self.user)

        self.assertEqual(progress, {
            "cups_collected": 4,
            "cups_required": COFFEE_CUP_THRESHOLD,
            "cups_remaining": COFFEE_CUP_THRESHOLD - 4,
            "free_cups_available": 2,
        })

    def test_redeem_free_cup_decrements_balance_once(self):
        self.user.free_coffee_cups = 1
        self.user.save(update_fields=["free_coffee_cups"])

        self.assertTrue(redeem_free_cup(self.user))
        self.user.refresh_from_db()
        self.assertEqual(self.user.free_coffee_cups, 0)

        self.assertFalse(redeem_free_cup(self.user))
        self.user.refresh_from_db()
        self.assertEqual(self.user.free_coffee_cups, 0)

    def test_ledger_rejects_duplicate_entry_for_same_order_and_reason(self):
        order = _make_order(self.user, self.cafe, status="delivered", total_price=100)
        LoyaltyTransaction.objects.create(
            user=self.user,
            delta=10,
            reason=LoyaltyTransaction.Reason.ORDER_EARNED,
            order=order,
            balance_after=10,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LoyaltyTransaction.objects.create(
                    user=self.user,
                    delta=10,
                    reason=LoyaltyTransaction.Reason.ORDER_EARNED,
                    order=order,
                    balance_after=20,
                )


class CourierBonusConfirmationAPITests(APITestCase):
    def setUp(self):
        self.cafe = Cafe.objects.create(name="Test Cafe", is_active=True)
        self.client_user = User.objects.create_user(phone_number="+996700000020")
        self.courier = User.objects.create_user(
            phone_number="+996700000021", is_courier=True
        )
        self.other_courier = User.objects.create_user(
            phone_number="+996700000022", is_courier=True
        )

        self.order = Order.objects.create(
            user=self.client_user,
            cafe=self.cafe,
            courier=self.courier,
            status="delivered",
            delivery_type="delivery",
            address="ул. Тестовая",
            total_price=200,
            bonus_earned=15,
        )
        # create() уже вызвал сигнал handle_order_delivered и начислил бонус.
        # queryset.update() не шлёт post_save — сбрасываем состояние, чтобы
        # протестировать ручное подтверждение курьером как отдельный путь
        # (например, если по какой-то причине авто-начисление не сработало).
        Order.objects.filter(pk=self.order.pk).update(bonus_awarded=False)
        LoyaltyTransaction.objects.filter(order=self.order).delete()
        self.order.refresh_from_db()
        self.client_user.loyalty_points = 0
        self.client_user.coffee_cups = 0
        self.client_user.save(update_fields=["loyalty_points", "coffee_cups"])

    def test_courier_confirms_points_for_own_delivered_order(self):
        self.client.force_authenticate(user=self.courier)
        response = self.client.post(
            reverse("add-points"), {"order_id": self.order.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["already_awarded"])
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.loyalty_points, 15)

    def test_confirming_twice_is_idempotent(self):
        self.client.force_authenticate(user=self.courier)
        self.client.post(reverse("add-points"), {"order_id": self.order.id}, format="json")
        response = self.client.post(
            reverse("add-points"), {"order_id": self.order.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["already_awarded"])
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.loyalty_points, 15)

    def test_courier_cannot_confirm_someone_elses_order(self):
        self.client.force_authenticate(user=self.other_courier)
        response = self.client.post(
            reverse("add-points"), {"order_id": self.order.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.loyalty_points, 0)

    def test_non_courier_forbidden(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post(
            reverse("add-points"), {"order_id": self.order.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_add_coffee_cup_confirms_for_own_delivered_order(self):
        self.client.force_authenticate(user=self.courier)
        response = self.client.post(
            reverse("add-coffee-cup"), {"order_id": self.order.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.coffee_cups, 1)

    def test_cannot_confirm_for_order_not_yet_delivered(self):
        self.order.status = "on_the_way"
        self.order.save(update_fields=["status"])

        self.client.force_authenticate(user=self.courier)
        response = self.client.post(
            reverse("add-points"), {"order_id": self.order.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class BonusInfoEndpointTests(APITestCase):
    def test_bonus_info_includes_coffee_mission_block(self):
        user = User.objects.create_user(phone_number="+996700000040")
        user.loyalty_points = 350
        user.coffee_cups = 4
        user.free_coffee_cups = 1
        user.save(update_fields=["loyalty_points", "coffee_cups", "free_coffee_cups"])
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("bonus-info"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["coffee_mission"], {
            "cups_collected": 4,
            "cups_required": COFFEE_CUP_THRESHOLD,
            "cups_remaining": COFFEE_CUP_THRESHOLD - 4,
            "free_cups_available": 1,
        })


class RedeemFreeCupAPITests(APITestCase):
    def setUp(self):
        self.courier = User.objects.create_user(
            phone_number="+996700000050", is_courier=True
        )
        self.client_user = User.objects.create_user(
            phone_number="+996700000051", free_coffee_cups=1
        )

    def test_courier_redeems_free_cup_by_qr_code(self):
        self.client.force_authenticate(user=self.courier)
        response = self.client.post(
            reverse("redeem-free-cup"),
            {"qr_code_data": self.client_user.qr_code},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["free_cups_available"], 0)
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.free_coffee_cups, 0)

    def test_cannot_redeem_when_none_available(self):
        self.client_user.free_coffee_cups = 0
        self.client_user.save(update_fields=["free_coffee_cups"])
        self.client.force_authenticate(user=self.courier)

        response = self.client.post(
            reverse("redeem-free-cup"),
            {"qr_code_data": self.client_user.qr_code},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_qr_code_returns_404(self):
        self.client.force_authenticate(user=self.courier)
        response = self.client.post(
            reverse("redeem-free-cup"), {"qr_code_data": "does-not-exist"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_courier_forbidden(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post(
            reverse("redeem-free-cup"),
            {"qr_code_data": self.client_user.qr_code},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
