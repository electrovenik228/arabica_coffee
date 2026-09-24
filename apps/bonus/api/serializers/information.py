from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.bonus.services.wallet import coffee_mission_progress
from apps.users.models import User


class CoffeeMissionSerializer(serializers.Serializer):
    """Готовые для отрисовки данные прогресса акции "Кофейная миссия" (6+1 бесплатная)."""

    cups_collected = serializers.IntegerField(help_text="Сколько чашек куплено в текущем цикле.")
    cups_required = serializers.IntegerField(help_text="Сколько чашек нужно купить до бесплатной.")
    cups_remaining = serializers.IntegerField(help_text="Сколько осталось купить до бесплатной чашки.")
    free_cups_available = serializers.IntegerField(
        help_text="Сколько бесплатных чашек уже заработано и ждут выдачи."
    )


class InformationSerializer(serializers.ModelSerializer):
    coffee_mission = serializers.SerializerMethodField()

    class Meta:
        model = User
        # coffee_cups оставлен для обратной совместимости — для новых экранов
        # используйте coffee_mission, там уже посчитан весь прогресс.
        fields = ('loyalty_points', 'coffee_cups', 'coffee_mission')

    @extend_schema_field(CoffeeMissionSerializer)
    def get_coffee_mission(self, user):
        return CoffeeMissionSerializer(coffee_mission_progress(user)).data
