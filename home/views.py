from django.shortcuts import render
from django.utils import timezone
from django.conf import settings
import os

def home(request):
    # Construct the correct absolute path for the gallery
    gallery_path = os.path.join(settings.BASE_DIR, 'static', 'images')
    gallery_images = []

    print(f'Checking directory: {gallery_path}')  # Debugging print

    # Ensure the directory exists before attempting to list files
    if os.path.exists(gallery_path):
        print(f'Files found: {os.listdir(gallery_path)}')  # Debugging print
        for filename in os.listdir(gallery_path):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                # Construct the static URL path for serving images
                gallery_images.append(f"{settings.STATIC_URL}images/{filename}")
    else:
        print("Gallery directory does not exist.")  # Debugging print

    context = {
        'gallery_images': gallery_images,
        'current_year': timezone.now().year,
    } 
    return render(request, "home/home.html", {
        "GOOGLE_CLIENT_ID": settings.GOOGLE_OAUTH2_CLIENT_ID,
    })