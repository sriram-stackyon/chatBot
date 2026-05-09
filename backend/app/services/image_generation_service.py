import base64
import logging
import urllib.request
from dataclasses import dataclass

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class GeneratedImageResult:
    image_bytes: bytes
    mime_type: str
    source_url: str | None


def _detect_mime_type(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
        return "image/gif"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _download_image(url: str) -> tuple[bytes, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
        content_type = response.headers.get("Content-Type")
    return payload, content_type


def _build_openai_client() -> OpenAI:
    return OpenAI(
        base_url=settings.LITELLM_PROXY_URL,
        api_key=settings.LITELLM_API_KEY,
    )


def generate_image_from_prompt(user_prompt: str, user_email: str | None = None) -> GeneratedImageResult:
    client = _build_openai_client()
    response = client.images.generate(
        model=settings.IMAGE_GEN_MODEL,
        prompt=user_prompt,
        user=user_email or "unknown-user",
    )

    if not response.data:
        raise RuntimeError("Image generation returned no data")

    first = response.data[0]

    if getattr(first, "b64_json", None):
        image_bytes = base64.b64decode(first.b64_json)
        mime_type = _detect_mime_type(image_bytes)
        return GeneratedImageResult(
            image_bytes=image_bytes,
            mime_type=mime_type,
            source_url=getattr(first, "url", None),
        )

    url = getattr(first, "url", None)
    if url:
        image_bytes, response_mime = _download_image(url)
        mime_type = response_mime or _detect_mime_type(image_bytes)
        return GeneratedImageResult(image_bytes=image_bytes, mime_type=mime_type, source_url=url)

    raise RuntimeError("Image generation response missing both b64_json and url")
