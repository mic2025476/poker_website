import boto3
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class SNSClient:
    """AWS SNS Client for sending SMS messages"""

    def __init__(self):
        """Initialize AWS SNS client with credentials from settings"""
        self.sns_client = boto3.client(
            'sns',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )

    def send_sms(self, phone_number, message):
        """
        Send SMS to a phone number using AWS SNS

        Args:
            phone_number (str): Phone number in E.164 format (e.g., +491234567890)
            message (str): Message text to send

        Returns:
            dict: Response from AWS SNS or error details
        """
        try:
            # Ensure phone number is in E.164 format
            if not phone_number.startswith('+'):
                logger.warning(f"Phone number {phone_number} doesn't start with '+'. Adding it.")
                phone_number = '+' + phone_number.lstrip('0')

            response = self.sns_client.publish(
                PhoneNumber=phone_number,
                Message=message,
                MessageAttributes={
                    'AWS.SNS.SMS.SenderID': {
                        'DataType': 'String',
                        'StringValue': 'PokerLng'
                    },
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional'  # Use 'Promotional' for marketing messages
                    }
                }
            )

            logger.info(f"SMS sent successfully to {phone_number}. MessageId: {response['MessageId']}")
            return {
                'success': True,
                'message_id': response['MessageId'],
                'message': 'SMS sent successfully'
            }

        except self.sns_client.exceptions.InvalidParameterException as e:
            logger.error(f"Invalid parameter when sending SMS to {phone_number}: {str(e)}")
            return {
                'success': False,
                'error': 'Invalid phone number or message format',
                'details': str(e)
            }

        except Exception as e:
            logger.error(f"Error sending SMS to {phone_number}: {str(e)}")
            return {
                'success': False,
                'error': 'Failed to send SMS',
                'details': str(e)
            }

    def send_otp_sms(self, phone_number, otp):
        """
        Send OTP SMS to a phone number

        Args:
            phone_number (str): Phone number in E.164 format
            otp (str): OTP code to send

        Returns:
            dict: Response from send_sms method
        """
        message = f"Your Poker Lounge verification code is: {otp}\n\nThis code will expire in 10 minutes."
        return self.send_sms(phone_number, message)


def send_otp_via_sns(phone_number, otp):
    """
    Helper function to send OTP via AWS SNS

    Args:
        phone_number (str): Phone number to send OTP to
        otp (str): OTP code

    Returns:
        dict: Response with success status and message
    """
    sns_client = SNSClient()
    return sns_client.send_otp_sms(phone_number, otp)
