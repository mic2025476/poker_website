import random
import braintree
import json
from django.contrib.sessions.models import Session
from django.utils.timezone import now
from requests import Response
from django.db import transaction
from rest_framework.decorators import api_view
from rest_framework.response import Response as DRFResponse
from rest_framework import status
from django.db import connection
from django.contrib.auth import login
from django.contrib.auth import logout
from poker_lounge import settings
from .models import CustomerModel, OTPModel
from .serializers import (
    CustomerSignupSerializer,
    OTPCombinedVerifySerializer
)
from django.http import JsonResponse
from django.db.models import Q
from response import Response as ResponseData  # Your custom response class
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

gateway = braintree.BraintreeGateway(
    braintree.Configuration(
        environment=getattr(braintree.Environment, settings.BRAINTREE_ENVIRONMENT),
        merchant_id=settings.BRAINTREE_MERCHANT_ID,
        public_key=settings.BRAINTREE_PUBLIC_KEY,
        private_key=settings.BRAINTREE_PRIVATE_KEY,
    )
)
@api_view(["POST"])
def customer_signup(request):
    try:
        serializer = CustomerSignupSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            email_id = data['email_id']
            phone_number = data.get('phone_number', None)
            first_name = data['first_name']
            last_name = data['last_name']
            password = data['password']
            confirm_password = data['confirm_password']
            terms_accepted = data['terms_accepted']

            if password != confirm_password:
                return DRFResponse(
                    ResponseData.error("Passwords do not match."),
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Build the query to check for existing customers
            query = Q(email_id=email_id)
            if phone_number:
                query |= Q(phone_number=phone_number)

            existing_customer = CustomerModel.objects.filter(query).first()

            if existing_customer:
                if not existing_customer.is_deleted:
                    if existing_customer.is_active:
                        return DRFResponse(
                            ResponseData.error("Customer already exists and is active."),
                            status=status.HTTP_200_OK
                        )
                    else:
                        return DRFResponse(
                            ResponseData.success_without_data("Customer exists but not active. New OTPs have been sent for phone & email."),
                            status=status.HTTP_200_OK
                        )
                else:
                    return DRFResponse(
                        ResponseData.error("Customer is deleted."),
                        status=status.HTTP_200_OK
                    )
            else:
                new_customer = CustomerModel.objects.create(
                    first_name=first_name,
                    last_name=last_name,
                    email_id=email_id,
                    phone_number=phone_number,
                    password=password,
                    is_active=True,
                    is_deleted=False,
                    terms_accepted=terms_accepted,
                    terms_accepted_at=now(),
                    terms_version="v1",  # or settings.TERMS_VERSION
                )
                result = gateway.customer.create({
                    "first_name": new_customer.first_name,
                    "last_name": new_customer.last_name,
                    "email": new_customer.email_id,
                    # "payment_method_nonce": "SOME_NONCE"  # only if you want to immediately store a payment method
                })
                if result.is_success:
                    # 3. Store the Braintree customer ID locally
                    new_customer.braintree_customer_id = result.customer.id
                    new_customer.save()
                else:
                    # Decide how you want to handle the Braintree error:
                    # e.g., you can still let signup succeed, or rollback user creation if Braintree fails
                    # For example:
                    new_customer.delete()
                    return Response({"error": "Error creating Braintree customer: " + result.message}, status=status.HTTP_400_BAD_REQUEST)


                return DRFResponse(
                    ResponseData.success_without_data("Customer signed up successfully. OTPs have been sent for phone & email."),
                    status=status.HTTP_201_CREATED
                )
        else:
            error_message = " ".join([f"{key}: {', '.join(value)}" for key, value in serializer.errors.items()])
            return DRFResponse(ResponseData.error(error_message), status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return DRFResponse(ResponseData.error(str(e)), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

import requests
from rest_framework.decorators import api_view
from rest_framework import status

APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzjgFhr_1tSuMUTWMutUCpyOYWUcWpOGpY-GO-t_nz75S-13QQt0Wpd3xrFZMeae7OcJw/exec"

@api_view(["POST"])
def verify_otp(request):
    try:
        email_id = request.data.get("email_id")
        email_otp = request.data.get("email_otp")

        if not email_id or not email_otp:
            return DRFResponse(
                ResponseData.error("Email and OTP are required."),
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🔹 Call Apps Script for verification
        response = requests.post(APPS_SCRIPT_URL, json={
            "email": email_id,
            "otp": email_otp
        })
        print(f"Apps Script Response: {response.text}")
        print(f'responseresponse {response.json()}')
        if response.status_code != 200:
            return DRFResponse(
                ResponseData.error("Failed to reach OTP verification service."),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        try:
            result = response.json()
        except ValueError:
            return DRFResponse(
                ResponseData.error("Invalid response from OTP verification service."),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        if not result.get("success"):
            return DRFResponse(
                ResponseData.error(result.get("message", "Invalid OTP.")),
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🔹 OTP verified → activate customer in DB
        customer = CustomerModel.objects.filter(email_id=email_id).first()
        if not customer:
            return DRFResponse(
                ResponseData.error("Customer not found."),
                status=status.HTTP_404_NOT_FOUND
            )

        customer.is_email_verified = True
        customer.is_phone_verified = True   # assuming phone OTP skipped now
        customer.is_active = True
        customer.save()

        return DRFResponse(
            ResponseData.success(str(customer.id), "OTP verification successful."),
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return DRFResponse(
            ResponseData.error(str(e)),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
@api_view(["POST"])
def customer_login(request):
    try:
        email = request.data.get('email_id')
        password = request.data.get('password')
        customer = CustomerModel.objects.filter(
            email_id=email, password=password, is_deleted=False
        ).first()
        if not customer:
            return DRFResponse(ResponseData.error("Invalid credentials or user not found."),
                               status=status.HTTP_400_BAD_REQUEST)
        if not customer.is_active:
            return DRFResponse(ResponseData.error("Account is not active. Please verify both phone and email."),
                               status=status.HTTP_200_OK)

        # Only use custom session (remove django login() if CustomerModel isn't an auth User)
        request.session.cycle_key()
        request.session['user_id'] = customer.id
        request.session.set_expiry(1209600)
        request.session.save()

        key = request.session.session_key
        exists_now = Session.objects.filter(session_key=key).exists()
        decoded = Session.objects.get(session_key=key).get_decoded() if exists_now else {}

        print("LOGIN session_key:", key)
        print("LOGIN session_row_exists:", exists_now)
        print("LOGIN decoded_keys:", list(decoded.keys()))
        print("LOGIN DB:", settings.DATABASES['default'])
        print("LOGIN CONN:", connection.settings_dict)

        return DRFResponse(ResponseData.success(customer.id, "Login successful."),
                           status=status.HTTP_200_OK)
    except Exception as e:
        return DRFResponse(ResponseData.error(str(e)),
                           status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
def customer_logout(request):
    logout(request)
    return DRFResponse(ResponseData.success_without_data("Logout successful."), status=status.HTTP_200_OK)

@api_view(["POST"])
def send_mobile_otp(request):
    """Send OTP to mobile number for verification"""
    try:
        phone_number = request.data.get('phone_number')
        customer_id = request.data.get('customer_id')

        if not phone_number or not customer_id:
            return JsonResponse({'success': False, 'message': 'Phone number and customer ID required'}, status=400)

        # Check if customer exists and owns this phone number
        customer = CustomerModel.objects.filter(id=customer_id, phone_number=phone_number, is_deleted=False).first()
        if not customer:
            return JsonResponse({'success': False, 'message': 'Invalid customer or phone number'}, status=400)

        if customer.is_phone_verified:
            return JsonResponse({'success': False, 'message': 'Phone number already verified'}, status=400)

        # Delete any existing OTP for this phone number
        OTPModel.objects.filter(phone_number=phone_number, otp_type='phone').delete()

        # Create new OTP
        otp_instance = OTPModel.objects.create(
            phone_number=phone_number,
            otp_type='phone'
        )
        otp_instance.generate_otp()

        # Send OTP via AWS SNS
        from utils.sns_utils import send_otp_via_sns
        sns_response = send_otp_via_sns(phone_number, otp_instance.otp)

        if not sns_response.get('success'):
            # Log the error but still return success (for development)
            print(f"Failed to send SMS: {sns_response.get('error')}")
            return JsonResponse({
                'success': False,
                'message': f"Failed to send SMS: {sns_response.get('error', 'Unknown error')}"
            }, status=500)

        print(f"Mobile OTP for {phone_number}: {otp_instance.otp}")

        return JsonResponse({
            'success': True,
            'message': 'OTP sent successfully via SMS',
            'message_id': sns_response.get('message_id')
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(["POST"])
def verify_mobile_otp(request):
    """Verify mobile OTP and mark phone as verified"""
    try:
        phone_number = request.data.get('phone_number')
        otp = request.data.get('otp')
        customer_id = request.data.get('customer_id')
        
        if not phone_number or not otp or not customer_id:
            return JsonResponse({'success': False, 'message': 'Phone number, OTP, and customer ID required'}, status=400)
        
        # Check if customer exists
        customer = CustomerModel.objects.filter(id=customer_id, phone_number=phone_number, is_deleted=False).first()
        if not customer:
            return JsonResponse({'success': False, 'message': 'Invalid customer or phone number'}, status=400)
        
        if customer.is_phone_verified:
            return JsonResponse({'success': False, 'message': 'Phone number already verified'}, status=400)
        
        # Check OTP
        otp_instance = OTPModel.objects.filter(
            phone_number=phone_number, 
            otp=otp, 
            otp_type='phone',
            is_verified=False
        ).first()
        
        if not otp_instance:
            return JsonResponse({'success': False, 'message': 'Invalid or expired OTP'}, status=400)
        
        # Check if OTP is not too old (10 minutes)
        from datetime import timedelta
        from django.utils import timezone
        if timezone.now() - otp_instance.created_at > timedelta(minutes=10):
            return JsonResponse({'success': False, 'message': 'OTP expired'}, status=400)
        
        # Mark OTP as verified
        otp_instance.is_verified = True
        otp_instance.save()
        
        # Mark customer phone as verified
        customer.is_phone_verified = True
        customer.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Mobile number verified successfully'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(["GET"])
def get_customer_profile(request):
    """Get customer profile information"""
    try:
        customer_id = request.session.get('user_id')
        if not customer_id:
            return JsonResponse({'success': False, 'message': 'Not logged in'}, status=401)
        
        customer = CustomerModel.objects.filter(id=customer_id, is_deleted=False).first()
        if not customer:
            return JsonResponse({'success': False, 'message': 'Customer not found'}, status=404)
        
        return JsonResponse({
            'success': True,
            'customer': {
                'id': customer.id,
                'first_name': customer.first_name,
                'last_name': customer.last_name,
                'email_id': customer.email_id,
                'phone_number': customer.phone_number,
                'is_email_verified': customer.is_email_verified,
                'is_phone_verified': customer.is_phone_verified,
                'created_at': customer.created_at.strftime('%Y-%m-%d %H:%M')
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@api_view(["POST"])
def update_phone_number(request):
    """Update customer's phone number"""
    try:
        customer_id = request.session.get('user_id')
        if not customer_id:
            return JsonResponse({'success': False, 'message': 'User not logged in'}, status=401)
        
        data = json.loads(request.body)
        phone_number = data.get('phone_number', '').strip()
        
        if not phone_number:
            return JsonResponse({'success': False, 'message': 'Phone number is required'}, status=400)
        
        # Basic phone validation
        import re
        phone_regex = re.compile(r'^\+?[\d\s\-\(\)]{8,}$')
        if not phone_regex.match(phone_number):
            return JsonResponse({'success': False, 'message': 'Invalid phone number format'}, status=400)
        
        # Check if phone number already exists for another user
        existing_customer = CustomerModel.objects.filter(
            phone_number=phone_number, 
            is_deleted=False
        ).exclude(id=customer_id).first()
        
        if existing_customer:
            return JsonResponse({'success': False, 'message': 'This phone number is already registered to another account'}, status=400)
        
        # Update the customer's phone number
        customer = CustomerModel.objects.filter(id=customer_id, is_deleted=False).first()
        if not customer:
            return JsonResponse({'success': False, 'message': 'Customer not found'}, status=404)
        
        customer.phone_number = phone_number
        customer.is_phone_verified = False  # Reset verification status
        customer.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Phone number updated successfully',
            'phone_number': phone_number
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(["POST"])
def google_auth(request):
    """
    Google sign-in handler.
    - flow_type = 'signup': if email exists, return message asking user to log in instead.
    - flow_type = 'login' : if email exists, log in; otherwise create and log in.
    """
    google_token = request.data.get("google_token")
    flow_type = request.data.get("flow_type", "login")  # 'signup' or 'login'
    terms_accepted = request.data.get("terms_accepted", False)

    # ✅ Only enforce consent when it's a sign-up flow
    if flow_type == "signup" and not terms_accepted:
        return DRFResponse(
            ResponseData.error("You must accept the Terms & Conditions to sign up."),
            status=status.HTTP_400_BAD_REQUEST
        )
    if not google_token:
        return DRFResponse(
            ResponseData.error("Google token missing."),
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        google_request = google_requests.Request()

        idinfo = id_token.verify_oauth2_token(
            google_token,
            google_request,
            settings.GOOGLE_OAUTH2_CLIENT_ID,
        )

        email = idinfo.get("email")
        given_name = idinfo.get("given_name") or ""
        family_name = idinfo.get("family_name") or ""

        if not email:
            return DRFResponse(
                ResponseData.error("Could not get email from Google."),
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if account already exists
        existing_qs = CustomerModel.objects.filter(
            email_id=email,
            is_deleted=False
        )

        # ✳️ Case 1: Sign-up flow, but account already exists → show message, do not log in
        if flow_type == "signup" and existing_qs.exists():
            return DRFResponse(
                ResponseData.error(
                    "An account with this email already exists. "
                    "Please log in instead or use 'Continue with Google' on the Login tab."
                ),
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✳️ Case 2: Login flow, or sign-up with new email → create or reuse
        with transaction.atomic():
            if existing_qs.exists():
                customer = existing_qs.first()
                created = False
            else:
                customer = CustomerModel.objects.create(
                    email_id=email,
                    first_name=given_name,
                    last_name=family_name,
                    is_email_verified=True,
                    is_active=True,
                    # ✅ store consent for Google signups
                    terms_accepted=bool(terms_accepted),
                    terms_accepted_at=now(),
                    terms_version="v1",
                )
                created = True

            # Optionally update some fields if we just reused an existing user
            if not created:
                updated = False
                if not customer.first_name and given_name:
                    customer.first_name = given_name
                    updated = True
                if not customer.last_name and family_name:
                    customer.last_name = family_name
                    updated = True
                if not customer.is_email_verified:
                    customer.is_email_verified = True
                    updated = True
                if updated:
                    customer.save()

        # Log the user in (same as your normal login)
        request.session["user_id"] = str(customer.id)

        return DRFResponse(
            ResponseData.success(str(customer.id), "Login successful."),
            status=status.HTTP_200_OK
        )

    except ValueError as e:
        return DRFResponse(
            ResponseData.error(f"Invalid Google token: {e}"),
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        print("google_auth error:", e)
        return DRFResponse(
            ResponseData.error(str(e)),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
@api_view(["GET"])
def whoami(request):
    incoming = request.COOKIES.get("sessionid")
    exists = Session.objects.filter(session_key=incoming).exists() if incoming else False
    print("COOKIES", request.COOKIES)
    print("SESSION_KEY", request.session.session_key)
    print("HAS_ROW_FOR_COOKIE", exists)
    print("DB NAME", settings.DATABASES['default']['NAME'])
    print("DB HOST", settings.DATABASES['default']['HOST'])
    print("DB USER", settings.DATABASES['default']['USER'])
    return DRFResponse({
        "session_cookie": incoming,
        "session_row_exists": exists,
        "session_user_id": request.session.get("user_id"),
    })

@api_view(["POST"])
def forgot_password(request):
    """
    Step 1: User submits email, we generate an email OTP and send it.
    """
    try:
        email_id = request.data.get("email_id")

        if not email_id:
            return DRFResponse(
                ResponseData.error("Email is required."),
                status=status.HTTP_400_BAD_REQUEST
            )

        # Don't reveal whether user exists or not
        customer = CustomerModel.objects.filter(
            email_id=email_id,
            is_deleted=False
        ).first()

        if customer:
            # Remove old unverified email OTPs for this address
            OTPModel.objects.filter(
                email_id=email_id,
                otp_type="email",
                is_verified=False
            ).delete()

            # Create new OTP record
            otp_instance = OTPModel.objects.create(
                email_id=email_id,
                otp_type="email"
            )
            otp_instance.generate_otp()  # sets otp + created_at + save()

            # Send OTP by email
            subject = "Your Poker Lounge password reset code"
            message = (
                f"Hi {customer.first_name},\n\n"
                f"Use the following one-time password (OTP) to reset your password: {otp_instance.otp}\n"
                "This code is valid for 10 minutes.\n\n"
                "If you did not request a password reset, you can ignore this email."
            )

            # Make sure EMAIL settings are configured in settings.py
            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    recipient_list=[email_id],
                    fail_silently=True,  # avoid breaking if email config is not perfect yet
                )
            except Exception as mail_error:
                # Log / print if needed
                print(f"Error sending reset email: {mail_error}")

        # Always return success message to avoid user enumeration
        return DRFResponse(
            ResponseData.success_without_data(
                "If an account with this email exists, an OTP has been sent."
            ),
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return DRFResponse(
            ResponseData.error(str(e)),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["POST"])
def reset_password(request):
    """
    Called after OTP has already been verified in /customers/api/verify-otp/.
    Just change the password for the given email.
    """
    try:
        email_id = request.data.get("email_id")
        new_password = request.data.get("password")
        confirm_password = request.data.get("confirm_password")

        if not email_id or not new_password or not confirm_password:
            return DRFResponse(
                ResponseData.error("Email, password and confirm password are required."),
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_password != confirm_password:
            return DRFResponse(
                ResponseData.error("Passwords do not match."),
                status=status.HTTP_400_BAD_REQUEST
            )

        customer = CustomerModel.objects.filter(
            email_id=email_id, is_deleted=False
        ).first()

        if not customer:
            return DRFResponse(
                ResponseData.error("Customer not found."),
                status=status.HTTP_404_NOT_FOUND
            )

        # NOTE: you currently store password as plain text in CustomerModel.
        # Keep it consistent so login keeps working.
        customer.password = new_password
        customer.save()

        return DRFResponse(
            ResponseData.success_without_data(
                "Password reset successfully. You can now log in with the new password."
            ),
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return DRFResponse(
            ResponseData.error(str(e)),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )