# core/models.py
import random
from django.db import models
from django.utils.timezone import now

class CustomerModel(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email_id = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, unique=True,blank=True,null=True)
    password = models.CharField(max_length=128, blank=True)
    last_login = models.DateTimeField(blank=True, null=True)
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    braintree_customer_id = models.CharField(
        max_length=50, 
        null=True, 
        blank=True, 
        help_text="ID of the Customer in Braintree's vault"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # ✅ NEW FIELDS
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(blank=True, null=True)
    terms_version = models.CharField(max_length=20, blank=True, default="v1")
    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class OTPModel(models.Model):
    """
    OTP model to handle both phone and email verification.
    - phone_number or email_id can be used based on `otp_type`.
    - otp_type: "phone" or "email"
    """
    OTP_TYPE_CHOICES = [
        ("phone", "Phone"),
        ("email", "Email"),
    ]

    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email_id = models.EmailField(blank=True, null=True)
    otp = models.CharField(max_length=6)
    otp_type = models.CharField(max_length=5, choices=OTP_TYPE_CHOICES, default="phone")

    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def generate_otp(self):
        self.otp = str(random.randint(100000, 999999))
        self.created_at = now()
        self.save()

    def __str__(self):
        return f"{self.otp_type.upper()} OTP - {self.phone_number or self.email_id}: {self.otp}"
