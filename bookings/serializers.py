from rest_framework import serializers
from bookings.models import UnavailableTimeSlotModel
from menu.models import DrinkModel
from customers.models import CustomerModel

class BookingSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField(required=True)
    start_time = serializers.TimeField(required=True)
    total_people = serializers.IntegerField(min_value=1, required=True)
    hours_booked = serializers.IntegerField(min_value=1, required=True)
    drink_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False
    )
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    deposit_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)

    def validate_customer_id(self, value):
        if not CustomerModel.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Invalid or inactive customer.")
        return value

    def validate_drink_ids(self, value):
        if not DrinkModel.objects.filter(id__in=value, is_active=True).exists():
            raise serializers.ValidationError("One or more drinks are invalid.")
        return value

class UnavailableTimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnavailableTimeSlotModel
        fields = ["start_time", "end_time"]