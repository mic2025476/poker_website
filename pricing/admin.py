from django.contrib import admin
from .models import PricingConfig

@admin.register(PricingConfig)
class PricingConfigAdmin(admin.ModelAdmin):
    list_display = ("gross_day_rental", "gross_dealer", "gross_service", "gross_drinks_flatrate", "vat_rate", "deposit_amount", "updated_at")
