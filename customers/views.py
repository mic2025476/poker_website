import random
import braintree
import json
from django.utils.timezone import now
from requests import Response
from rest_framework.decorators import api_view
from rest_framework.response import Response as DRFResponse
from rest_framework import status
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
                    is_active=False,
                    is_deleted=False
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
        print(f'request.data {request.data}')
        email = request.data.get('email_id')
        password = request.data.get('password')
        customer = CustomerModel.objects.filter(email_id=email, password=password, is_deleted=False).first()
        if not customer:
            return DRFResponse(ResponseData.error("Invalid credentials or user not found."), status=status.HTTP_400_BAD_REQUEST)
        if not customer.is_active:
            return DRFResponse(ResponseData.error("Account is not active. Please verify both phone and email."), status=status.HTTP_200_OK)
        login(request, customer)  # or set session variables manually
        request.session["user_id"] = customer.id
        request.session.set_expiry(1209600)            # 2 weeks (matches your settings)
        request.session.save()                        # <- force write
        return DRFResponse(ResponseData.success(customer.id,"Login successful."), status=status.HTTP_200_OK)
    except Exception as e:
        return DRFResponse(ResponseData.error(str(e)), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
    """Handle Google OAuth authentication"""
    try:
        google_token = request.data.get('google_token')
        if not google_token:
            return DRFResponse(
                ResponseData.error("Google token is required."),
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify the Google token
        try:
            idinfo = id_token.verify_oauth2_token(
                google_token,
                google_requests.Request(),
                settings.GOOGLE_OAUTH2_CLIENT_ID
            )

            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('Wrong issuer.')

            # Extract user information from Google token
            google_id = idinfo['sub']
            email = idinfo['email']
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
            picture = idinfo.get('picture', '')

        except ValueError as e:
            return DRFResponse(
                ResponseData.error("Invalid Google token."),
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if user already exists
        customer = CustomerModel.objects.filter(email_id=email, is_deleted=False).first()

        if customer:
            # User exists, log them in
            if not customer.is_active:
                # Activate the account since Google has verified the email
                customer.is_active = True
                customer.is_email_verified = True
                customer.save()

            # Update last login
            customer.last_login = now()
            customer.save()

            # Set session
            request.session["user_id"] = customer.id

            return DRFResponse(
                ResponseData.success(customer.id, "Login successful."),
                status=status.HTTP_200_OK
            )
        else:
            # Create new user
            new_customer = CustomerModel.objects.create(
                first_name=first_name,
                last_name=last_name,
                email_id=email,
                password='',  # No password for Google users
                is_email_verified=True,  # Google has verified the email
                is_active=True,
                is_deleted=False,
                last_login=now()
            )

            # Create Braintree customer
            try:
                result = gateway.customer.create({
                    "first_name": new_customer.first_name,
                    "last_name": new_customer.last_name,
                    "email": new_customer.email_id,
                })
                if result.is_success:
                    new_customer.braintree_customer_id = result.customer.id
                    new_customer.save()
                else:
                    # Log the error but don't fail the registration
                    print(f"Braintree customer creation failed: {result.message}")
            except Exception as e:
                print(f"Braintree error: {str(e)}")

            # Set session
            request.session["user_id"] = new_customer.id

            return DRFResponse(
                ResponseData.success(new_customer.id, "Account created and logged in successfully."),
                status=status.HTTP_201_CREATED
            )

    except Exception as e:
        return DRFResponse(
            ResponseData.error(str(e)),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(["GET"])
def whoami(request):
    print("COOKIES", request.COOKIES)                 # see sessionid sent by client
    print("SESSION_KEY", request.session.session_key) # server’s current key
    return DRFResponse({
        "request_user_is_authenticated": getattr(request.user, "is_authenticated", False),
        "session_user_id": request.session.get("user_id"),
        "session_keys": list(request.session.keys()),
    })
