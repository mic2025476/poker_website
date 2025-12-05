# contact/urls.py
from django.urls import path
from . import views

app_name = 'contact'

urlpatterns = [
    path('', views.contact, name='contact'),
    path('api/submit/', views.contact_submit, name='submit_message'),
]
