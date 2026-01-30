from decimal import Decimal
from .models import PricingConfig

def get_pricing() -> PricingConfig:
    cfg = PricingConfig.objects.order_by("-updated_at").first()
    if cfg:
        return cfg

    return PricingConfig(
        gross_day_rental=Decimal("350.00"),
        gross_dealer=Decimal("250.00"),
        gross_service=Decimal("250.00"),
        gross_drinks_flatrate=Decimal("150.00"),
        vat_rate=Decimal("0.19"),
        deposit_amount=Decimal("500.00"),
    )
