from rest_framework import serializers

class ScanQRCodeResponseSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    name = serializers.CharField()
    loyalty_points = serializers.IntegerField()
    coffee_cups = serializers.IntegerField()
    free_cups_available = serializers.IntegerField()
