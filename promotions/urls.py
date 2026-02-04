from django.urls import path
from .views import apply_promo

urlpatterns = [
    path("apply/", apply_promo, name="apply_promo"),
]
