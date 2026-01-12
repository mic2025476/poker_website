# contact/urls.py
from django.urls import path
from . import views
from .views import contact_form  # <-- dot matters
app_name = 'contact'

urlpatterns = [
    path('', views.contact, name='contact'),
    path("api/contact/", contact_form, name="contact_api"),
    path('api/submit/', views.contact_submit, name='submit_message'),
]
