#!/usr/bin/env python
"""
Enable CloudWatch logging for SNS SMS delivery and check specific message
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poker_lounge.settings')
django.setup()

import boto3
from django.conf import settings

def enable_sms_logging():
    """Enable CloudWatch logging for SMS delivery"""

    sns_client = boto3.client(
        'sns',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION
    )

    print("=" * 70)
    print("Enabling SMS Delivery Logging")
    print("=" * 70)

    try:
        # Set SMS attributes to enable logging
        response = sns_client.set_sms_attributes(
            attributes={
                'DefaultSMSType': 'Transactional',
                'DeliveryStatusIAMRole': 'arn:aws:iam::315115842199:role/SNSSuccessFeedback',
                'DeliveryStatusSuccessSamplingRate': '100'
            }
        )
        print("✓ SMS logging enabled successfully")
        print("\nNote: You may need to create an IAM role first if it doesn't exist")
        print("Go to: AWS Console → IAM → Roles → Create role")

    except Exception as e:
        print(f"❌ Error enabling logging: {e}")
        print("\nTo manually enable:")
        print("1. Go to: AWS Console → SNS → Text messaging (SMS)")
        print("2. Click 'Delivery status logging'")
        print("3. Enable logging with CloudWatch")

    # Check verified numbers in eu-north-1
    print("\n" + "=" * 70)
    print(f"Checking Sandbox Numbers in {settings.AWS_REGION}")
    print("=" * 70)

    try:
        response = sns_client.list_sms_sandbox_phone_numbers()
        phone_numbers = response.get('PhoneNumbers', [])

        if phone_numbers:
            for phone in phone_numbers:
                status = phone.get('Status', 'Unknown')
                number = phone.get('PhoneNumber', 'Unknown')
                print(f"  ✓ {number}: {status}")
        else:
            print("  No verified numbers found OR account is out of sandbox")

    except Exception as e:
        if 'NotFoundException' in str(e):
            print("  ✓ Account appears to be OUT OF SANDBOX (production mode)")
        else:
            print(f"  Info: {e}")

    print("\n" + "=" * 70)
    print("Manual Checks")
    print("=" * 70)
    print("\n1. Go to AWS Console → SNS → Text messaging (SMS) → [eu-north-1]")
    print("2. Check 'Recent deliveries' or 'Delivery logs'")
    print(f"3. Search for Message ID: b2c3de65-3aa6-5370-b9b4-bf02317701b7")
    print("4. Check if there are any failed deliveries")

    print("\n" + "=" * 70)
    print("Common Reasons for Not Receiving SMS")
    print("=" * 70)
    print("\n1. Carrier Blocking:")
    print("   - Some carriers block AWS SMS numbers")
    print("   - Try with a different carrier/SIM card")

    print("\n2. Sandbox vs Production:")
    print("   - If in sandbox, phone must be verified in eu-north-1")
    print("   - Go to: AWS Console → SNS [eu-north-1] → Text messaging → Sandbox")

    print("\n3. Message Delays:")
    print("   - Can take 1-5 minutes depending on carrier")

    print("\n4. Phone Number Format:")
    print("   - Ensure it's in E.164 format: +491628893421")

    print("\n5. AWS Service Health:")
    print("   - Check: https://health.aws.amazon.com/health/status")
    print("   - Select eu-north-1 region")

if __name__ == '__main__':
    enable_sms_logging()
