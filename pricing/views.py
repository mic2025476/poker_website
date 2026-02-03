from django.shortcuts import render
from pricing.services import pricing_context

def pricing(request):
    return render(request, "price/pricing.html", pricing_context())
