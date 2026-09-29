import mimetypes

from django.core.exceptions import ValidationError

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB


def validate_image_upload(file):
    if file is None:
        return
    if file.size > MAX_IMAGE_SIZE:
        raise ValidationError("Image size must not exceed 5MB.")
    mime, _ = mimetypes.guess_type(file.name)
    content_type = getattr(file, "content_type", None) or mime
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError("Only JPEG, PNG or WebP images are allowed.")
