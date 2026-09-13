# API для получения/редактирования/удаления профиля
from rest_framework import generics, permissions
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from apps.users.api.serializers import UserProfileSerializer


class UserProfileView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def perform_destroy(self, instance):
        instance.soft_delete()

        outstanding_tokens = OutstandingToken.objects.filter(user=instance)
        BlacklistedToken.objects.bulk_create(
            (BlacklistedToken(token=token) for token in outstanding_tokens),
            ignore_conflicts=True,
        )