from django.urls import path
from .views import customer_logout, customer_signup, verify_otp, customer_login

urlpatterns = [
    path('api/signup/', customer_signup, name='customer_signup'),
    path('api/verify-otp/', verify_otp, name='verify_otp'),
    path('api/login/', customer_login, name='customer_login'),
    path('api/logout/', customer_logout, name='customer_logout'),
]
