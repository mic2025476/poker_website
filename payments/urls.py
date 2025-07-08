# payments/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('braintree/client-token/', views.generate_client_token, name='generate_client_token'),
    path('braintree/process-payment/', views.process_payment, name='process_payment'),
]
