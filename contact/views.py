from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import ContactMessage
from .serializers import ContactMessageSerializer
from response import Response as ResponseData

def contact(request):
    return render(request, 'contact/contact.html')

@api_view(['POST'])
def submit_contact_message(request):
    """
    API endpoint to submit a contact message
    """
    try:
        serializer = ContactMessageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                ResponseData.success_without_data("Your message has been sent successfully. We'll get back to you soon!"),
                status=status.HTTP_201_CREATED
            )
        else:
            error_message = " ".join([f"{key}: {', '.join(value)}" for key, value in serializer.errors.items()])
            return Response(
                ResponseData.error(error_message),
                status=status.HTTP_400_BAD_REQUEST
            )
    except Exception as e:
        return Response(
            ResponseData.error(str(e)),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )