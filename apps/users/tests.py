from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


User = get_user_model()


class PhoneVerificationAuthTests(APITestCase):
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

    def test_send_code_returns_error_when_twilio_fails(self):
        with patch(
            "apps.users.api.views.login.send_verification_code",
            side_effect=Exception("twilio error"),
        ):
            response = self.client.post(
                reverse("send_code"),
                {"phone_number": "+996700123456"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(response.data["success"], False)

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
