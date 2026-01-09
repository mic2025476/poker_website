from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("create-checkout-session/", views.create_checkout_session, name="create_checkout_session"),
    path("stripe-webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("stripe/success/", views.stripe_success, name="stripe_success"),
    path("stripe/cancel/", views.stripe_cancel, name="stripe_cancel"),
]
