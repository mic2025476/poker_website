from django.db import models
from menu.models import DrinkModel
from customers.models import CustomerModel
from django.utils import timezone

class BookingModel(models.Model):
    customer = models.ForeignKey(CustomerModel, on_delete=models.CASCADE, related_name="customer")
    start_time = models.TimeField()
    total_people = models.PositiveIntegerField()
    hours_booked = models.PositiveIntegerField()
    drinks = models.ManyToManyField(DrinkModel, related_name="bookings")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2,null=True,blank=True)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_cancelled = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Booking {self.id} - {self.customer.first_name} {self.customer.last_name} at {self.start_time}"

class UnavailableTimeSlotModel(models.Model):
    date = models.DateField(default=timezone.now)
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"Unavailable on {self.date} from {self.start_time} to {self.end_time}"