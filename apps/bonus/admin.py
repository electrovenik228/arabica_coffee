from django.contrib import admin

from apps.bonus.models import LoyaltyTransaction


@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "delta", "reason", "order", "created_by", "balance_after", "created_at")
    list_filter = ("reason",)
    search_fields = ("user__phone_number",)
    autocomplete_fields = ("user", "order", "created_by")
    readonly_fields = (
        "user", "delta", "reason", "order", "created_by", "balance_after", "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
