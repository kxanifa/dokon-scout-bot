import io

from PIL import Image, ImageOps


class InvalidImageError(Exception):
    """Raised when the image bytes cannot be identified or processed."""
    pass


def compress_image(image_bytes: bytes, max_dimension: int = 1600, quality: int = 80) -> bytes:
    """
    Compress an image according to SPEC section 8:
    - Auto-rotate based on EXIF metadata (ImageOps.exif_transpose)
    - Convert to RGB
    - Resize so longest side <= max_dimension (default 1600px)
    - Save as JPEG with specified quality (default 80)
    """
    if not image_bytes:
        raise InvalidImageError("Bo'sh rasm baytlari berildi.")

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Fix orientation from EXIF
            img = ImageOps.exif_transpose(img)

            # Convert RGBA/P to RGB for JPEG
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Check dimensions and scale down if needed
            width, height = img.size
            if max(width, height) > max_dimension:
                if width > height:
                    new_width = max_dimension
                    new_height = int(height * (max_dimension / width))
                else:
                    new_height = max_dimension
                    new_width = int(width * (max_dimension / height))
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            output = io.BytesIO()
            img.save(output, format="JPEG", quality=quality, optimize=True)
            return output.getvalue()
    except Exception as e:
        if isinstance(e, InvalidImageError):
            raise
        raise InvalidImageError(f"Rasm qayta ishlashda xatolik: {e}") from e


def create_thumbnail(image_bytes: bytes, max_width: int = 300) -> bytes:
    """Create a smaller thumbnail for fast loading in UI/list view."""
    return compress_image(image_bytes, max_dimension=max_width, quality=70)
