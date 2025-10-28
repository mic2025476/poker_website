from django.urls import path
from .views import (
    customer_logout, customer_signup, verify_otp, customer_login,
    send_mobile_otp, verify_mobile_otp, get_customer_profile, update_phone_number,
    google_auth
)

urlpatterns = [
    path('api/signup/', customer_signup, name='customer_signup'),
    path('api/verify-otp/', verify_otp, name='verify_otp'),
    path('api/login/', customer_login, name='customer_login'),
    path('api/logout/', customer_logout, name='customer_logout'),
    path('api/send-mobile-otp/', send_mobile_otp, name='send_mobile_otp'),
    path('api/verify-mobile-otp/', verify_mobile_otp, name='verify_mobile_otp'),
    path('api/profile/', get_customer_profile, name='get_customer_profile'),
    path('api/update-phone/', update_phone_number, name='update_phone_number'),
    path('api/google-auth/', google_auth, name='google_auth'),
]
