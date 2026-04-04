import cloudinary
import cloudinary.uploader
from fastapi import UploadFile

from app.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)


async def upload_audio(file: UploadFile, subject_id: int) -> dict:
    """Upload an audio file to Cloudinary and return url + public_id."""
    contents = await file.read()
    result = cloudinary.uploader.upload(
        contents,
        resource_type="video",  # Cloudinary uses 'video' for audio files
        folder=f"scholarmetric/recordings/{subject_id}",
        use_filename=True,
        unique_filename=True,
    )
    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "duration": result.get("duration"),  # seconds, available for audio
    }


def delete_audio(public_id: str) -> None:
    cloudinary.uploader.destroy(public_id, resource_type="video")


async def upload_image(file: UploadFile, folder: str) -> dict:
    """Upload an image file to Cloudinary and return url + public_id."""
    ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
    ct = (file.content_type or "").split(";")[0].strip().lower()
    if ct not in ALLOWED_IMAGE_TYPES:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, and WebP images are allowed")
    contents = await file.read()
    result = cloudinary.uploader.upload(
        contents,
        resource_type="image",
        folder=folder,
        use_filename=True,
        unique_filename=True,
        transformation=[{"width": 400, "height": 400, "crop": "fill"}],
    )
    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
    }
