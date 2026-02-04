# payments/views.py
import os
import json
from datetime import datetime
from django.shortcuts import render
import stripe
from promotions.services import validate_promo, calculate_discount_gross
from datetime import date
from decimal import Decimal
from django.views.decorators.http import require_POST
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
import requests
from bookings.models import BookingModel
from customers.models import CustomerModel
from utils.google_calendar import GoogleCalendarService
from response import Response as ResponseData  
from pricing.services import get_pricing
from decimal import Decimal

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

VAT_RATE = Decimal("0.19")
from decimal import Decimal, ROUND_HALF_UP

def euros_to_cents(value) -> int:
    """
    Accepts '0.7', 0.7, Decimal('0.70'), 1, '12.34' (euros)
    Returns integer cents.
    """
    eur = Decimal(str(value))
    cents = (eur * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)
# -------------------------
# Stripe configuration
# -------------------------
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# If you want to explicitly allow multiple payment methods, you can set this to None and use
# "automatic_payment_methods" in the session create call below.
STRIPE_CURRENCY_DEFAULT = "eur"

VAT = 0.19
GROSS_DAY = 350
# ⚠️ TEMPORARY – REMOVE AFTER LIVE TEST
LIVE_TEST_AMOUNT_CENTS = None  # €0.70


GAS_RECEIPT_WEBAPP_URL = os.getenv("GAS_RECEIPT_WEBAPP_URL", "")
GAS_SHARED_SECRET = os.getenv("GAS_SHARED_SECRET", "")
RECEIPT_LOGO_URL = os.getenv("RECEIPT_LOGO_URL", "")

def money2(x) -> str:
    return str(Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def build_receipt_payload(*, customer, booking_payload, pi, company_cfg: dict):
    """
    customer: CustomerModel
    booking_payload: dict (from metadata)
    pi: Stripe PaymentIntent (dict)
    company_cfg: dict of brand/legal info
    """
    dealer = bool(booking_payload.get("dealer", False))
    drinks = bool(booking_payload.get("drinks_flatrate", False))
    cfg = get_pricing()
    GROSS_DEALER = cfg.gross_dealer
    GROSS_DRINKS = cfg.gross_drinks_flatrate
    # Line items (GROSS)
    items = [{"name": "Poker Rental", "qty": 1, "gross_unit": float(GROSS_DAY)}]
    if dealer:
        items.append({"name": "Dealer", "qty": 1, "gross_unit": float(GROSS_DEALER)})
    if drinks:
        items.append({"name": "Drinks Flatrate", "qty": 1, "gross_unit": float(GROSS_DRINKS)})
    net_subtotal = sum(i["qty"] * i["net_unit"] for i in items)

    # Stripe paid amount (gross) from PI
    paid_cents = (pi.get("amount_received") or pi.get("amount") or 0)
    paid_gross = float(Decimal(paid_cents) / Decimal(100))

    # If you want: ensure your calculated gross matches Stripe (optional)
    # paid_gross is the truth.

    # Build receipt number format: MGEN-YYYY-000123 (example)
    # easiest: use booking id if you have it, or PI created timestamp hash.
    year = datetime.utcnow().strftime("%Y")
    # You can swap this with booking.id once created:
    unique = pi.get("id", "")[-6:].upper()
    receipt_number = f"MGEN-{year}-{unique}"

    # Convert items to display format (with VAT)
    display_items = []
    for it in items:
        net_total = it["qty"] * it["net_unit"]
        gross_unit = float(Decimal(it["net_unit"]) * (Decimal("1.0") + VAT_RATE))
        gross_total_line = float(Decimal(net_total) * (Decimal("1.0") + VAT_RATE))
        display_items.append({
            "name": it["name"],
            "qty": it["qty"],
            "net_unit": float(it["net_unit"]),
            "net_total": float(net_total),
            "gross_unit": float(gross_unit),
            "gross_total": float(gross_total_line),
        })

    return {
        # Recipient
        "to_email": customer.email_id,
        "customer_name": f"{customer.first_name} {customer.last_name}".strip(),
        "customer_email": customer.email_id,

        # Company/legal
        "company_name": company_cfg["name"],
        "company_address_lines": company_cfg["address_lines"],  # list
        "company_website": company_cfg.get("website", ""),
        "support_email": company_cfg.get("support_email", ""),
        "vat_id": company_cfg.get("vat_id", ""),
        "register_info": company_cfg.get("register_info", ""),

        # Document info
        "receipt_number": receipt_number,
        "date_paid": datetime.utcfromtimestamp(pi["created"]).strftime("%Y-%m-%d %H:%M UTC"),
        "payment_method": "Card",
        "currency": (pi.get("currency") or "eur").upper(),

        # VAT
        "vat_rate": 0.19,
        "net_subtotal": float(Decimal(net_subtotal)),
        "vat_amount": float(Decimal(net_subtotal) * VAT_RATE),
        "gross_total": float(Decimal(net_subtotal) * (Decimal("1.0") + VAT_RATE)),
        "amount_paid": float(paid_gross),  # use Stripe truth

        # Booking
        "booking_date": booking_payload.get("booking_date", ""),
        "booking_time": booking_payload.get("booking_time", ""),
        "people": booking_payload.get("number_of_people", ""),
        "hours": booking_payload.get("number_of_hours", ""),
        "dealer": bool(dealer),
        "drinks_flatrate": bool(drinks),

        # Items for PDF table
        "items": display_items,
    }


def send_receipt_via_gas(receipt: dict) -> None:
    """
    Calls Google Apps Script Web App to generate branded PDF and email it.
    Never raise errors to avoid breaking Stripe webhook.
    """
    if not GAS_RECEIPT_WEBAPP_URL:
        print("⚠️ GAS_RECEIPT_WEBAPP_URL not set")
        return

    payload = {
        "secret": GAS_SHARED_SECRET,
        "receipt": receipt,
    }

    try:
        r = requests.post(GAS_RECEIPT_WEBAPP_URL, json=payload, timeout=20)
        print("✅ GAS response:", r.status_code, r.text[:200])
    except Exception as e:
        print("⚠️ GAS call failed:", e)


def calc_gross_total_from_db(*, dealer: bool, drinks_flatrate: bool, service: bool) -> Decimal:
    cfg = get_pricing()

    gross_total = cfg.gross_day_rental
    if dealer:
        gross_total += cfg.gross_dealer
    if drinks_flatrate:
        gross_total += cfg.gross_drinks_flatrate
    if service:
        gross_total += cfg.gross_service

    return round(gross_total, 2)


def _finalize_booking_and_calendar(booking_id: int, data: dict, payment_reference: str = ""):
    """
    Finalizes an EXISTING pending booking (created at checkout session creation):
    - Updates booking fields (safe server-side values)
    - Sets is_active=True
    - assigns drinks (M2M)
    - creates Google Calendar event
    Returns booking object.
    """
    if not booking_id:
        raise ValueError("Missing booking_id")

    # load the existing booking (must exist from create_checkout_session)
    booking = BookingModel.objects.select_related("customer").filter(id=booking_id).first()
    if not booking:
        raise ValueError(f"Booking {booking_id} not found")

    # idempotency: if webhook repeats, don't create multiple calendar events
    # (We can't fully prevent duplicates unless you store calendar_event_id on booking;
    #  but at least don't re-run if already active AND you decide that's enough.)
    if booking.is_active:
        return booking

    required_fields = ["booking_date", "number_of_people", "number_of_hours", "user_id"]
    for f in required_fields:
        if f not in data:
            raise ValueError(f"Missing {f}")

    # always compute server-side
    people = int(data["number_of_people"])
    dealer = bool(data.get("dealer"))
    drinks_flat = bool(data.get("drinks_flatrate"))
    service = bool(data.get("service"))
    gross_total = calc_gross_total_from_db(dealer=dealer, drinks_flatrate=drinks_flat, service=service)

    booking_date = datetime.strptime(data["booking_date"], "%Y-%m-%d").date()
    start_time = datetime.strptime("18:00", "%H:%M").time()
    hours = 18  # fixed slot

    # Optional: ensure the booking belongs to the expected customer
    customer = CustomerModel.objects.get(id=data["user_id"], is_active=True)
    if booking.customer_id != customer.id:
        # safety check: don't finalize someone else's booking
        raise ValueError("Booking customer mismatch")
    cfg = get_pricing()
    DEPOSIT_EUR = cfg.deposit_amount
    # Update the existing booking
    booking.booking_date = booking_date
    booking.start_time = start_time
    booking.total_people = people
    booking.hours_booked = hours
    booking.total_amount = gross_total
    booking.deposit_amount = float(DEPOSIT_EUR)
    booking.is_active = True
    booking.has_dealer = bool(data.get("dealer"))
    booking.has_service_personal = bool(data.get("service"))
    booking.has_drinks_flatrate = bool(data.get("drinks_flatrate"))

    # OPTIONAL: if your model has a payment reference field
    # booking.payment_reference = payment_reference

    booking.save()

    # Assign drinks (M2M) if present (expects list of IDs)
    if data.get("drinks"):
        booking.drinks.set(data["drinks"])
        booking.save()

    # Add event to Google Calendar
    try:
        calendar_service = GoogleCalendarService()

        drink_names = []
        if data.get("drinks"):
            from menu.models import DrinkModel
            drink_objects = DrinkModel.objects.filter(id__in=data["drinks"])
            drink_names = [d.name for d in drink_objects]

        booking_data = {
            "customer_name": f"{customer.first_name} {customer.last_name}",
            "booking_date": booking_date,
            "start_time": start_time,
            "duration_hours": hours,
            "total_people": people,
            "drinks": drink_names,
            "booking_id": booking.id,
        }

        calendar_event = calendar_service.add_booking_event(booking_data)
        if calendar_event:
            print(f"✅ Created calendar event for booking {booking.id}")
        else:
            print(f"⚠️ Calendar event creation failed for booking {booking.id}")

    except Exception as e:
        print(f"⚠️ Error adding booking to calendar: {e}")

    return booking


def round_up_to_nearest_10(eur: Decimal) -> Decimal:
    # round UP to nearest 10
    # 357 -> 360, 360 -> 360
    eur = eur.quantize(Decimal("0.01"))
    remainder = eur % Decimal("10")
    if remainder == 0:
        return eur
    return eur + (Decimal("10") - remainder)

def days_from_today(d: date) -> int:
    return (d - date.today()).days

@require_POST
def pay_with_cash(request):
    cfg = get_pricing()
    DEPOSIT_EUR = cfg.deposit_amount
    payload = json.loads(request.body.decode("utf-8"))

    required = ["booking_date", "number_of_people", "user_id"]
    for f in required:
        if f not in payload:
            return JsonResponse({"error": f"Missing {f}"}, status=400)

    booking_date = datetime.strptime(payload["booking_date"], "%Y-%m-%d").date()

    # ✅ Cash allowed only if booking is MORE than 2 days away
    if days_from_today(booking_date) <= 2:
        return JsonResponse({"error": "Cash payment is not available for bookings within 2 days."}, status=400)

    user_id = int(payload["user_id"])
    people = int(payload["number_of_people"])
    dealer = bool(payload.get("dealer"))
    service = bool(payload.get("service"))
    drinks = bool(payload.get("drinks_flatrate"))

    customer = CustomerModel.objects.get(id=user_id, is_active=True)

    # booking price (gross)
    gross_total = Decimal(str(calc_gross_total_from_db(dealer=dealer, drinks_flatrate=drinks, service=service)))
    promo_code = payload.get("promo_code", "").strip()
    discount_gross = Decimal("0.00")
    applied_promo = None

    if promo_code:
        promo, err = validate_promo(promo_code, gross_total, customer=customer)
        if err:
            return JsonResponse({"error": f"Promo code invalid: {err}"}, status=400)

        discount_gross = calculate_discount_gross(promo, gross_total)
        applied_promo = promo

    gross_total = gross_total - discount_gross

    deposit = DEPOSIT_EUR

    # cash due = booking + deposit
    cash_due = gross_total + deposit

    # ✅ round UP to nearest 10
    rounded_cash_due = round_up_to_nearest_10(cash_due)
    fee = (rounded_cash_due - cash_due).quantize(Decimal("0.01"))

    start_time = datetime.strptime("18:00", "%H:%M").time()

    booking = BookingModel.objects.create(
        customer=customer,
        booking_date=booking_date,
        start_time=start_time,
        total_people=people,
        hours_booked=18,
        total_amount=gross_total,
        deposit_amount=deposit,
        is_active=True,
        promo_code=applied_promo,
        discount_gross=discount_gross,


        # ✅ NEW: store add-ons
        has_dealer=dealer,
        has_service_personal=service,
        has_drinks_flatrate=drinks,

        is_cash=True,
        cash_paid=False,
        cash_rounding_fee=fee,
    )


    # drinks M2M
    if payload.get("drinks"):
        booking.drinks.set(payload["drinks"])

    # calendar (optional - use your existing helper)
    try:
        calendar_service = GoogleCalendarService()

        drink_names = []
        if payload.get("drinks"):
            from menu.models import DrinkModel
            drink_objects = DrinkModel.objects.filter(id__in=payload["drinks"])
            drink_names = [d.name for d in drink_objects]

        booking_data = {
            "customer_name": f"{customer.first_name} {customer.last_name}",
            "booking_date": booking_date,
            "start_time": start_time,     # 18:00
            "duration_hours": 18,
            "total_people": people,
            "drinks": drink_names,
            "booking_id": booking.id,
        }

        calendar_event = calendar_service.add_booking_event(booking_data)
        if calendar_event:
            print(f"✅ Created calendar event for CASH booking {booking.id}")
        else:
            print(f"⚠️ Calendar event creation failed for CASH booking {booking.id}")

    except Exception as e:
        print(f"⚠️ Error adding CASH booking to calendar: {e}")


    return JsonResponse({
        "ok": True,
        "booking_id": booking.id,
        "gross_total": str(gross_total),
        "deposit": str(deposit),
        "cash_due": str(cash_due),
        "rounded_cash_due": str(rounded_cash_due),
        "cash_rounding_fee": str(fee),
        "redirect_url": "/payments/cash/success/",
    })

@require_POST
def create_checkout_session(request):
    cfg = get_pricing()
    DEPOSIT_EUR = cfg.deposit_amount
    DEPOSIT_CENTS = euros_to_cents(DEPOSIT_EUR)
    """
    Called from your booking page JS.
    Receives booking form data and returns Stripe Checkout URL.
    We store booking data in session.metadata so webhook can finalize booking.
    """
    if not stripe.api_key:
        return JsonResponse({"error": "STRIPE_SECRET_KEY not set"}, status=500)

    try:
        print(f'request.body11 {request.body}')
        # IMPORTANT: your frontend must send JSON
        # If you currently send FormData, change frontend OR parse request.POST instead.
        payload = json.loads(request.body.decode("utf-8"))
        promo_code = (payload.get("promo_code") or "").strip()
        # ✅ FIXED SLOT - never trust client time/hours
        payload["booking_time"] = "18:00"
        payload["number_of_hours"] = 18

        # Validate required booking fields
        required = ["booking_date", "number_of_people", "number_of_hours"]
        for f in required:
            if f not in payload:
                return JsonResponse({"error": f"Missing {f}"}, status=400)

        hours = int(payload["number_of_hours"])
        user_id = int(payload["user_id"])
        people = int(payload["number_of_people"])
        dealer = bool(payload.get("dealer"))
        service = bool(payload.get("service"))
        drinks = bool(payload.get("drinks_flatrate"))
        include_booking_amount = bool(payload.get("include_booking_amount", True))
        customer = CustomerModel.objects.get(id=user_id, is_active=True)

        # 1. Base gross (server truth)
        gross_total = calc_gross_total_from_db(
            dealer=dealer,
            drinks_flatrate=drinks,
            service=service
        )

        # 2. Promo validation (server-side)
        discount_gross = Decimal("0.00")
        applied_promo = None

        if promo_code:
            promo, err = validate_promo(
                promo_code,
                gross_total,
                customer=customer,
            )
            if err:
                return JsonResponse({"error": f"Promo code invalid: {err}"}, status=400)

            discount_gross = calculate_discount_gross(promo, gross_total)
            applied_promo = promo

        # 3. Final booking total AFTER discount
        discounted_booking_total = gross_total - discount_gross

        gross_total_cents = euros_to_cents(discounted_booking_total)
        amount_cents = gross_total_cents + DEPOSIT_CENTS

        amount_cents = gross_total_cents + DEPOSIT_CENTS  # ALWAYS full + deposit
        booking_date = datetime.strptime(payload["booking_date"], "%Y-%m-%d").date()
        start_time = datetime.strptime("18:00", "%H:%M").time()
        hours = 18
        people = int(payload["number_of_people"])

        pending_booking = BookingModel.objects.create(
            customer=customer,
            booking_date=booking_date,
            start_time=start_time,
            total_people=people,
            hours_booked=hours,
            total_amount=discounted_booking_total,
            deposit_amount=float(DEPOSIT_EUR),

            promo_code=applied_promo,
            discount_gross=discount_gross,

            is_active=False,
        )

        success_url = request.build_absolute_uri("/payments/stripe/success/") + "?session_id={CHECKOUT_SESSION_ID}"
        cancel_url  = request.build_absolute_uri("/payments/stripe/cancel/")  + "?session_id={CHECKOUT_SESSION_ID}"
        # Get customer email (prefer backend DB if you can)
        customer_email = customer.email_id  # <-- you must send this from frontend OR fetch from CustomerModel
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],

            # IMPORTANT: needed so Stripe can attach invoice to a customer + email it
            customer_email=customer_email,

            # ✅ Turn on Stripe-generated invoices for this Checkout payment
            payment_intent_data={
                "receipt_email": customer.email_id,
                "metadata": {
                    "booking_id": str(pending_booking.id),
                    "gross_total_cents": str(gross_total_cents),
                    "deposit_cents": str(DEPOSIT_CENTS),
                    "charge_type": "gross_plus_deposit",
                },
            },
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": "MGEN Booking (Total + Refundable Deposit)",
                        "description": f"Booking total €{discounted_booking_total:.2f} (VAT included) + deposit €{DEPOSIT_EUR:.2f}",
                    },
                    "unit_amount": amount_cents,  # ✅ gross + deposit
                },
                "quantity": 1,
            }],

            success_url=success_url,
            cancel_url=cancel_url,

            metadata={
                "booking_id": str(pending_booking.id),
                "booking_payload": json.dumps(payload),
                "gross_total_cents": str(gross_total_cents),
                "deposit_cents": str(DEPOSIT_CENTS),
                "charge_type": "gross_plus_deposit",
                "include_booking_amount": "true" if include_booking_amount else "false",
                "promo_code": promo_code or "",
                "discount_cents": str(euros_to_cents(discount_gross)),
            },
        )


        return JsonResponse({"url": session.url})

    except json.JSONDecodeError:
        # This is likely your "Unexpected token '<'" situation in reverse:
        # Your frontend expects JSON but sends/receives HTML or wrong content-type.
        return JsonResponse({"error": "Invalid JSON body. Send application/json."}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ----------------------------------------
# Stripe Webhook - finalize booking after payment
# ----------------------------------------
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    print(f'STRIPE_WEBHOOK_SECRET {STRIPE_WEBHOOK_SECRET}')
    if not STRIPE_WEBHOOK_SECRET:
        return HttpResponse("Webhook secret not set", status=500)

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        return HttpResponse("Invalid payload", status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse("Invalid signature", status=400)
    
    if event["type"] == "payment_intent.payment_failed":
        pi = event["data"]["object"]
        booking_id = (pi.get("metadata") or {}).get("booking_id")
        if booking_id:
            BookingModel.objects.filter(id=booking_id, is_active=False).delete()

    elif event["type"] == "checkout.session.expired":
        session = event["data"]["object"]
        md = session.get("metadata") or {}
        booking_id = md.get("booking_id")

        if booking_id:
            BookingModel.objects.filter(id=booking_id, is_active=False).delete()
    # Only finalize booking when checkout completed
    elif event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        md = session.get("metadata") or {}
        booking_id = md.get("booking_id")
        if not booking_id:
            return HttpResponse(status=200)

        data = json.loads(md.get("booking_payload") or "{}")
        customer_email = (session.get("customer_details") or {}).get("email") or session.get("customer_email")
        payment_intent_id = session.get("payment_intent")
        booking = BookingModel.objects.filter(id=booking_id).first()
        if booking:
            booking.deposit_payment_intent_id = payment_intent_id
            booking.save(update_fields=["deposit_payment_intent_id"])

        _finalize_booking_and_calendar(
            booking_id=int(booking_id),
            data=data,
            payment_reference=f"pi:{payment_intent_id}",
        )
        # Safety checks
        if not customer_email or not payment_intent_id:
            print("⚠️ Missing customer_email or payment_intent_id; cannot send branded receipt.")
            return HttpResponse(status=200)

        md = session.get("metadata") or {}
        booking_id = md.get("booking_id")

        # Safety
        if not booking_id:
            return HttpResponse(status=200)

        # idempotency: webhook can be delivered multiple times
        booking = BookingModel.objects.filter(id=booking_id).first()
        if not booking:
            return HttpResponse(status=200)

        include_booking_amount = (
            (session.get("metadata") or {}).get("include_booking_amount") == "true"
        )

        if include_booking_amount:
            # Full booking + deposit paid online
            booking.total_amount = booking.total_amount  # keep booking amount
            booking.deposit_amount = Decimal("500.00")
        else:
            # Only deposit paid online
            booking.total_amount = Decimal("0.00")
            booking.deposit_amount = Decimal("500.00")

        booking.is_active = True
        booking.save()
    return HttpResponse(status=200)


# ----------------------------------------
# OPTIONAL: keep your old endpoint name for frontend compatibility
# (If frontend calls /payments/process_payment/ directly)
# ----------------------------------------
@api_view(["POST"])
def process_payment(request):
    """
    Keep this endpoint ONLY if some part of your system still calls it.
    With Stripe Checkout, you typically don't call this directly anymore.
    """
    return Response(ResponseData.error("Use Stripe Checkout: /payments/create-checkout-session/"), status=400)


def stripe_success(request):
    # session_id is optional; you can show it or ignore it
    return render(request, "payments/stripe_success.html")

def pay_with_cash_success(request):
    # session_id is optional; you can show it or ignore it
    return render(request, "payments/pay_with_cash_success.html")


def stripe_cancel(request):
    session_id = request.GET.get("session_id")
    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            booking_id = (session.get("metadata") or {}).get("booking_id")
            if booking_id:
                BookingModel.objects.filter(id=booking_id, is_active=False).delete()
        except Exception as e:
            print("⚠️ cancel cleanup failed:", e)

    return render(request, "payments/stripe_cancel.html")
