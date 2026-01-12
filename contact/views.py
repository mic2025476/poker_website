# contact/views.py
from django.core.mail import send_mail
from django.conf import settings
from customers.models import CustomerModel
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render
import json, requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


def contact(request):
    prefill_email = ""
    prefill_name = ""

    user_id = request.session.get("user_id")
    print(f'user_id {user_id}')
    if user_id:
        customer = CustomerModel.objects.filter(id=user_id, is_deleted=False).first()
        if customer:
            prefill_email = customer.email_id or ""
            prefill_name = f"{customer.first_name} {customer.last_name}".strip()

    return render(request, "contact/contact.html", {
        "prefill_email": prefill_email,
        "prefill_name": prefill_name,   # optional
    })


GAS_URL = "https://script.google.com/macros/s/AKfycbyLHLubienniLruGYUdm353W9gt7CK3_RQM1ZrUmVU97fdRbOEw-BySGPuS9iwvAs7FMQ/exec"

@csrf_exempt
def contact_form(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST only"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)

    gas_payload = {
        "auth_key": "MY_SECRET_KEY_123",
        "event_type": "contact",
        "name": payload.get("name"),
        "email": payload.get("email"),
        "message": payload.get("message"),
    }

    try:
        r = requests.post(GAS_URL, json=gas_payload, timeout=15)
    except requests.RequestException as e:
        return JsonResponse({"success": False, "message": "GAS request failed", "error": str(e)}, status=502)

    # ✅ Return JSON if possible, otherwise return first 1000 chars of raw response
    content_type = r.headers.get("Content-Type", "")
    try:
        data = r.json()
        return JsonResponse(data, status=r.status_code)
    except ValueError:
        print(f'dfvsfvsdvdv {r.text[:1000]}')
        return JsonResponse(
            {
                "success": False,
                "message": "GAS did not return JSON",
                "status_code": r.status_code,
                "content_type": content_type,
                "raw": r.text[:1000],
            },
            status=500,
        )
    
@api_view(["POST"])
def contact_submit(request):
    data = request.data
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    message = data.get("message", "").strip()

    if not name or not email or not message:
        return Response(
            {"success": False, "message": "Please fill in all fields."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    subject = f"[MGEN Poker] New contact request from {name}"
    body = (
        f"Name: {name}\n"
        f"Email: {email}\n\n"
        f"Message:\n{message}"
    )

    to_email = getattr(settings, "CONTACT_RECEIVER_EMAIL", None) or settings.DEFAULT_FROM_EMAIL

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            fail_silently=False,
        )
    except Exception as e:
        print("Error sending contact email:", e)
        return Response(
            {"success": False, "message": "Could not send your message. Please try again later."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {"success": True, "message": "Thank you! Your message has been sent."},
        status=status.HTTP_200_OK,
    )
