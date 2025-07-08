import random
import braintree
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
from django.db.models import Q
from response import Response as ResponseData  # Your custom response class

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
            phone_number = data['phone_number']
            email_id = data['email_id']
            first_name = data['first_name']
            last_name = data['last_name']
            password = data['password']
            confirm_password = data['confirm_password']

            if password != confirm_password:
                return DRFResponse(
                    ResponseData.error("Passwords do not match."),
                    status=status.HTTP_400_BAD_REQUEST
                )

            existing_customer = CustomerModel.objects.filter(
                Q(phone_number=phone_number) | Q(email_id=email_id)
            ).first()

            if existing_customer:
                if not existing_customer.is_deleted:
                    if existing_customer.is_active:
                        return DRFResponse(
                            ResponseData.error("Customer already exists and is active."),
                            status=status.HTTP_200_OK
                        )
                    else:
                        _generate_or_regenerate_otp(email_id=email_id, otp_type="email")
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


                _generate_or_regenerate_otp(email_id=email_id, otp_type="email")
                return DRFResponse(
                    ResponseData.success_without_data("Customer signed up successfully. OTPs have been sent for phone & email."),
                    status=status.HTTP_201_CREATED
                )
        else:
            error_message = " ".join([f"{key}: {', '.join(value)}" for key, value in serializer.errors.items()])
            return DRFResponse(ResponseData.error(error_message), status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return DRFResponse(ResponseData.error(str(e)), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
def verify_otp(request):
    try:
        print(f'request.data {request.data}')
        serializer = OTPCombinedVerifySerializer(data=request.data)
        if not serializer.is_valid():
            error_message = " ".join([f"{key}: {', '.join(value)}" for key, value in serializer.errors.items()])
            return DRFResponse(ResponseData.error(error_message), status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        email_verified = False

        if 'email_id' in data and 'email_otp' in data:
            email_id = data['email_id']
            email_otp = data['email_otp']
            otp_instance = OTPModel.objects.filter(
                email_id=email_id,
                otp=email_otp,
                otp_type="email",
                is_verified=False
            ).first()
            if not otp_instance:
                return DRFResponse(ResponseData.error("Invalid or expired Email OTP."), status=status.HTTP_400_BAD_REQUEST)
            otp_instance.is_verified = True
            otp_instance.save()
            customer = CustomerModel.objects.filter(email_id=email_id).first()
            if not customer:
                return DRFResponse(ResponseData.error("Customer not found."), status=status.HTTP_400_BAD_REQUEST)
            customer.is_email_verified = True
            customer.save()

        # Activate customer if both phone and email are verified
        customer = None
        if 'email_id' in data:
            customer = CustomerModel.objects.filter(email_id=data['email_id']).first()
        if customer and customer.is_email_verified:
            customer.is_active = True
            customer.is_phone_verified = True
            customer.save()

        return DRFResponse(ResponseData.success(str(customer.id),"OTP verification successful."), status=status.HTTP_200_OK)
    except Exception as e:
        return DRFResponse(ResponseData.error(str(e)), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        return DRFResponse(ResponseData.success(customer.id,"Login successful."), status=status.HTTP_200_OK)
    except Exception as e:
        return DRFResponse(ResponseData.error(str(e)), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def _generate_or_regenerate_otp(email_id: str, otp_type: str):
    otp_instance = OTPModel.objects.filter(email_id=email_id, otp_type="email", is_verified=False).first()
    if otp_instance:
        otp_instance.generate_otp()
    else:
        OTPModel.objects.create(
            email_id=email_id,
            otp_type="email",
            otp=str(random.randint(100000, 999999))
        )


@api_view(["POST"])
def customer_logout(request):
    logout(request)
    return DRFResponse(ResponseData.success_without_data("Logout successful."), status=status.HTTP_200_OK)
