#!/usr/bin/env python
"""
Check AWS SNS SMS delivery status and configuration
"""

import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poker_lounge.settings')
django.setup()

import boto3
from django.conf import settings

def check_sns_configuration():
    """Check AWS SNS configuration and SMS settings"""

    print("=" * 70)
    print("AWS SNS Configuration Check")
    print("=" * 70)

    # Initialize SNS client
    sns_client = boto3.client(
        'sns',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION
    )

    print(f"\n✓ AWS Region: {settings.AWS_REGION}")
    print(f"✓ Access Key ID: {settings.AWS_ACCESS_KEY_ID[:10]}...")

    # Check SMS attributes
    print("\n" + "=" * 70)
    print("SMS Attributes")
    print("=" * 70)

    try:
        response = sns_client.get_sms_attributes()
        attributes = response.get('attributes', {})

        if attributes:
            for key, value in attributes.items():
                print(f"{key}: {value}")
        else:
            print("No SMS attributes configured")

        print("\n⚠️  Important SMS Attribute Settings:")
        print("   - DefaultSMSType: Should be 'Transactional' or 'Promotional'")
        print("   - MonthlySpendLimit: Check if you have a spending limit")

    except Exception as e:
        print(f"❌ Error getting SMS attributes: {e}")

    # Check if we can get SMS sandbox phone numbers
    print("\n" + "=" * 70)
    print("Verified Phone Numbers (Sandbox)")
    print("=" * 70)

    try:
        # List verified phone numbers
        response = sns_client.list_sms_sandbox_phone_numbers()
        phone_numbers = response.get('PhoneNumbers', [])

        if phone_numbers:
            for phone in phone_numbers:
                status = phone.get('Status', 'Unknown')
                number = phone.get('PhoneNumber', 'Unknown')
                print(f"  {number}: {status}")
        else:
            print("  No verified phone numbers found in sandbox")

    except Exception as e:
        if 'VerifiedAccessDeniedException' in str(e) or 'sandbox' in str(e).lower():
            print("  ℹ️  Sandbox check not available or account is out of sandbox")
        else:
            print(f"  ❌ Error: {e}")

    # Check account SMS sending status
    print("\n" + "=" * 70)
    print("Account Status")
    print("=" * 70)

    try:
        response = sns_client.check_if_phone_number_is_opted_out(
            phoneNumber='+491628893421'
        )
        is_opted_out = response.get('isOptedOut', False)

        if is_opted_out:
            print("❌ Phone number is OPTED OUT from receiving SMS")
            print("   To opt back in, reply 'START' to the AWS number")
        else:
            print("✓ Phone number is NOT opted out")

    except Exception as e:
        print(f"Could not check opt-out status: {e}")

    # Get CloudWatch logs suggestion
    print("\n" + "=" * 70)
    print("Next Steps for Troubleshooting")
    print("=" * 70)
    print("\n1. Check AWS CloudWatch Logs:")
    print("   - Go to: AWS Console → CloudWatch → Log groups")
    print("   - Look for: sns/[region]/[account-id]/DirectPublish")
    print("   - Search for Message ID: dff96f14-6644-55be-b3ff-0e736cfb8d0d")

    print("\n2. Check SNS Dashboard:")
    print("   - Go to: AWS Console → SNS → Text messaging (SMS)")
    print("   - Check 'SMS delivery logs'")
    print("   - Check 'SMS spending'")

    print("\n3. Common Issues:")
    print("   - Phone number opted out (reply START to AWS number)")
    print("   - Carrier blocking AWS messages")
    print("   - Monthly spending limit reached ($1 default)")
    print("   - Account still in sandbox mode")
    print("   - Wrong region selected")

    print("\n4. Enable SMS Delivery Logs (if not enabled):")
    print("   Run the following command to enable CloudWatch logging:")
    print(f"   python enable_sns_logging.py")

    print("\n" + "=" * 70)

if __name__ == '__main__':
    check_sns_configuration()
