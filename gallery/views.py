import os
from django.conf import settings
from django.templatetags.static import static
from django.shortcuts import render

def gallery(request):
    # locate static base
    if getattr(settings, "STATICFILES_DIRS", None):
        static_base = settings.STATICFILES_DIRS[0]
    else:
        static_base = settings.STATIC_ROOT

    thumbs_dir = os.path.join(static_base, "mge_pictures", "thumbs")
    full_dir = os.path.join(static_base, "mge_pictures", "full")

    gallery_images = []
    if os.path.isdir(thumbs_dir):
        for name in sorted(os.listdir(thumbs_dir)):
            if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                gallery_images.append({
                    "thumb": static(f"mge_pictures/thumbs/{name}"),
                    "full": static(f"mge_pictures/full/{name}"),
                    "name": name,
                })

    return render(request, "gallery/gallery.html", {"gallery_images": gallery_images})
