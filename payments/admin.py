from django.contrib import admin
from .models import CustomerPaymentModel

@admin.register(CustomerPaymentModel)
class CustomerPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'amount', 'status', 'payment_method', 'transaction_id', 'paid_at', 'is_active')
    list_filter = ('status', 'payment_method', 'is_active', 'created_at')
    search_fields = ('customer__first_name', 'customer__last_name', 'transaction_id')
    ordering = ('-paid_at',)
    readonly_fields = ('paid_at', 'created_at', 'transaction_id')

    def customer(self, obj):
        return f"{obj.customer.first_name} {obj.customer.last_name}"

    customer.admin_order_field = 'customer__first_name'  # Enable sorting by customer name
