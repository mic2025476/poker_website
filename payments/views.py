# payments/views.py
import os
import json
from datetime import datetime
from django.shortcuts import render
import stripe
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
from response import Response as ResponseData  # your custom ResponseData wrapper

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

VAT_RATE = Decimal("0.19")
# -------------------------
# Stripe configuration
# -------------------------
stripe.api_key = os.getenv("STRIPE_SECRET_KEY_sandbox", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET_sandbox", "")

# If you want to explicitly allow multiple payment methods, you can set this to None and use
# "automatic_payment_methods" in the session create call below.
STRIPE_CURRENCY_DEFAULT = "eur"

VAT = 0.19
NET_DAY = 300
NET_DEALER = 200
NET_DRINKS = 200
NET_SERVICE = 200
# ⚠️ TEMPORARY – REMOVE AFTER LIVE TEST
LIVE_TEST_AMOUNT_CENTS = 0.7  # €0.70


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

    # Line items (NET)
    items = [{"name": "Entire Day", "qty": 1, "net_unit": 300.00}]
    if dealer:
        items.append({"name": "Dealer", "qty": 1, "net_unit": 200.00})
    if drinks:
        items.append({"name": "Drinks Flatrate", "qty": 1, "net_unit": 200.00})

    net_subtotal = sum(i["qty"] * i["net_unit"] for i in items)
    vat_amount = float(Decimal(net_subtotal) * VAT_RATE)
    gross_total = float(Decimal(net_subtotal) * (Decimal("1.0") + VAT_RATE))

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


def calc_boss_gross_total(dealer: bool, drinks_flatrate: bool, service: bool) -> float:
    net_total = NET_DAY
    if dealer:
        net_total += NET_DEALER
    if drinks_flatrate:
        net_total += NET_DRINKS
    if service:
        net_total += NET_SERVICE
    gross_total = round(net_total * (1 + VAT), 2)
    return gross_total

def _deposit_to_cents(deposit_eur: float) -> int:
    return int(round(deposit_eur * 100))


def _create_booking_and_calendar(data: dict, payment_reference: str = ""):
    """
    This recreates your old DB logic in a cleaner way:
    - Creates a booking
    - assigns drinks (M2M)
    - creates Google Calendar event
    Returns booking object.
    """
    required_fields = ["booking_date", "number_of_people", "number_of_hours", "user_id"]
    for f in required_fields:
        if f not in data:
            raise ValueError(f"Missing {f}")

    hours = int(data["number_of_hours"])
    people = int(data["number_of_people"])
    dealer = bool(data.get("dealer"))
    drinks = bool(data.get("drinks_flatrate"))
    service = bool(data.get("service"))
    gross_total = calc_boss_gross_total(dealer, drinks, service)

    total = gross_total
    deposit = gross_total  # if you charge full
    customer = CustomerModel.objects.get(id=data["user_id"], is_active=True)

    booking_date_str = data.get("booking_date", "")

    # ✅ ALWAYS fixed slot: 18:00 → next day 12:00 (18 hours)
    booking_date = datetime.strptime(booking_date_str, "%Y-%m-%d").date()
    start_time = datetime.strptime("18:00", "%H:%M").time()

    # ✅ also force hours (don’t trust client)
    hours = 18



    # Create booking AFTER payment
    booking = BookingModel.objects.create(
        customer=customer,
        booking_date=booking_date,
        start_time=start_time,
        total_people=people,
        hours_booked=hours,
        total_amount=total,
        deposit_amount=deposit,
        is_active=True,  # paid booking
        # OPTIONAL: if your model has a field for payment reference
        # payment_reference=payment_reference,
    )

    # Assign drinks (M2M)
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

from decimal import Decimal, ROUND_HALF_UP

def euros_to_cents(value) -> int:
    """
    Accepts '0.7', 0.7, Decimal('0.70'), 1, '12.34' (euros)
    Returns integer cents.
    """
    eur = Decimal(str(value))
    cents = (eur * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)
# ----------------------------------------
# STEP: Create Stripe Checkout Session
# ----------------------------------------
@require_POST
def create_checkout_session(request):
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
        customer = CustomerModel.objects.get(id=user_id, is_active=True)

        gross_total = calc_boss_gross_total(dealer, drinks, service)
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
            total_amount=gross_total,
            deposit_amount=gross_total,
            is_active=False,                 # ✅ pending until paid
            # payment_reference="",          # optional if you have it
        )
        # ----------------------------
        # TEMP LIVE TEST OVERRIDE
        # ----------------------------
        if LIVE_TEST_AMOUNT_CENTS is not None:
            amount_cents = euros_to_cents(LIVE_TEST_AMOUNT_CENTS)
        else:
            amount_cents = euros_to_cents(gross_total)

        # IMPORTANT: redirect back to your booking tab, not /book/
        success_url = request.build_absolute_uri("/payments/stripe/success/") + "?session_id={CHECKOUT_SESSION_ID}"
        cancel_url  = request.build_absolute_uri("/payments/stripe/cancel/")  + "?session_id={CHECKOUT_SESSION_ID}"
        # Get customer email (prefer backend DB if you can)
        customer_email = customer.email_id  # <-- you must send this from frontend OR fetch from CustomerModel
        print(f"customer_email1111: {customer_email}")
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],

            # IMPORTANT: needed so Stripe can attach invoice to a customer + email it
            customer_email=customer_email,

            # ✅ Turn on Stripe-generated invoices for this Checkout payment
                payment_intent_data={
                    "receipt_email": customer_email,
                    "metadata": {"booking_id": str(pending_booking.id)},  # ✅ so PI events can find it
                },
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {"name": "MGEN Booking"},
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }],

            success_url=success_url,
            cancel_url=cancel_url,

            metadata={
                "booking_id": str(pending_booking.id),
                "booking_payload": json.dumps(payload),  # optional; keep if you want it for receipts
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
        customer_email = (session.get("customer_details") or {}).get("email") or session.get("customer_email")
        payment_intent_id = session.get("payment_intent")

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

        # If already active, do nothing
        if not booking.is_active:
            booking.is_active = True
            booking.save(update_fields=["is_active"])

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
