from django.db import models
from django.conf import settings

from customers.models import CustomerModel

class CustomerPaymentModel(models.Model):
    customer = models.ForeignKey(CustomerModel, on_delete=models.CASCADE, related_name='customer_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_at = models.DateTimeField(auto_now_add=True)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=50, choices=[
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ], default='pending')
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.customer} - {self.amount} ({self.status})"