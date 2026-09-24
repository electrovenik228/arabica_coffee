from rest_framework import serializers


class AddLoyaltyPointsResponseSerializer(serializers.Serializer):
    message              = serializers.CharField()
    already_awarded      = serializers.BooleanField()
    total_loyalty_points = serializers.IntegerField()


class AddCoffeeCupResponseSerializer(serializers.Serializer):
    message             = serializers.CharField()
    already_awarded     = serializers.BooleanField()
    current_coffee_cups = serializers.IntegerField()


class RedeemFreeCupSerializer(serializers.Serializer):
    qr_code_data = serializers.CharField()


class RedeemFreeCupResponseSerializer(serializers.Serializer):
    message              = serializers.CharField()
    free_cups_available  = serializers.IntegerField()

