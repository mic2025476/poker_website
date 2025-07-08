from django.contrib import admin
from .models import DrinkModel

@admin.register(DrinkModel)
class DrinkModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('-created_at',)
