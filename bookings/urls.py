from django.urls import path
from . import views
from .views import check_availability, create_booking, get_unavailable_slots, get_user_bookings

app_name = 'bookings'  # Set the app namespace
urlpatterns = [
    path('book/', views.book, name='book'),  # Example URL pattern
    path("create_booking/", create_booking, name="create-booking"),
    path('get-user-bookings/', get_user_bookings, name='get_user_bookings'),
    path('get_unavailable_slots/', get_unavailable_slots, name='get_unavailable_slots'),
    path('check_availability/', check_availability, name='check_availability'),
]