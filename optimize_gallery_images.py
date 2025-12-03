# optimize_gallery_images.py
import os
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "static" / "mge_pictures"
FULL_DIR = SRC_DIR / "full"
THUMB_DIR = SRC_DIR / "thumbs"

FULL_DIR.mkdir(parents=True, exist_ok=True)
THUMB_DIR.mkdir(parents=True, exist_ok=True)

MAX_FULL_WIDTH = 1600   # px for modal / fullscreen
MAX_THUMB_WIDTH = 480   # px for grid
QUALITY = 80            # JPEG quality

def process_image(src_path: Path):
    name = src_path.name
    if not src_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
        return

    print("Processing", name)

    img = Image.open(src_path).convert("RGB")

    # ---------- full ----------
    full_path = FULL_DIR / name
    img_full = img.copy()
    if img_full.width > MAX_FULL_WIDTH:
        ratio = MAX_FULL_WIDTH / img_full.width
        img_full = img_full.resize(
            (MAX_FULL_WIDTH, int(img_full.height * ratio)),
            Image.LANCZOS
        )
    img_full.save(full_path, "JPEG", quality=QUALITY, optimize=True)

    # ---------- thumbnail ----------
    thumb_path = THUMB_DIR / name
    img_thumb = img.copy()
    if img_thumb.width > MAX_THUMB_WIDTH:
        ratio = MAX_THUMB_WIDTH / img_thumb.width
        img_thumb = img_thumb.resize(
            (MAX_THUMB_WIDTH, int(img_thumb.height * ratio)),
            Image.LANCZOS
        )
    img_thumb.save(thumb_path, "JPEG", quality=QUALITY, optimize=True)

def main():
    for f in SRC_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
            process_image(f)

if __name__ == "__main__":
    main()
