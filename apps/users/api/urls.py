from django.urls import path

from .views import *

urlpatterns = [
    path('send-code/', SendCodeView.as_view(), name='send_code'),
    path('verify-code/', VerifyCodeView.as_view(), name='verify_code'),
    path('me/', UserProfileView.as_view(), name='my-profile'),
    path('telegram/webhook/', TelegramWebhookView.as_view(), name='telegram-webhook'),

    # Token management
    path("token/", CustomTokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token-refresh"),
    path("token/status/", CheckTokenStatusView.as_view(), name="token-status"),

]
