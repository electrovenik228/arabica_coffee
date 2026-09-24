from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.bonus.models import LoyaltyTransaction
from apps.bonus.services.wallet import adjust_points
from apps.cart.models import Cart, CartItem
from apps.menu.models import Category, Product, Subcategory
from apps.order.models import Cafe
from apps.order.models.code import Order

User = get_user_model()


class CreateOrderBonusTests(APITestCase):
    """Бонусные баллы не должны начисляться на часть заказа, оплаченную баллами."""

    def setUp(self):
        self.user = User.objects.create_user(phone_number="+996700000030")
        self.client.force_authenticate(user=self.user)
        self.cafe = Cafe.objects.create(name="Test Cafe", is_active=True)

        category = Category.objects.create(title="Напитки")
        subcategory = Subcategory.objects.create(title="Кофе", category=category)
        self.product = Product.objects.create(
            title="Капучино",
            price=200,
            description="",
            subcategory=subcategory,
            bonus_percent=10,
        )
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)

    def test_earns_bonus_when_no_points_spent(self):
        response = self.client.post(
            "/api/v1/orders/create/", {"cafe_id": self.cafe.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(id=response.data["id"])
        self.assertEqual(order.bonus_earned, 20)  # 10% от 200
        self.assertEqual(order.bonus_spent, 0)

    def test_earns_zero_bonus_when_points_cover_part_of_order(self):
        adjust_points(self.user, 50, LoyaltyTransaction.Reason.ADMIN_ADJUSTMENT)

        response = self.client.post(
            "/api/v1/orders/create/",
            {"cafe_id": self.cafe.id, "use_bonus_points": 50},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(id=response.data["id"])
        self.assertEqual(order.bonus_spent, 50)
        self.assertEqual(order.bonus_earned, 0)  # без этого клиент мог бы бесконечно копить баллы

        self.user.refresh_from_db()
        self.assertEqual(self.user.loyalty_points, 0)
        self.assertTrue(
            LoyaltyTransaction.objects.filter(
                order=order, reason=LoyaltyTransaction.Reason.ORDER_SPENT, delta=-50
            ).exists()
        )

    def test_insufficient_points_rejected_and_no_order_created(self):
        response = self.client.post(
            "/api/v1/orders/create/",
            {"cafe_id": self.cafe.id, "use_bonus_points": 50},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Order.objects.exists())


class CancelOrderBonusRefundTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number="+996700000031")
        self.client.force_authenticate(user=self.user)
        self.cafe = Cafe.objects.create(name="Test Cafe", is_active=True)
        adjust_points(self.user, 100, LoyaltyTransaction.Reason.ADMIN_ADJUSTMENT)

        self.order = Order.objects.create(
            user=self.user,
            cafe=self.cafe,
            status="accepted",
            delivery_type="pickup",
            total_price=50,
            bonus_spent=40,
        )
        from apps.bonus.services.wallet import spend_order_points
        spend_order_points(self.user, self.order, 40)

    def test_cancel_refunds_spent_points(self):
        self.user.refresh_from_db()
        self.assertEqual(self.user.loyalty_points, 60)

        response = self.client.post(reverse("order-cancel", args=[self.order.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.loyalty_points, 100)

    def test_cancelling_twice_does_not_double_refund(self):
        self.client.post(reverse("order-cancel", args=[self.order.id]))
        self.client.post(reverse("order-cancel", args=[self.order.id]))

        self.user.refresh_from_db()
        self.assertEqual(self.user.loyalty_points, 100)

    def test_cannot_cancel_order_that_is_already_being_prepared(self):
        self.order.status = "ready"
        self.order.save(update_fields=["status"])

        response = self.client.post(reverse("order-cancel", args=[self.order.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertEqual(self.user.loyalty_points, 60)  # баллы не возвращены — заказ не отменён
