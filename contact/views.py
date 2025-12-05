# contact/views.py
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render


def contact(request):
    return render(request, "contact/contact.html")


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
