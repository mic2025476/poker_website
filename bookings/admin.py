from django.contrib import admin
from .models import BookingModel, UnavailableTimeSlotModel

@admin.register(BookingModel)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "start_time", "total_people", "hours_booked", "total_amount", "deposit_amount", "is_cancelled", "is_active", "created_at")
    list_filter = ("is_cancelled", "is_active", "created_at")
    search_fields = ("customer__first_name", "customer__last_name", "start_time")
    ordering = ("-created_at",)
    filter_horizontal = ("drinks",)

@admin.register(UnavailableTimeSlotModel)
class UnavailableTimeSlotAdmin(admin.ModelAdmin):
    list_display = ("id", "start_time", "end_time")
    search_fields = ("start_time", "end_time")
