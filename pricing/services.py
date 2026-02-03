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

from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal("0.01")

def money(x: Decimal) -> Decimal:
    return Decimal(x).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def breakdown_from_gross(gross: Decimal, vat_rate: Decimal) -> dict:
    """
    Convert gross price (VAT included) to net + vat + gross.
    """
    gross = Decimal(gross)
    vat_rate = Decimal(vat_rate)
    net = gross / (Decimal("1.0") + vat_rate)
    net = money(net)
    gross = money(gross)
    vat = money(gross - net)
    return {"net": net, "vat": vat, "gross": gross}

def pricing_context() -> dict:
    cfg = get_pricing()
    vat_percent = money(cfg.vat_rate * Decimal("100"))

    base = breakdown_from_gross(cfg.gross_day_rental, cfg.vat_rate)
    dealer = breakdown_from_gross(cfg.gross_dealer, cfg.vat_rate)
    service = breakdown_from_gross(cfg.gross_service, cfg.vat_rate)
    drinks = breakdown_from_gross(cfg.gross_drinks_flatrate, cfg.vat_rate)

    return {
        "cfg": cfg,
        "vat_percent": vat_percent,
        "base": base,
        "dealer": dealer,
        "service": service,
        "drinks": drinks,
        "deposit_amount": money(cfg.deposit_amount),
    }
