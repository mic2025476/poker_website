from decimal import Decimal
from django.db import models
from menu.models import DrinkModel
from customers.models import CustomerModel
from django.utils import timezone

class BookingModel(models.Model):
    customer = models.ForeignKey(CustomerModel, on_delete=models.CASCADE, related_name="customer")
    booking_date = models.DateField()  # Add booking date field - no default
    start_time = models.TimeField()
    total_people = models.PositiveIntegerField()
    hours_booked = models.PositiveIntegerField()
    drinks = models.ManyToManyField(DrinkModel, related_name="bookings",blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2,null=True,blank=True)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_cancelled = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    is_delete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_cash = models.BooleanField(default=False)  # ✅ cash vs stripe
    cash_paid = models.BooleanField(default=False)  # ✅ only meaningful when is_cash=True
    cash_rounding_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    # bookings/models.py
    has_dealer = models.BooleanField(default=False)
    has_service_personal = models.BooleanField(default=False)
    has_drinks_flatrate = models.BooleanField(default=False)

    deposit_payment_intent_id = models.CharField(max_length=64, blank=True, null=True)
    deposit_refunded = models.BooleanField(default=False)
    promo_code = models.ForeignKey("promotions.PromoCode", null=True, blank=True, on_delete=models.SET_NULL)
    discount_gross = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_gross = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # final total after discount



    def __str__(self):
        return f"Booking {self.id} - {self.customer.first_name} {self.customer.last_name} at {self.start_time}"

class UnavailableTimeSlotModel(models.Model):
    date = models.DateField(default=timezone.now)
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"Unavailable on {self.date} from {self.start_time} to {self.end_time}"
    
class ReservationSettingsModel(models.Model):
    cash_cutoff_days = models.PositiveIntegerField(default=3)  # N days before date
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Reservation Settings"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
