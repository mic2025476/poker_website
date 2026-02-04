from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt  # only if needed
from .services import validate_promo, calculate_discount_gross

@require_POST
def apply_promo(request):
    code = request.POST.get("code", "")
    gross_total = Decimal(request.POST.get("gross_total", "0") or "0")

    # if you have logged-in users/customers, resolve customer here
    customer = None

    promo, err = validate_promo(code, gross_total, customer=customer)
    if err:
        return JsonResponse({"ok": False, "error": err})

    discount = calculate_discount_gross(promo, gross_total)
    new_total = gross_total - discount

    return JsonResponse({
        "ok": True,
        "code": promo.code,
        "discount_gross": str(discount),
        "new_total_gross": str(new_total),
        "discount_type": promo.discount_type,
        "discount_value": str(promo.discount_value),
    })
