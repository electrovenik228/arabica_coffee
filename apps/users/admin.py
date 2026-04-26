from django.contrib import admin

from apps.users.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "phone_number",
        "first_name",
        "last_name",
        "coffee_cups",
        "loyalty_points",
        "is_staff",
        "is_active",
    )
    search_fields = ("phone_number", "first_name", "last_name")
    list_filter = ("is_staff", "is_active", "is_courier")
    fields = (
        "phone_number",
        "first_name",
        "last_name",
        "gender",
        "birth_date",
        "avatar",
        "qr_code",
        "loyalty_points",
        "coffee_cups",
        "is_active",
        "is_staff",
        "is_courier",
        "is_superuser",
        "groups",
        "user_permissions",
    )
