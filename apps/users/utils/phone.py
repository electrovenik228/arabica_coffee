import re

from rest_framework import serializers


PHONE_NUMBER_RE = re.compile(r"^\+?[1-9]\d{9,14}$")


def normalize_phone_number(phone_number: str) -> str:
    value = re.sub(r"[\s\-\(\)]", "", phone_number or "")

    if value.startswith("00"):
        value = f"+{value[2:]}"
    elif value and not value.startswith("+"):
        value = f"+{value}"

    if not PHONE_NUMBER_RE.fullmatch(value):
        raise serializers.ValidationError(
            "Неверный формат номера телефона. Используйте международный формат, например +996700123456."
        )

    return value
