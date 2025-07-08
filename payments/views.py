# payments/views.py
from datetime import datetime
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from bookings.models import BookingModel
from payments.models import CustomerPaymentModel
from response import Response as ResponseData  # or wherever your ResponseData is located
from django.conf import settings
import braintree

from customers.models import CustomerModel  # to fetch the customer
# Make sure you have a CustomerPaymentModel that references CustomerModel

gateway = braintree.BraintreeGateway(
    braintree.Configuration(
        environment=getattr(braintree.Environment, settings.BRAINTREE_ENVIRONMENT),
        merchant_id=settings.BRAINTREE_MERCHANT_ID,
        public_key=settings.BRAINTREE_PUBLIC_KEY,
        private_key=settings.BRAINTREE_PRIVATE_KEY,
    )
)

def generate_client_token(request):
    """Return Braintree client token to the client (plain text)."""
    token = gateway.client_token.generate()
    return HttpResponse(token, content_type='text/plain')


def process_braintree_payment(nonce, amount, customer_id):
    """
    Reusable function to process a payment using Braintree.
    
    Returns:
        (success: bool, message: str, transaction_id: str or None)
    """
    if not nonce or not amount or not customer_id:
        return (False, "Missing nonce, amount, or customer_id.", None)

    try:
        result = gateway.transaction.sale({
            "amount": str(amount),  # convert Decimal to str for Braintree
            "payment_method_nonce": nonce,
            "options": {
                "submit_for_settlement": True
            }
        })

        if result.is_success:
            transaction = result.transaction
            # Save in CustomerPaymentModel
            try:
                customer = CustomerModel.objects.get(id=customer_id, is_active=True)
            except CustomerModel.DoesNotExist:
                return (False, "Customer not found or inactive.", None)

            CustomerPaymentModel.objects.create(
                customer=customer,
                amount=transaction.amount,
                transaction_id=transaction.id,
                status=transaction.status
            )
            return (True, "Transaction successful", transaction.id)
        else:
            return (False, f"Transaction failed: {result.message}", None)

    except Exception as e:
        return (False, f"Error processing payment: {str(e)}", None)


@api_view(["POST"])
def process_payment(request):
    try:
        print(f'data123 {request.data}')
        data = request.data
        # Validate required fields
        required_fields = ['booking_date', 'number_of_people', 'number_of_hours', 'payment_method_nonce','user_id','drinks']
        for field in required_fields:
            if field not in data:
                return Response(ResponseData.error(f"Missing {field}"), status=400)

        # Calculate deposit on server
        rate = 2  # Euros/hour/person
        hours = int(data['number_of_hours'])
        people = int(data['number_of_people'])
        total = hours * people * rate
        deposit = round(total * 0.3, 2)
        customer = CustomerModel.objects.get(id=data['user_id'], is_active=True)
        # Process payment
        success, message, transaction_id = process_braintree_payment(
            nonce=data['payment_method_nonce'],
            amount=str(deposit),
            customer_id=customer.id  # Assuming user has a Braintree customer ID
        )

        if not success:
            return Response(ResponseData.error(message), status=400)

        # Create booking
        start_time = datetime.strptime(data['booking_date'], "%Y-%m-%dT%H:%M").time()

        # Try to find existing booking with is_active = False
        existing_booking = BookingModel.objects.filter(
            customer=customer,
            start_time=start_time,
            total_people=data['number_of_people'],
            hours_booked=data['number_of_hours'],
            total_amount=total,
            deposit_amount=deposit,
            is_active=False
        ).first()
# Assign many-to-many field after object creation
        if 'drinks' in data:
            existing_booking.drinks.set(data['drinks'])  # Correct way to assign M2M relationships
            existing_booking.is_active = True
            existing_booking.save()
        return Response(ResponseData.success_without_data("Booking created & payment processed"))

    except Exception as e:
        return Response(ResponseData.error(str(e)), status=500)