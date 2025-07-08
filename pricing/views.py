from django.shortcuts import render

def pricing(request):
    return render(request, 'price/pricing.html')