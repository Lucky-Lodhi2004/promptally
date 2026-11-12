import asyncio
import io
import tempfile

from fastapi import UploadFile
from PIL import Image
from starlette.datastructures import Headers

from backend.app.services import storage


def image_bytes(fmt="PNG", size=(128, 128)):
    output = io.BytesIO()
    Image.effect_noise(size, 80).convert("RGB").save(output, format=fmt)
    return output.getvalue()


def animated_gif_bytes(size=(128, 128)):
    frames = [Image.effect_noise(size, noise).convert("RGB") for noise in (50, 70, 90)]
    output = io.BytesIO()
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=[80, 90, 100],
        loop=0,
    )
    return output.getvalue()


def upload_file(filename: str, content: bytes, content_type: str | None = None):
    file = tempfile.SpooledTemporaryFile(max_size=1024 * 1024)
    file.write(content)
    file.seek(0)
    headers = Headers({"content-type": content_type}) if content_type else None
    return UploadFile(filename=filename, file=file, headers=headers)


def test_preview_is_validated_reencoded_and_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path)
    monkeypatch.setattr(storage, "MAX_PREVIEW_IMAGE_SIZE", 1_000)
    upload = upload_file("preview.png", image_bytes())
    url = asyncio.run(storage.save_media_file(upload))
    saved = tmp_path / url.rsplit("/", 1)[-1]
    assert saved.suffix == ".webp"
    assert saved.stat().st_size <= 1_000
    with Image.open(saved) as image:
        assert image.format == "WEBP"


def test_fake_image_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path)
    upload = upload_file("preview.png", b"not an image")
    try:
        asyncio.run(storage.save_media_file(upload))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("fake image was accepted")


def test_gif_is_validated_and_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path)
    monkeypatch.setattr(storage, "MAX_PREVIEW_GIF_SIZE", 1_000)
    content = animated_gif_bytes()
    upload = upload_file("preview.gif", content, "image/gif")
    url = asyncio.run(storage.save_media_file(upload, is_gif=True))
    saved = tmp_path / url.rsplit("/", 1)[-1]
    assert saved.suffix == ".gif"
    assert saved.stat().st_size <= storage.MAX_PREVIEW_GIF_SIZE
    with Image.open(saved) as image:
        assert image.format == "GIF"
        assert image.n_frames == 3
