from django.http import JsonResponse
from django.shortcuts import render
import braintree
from django.http import HttpResponse  # Add this import
from rest_framework.decorators import api_view
from rest_framework import status
from rest_framework.response import Response as DRFResponse
from django.shortcuts import get_object_or_404
from bookings.models import BookingModel
from menu.models import DrinkModel
from customers.models import CustomerModel
from .serializers import BookingSerializer
from response import Response as ResponseData  # Assuming you have a utility for handling responses
from django.utils.dateparse import parse_date
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import UnavailableTimeSlotModel
from .serializers import UnavailableTimeSlotSerializer
from datetime import datetime, timedelta
from poker_lounge import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils.dateparse import parse_time, parse_date


gateway = braintree.BraintreeGateway(
    braintree.Configuration(
        environment=getattr(braintree.Environment, settings.BRAINTREE_ENVIRONMENT),
        merchant_id=settings.BRAINTREE_MERCHANT_ID,
        public_key=settings.BRAINTREE_PUBLIC_KEY,
        private_key=settings.BRAINTREE_PRIVATE_KEY,
    )
)

def book(request):
    if not request.session.get("user_id"):
        return redirect("/")  # or use reverse('home') if you're using named URLs

    drinks = DrinkModel.objects.all()
    return render(request, 'bookings/book.html', {
        'drinks': drinks,
        'timestamp': datetime.now().timestamp()
        })

@api_view(["POST"])
def create_booking(request):
    try:
        serializer = BookingSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            customer_id = data['customer_id']
            start_time = data['start_time']
            total_people = data['total_people']
            hours_booked = data['hours_booked']
            total_amount = data['total_amount']
            deposit_amount = data['deposit_amount']
            drink_ids = data.get('drink_ids', [])

            # Get customer
            customer = get_object_or_404(CustomerModel, id=customer_id, is_active=True)

            # Check and get drinks
            drinks = DrinkModel.objects.filter(id__in=drink_ids, is_active=True)
            if len(drinks) != len(drink_ids):
                return DRFResponse(
                    ResponseData.error("Some drinks are invalid or inactive."),
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create the booking
            booking = BookingModel.objects.create(
                customer=customer,
                start_time=start_time,
                total_people=total_people,
                hours_booked=hours_booked,
                total_amount=total_amount,
                deposit_amount=deposit_amount,
            )

            # Add drinks
            booking.drinks.set(drinks)

            return DRFResponse(
                ResponseData.success({"booking_id": booking.id}, "Booking created successfully."),
                status=status.HTTP_201_CREATED
            )
        else:
            error_message = " ".join([f"{key}: {', '.join(value)}" for key, value in serializer.errors.items()])
            return DRFResponse(ResponseData.error(error_message), status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return DRFResponse(ResponseData.error(str(e)), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(["POST"])
def get_user_bookings(request):
    """ Fetches all bookings of the logged-in user via POST """
    if request.method == "POST":
        try:
            customer_id = request.data['customer_id']
            bookings = BookingModel.objects.filter(customer_id=customer_id).order_by('-created_at')
            print(f'bookings123 {bookings}')
            booking_list = []
            for booking in bookings:
                booking_list.append({
                    'id': booking.id,
                    'start_time': datetime.combine(booking.created_at.date(), booking.start_time).strftime('%Y-%m-%d %H:%M'),
                    'total_people': booking.total_people,
                    'hours_booked': booking.hours_booked,
                    'total_amount': float(booking.total_amount),
                    'deposit_amount': float(booking.deposit_amount),
                    'is_cancelled': booking.is_cancelled,
                    'is_active': booking.is_active,
                    'created_at': booking.created_at.strftime('%Y-%m-%d %H:%M'),
                    'drinks': [drink.name for drink in booking.drinks.all()]
                })

            return JsonResponse({'bookings': booking_list}, status=200)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=400)

@api_view(["GET"])
def get_unavailable_slots(request):
    # Expecting date in 'YYYY-MM-DD' format as a query parameter
    date_str = request.GET.get("date")
    if not date_str:
        return Response({"error": "Missing 'date' parameter."}, status=status.HTTP_400_BAD_REQUEST)
    
    date_val = parse_date(date_str)
    if not date_val:
        return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

    # Get unavailable slots from UnavailableTimeSlotModel
    slots_queryset = UnavailableTimeSlotModel.objects.filter(date=date_val)
    slots_data = UnavailableTimeSlotSerializer(slots_queryset, many=True).data

    # Also, get booking slots (only active and not cancelled)
    booking_slots = BookingModel.objects.filter(created_at__date=date_val, is_cancelled=False, is_active=True)
    booking_slots_data = []
    print(f'booking_slots {booking_slots}')
    for booking in booking_slots:
        start_time = booking.start_time  # TimeField
        hours = booking.hours_booked
        start_datetime = datetime.combine(date_val, start_time)
        end_datetime = start_datetime + timedelta(hours=hours)
        booking_slots_data.append({
            "date": date_str,
            "start_time": start_time.strftime("%H:%M:%S"),
            "end_time": end_datetime.time().strftime("%H:%M:%S")
        })

    # Combine both lists and return the result
    combined_slots = slots_data + booking_slots_data
    print(f'slots_data {slots_data}')
    print(f'booking_slots_data {booking_slots_data}')
    print(f'combined_slots {combined_slots}')
    return Response({"unavailable_slots": combined_slots}, status=status.HTTP_200_OK)

    # Get the booking instance or return a 404 if not found
    booking = get_object_or_404(BookingModel, id=booking_id)
    # Get all available drinks for the form
    drinks = DrinkModel.objects.all()
    
    if request.method == "POST":
        # Retrieve form values
        booking_date = request.POST.get("booking_date")
        booking_time = request.POST.get("booking_time")
        number_of_people = request.POST.get("number_of_people")
        number_of_hours = request.POST.get("number_of_hours")
        selected_drinks = request.POST.getlist("drinks")
        
        # Update the booking instance with new values
        booking.booking_date = booking_date
        booking.booking_time = booking_time
        booking.total_people = number_of_people
        booking.hours_booked = number_of_hours
        # Assuming booking.drinks is a ManyToManyField
        booking.drinks.set(selected_drinks)
        booking.save()
        
        messages.success(request, "Booking updated successfully.")
        # Redirect back to your My Bookings page (adjust the URL name as needed)
        return redirect("my_bookings")
    
    # Prepare a list of drink IDs for prechecking checkboxes in the template.
    # This assumes booking.drinks.all() returns a queryset of Drink objects.
    booking_drink_ids = list(booking.drinks.values_list("id", flat=True))
    
    # Render the edit booking template with the booking and drinks context.
    return render(request, "edit_booking.html", {
        "booking": booking,
        "drinks": drinks,
        "booking_drink_ids": booking_drink_ids
    })

@api_view(["POST"])
def check_availability(request):
    try:
        print(f'request.data {request.data}')
        date_str = request.data.get("date")
        user_id = request.data.get("user_id")
        time_str = request.data.get("start_time")
        total_people = request.data.get("total_people")
        hours_booked_raw = request.data.get("hours_booked")

        if not date_str or not time_str or not hours_booked_raw:
            return Response({"available": False, "message": "Missing required parameters."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            hours_booked = int(hours_booked_raw)
        except ValueError:
            return Response({"available": False, "message": "Invalid value for number of hours."}, status=status.HTTP_400_BAD_REQUEST)

        # Parse date and time properly
        booking_date = parse_date(date_str)         # returns datetime.date
        start_time = parse_time(time_str)           # returns datetime.time

        if not booking_date or not start_time:
            return Response({"available": False, "message": "Invalid date or time format."}, status=status.HTTP_400_BAD_REQUEST)

        start_dt = datetime.combine(booking_date, start_time)
        end_dt = start_dt + timedelta(hours=hours_booked)

        # Check existing active bookings (not cancelled)
        existing_bookings = BookingModel.objects.filter(
            created_at__date=booking_date,
            is_cancelled=False
        )

        for booking in existing_bookings:
            b_start = datetime.combine(booking_date, booking.start_time)
            b_end = b_start + timedelta(hours=booking.hours_booked)
            if start_dt < b_end and end_dt > b_start:
                return Response({"available": False, "message": "Selected time overlaps with an existing booking."}, status=status.HTTP_200_OK)

        # Check unavailable manual blocks
        blocked_slots = UnavailableTimeSlotModel.objects.filter(date=booking_date)
        for slot in blocked_slots:
            s_start = datetime.combine(booking_date, slot.start_time)
            s_end = datetime.combine(booking_date, slot.end_time)
            if start_dt < s_end and end_dt > s_start:
                return Response({"available": False, "message": "Selected time overlaps with an unavailable slot."}, status=status.HTTP_200_OK)
        rate = 2
        try:
            total_people = int(float(total_people))
        except (ValueError, TypeError):
            return Response({"available": False, "message": "Invalid input for hours or people."}, status=status.HTTP_400_BAD_REQUEST)

        total = hours_booked * total_people * rate
        deposit = round(total * 0.3, 2)
        # Create a temp inactive booking to "hold" the slot
        customer = CustomerModel.objects.get(id=user_id, is_active=True)
        BookingModel.objects.create(
            customer=customer,
            start_time=start_time,
            total_amount=total,
            deposit_amount=deposit,
            total_people=total_people,
            hours_booked=hours_booked,
            is_active=False  # Hold the slot, but don't activate yet
        )

        return Response({"available": True, "message": "Time slot is available."}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"available": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)