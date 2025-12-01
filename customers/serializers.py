from rest_framework import serializers

class CustomerSignupSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=255)
    last_name = serializers.CharField(max_length=255)
    email_id = serializers.EmailField()
    phone_number = serializers.CharField(max_length=15, required=False, allow_blank=True)
    password = serializers.CharField(max_length=128)
    confirm_password = serializers.CharField(max_length=128)
    # ✅ New: user must tick this
    terms_accepted = serializers.BooleanField()

    def validate_terms_accepted(self, value):
        if not value:
            raise serializers.ValidationError(
                "You must accept the Terms & Conditions to create an account."
            )
        return value
    
class OTPCombinedVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15, required=False)
    phone_otp = serializers.CharField(max_length=6, required=False)
    email_id = serializers.EmailField(required=False)
    email_otp = serializers.CharField(max_length=6, required=False)

    def validate(self, data):
        if not data.get('phone_number') and not data.get('email_id'):
            raise serializers.ValidationError("At least one of phone_number or email_id is required.")
        if data.get('phone_number') and not data.get('phone_otp'):
            raise serializers.ValidationError("phone_otp is required when phone_number is provided.")
        if data.get('email_id') and not data.get('email_otp'):
            raise serializers.ValidationError("email_otp is required when email_id is provided.")
        return data
