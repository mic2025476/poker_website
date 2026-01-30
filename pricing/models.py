from decimal import Decimal
from django.db import models

class PricingConfig(models.Model):
    # Base prices are NET (without VAT) if you follow the boss pricing style
    gross_day_rental = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("350.00"))
    gross_dealer = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("250.00"))
    gross_service = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("250.00"))
    gross_drinks_flatrate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("150.00"))

    vat_rate = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("0.19"))  # 0.19 = 19%
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("500.00"))

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pricing Configuration"
        verbose_name_plural = "Pricing Configuration"

    def __str__(self):
        return f"PricingConfig (VAT {self.vat_rate}, deposit {self.deposit_amount})"
