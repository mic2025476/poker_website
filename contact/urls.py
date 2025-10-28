from django.urls import path
from . import views

app_name = 'contact'
urlpatterns = [
    path('', views.contact, name='contact'),
    path('api/submit/', views.submit_contact_message, name='submit_message'),
]