from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string  # Для генерации уникального QR-кода
from uuid import uuid4  # Генератор уникальных ID для пользователя


class UserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError("Номер телефона обязателен")
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, phone_number, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(phone_number, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    GENDER_CHOICES = (
        ("male", "Мужской"),
        ("female", "Женский"),
        ("other", "Другой"),
    )

    phone_number = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    qr_code = models.CharField(max_length=40, unique=True, blank=True, null=True)

    loyalty_points = models.IntegerField(default=0)  # Бонусные баллы
    coffee_cups = models.IntegerField(default=0)  # Чашки кофе для программы лояльности

    is_phone_verified = models.BooleanField(default=False)
    phone_verified_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_courier = models.BooleanField(default=False)

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.phone_number

    def save(self, *args, **kwargs):
        # Генерация уникального QR-кода
        if not self.qr_code:
            self.qr_code = get_random_string(40)  # Генерирует строку из 40 символов
        super().save(*args, **kwargs)

    def mark_phone_as_verified(self):
        self.is_phone_verified = True
        if not self.phone_verified_at:
            self.phone_verified_at = timezone.now()
