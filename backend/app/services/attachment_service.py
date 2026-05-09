import base64
import logging
import mimetypes
import re
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

import aiofiles
import pandas as pd
from fastapi import HTTPException, UploadFile, status
from langchain_core.messages import HumanMessage
from pypdf import PdfReader

from app.ai.llm import get_chat_llm
from app.ai.rag.rag_service import process_and_index_pdf
from app.core.config import settings
from app.db.postgres import get_db_cursor
from app.schemas.chat import ChatAttachment

_CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".cs",
    ".go",
    ".rb",
    ".php",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".css",
    ".sql",
    ".md",
    ".sh",
    ".ps1",
}
_TEXT_EXTENSIONS = {".txt", ".log", ".rst"}
_TABLE_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls"}
_PDF_EXTENSIONS = {".pdf"}
_MAX_IMAGE_EXTRACTION_BYTES = 4 * 1024 * 1024
_MAX_VIDEO_ANALYSIS_FRAMES = 8
_MIN_VIDEO_FRAME_GAP_SECONDS = 2.0
_MAX_VIDEO_FRAME_WIDTH = 960
_VIDEO_JPEG_QUALITY = 75

logger = logging.getLogger(__name__)


def _attachment_from_row(row: dict) -> ChatAttachment:
    return ChatAttachment(
        id=str(row["id"]),
        thread_id=str(row["thread_id"]),
        message_id=str(row["message_id"]) if row["message_id"] else None,
        original_filename=row["original_filename"],
        stored_filename=row["stored_filename"],
        storage_path=row["storage_path"],
        public_url=row["public_url"],
        image_url=row.get("image_url"),
        prompt_used=row.get("prompt_used"),
        mime_type=row["mime_type"],
        file_size=int(row["file_size"]),
        attachment_type=row["attachment_type"],
        created_at=row["created_at"],
    )


def _upload_root() -> Path:
    root = Path(settings.UPLOAD_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _assert_thread_owner(user_id: str, thread_id: str) -> None:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            select 1
            from public.chat_threads
            where id = %s and user_id = %s
            limit 1
            """,
            (thread_id, user_id),
        )
        row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")


def _sanitize_filename(filename: str) -> str:
    name = Path(filename or "upload").name
    return re.sub(r"[^A-Za-z0-9._-]", "_", name) or "upload"


def _infer_attachment_type(filename: str, mime_type: str) -> str:
    extension = Path(filename).suffix.lower()
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    if mime_type == "application/pdf" or extension in _PDF_EXTENSIONS:
        return "pdf"
    if mime_type in {"text/csv", "application/vnd.ms-excel"} or extension in _TABLE_EXTENSIONS:
        return "table"
    if extension in _CODE_EXTENSIONS:
        return "code"
    if mime_type.startswith("text/") or extension in _TEXT_EXTENSIONS:
        return "text"
    return "other"


def _validate_file(filename: str, mime_type: str, size: int) -> str:
    if size <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{filename}: empty files are not allowed")

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{filename}: file exceeds {settings.MAX_UPLOAD_MB} MB limit",
        )

    attachment_type = _infer_attachment_type(filename, mime_type)
    if attachment_type == "other":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{filename}: unsupported file type",
        )
    return attachment_type


async def upload_attachments(user_id: str, thread_id: str, files: list[UploadFile]) -> list[ChatAttachment]:
    _assert_thread_owner(user_id, thread_id)
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files were uploaded")

    upload_root = _upload_root()
    thread_dir = upload_root / user_id / thread_id
    thread_dir.mkdir(parents=True, exist_ok=True)

    attachments: list[ChatAttachment] = []
    for file in files:
        if not file.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is missing a filename")

        original_filename = _sanitize_filename(file.filename)
        mime_type = file.content_type or mimetypes.guess_type(original_filename)[0] or "application/octet-stream"
        payload = await file.read()
        attachment_type = _validate_file(original_filename, mime_type, len(payload))

        attachment_id = str(uuid4())
        extension = Path(original_filename).suffix.lower()
        stored_filename = f"{attachment_id}{extension}"
        relative_path = Path(user_id) / thread_id / stored_filename
        absolute_path = upload_root / relative_path

        async with aiofiles.open(absolute_path, "wb") as out_file:
            await out_file.write(payload)

        public_path = f"/uploads/{relative_path.as_posix()}"
        public_url = f"{settings.API_BASE_URL.rstrip('/')}{public_path}"

        with get_db_cursor() as cursor:
            cursor.execute(
                """
                insert into public.chat_attachments(
                    id,
                    user_id,
                    thread_id,
                    message_id,
                    original_filename,
                    file_name,
                    stored_filename,
                    stored_path,
                    storage_path,
                    public_url,
                    image_url,
                    prompt_used,
                    mime_type,
                    file_size,
                    size_bytes,
                    attachment_type
                )
                values (%s, %s, %s, null, %s, %s, %s, %s, %s, %s, null, null, %s, %s, %s, %s)
                returning
                    id,
                    thread_id,
                    message_id,
                    original_filename,
                    stored_filename,
                    storage_path,
                    public_url,
                    image_url,
                    prompt_used,
                    mime_type,
                    file_size,
                    attachment_type,
                    created_at
                """,
                (
                    attachment_id,
                    user_id,
                    thread_id,
                    original_filename,
                    original_filename,
                    stored_filename,
                    relative_path.as_posix(),
                    relative_path.as_posix(),
                    public_url,
                    mime_type,
                    len(payload),
                    len(payload),
                    attachment_type,
                ),
            )
            row = cursor.fetchone()
        attachment = _attachment_from_row(row)
        attachments.append(attachment)

        # Index PDF in RAG system if it's a PDF file
        if attachment.attachment_type == "pdf":
            try:
                result = process_and_index_pdf(
                    user_id=user_id,
                    thread_id=thread_id,
                    attachment_id=attachment.id,
                    original_filename=attachment.original_filename,
                    storage_path=attachment.storage_path,
                )
                if result.get("success"):
                    logger.info(
                        "Successfully indexed PDF: %s (%d chunks)",
                        attachment.original_filename,
                        result.get("chunks_indexed", 0),
                    )
                else:
                    logger.warning(
                        "Failed to index PDF: %s - %s",
                        attachment.original_filename,
                        result.get("error"),
                    )
            except Exception as e:
                logger.exception(
                    "Error indexing PDF for attachment_id=%s",
                    attachment.id,
                )

    return attachments


def link_attachments_to_message(
    user_id: str,
    thread_id: str,
    message_id: str,
    attachment_ids: list[str],
) -> list[ChatAttachment]:
    if not attachment_ids:
        return []

    _assert_thread_owner(user_id, thread_id)
    unique_attachment_ids = list(dict.fromkeys(attachment_ids))
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            select id
            from public.chat_attachments
            where id = any(%s)
              and user_id = %s
              and thread_id = %s
              and message_id is null
            """,
            (unique_attachment_ids, user_id, thread_id),
        )
        rows = cursor.fetchall()

        if len(rows) != len(unique_attachment_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more attachments are invalid or already linked",
            )

        cursor.execute(
            """
            update public.chat_attachments
            set message_id = %s
            where id = any(%s)
              and user_id = %s
              and thread_id = %s
            """,
            (message_id, unique_attachment_ids, user_id, thread_id),
        )

        cursor.execute(
            """
            select
                id,
                thread_id,
                message_id,
                original_filename,
                stored_filename,
                storage_path,
                public_url,
                image_url,
                prompt_used,
                mime_type,
                file_size,
                attachment_type,
                created_at
            from public.chat_attachments
            where id = any(%s)
            order by created_at asc
            """,
            (unique_attachment_ids,),
        )
        linked = cursor.fetchall()

    return [_attachment_from_row(row) for row in linked]


def get_message_attachments(user_id: str, thread_id: str) -> dict[str, list[ChatAttachment]]:
    _assert_thread_owner(user_id, thread_id)
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            select
                id,
                thread_id,
                message_id,
                original_filename,
                stored_filename,
                storage_path,
                public_url,
                image_url,
                prompt_used,
                mime_type,
                file_size,
                attachment_type,
                created_at
            from public.chat_attachments
            where user_id = %s
              and thread_id = %s
              and message_id is not null
            order by created_at asc
            """,
            (user_id, thread_id),
        )
        rows = cursor.fetchall()

    attachments_by_message: dict[str, list[ChatAttachment]] = defaultdict(list)
    for row in rows:
        attachment = _attachment_from_row(row)
        if attachment.message_id:
            attachments_by_message[attachment.message_id].append(attachment)
    return dict(attachments_by_message)


def _resolve_absolute_path(storage_path: str) -> Path:
    return _upload_root() / storage_path


def create_generated_image_attachment(
    user_id: str,
    thread_id: str,
    message_id: str,
    prompt_used: str,
    image_bytes: bytes,
    mime_type: str,
    source_url: str | None = None,
) -> ChatAttachment:
    _assert_thread_owner(user_id, thread_id)

    upload_root = _upload_root()
    thread_dir = upload_root / user_id / thread_id
    thread_dir.mkdir(parents=True, exist_ok=True)

    attachment_id = str(uuid4())
    extension = mimetypes.guess_extension(mime_type) or ".png"
    if extension == ".jpe":
        extension = ".jpg"
    stored_filename = f"{attachment_id}{extension}"
    original_filename = f"generated_{attachment_id[:8]}{extension}"
    relative_path = Path(user_id) / thread_id / stored_filename
    absolute_path = upload_root / relative_path
    absolute_path.write_bytes(image_bytes)

    public_path = f"/uploads/{relative_path.as_posix()}"
    public_url = f"{settings.API_BASE_URL.rstrip('/')}{public_path}"
    image_url = source_url or public_url

    with get_db_cursor() as cursor:
        cursor.execute(
            """
            insert into public.chat_attachments(
                id,
                user_id,
                thread_id,
                message_id,
                original_filename,
                file_name,
                stored_filename,
                stored_path,
                storage_path,
                public_url,
                image_url,
                prompt_used,
                mime_type,
                file_size,
                size_bytes,
                attachment_type
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            returning
                id,
                thread_id,
                message_id,
                original_filename,
                stored_filename,
                storage_path,
                public_url,
                image_url,
                prompt_used,
                mime_type,
                file_size,
                attachment_type,
                created_at
            """,
            (
                attachment_id,
                user_id,
                thread_id,
                message_id,
                original_filename,
                original_filename,
                stored_filename,
                relative_path.as_posix(),
                relative_path.as_posix(),
                public_url,
                image_url,
                prompt_used,
                mime_type,
                len(image_bytes),
                len(image_bytes),
                "generated_image",
            ),
        )
        row = cursor.fetchone()

    return _attachment_from_row(row)


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def _extract_table_summary(path: Path, attachment: ChatAttachment) -> str:
    suffix = Path(attachment.original_filename).suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(path)
    elif suffix == ".tsv":
        frame = pd.read_csv(path, sep="\t")
    else:
        frame = pd.read_csv(path)

    sample = frame.head(10).fillna("")
    preview = sample.to_csv(index=False)
    return (
        f"Rows: {len(frame)}\n"
        f"Columns: {', '.join(str(col) for col in frame.columns)}\n"
        f"Preview:\n{preview}"
    )


def _llm_response_to_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text_value = item.get("text")
                if isinstance(text_value, str):
                    parts.append(text_value)
        return "\n".join(part.strip() for part in parts if part and part.strip()).strip()
    return ""


def _extract_image_text_with_llm(path: Path, attachment: ChatAttachment) -> str:
    try:
        payload = path.read_bytes()
        if len(payload) > _MAX_IMAGE_EXTRACTION_BYTES:
            return (
                f"Filename: {attachment.original_filename}\n"
                f"Type: {attachment.attachment_type}\n"
                f"MIME: {attachment.mime_type}\n"
                f"Size: {attachment.file_size} bytes\n"
                "Image content extraction skipped because file is too large for OCR context."
            )

        mime = attachment.mime_type if attachment.mime_type.startswith("image/") else "image/png"
        encoded = base64.b64encode(payload).decode("ascii")
        data_url = f"data:{mime};base64,{encoded}"

        prompt = (
            "Extract all readable text from this image and summarize important visual details. "
            "If there is tabular data, provide a compact row/column summary. "
            "Return plain text only."
        )
        llm = get_chat_llm()
        response = llm.invoke(
            [
                HumanMessage(
                    content=[
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ]
                )
            ]
        )
        extracted = _llm_response_to_text(response.content)
        if extracted:
            return extracted[:12000]
    except Exception:
        logger.exception("Image extraction via LLM failed for %s", attachment.original_filename)

    return (
        f"Filename: {attachment.original_filename}\n"
        f"Type: {attachment.attachment_type}\n"
        f"MIME: {attachment.mime_type}\n"
        f"Size: {attachment.file_size} bytes\n"
        "Image content extraction failed; using metadata only."
    )


def _select_evenly_spaced_indices(total: int, limit: int) -> list[int]:
    if total <= 0:
        return []
    if total <= limit:
        return list(range(total))
    step = (total - 1) / float(limit - 1)
    indices = [int(round(i * step)) for i in range(limit)]
    return sorted(set(min(total - 1, max(0, idx)) for idx in indices))


def _extract_video_frame_data_urls(path: Path) -> tuple[list[str], float | None, int | None]:
    try:
        import cv2
    except Exception:
        logger.exception("OpenCV import failed while processing video: %s", path.name)
        return [], None, None

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return [], None, None

    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration_seconds = (frame_count / fps) if fps > 0 and frame_count > 0 else None

        if frame_count <= 0:
            return [], duration_seconds, frame_count

        if fps > 0:
            min_gap = max(1, int(fps * _MIN_VIDEO_FRAME_GAP_SECONDS))
        else:
            min_gap = 1

        candidate_indices = list(range(0, frame_count, min_gap))
        sample_indices = _select_evenly_spaced_indices(len(candidate_indices), _MAX_VIDEO_ANALYSIS_FRAMES)
        frame_indices = [candidate_indices[idx] for idx in sample_indices] if candidate_indices else []

        data_urls: list[str] = []
        for frame_idx in frame_indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue

            height, width = frame.shape[:2]
            if width > _MAX_VIDEO_FRAME_WIDTH:
                scale = _MAX_VIDEO_FRAME_WIDTH / float(width)
                target_size = (_MAX_VIDEO_FRAME_WIDTH, max(1, int(height * scale)))
                frame = cv2.resize(frame, target_size, interpolation=cv2.INTER_AREA)

            ok_enc, encoded = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), _VIDEO_JPEG_QUALITY],
            )
            if not ok_enc:
                continue

            b64 = base64.b64encode(encoded.tobytes()).decode("ascii")
            data_urls.append(f"data:image/jpeg;base64,{b64}")

        return data_urls, duration_seconds, frame_count
    finally:
        capture.release()


def _extract_video_text_with_llm(path: Path, attachment: ChatAttachment) -> str:
    data_urls, duration_seconds, frame_count = _extract_video_frame_data_urls(path)
    if not data_urls:
        return (
            f"Filename: {attachment.original_filename}\n"
            f"Type: {attachment.attachment_type}\n"
            f"MIME: {attachment.mime_type}\n"
            f"Size: {attachment.file_size} bytes\n"
            "Video content extraction failed; using metadata only."
        )

    try:
        duration_display = f"{duration_seconds:.1f}s" if duration_seconds is not None else "unknown"
        frame_count_display = str(frame_count) if frame_count is not None else "unknown"
        prompt = (
            "Analyze this video using the provided sampled frames. "
            "Extract visible text exactly where possible and summarize important events, objects, scenes, and actions in order. "
            "If tables/charts appear, summarize key values. "
            "Return plain text only with concise bullet points.\n"
            f"Video filename: {attachment.original_filename}\n"
            f"Video duration: {duration_display}\n"
            f"Frame count: {frame_count_display}\n"
            f"Sampled frames: {len(data_urls)}"
        )

        content: list[dict] = [{"type": "text", "text": prompt}]
        for url in data_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})

        llm = get_chat_llm()
        response = llm.invoke([HumanMessage(content=content)])
        extracted = _llm_response_to_text(response.content)
        if extracted:
            return extracted[:12000]
    except Exception:
        logger.exception("Video extraction via LLM failed for %s", attachment.original_filename)

    return (
        f"Filename: {attachment.original_filename}\n"
        f"Type: {attachment.attachment_type}\n"
        f"MIME: {attachment.mime_type}\n"
        f"Size: {attachment.file_size} bytes\n"
        "Video content extraction failed; using metadata only."
    )


def _extract_attachment_text(attachment: ChatAttachment) -> str:
    path = _resolve_absolute_path(attachment.storage_path)
    if not path.exists():
        return f"File missing on disk for {attachment.original_filename}."

    if attachment.attachment_type == "pdf":
        text = _extract_pdf_text(path)
    elif attachment.attachment_type == "table":
        text = _extract_table_summary(path, attachment)
    elif attachment.attachment_type in {"text", "code"}:
        text = _read_text_file(path)
    elif attachment.attachment_type == "image":
        text = _extract_image_text_with_llm(path, attachment)
    elif attachment.attachment_type == "video":
        text = _extract_video_text_with_llm(path, attachment)
    elif attachment.attachment_type == "generated_image":
        text = (
            f"Generated image URL: {attachment.public_url or attachment.image_url or 'unknown'}\n"
            f"Prompt used: {attachment.prompt_used or 'not available'}"
        )
    else:
        return f"Filename: {attachment.original_filename}\nUnsupported content extraction type."

    compact = text.strip()
    if not compact:
        return f"Filename: {attachment.original_filename}\nNo readable content extracted."
    return compact[:12000]


def build_attachment_context(attachments: list[ChatAttachment]) -> str:
    if not attachments:
        return "No attachment context."

    blocks: list[str] = []
    for attachment in attachments:
        blocks.append(
            "\n".join(
                [
                    f"Attachment: {attachment.original_filename}",
                    f"Type: {attachment.attachment_type}",
                    f"MIME: {attachment.mime_type}",
                    f"Content:\n{_extract_attachment_text(attachment)}",
                ]
            )
        )
    return "\n\n---\n\n".join(blocks)
