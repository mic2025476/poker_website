from django.contrib import admin
from .models import CustomerModel, OTPModel

@admin.register(CustomerModel)
class CustomerModelAdmin(admin.ModelAdmin):
    list_display = (
        'id', 
        'first_name', 
        'last_name', 
        'email_id', 
        'phone_number', 
        'is_email_verified', 
        'is_phone_verified', 
        'is_active', 
        'created_at'
    )
    search_fields = ('first_name', 'last_name', 'email_id', 'phone_number')
    list_filter = ('is_active', 'is_deleted', 'is_email_verified', 'is_phone_verified', 'created_at')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OTPModel)
class OTPModelAdmin(admin.ModelAdmin):
    list_display = (
        'id', 
        'otp_type', 
        'phone_number', 
        'email_id', 
        'otp', 
        'is_verified', 
        'created_at'
    )
    search_fields = ('phone_number', 'email_id', 'otp')
    list_filter = ('otp_type', 'is_verified', 'created_at')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)
