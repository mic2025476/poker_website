from django.urls import path
from . import views
from .views import check_availability, create_booking, get_unavailable_slots, get_user_bookings, cancel_booking, test_google_calendar, get_available_time_slots, get_available_durations, get_all_booking_data, get_unavailable_dates_range

app_name = 'bookings'  # Set the app namespace
urlpatterns = [
    path('book/', views.book, name='book'),  # Example URL pattern
    path("create_booking/", create_booking, name="create-booking"),
    path('get-user-bookings/', get_user_bookings, name='get_user_bookings'),
    path('get_unavailable_slots/', get_unavailable_slots, name='get_unavailable_slots'),
    path('check_availability/', check_availability, name='check_availability'),
    path('cancel-booking/', cancel_booking, name='cancel_booking'),
    path('test-google-calendar/', test_google_calendar, name='test_google_calendar'),
    path('get-available-time-slots/', get_available_time_slots, name='get_available_time_slots'),
    path('get-available-durations/', get_available_durations, name='get_available_durations'),
    path('get-all-booking-data/', get_all_booking_data, name='get_all_booking_data'),
    path('get_unavailable_dates_range/', get_unavailable_dates_range, name='get_unavailable_dates_range'),
]