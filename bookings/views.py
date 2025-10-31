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
from utils.google_calendar import GoogleCalendarService


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
                    'start_time': datetime.combine(booking.booking_date, booking.start_time).strftime('%Y-%m-%d %H:%M'),
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
    booking_slots = BookingModel.objects.filter(booking_date=date_val, is_cancelled=False, is_active=True)
    booking_slots_data = []
    print(f'booking_slots {booking_slots}')
    for booking in booking_slots:
        start_time = booking.start_time  # TimeField
        hours = booking.hours_booked
        start_datetime = datetime.combine(date_val, start_time)
        # Calculate actual end time based on booking duration
        end_datetime = start_datetime + timedelta(hours=hours)
        end_time_str = end_datetime.time().strftime("%H:%M:%S")
            
        booking_slots_data.append({
            "date": date_str,
            "start_time": start_time.strftime("%H:%M:%S"),
            "end_time": end_time_str
        })

    # Get Google Calendar busy times
    calendar_slots_data = []
    try:
        calendar_service = GoogleCalendarService()
        busy_times = calendar_service.get_busy_times(date_val)
        print(f'busy_timesbusy_times {busy_times}')
        for busy_time in busy_times:
            calendar_slots_data.append({
                "date": date_str,
                "start_time": busy_time['start_time'],
                "end_time": busy_time['end_time'],
                "source": "google_calendar",
                "title": busy_time.get('title', 'HOANG Event')
            })
    except Exception as e:
        print(f"Google Calendar fetch failed: {e}")
        # Continue without calendar data if service is unavailable

    # Combine all lists and return the result
    combined_slots = slots_data + booking_slots_data + calendar_slots_data
    print(f'slots_data {slots_data}')
    print(f'booking_slots_data {booking_slots_data}')
    print(f'calendar_slots_data {calendar_slots_data}')
    print(f'combined_slots {combined_slots}')
    return Response({"unavailable_slots": combined_slots}, status=status.HTTP_200_OK)

def edit_booking(request, booking_id):
    """Edit an existing booking"""
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

        # Debug logging
        print(f'check_availability: date_str={date_str}, time_str={time_str}')
        print(f'check_availability: parsed booking_date={booking_date}, start_time={start_time}')

        start_dt = datetime.combine(booking_date, start_time)
        # Calculate actual end time based on booking duration
        end_dt = start_dt + timedelta(hours=hours_booked)

        # Check existing active bookings (not cancelled)
        existing_bookings = BookingModel.objects.filter(
            booking_date=booking_date,
            is_cancelled=False
        )

        for booking in existing_bookings:
            b_start = datetime.combine(booking_date, booking.start_time)
            # Calculate actual end time based on booking duration
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

        # Check Google Calendar events
        try:
            calendar_service = GoogleCalendarService()
            if not calendar_service.is_time_available(booking_date, start_time, end_dt.time()):
                return Response({"available": False, "message": "Selected time conflicts with a HOANG event."}, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"Google Calendar check failed: {e}")
            # Continue without calendar check if service is unavailable
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
            booking_date=booking_date,
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

@api_view(["GET"])
def test_google_calendar(request):
    """Test endpoint to show all Google Calendar events for debugging"""
    try:
        date_str = request.GET.get("date")
        if not date_str:
            return Response({"error": "Missing 'date' parameter."}, status=status.HTTP_400_BAD_REQUEST)
        
        date_val = parse_date(date_str)
        if not date_val:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        calendar_service = GoogleCalendarService()
        events = calendar_service.get_events(date_val)
        
        event_titles = []
        for event in events:
            event_title = event.get('summary', '').strip()
            event_titles.append({
                'title': event_title,
                'start': event['start'],
                'end': event['end']
            })
        
        return Response({
            "date": date_str,
            "total_events": len(events),
            "event_titles": event_titles
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
def cancel_booking(request):
    try:
        booking_id = request.data.get('booking_id')
        customer_id = request.data.get('customer_id')
        
        if not booking_id or not customer_id:
            return Response({"success": False, "message": "Missing booking_id or customer_id"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get the booking
        booking = get_object_or_404(BookingModel, id=booking_id, customer_id=customer_id, is_active=True)
        
        # Check if already cancelled
        if booking.is_cancelled:
            return Response({"success": False, "message": "Booking is already cancelled"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Cancel the booking
        booking.is_cancelled = True
        booking.save()
        
        # Remove event from Google Calendar
        try:
            calendar_service = GoogleCalendarService()
            
            booking_data = {
                'customer_name': f"{booking.customer.first_name} {booking.customer.last_name}",
                'booking_date': booking.booking_date,
                'start_time': booking.start_time,
                'booking_id': booking.id
            }
            
            calendar_deleted = calendar_service.delete_booking_event(booking_data)
            if calendar_deleted:
                print(f"Successfully deleted calendar event for cancelled booking {booking.id}")
            else:
                print(f"Could not find calendar event to delete for booking {booking.id}")
                
        except Exception as e:
            print(f"Error deleting calendar event for booking {booking.id}: {e}")
            # Don't fail the cancellation if calendar deletion fails
        
        return Response({"success": True, "message": "Booking cancelled successfully"}, status=status.HTTP_200_OK)
        
    except BookingModel.DoesNotExist:
        return Response({"success": False, "message": "Booking not found or you don't have permission to cancel it"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"success": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
def get_available_time_slots(request):
    """
    Get available time slots for a specific date considering MGEN-F24 calendar events
    """
    try:
        date_str = request.GET.get('date')
        if not date_str:
            return Response({"success": False, "message": "Date parameter is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({"success": False, "message": "Invalid date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Initialize Google Calendar service
        calendar_service = GoogleCalendarService()
        
        # Get available time slots (full day: 00:00 to 23:00)
        available_slots = calendar_service.get_available_time_slots(
            date=booking_date,
            business_start='00:00',
            business_end='23:00'
        )
        
        return Response({
            "success": True,
            "date": date_str,
            "available_time_slots": available_slots
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"Error getting available time slots: {e}")
        return Response({"success": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
def get_available_durations(request):
    """
    Get available booking durations for a specific date and start time considering MGEN-F24 calendar events
    """
    try:
        date_str = request.GET.get('date')
        start_time_str = request.GET.get('start_time')
        
        if not date_str or not start_time_str:
            return Response({"success": False, "message": "Both date and start_time parameters are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            # Validate start time format
            datetime.strptime(start_time_str, '%H:%M')
        except ValueError:
            return Response({"success": False, "message": "Invalid date format (use YYYY-MM-DD) or time format (use HH:MM)"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Initialize Google Calendar service
        calendar_service = GoogleCalendarService()
        
        # Get available durations (max 12 hours, full day until 23:59)
        available_durations = calendar_service.get_available_durations(
            date=booking_date,
            start_time=start_time_str,
            max_duration=12,
            business_end='23:59'
        )
        
        return Response({
            "success": True,
            "date": date_str,
            "start_time": start_time_str,
            "available_durations": available_durations
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"Error getting available durations: {e}")
        return Response({"success": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_all_booking_data(request):
    """
    Get ALL available time slots with their durations in ONE API call for super fast loading
    """
    try:
        date_str = request.GET.get('date')
        if not date_str:
            return Response({"success": False, "message": "Date parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({"success": False, "message": "Invalid date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

        # Initialize Google Calendar service
        calendar_service = GoogleCalendarService()

        # Authenticate with Google Calendar
        try:
            calendar_service.authenticate()
        except Exception as auth_error:
            print(f"Google Calendar authentication failed: {auth_error}")
            return Response({
                "success": False,
                "message": "Calendar service authentication failed",
                "time_slots_with_hours": {},
                "total_time_slots": 0
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Get available time slots (full day: 00:00 to 23:00)
        available_slots = calendar_service.get_available_time_slots(
            date=booking_date,
            business_start='00:00',
            business_end='23:00'
        )

        # Get durations for each time slot in one go
        time_slots_with_hours = {}

        for time_slot in available_slots:
            # Get available durations for this specific time slot
            available_durations = calendar_service.get_available_durations(
                date=booking_date,
                start_time=time_slot,
                max_duration=24  # Maximum possible duration
            )

            # Only include time slots that have available durations
            if available_durations:
                time_slots_with_hours[time_slot] = available_durations

        return Response({
            "success": True,
            "date": date_str,
            "time_slots_with_hours": time_slots_with_hours,
            "total_time_slots": len(time_slots_with_hours)
        }, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Error getting all booking data: {e}")
        return Response({"success": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_unavailable_dates_range(request):
    """
    Get all fully booked dates within a date range to block them in the calendar picker
    """
    try:
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')

        if not start_date_str or not end_date_str:
            return Response({"success": False, "message": "Both start_date and end_date parameters are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({"success": False, "message": "Invalid date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

        # Initialize Google Calendar service
        calendar_service = GoogleCalendarService()

        # Authenticate with Google Calendar
        try:
            calendar_service.authenticate()
        except Exception as auth_error:
            print(f"Google Calendar authentication failed: {auth_error}")
            # Return empty unavailable dates if calendar is not available
            return Response({
                "success": True,
                "start_date": start_date_str,
                "end_date": end_date_str,
                "unavailable_dates": [],
                "total_unavailable": 0,
                "note": "Calendar service unavailable - all dates shown as available"
            }, status=status.HTTP_200_OK)

        unavailable_dates = []
        current_date = start_date

        # Check each date in the range (limit to 30 days to avoid timeout)
        days_checked = 0
        max_days = 30

        while current_date <= end_date and days_checked < max_days:
            try:
                # Get available time slots for this date (remove invalid parameter)
                available_slots = calendar_service.get_available_time_slots(
                    date=current_date,
                    business_start='00:00',
                    business_end='23:00'
                )

                # If no available slots, this date is fully booked
                if not available_slots or len(available_slots) == 0:
                    unavailable_dates.append(current_date.strftime('%Y-%m-%d'))
                    print(f"Date {current_date} is fully booked - added to unavailable dates")

            except Exception as slot_error:
                print(f"Error checking slots for {current_date}: {slot_error}")
                # Continue checking other dates

            # Move to next day
            current_date += timedelta(days=1)
            days_checked += 1

        return Response({
            "success": True,
            "start_date": start_date_str,
            "end_date": end_date_str,
            "unavailable_dates": unavailable_dates,
            "total_unavailable": len(unavailable_dates),
            "days_checked": days_checked
        }, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Error getting unavailable dates range: {e}")
        return Response({"success": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)