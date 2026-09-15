from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import PhoneConfirmationCode, TelegramLink
from apps.users.utils.telegram import TelegramNotLinkedError


User = get_user_model()


class PhoneVerificationAuthTests(APITestCase):
    def setUp(self):
        cache.clear()  # reset per-IP send/verify code throttle counters between tests

    def test_send_code_accepts_e164_phone_and_does_not_create_user(self):
        with patch("apps.users.api.views.login.send_verification_code") as mock_send:
            response = self.client.post(
                reverse("send_code"),
                {"phone_number": "+996700123456"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["is_new_user"], True)
        self.assertFalse(User.objects.filter(phone_number="+996700123456").exists())
        mock_send.assert_called_once_with("+996700123456")

    def test_send_code_returns_error_when_delivery_fails(self):
        with patch(
            "apps.users.api.views.login.send_verification_code",
            side_effect=Exception("telegram error"),
        ):
            response = self.client.post(
                reverse("send_code"),
                {"phone_number": "+996700123456"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(response.data["success"], False)

    def test_send_code_returns_telegram_not_linked_error(self):
        with patch(
            "apps.users.api.views.login.send_verification_code",
            side_effect=TelegramNotLinkedError("+996700123456"),
        ):
            response = self.client.post(
                reverse("send_code"),
                {"phone_number": "+996700123456"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "telegram_not_linked")

    def test_send_and_verify_code_via_telegram_flow(self):
        TelegramLink.objects.create(phone_number="+996700123456", chat_id=555)

        with patch("apps.users.utils.telegram.send_telegram_message") as mock_send:
            response = self.client.post(
                reverse("send_code"),
                {"phone_number": "+996700123456"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args.args[0], 555)

        confirmation = PhoneConfirmationCode.objects.get(phone_number="+996700123456")

        response = self.client.post(
            reverse("verify_code"),
            {"phone_number": "+996700123456", "code": confirmation.code},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

        # A used code cannot be replayed.
        response = self.client.post(
            reverse("verify_code"),
            {"phone_number": "+996700123456", "code": confirmation.code},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_code_marks_user_as_verified_and_returns_tokens(self):
        with patch("apps.users.api.views.login.check_verification_code", return_value=True):
            response = self.client.post(
                reverse("verify_code"),
                {"phone_number": "+996700123456", "code": "1234"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        user = User.objects.get(phone_number="+996700123456")
        self.assertTrue(user.is_phone_verified)
        self.assertIsNotNone(user.phone_verified_at)

    def test_verify_code_rejects_invalid_phone_format(self):
        response = self.client.post(
            reverse("verify_code"),
            {"phone_number": "0700-123-456", "code": "1234"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["success"], False)


class ProfileDeletionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number="+996700123456",
            first_name="Aman",
            last_name="Testov",
        )
        self.original_pk = self.user.pk
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_delete_profile_deactivates_and_anonymizes_user(self):
        response = self.client.delete(reverse("my-profile"))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertNotEqual(self.user.phone_number, "+996700123456")
        self.assertIsNone(self.user.first_name)
        self.assertIsNone(self.user.last_name)
        self.assertIsNone(self.user.qr_code)

    def test_delete_profile_blacklists_outstanding_tokens(self):
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        outstanding = OutstandingToken.objects.get(jti=refresh["jti"])

        self.client.delete(reverse("my-profile"))

        self.assertTrue(BlacklistedToken.objects.filter(token=outstanding).exists())

    def test_freed_phone_number_can_be_used_to_register_again(self):
        self.client.delete(reverse("my-profile"))
        self.client.credentials()  # deleted account's token is now blacklisted

        confirmation = PhoneConfirmationCode.objects.create(
            phone_number="+996700123456", code="482913"
        )

        response = self.client.post(
            reverse("verify_code"),
            {"phone_number": "+996700123456", "code": confirmation.code},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_new_user"])
        new_user = User.objects.get(phone_number="+996700123456")
        self.assertNotEqual(new_user.pk, self.original_pk)


class TelegramWebhookTests(APITestCase):
    def test_contact_message_links_phone_to_chat(self):
        with patch("apps.users.utils.telegram.send_telegram_message") as mock_send:
            response = self.client.post(
                reverse("telegram-webhook"),
                {
                    "message": {
                        "chat": {"id": 777},
                        "contact": {"phone_number": "996700123456"},
                    }
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        link = TelegramLink.objects.get(phone_number="+996700123456")
        self.assertEqual(link.chat_id, 777)
        mock_send.assert_called_once()

    def test_start_command_prompts_contact_share(self):
        with patch("apps.users.utils.telegram.send_telegram_message") as mock_send:
            response = self.client.post(
                reverse("telegram-webhook"),
                {"message": {"chat": {"id": 777}, "text": "/start"}},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send.assert_called_once()
        self.assertIn("reply_markup", mock_send.call_args.kwargs)

    @override_settings(TELEGRAM_WEBHOOK_SECRET="expected-secret")
    def test_rejects_request_with_wrong_secret(self):
        response = self.client.post(
            reverse("telegram-webhook"),
            {"message": {"chat": {"id": 777}, "text": "/start"}},
            format="json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="wrong-secret",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TelegramPollingCommandTests(APITestCase):
    """Сервер хостится в РФ, поэтому вебхук ненадёжен и апдейты забираются long polling'ом."""

    @override_settings(TELEGRAM_BOT_TOKEN="test-token")
    def test_processes_updates_and_advances_offset(self):
        calls = []

        def fake_get_updates(offset=None, timeout=30):
            calls.append(offset)
            if len(calls) == 1:
                return [{"update_id": 100, "message": {"chat": {"id": 777}, "text": "/start"}}]
            raise KeyboardInterrupt  # stop the infinite polling loop for the test

        with patch(
            "apps.users.management.commands.poll_telegram_updates.get_updates",
            side_effect=fake_get_updates,
        ), patch(
            "apps.users.management.commands.poll_telegram_updates.requests.post"
        ), patch(
            "apps.users.utils.telegram.send_telegram_message"
        ) as mock_send:
            with self.assertRaises(KeyboardInterrupt):
                call_command("poll_telegram_updates")

        mock_send.assert_called_once()
        self.assertEqual(calls, [None, 101])  # offset advances past the processed update_id

    def test_exits_without_token(self):
        out = StringIO()
        with override_settings(TELEGRAM_BOT_TOKEN=""):
            call_command("poll_telegram_updates", stderr=out)

        self.assertIn("TELEGRAM_BOT_TOKEN", out.getvalue())
