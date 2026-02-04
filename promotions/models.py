from django.db import models
from django.utils import timezone

class PromoCode(models.Model):
    DISCOUNT_PERCENT = "percent"
    DISCOUNT_AMOUNT = "amount"
    DISCOUNT_TYPES = [
        (DISCOUNT_PERCENT, "Percent"),
        (DISCOUNT_AMOUNT, "Fixed amount"),
    ]

    code = models.CharField(max_length=40, unique=True)  # store uppercase
    active = models.BooleanField(default=True)

    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)  # 10 => 10% OR 10€ depending type

    # rules
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    max_redemptions_total = models.PositiveIntegerField(null=True, blank=True)
    max_redemptions_per_customer = models.PositiveIntegerField(null=True, blank=True)

    min_gross_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_discount_gross = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} ({self.discount_type} {self.discount_value})"

    def is_valid_now(self):
        now = timezone.now()
        if not self.active:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True


class PromoRedemption(models.Model):
    promo = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name="redemptions")
    # If you have a Customer model, point to it. Otherwise use user/email.
    customer = models.ForeignKey("customers.CustomerModel", on_delete=models.SET_NULL, null=True, blank=True)
    booking = models.OneToOneField("bookings.BookingModel", on_delete=models.CASCADE)
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["promo"]),
            models.Index(fields=["customer"]),
        ]
