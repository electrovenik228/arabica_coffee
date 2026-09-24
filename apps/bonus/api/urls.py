from django.urls import path

from apps.bonus.api.views.information import InformationAboutBonusList
from apps.bonus.api.views.loyalty import AddCoffeeCupView, AddLoyaltyPointsView, RedeemFreeCupView
from apps.bonus.api.views.qr_scan import ScanQRCodeView

urlpatterns = [
    path("qr-scan",           ScanQRCodeView.as_view(),          name="scan-qr"),
    path("add-points/",       AddLoyaltyPointsView.as_view(),    name="add-points"),
    path("add-coffee-cup/",   AddCoffeeCupView.as_view(),        name="add-coffee-cup"),
    path("redeem-free-cup/",  RedeemFreeCupView.as_view(),       name="redeem-free-cup"),
    path("",                  InformationAboutBonusList.as_view(), name="bonus-info"),
]
