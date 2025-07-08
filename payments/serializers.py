# payments/serializers.py
from rest_framework import serializers
from .models import CustomerPaymentModel

class CustomerPaymentSerializer(serializers.ModelSerializer):
    customer = serializers.PrimaryKeyRelatedField(
        queryset=CustomerPaymentModel.objects.filter(is_active=True),
        help_text="ID of the customer making the payment",
    )

    class Meta:
        model = CustomerPaymentModel
        fields = (
            'customer',
            'payment_method',
            'amount',
            'transaction_id',
            'status',
            'paid_at', 
        )
        read_only_fields = ('transaction_id', 'status','paid_at','amount','payment_method','customer')
