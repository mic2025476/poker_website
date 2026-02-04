from decimal import Decimal
from .models import PromoCode, PromoRedemption
from typing import Optional, Tuple
from decimal import Decimal
from .models import PromoCode
def normalize_code(code: str) -> str:
    return (code or "").strip().upper()

def calculate_discount_gross(promo: PromoCode, gross_total: Decimal) -> Decimal:
    if promo.discount_type == PromoCode.DISCOUNT_PERCENT:
        disc = (gross_total * promo.discount_value) / Decimal("100")
    else:
        disc = promo.discount_value

    if promo.max_discount_gross is not None:
        disc = min(disc, promo.max_discount_gross)

    disc = max(Decimal("0"), min(disc, gross_total))
    return disc

def validate_promo(code: str, gross_total: Decimal, customer=None) -> Tuple[Optional[PromoCode], Optional[str]]:
    code = normalize_code(code)
    if not code:
        return None, "empty"

    promo = PromoCode.objects.filter(code=code).first()
    if not promo:
        return None, "not_found"
    if not promo.is_valid_now():
        return None, "inactive_or_expired"

    if promo.min_gross_total is not None and gross_total < promo.min_gross_total:
        return None, {
            "code": "min_total_not_met",
            "min_required": str(promo.min_gross_total),
            "current_total": str(gross_total),
        }


    # total usage limit
    if promo.max_redemptions_total is not None:
        used = PromoRedemption.objects.filter(promo=promo).count()
        if used >= promo.max_redemptions_total:
            return None, "max_total_reached"

    # per-customer limit
    if customer and promo.max_redemptions_per_customer is not None:
        used = PromoRedemption.objects.filter(promo=promo, customer=customer).count()
        if used >= promo.max_redemptions_per_customer:
            return None, "max_per_customer_reached"

    return promo, None
