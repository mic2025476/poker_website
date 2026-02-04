from django.contrib import admin
from django.db.models import Count
from django.utils import timezone

from .models import PromoCode, PromoRedemption


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "active",
        "discount_type",
        "discount_value",
        "starts_at",
        "ends_at",
        "min_gross_total",
        "max_discount_gross",
        "max_redemptions_total",
        "redemptions_count",
        "created_at",
        "status_badge",
    )
    list_filter = ("active", "discount_type", "starts_at", "ends_at", "created_at")
    search_fields = ("code",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)

    fieldsets = (
        (None, {"fields": ("code", "active")}),
        ("Discount", {"fields": ("discount_type", "discount_value", "max_discount_gross")}),
        ("Validity window", {"fields": ("starts_at", "ends_at")}),
        ("Usage limits", {"fields": ("max_redemptions_total", "max_redemptions_per_customer")}),
        ("Order rules", {"fields": ("min_gross_total",)}),
        ("Meta", {"fields": ("created_at",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_redemptions_count=Count("redemptions"))

    @admin.display(description="Redemptions", ordering="_redemptions_count")
    def redemptions_count(self, obj):
        return getattr(obj, "_redemptions_count", 0)

    @admin.display(description="Status")
    def status_badge(self, obj):
        """
        Quick human-readable status in list view:
        - Active
        - Scheduled
        - Expired
        - Inactive
        """
        now = timezone.now()
        if not obj.active:
            return "Inactive"
        if obj.starts_at and now < obj.starts_at:
            return "Scheduled"
        if obj.ends_at and now > obj.ends_at:
            return "Expired"
        return "Active"

    def save_model(self, request, obj, form, change):
        # Normalize code to uppercase to avoid duplicates like "save10" vs "SAVE10"
        if obj.code:
            obj.code = obj.code.strip().upper()
        super().save_model(request, obj, form, change)


@admin.register(PromoRedemption)
class PromoRedemptionAdmin(admin.ModelAdmin):
    list_display = ("promo", "booking", "customer", "redeemed_at")
    list_filter = ("redeemed_at", "promo")
    search_fields = ("promo__code", "booking__id", "customer__id")
    ordering = ("-redeemed_at",)
    autocomplete_fields = ("promo", "booking", "customer")
    readonly_fields = ("redeemed_at",)
