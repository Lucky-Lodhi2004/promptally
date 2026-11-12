import os
import io
import uuid
import zipfile
import shutil
from pathlib import Path
from typing import List, Tuple, Optional
from fastapi import UploadFile, HTTPException, status
from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError

from backend.app.core.config import settings

# Upload Subdirectories
MEDIA_DIR = settings.UPLOAD_DIR / "media"
ARCHIVES_DIR = settings.PRIVATE_STORAGE_DIR / "archives"
COLLECTIONS_DIR = settings.UPLOAD_DIR / "collections"
AVATARS_DIR = settings.UPLOAD_DIR / "avatars"

for d in (MEDIA_DIR, ARCHIVES_DIR, COLLECTIONS_DIR, AVATARS_DIR):
    d.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_GIF_TYPES = {"image/gif"}
MAX_MEDIA_UPLOAD_SIZE = 15 * 1024 * 1024  # Bound source bytes before decoding.
MAX_PREVIEW_IMAGE_SIZE = 5 * 1024 * 1024
MAX_PREVIEW_GIF_SIZE = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_GIF_FRAMES = 500
MAX_GIF_TOTAL_PIXELS = 60_000_000
# Kept for avatar and collection-cover compatibility.
MAX_IMAGE_SIZE = MAX_MEDIA_UPLOAD_SIZE
MAX_ZIP_SIZE = 100 * 1024 * 1024   # 100 MB


async def read_upload_limited(upload_file: UploadFile, limit: int) -> bytes:
    """Never allocate an unbounded uploaded body, including rolled disk files."""
    chunks, total = [], 0
    while True:
        chunk = await upload_file.read(min(64 * 1024, limit - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(413, 'Uploaded file exceeds its size limit')
        chunks.append(chunk)
    return b''.join(chunks)


def _static_webp(content: bytes) -> bytes:
    """Decode a real image and produce a metadata-free WebP under 5 MiB."""
    with Image.open(io.BytesIO(content)) as source:
        if source.format not in {"JPEG", "PNG", "WEBP"} or getattr(source, "is_animated", False):
            raise ValueError("Expected a JPEG, PNG, or WebP image")
        if source.width * source.height > MAX_IMAGE_PIXELS:
            raise ValueError("Image dimensions are too large")
        source.load()
        image = ImageOps.exif_transpose(source)
        has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
        image = image.convert("RGBA" if has_alpha else "RGB")

    current = image
    for _ in range(8):
        smallest_result = b""
        for quality in (82, 62, 42):
            output = io.BytesIO()
            current.save(output, format="WEBP", quality=quality, method=4)
            result = output.getvalue()
            if len(result) <= MAX_PREVIEW_IMAGE_SIZE:
                return result
            smallest_result = result

        # Pixel count and encoded size are roughly proportional. Jump close to
        # the required dimensions instead of repeatedly shrinking by a fixed
        # percentage, while leaving headroom for encoder variance.
        ratio = (MAX_PREVIEW_IMAGE_SIZE / len(smallest_result)) ** 0.5
        scale = max(0.35, min(0.85, ratio * 0.92))
        width = max(1, round(current.width * scale))
        height = max(1, round(current.height * scale))
        if (width, height) == current.size:
            break
        current = current.resize((width, height), Image.Resampling.LANCZOS)
    raise ValueError("Image could not be compressed below 5 MiB")


def _validate_gif(content: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(content)) as image:
        if image.format != "GIF":
            raise ValueError("Expected a GIF image")
        frames = getattr(image, "n_frames", 1)
        if frames > MAX_GIF_FRAMES or image.width * image.height * frames > MAX_GIF_TOTAL_PIXELS:
            raise ValueError("GIF dimensions or frame count are too large")
        image.seek(frames - 1)  # Force frame parsing before accepting the file.
        image.load()
        return image.width, image.height


def _gif_bytes(content: bytes) -> bytes:
    """Validate and optimize an animated GIF, reducing dimensions/colors if needed."""
    _validate_gif(content)
    if len(content) <= MAX_PREVIEW_GIF_SIZE:
        return content

    # First preserve the original dimensions and frames while enabling GIF optimization.
    with Image.open(io.BytesIO(content)) as image:
        output = io.BytesIO()
        image.save(output, format="GIF", save_all=True, optimize=True,
                   loop=image.info.get("loop", 0), duration=image.info.get("duration", 100))
        if len(output.getvalue()) <= MAX_PREVIEW_GIF_SIZE:
            return output.getvalue()

    for scale in (0.85, 0.70, 0.55, 0.40, 0.30, 0.20):
        for colors in (256, 128, 64):
            with Image.open(io.BytesIO(content)) as image:
                frames = []
                durations = []
                size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
                loop = image.info.get("loop", 0)
                for frame in ImageSequence.Iterator(image):
                    durations.append(frame.info.get("duration", image.info.get("duration", 100)))
                    resized = frame.convert("RGBA").resize(size, Image.Resampling.LANCZOS)
                    frames.append(resized.convert("P", palette=Image.Palette.ADAPTIVE, colors=colors))
                output = io.BytesIO()
                frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:],
                               optimize=True, loop=loop, duration=durations, disposal=2)
                result = output.getvalue()
                if len(result) <= MAX_PREVIEW_GIF_SIZE:
                    return result
    raise ValueError("GIF could not be compressed below 10 MiB")

async def save_media_file(upload_file: UploadFile, is_gif: bool = False) -> str:
    """
    Validates and saves an uploaded image or animated GIF.
    Returns relative public URL path (e.g. /uploads/media/{uuid}.ext).
    """
    if not upload_file or not upload_file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided")

    content_type = upload_file.content_type or ""
    if is_gif:
        if content_type not in ALLOWED_GIF_TYPES and not upload_file.filename.lower().endswith(".gif"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file type. Expected GIF image.")
    else:
        if content_type not in ALLOWED_IMAGE_TYPES and not any(upload_file.filename.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image type. Expected PNG, JPG, or WEBP.")

    ext = Path(upload_file.filename).suffix.lower() or (".gif" if is_gif else ".png")
    if ext not in ({".gif"} if is_gif else {".jpg", ".jpeg", ".png", ".webp"}):
        raise HTTPException(400, "Unsupported preview extension")

    content = await read_upload_limited(upload_file, MAX_MEDIA_UPLOAD_SIZE)
    if not content:
        raise HTTPException(400, "Image file is empty")
    if len(content) > MAX_MEDIA_UPLOAD_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source image exceeds 15 MiB upload limit.")
    try:
        # Publishing cannot commit the media URL until encoding succeeds. Keep
        # this inline rather than queueing a Celery job that could leave an
        # asset pointing at an unfinished or failed preview.
        stored = _gif_bytes(content) if is_gif else _static_webp(content)
    except (UnidentifiedImageError, OSError, ValueError, EOFError):
        detail = "Invalid or unsafe GIF image." if is_gif else "Invalid or unsafe preview image."
        raise HTTPException(400, detail) from None

    final_ext = ".gif" if is_gif else ".webp"
    filename = f"{uuid.uuid4()}{final_ext}"
    dest_path = MEDIA_DIR / filename
    with open(dest_path, "wb") as f:
        f.write(stored)

    return f"/uploads/media/{filename}"

async def save_avatar_file(upload_file: UploadFile) -> str:
    """Saves user avatar and returns relative URL."""
    if not upload_file or not upload_file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No avatar file provided")

    ext = Path(upload_file.filename).suffix.lower() or ".png"
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        raise HTTPException(400, "Unsupported avatar extension")
    filename = f"avatar_{uuid.uuid4()}{ext}"
    dest_path = AVATARS_DIR / filename

    content = await read_upload_limited(upload_file, MAX_IMAGE_SIZE)
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Avatar file exceeds 15 MB limit.")

    with open(dest_path, "wb") as f:
        f.write(content)

    return f"/uploads/avatars/{filename}"

async def save_collection_cover(upload_file: UploadFile) -> str:
    """Saves collection cover image and returns relative URL."""
    if not upload_file or not upload_file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No cover file provided")

    ext = Path(upload_file.filename).suffix.lower() or ".png"
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        raise HTTPException(400, "Unsupported cover extension")
    filename = f"coll_{uuid.uuid4()}{ext}"
    dest_path = COLLECTIONS_DIR / filename

    content = await read_upload_limited(upload_file, MAX_IMAGE_SIZE)
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(400, "Cover exceeds 15 MB limit")
    with open(dest_path, "wb") as f:
        f.write(content)

    return f"/uploads/collections/{filename}"

async def save_folder_as_zip(files: List[UploadFile], base_name: str = "bundle") -> Tuple[str, str, int]:
    """
    Compresses multiple uploaded folder files into a single .zip archive.
    Returns: (archive_path, file_name, file_size_bytes)
    """
    if len(files) > settings.MAX_UPLOAD_FILES:
        raise HTTPException(413, 'Too many uploaded files')
    zip_filename = f"{base_name}_{uuid.uuid4().hex[:8]}.zip"
    dest_path = ARCHIVES_DIR / zip_filename

    total_bytes = 0
    try:
        with zipfile.ZipFile(dest_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for uf in files:
                if not uf.filename:
                    continue
                clean_rel_path = uf.filename.replace("\\", "/").lstrip("/")
                if ".." in Path(clean_rel_path).parts:
                    raise HTTPException(400, 'Unsafe archive path')
                with zf.open(clean_rel_path, 'w') as target:
                    while chunk := await uf.read(64 * 1024):
                        total_bytes += len(chunk)
                        if total_bytes > MAX_ZIP_SIZE:
                            raise HTTPException(413, 'Folder upload exceeds 100 MB limit')
                        target.write(chunk)
    except BaseException:
        dest_path.unlink(missing_ok=True)
        raise

    return str(dest_path), zip_filename, total_bytes

async def save_single_file(upload_file: UploadFile) -> Tuple[str, str, str, str]:
    """
    Saves a single uploaded code/prompt/config file.
    Returns: (archive_path, file_name, file_extension, text_content_preview)
    """
    ext = Path(upload_file.filename).suffix.lower() or ".txt"
    filename = Path(upload_file.filename.replace("\\", "/")).name
    dest_path = ARCHIVES_DIR / f"{uuid.uuid4()}_{filename}"

    content = await read_upload_limited(upload_file, MAX_ZIP_SIZE)
    if len(content) > MAX_ZIP_SIZE:
        raise HTTPException(400, "File exceeds 100 MB limit")
    with open(dest_path, "wb") as f:
        f.write(content)

    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        text_content = f"Binary file ({len(content)} bytes)"

    return str(dest_path), filename, ext, text_content

