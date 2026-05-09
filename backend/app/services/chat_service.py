import logging
import re
from typing import AsyncIterator

from fastapi import HTTPException, status
from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.chains.chat_chain import stream_chat_response
from app.ai.llm import get_chat_llm
from app.ai.memory.conversation import format_history_for_prompt
from app.ai.rag.rag_service import retrieve_pdf_context
from app.db.postgres import get_db_cursor
from app.schemas.chat import ChatAttachment, ChatMessage, ChatRequest, ChatThread, Message
from app.services.attachment_service import (
    build_attachment_context,
    create_generated_image_attachment,
    get_message_attachments,
    link_attachments_to_message,
)
from app.services.image_generation_service import generate_image_from_prompt

logger = logging.getLogger(__name__)

_IMAGE_INTENT_PATTERN = re.compile(
    r"\b(generate|create|make|draw|design)\b.{0,40}\b(image|picture|photo|art|illustration|poster|logo|wallpaper)\b|\b(image|picture|photo)\b.{0,20}\b(of|for)\b",
    re.IGNORECASE,
)

_PROMPT_LOOKUP_PATTERN = re.compile(
    r"\b(?:what\s+(?:is|was)|tell\s+me|show\s+me)\b.*\b(?:my\s+)?(\d+)(?:st|nd|rd|th)?\s+prompt\b.*\b(?:i\s+(?:gave|sent)|of\s+mine)\b",
    re.IGNORECASE,
)

_ORDINAL_WORDS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}


def _extract_prompt_lookup_index(message: str) -> int | None:
    compact = " ".join(message.strip().lower().split())
    if not compact or "prompt" not in compact:
        return None

    match = _PROMPT_LOOKUP_PATTERN.search(compact)
    if match:
        try:
            value = int(match.group(1))
            return value if value > 0 else None
        except ValueError:
            return None

    if "i gave" not in compact and "i sent" not in compact and "of mine" not in compact:
        return None

    for word, value in _ORDINAL_WORDS.items():
        if f" {word} prompt" in f" {compact}":
            return value
    return None


def _get_nth_user_prompt(thread_id: str, user_id: str, index: int) -> str | None:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            select m.content
            from public.chat_messages m
            join public.chat_threads t on t.id = m.thread_id
            where m.thread_id = %s
              and t.user_id = %s
              and m.role = 'user'
            order by m.created_at asc
            offset %s
            limit 1
            """,
            (thread_id, user_id, index - 1),
        )
        row = cursor.fetchone()
    return row["content"] if row else None


def _ordinal_label(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _thread_from_row(row: dict) -> ChatThread:
    return ChatThread(
        id=str(row["id"]),
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _message_from_row(row: dict, attachments: list[ChatAttachment] | None = None) -> ChatMessage:
    return ChatMessage(
        id=str(row["id"]),
        thread_id=str(row["thread_id"]),
        role=row["role"],
        content=row["content"],
        created_at=row["created_at"],
        attachments=attachments or [],
    )


def list_threads(user_id: str) -> list[ChatThread]:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            select id, title, created_at, updated_at
            from public.chat_threads
            where user_id = %s
            order by updated_at desc
            """,
            (user_id,),
        )
        rows = cursor.fetchall()
    return [_thread_from_row(row) for row in rows]


def create_thread(user_id: str, title: str) -> ChatThread:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            insert into public.chat_threads(user_id, title)
            values (%s, %s)
            returning id, title, created_at, updated_at
            """,
            (user_id, title),
        )
        row = cursor.fetchone()
    return _thread_from_row(row)


def rename_thread(user_id: str, thread_id: str, title: str) -> ChatThread:
    _assert_thread_owner(user_id, thread_id)
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            update public.chat_threads
            set title = %s, updated_at = now()
            where id = %s and user_id = %s
            returning id, title, created_at, updated_at
            """,
            (title[:120], thread_id, user_id),
        )
        row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return _thread_from_row(row)


def get_thread_messages(user_id: str, thread_id: str) -> list[ChatMessage]:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            select m.id, m.thread_id, m.role, m.content, m.created_at
            from public.chat_messages m
            join public.chat_threads t on t.id = m.thread_id
            where m.thread_id = %s and t.user_id = %s
            order by m.created_at asc
            limit 1000
            """,
            (thread_id, user_id),
        )
        data = cursor.fetchall()

    attachments_by_message = get_message_attachments(user_id, thread_id)
    return [
        _message_from_row(item, attachments_by_message.get(str(item["id"]), []))
        for item in data
    ]


def get_recent_thread_memory(thread_id: str, user_id: str, limit: int = 5) -> list[Message]:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            select m.role, m.content
            from public.chat_messages m
            join public.chat_threads t on t.id = m.thread_id
            where m.thread_id = %s and t.user_id = %s
            order by m.created_at desc
            limit %s
            """,
            (thread_id, user_id, limit * 2),
        )
        rows = cursor.fetchall()
    return [Message(role=row["role"], content=row["content"]) for row in reversed(rows)]


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


def delete_thread(user_id: str, thread_id: str) -> None:
    _assert_thread_owner(user_id, thread_id)
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            delete from public.chat_threads
            where id = %s and user_id = %s
            """,
            (thread_id, user_id),
        )


def _save_message(thread_id: str, role: str, content: str) -> str:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            insert into public.chat_messages(thread_id, role, content)
            values (%s, %s, %s)
            returning id
            """,
            (thread_id, role, content),
        )
        row = cursor.fetchone()
    return str(row["id"])


def _touch_thread(thread_id: str, title: str | None = None) -> None:
    with get_db_cursor() as cursor:
        if title:
            cursor.execute(
                """
                update public.chat_threads
                set title = %s, updated_at = now()
                where id = %s
                """,
                (title[:120], thread_id),
            )
        else:
            cursor.execute(
                """
                update public.chat_threads
                set updated_at = now()
                where id = %s
                """,
                (thread_id,),
            )


def _fallback_thread_title(message: str) -> str:
    compact = " ".join(message.strip().split())
    if not compact:
        return "New Chat"
    return compact[:40]


def _is_image_generation_request(message: str) -> bool:
    compact = " ".join(message.strip().split())
    if not compact:
        return False
    return bool(_IMAGE_INTENT_PATTERN.search(compact))


async def _generate_thread_title(initial_message: str) -> str:
    fallback = _fallback_thread_title(initial_message)
    try:
        llm = get_chat_llm()
        response = await llm.ainvoke(
            [
                SystemMessage(
                    content=(
                        "Generate a concise chat thread title (max 6 words) for the user's first message. "
                        "Return only the title text with no quotes or punctuation at the end."
                    )
                ),
                HumanMessage(content=initial_message[:2000]),
            ]
        )
        raw_title = response.content if isinstance(response.content, str) else ""
        title = " ".join(raw_title.strip().split())
        if not title:
            return fallback
        return title[:120]
    except Exception:
        logger.exception("Thread title generation failed; using fallback")
        return fallback


async def process_chat_stream(user_id: str, request: ChatRequest, user_email: str | None = None) -> AsyncIterator[str]:
    logger.info(
        "Chat request received: message_len=%d attachment_count=%d",
        len(request.message),
        len(request.attachment_ids),
    )
    _assert_thread_owner(user_id, request.thread_id)

    prompt_lookup_index = _extract_prompt_lookup_index(request.message)
    if prompt_lookup_index is not None:
        user_message_id = _save_message(request.thread_id, "user", request.message)
        linked_attachments = link_attachments_to_message(
            user_id,
            request.thread_id,
            user_message_id,
            request.attachment_ids,
        )
        _ = linked_attachments  # Keep standard attachment-linking behavior for consistency.

        recalled_prompt = _get_nth_user_prompt(request.thread_id, user_id, prompt_lookup_index)
        if recalled_prompt is None:
            assistant_response = (
                f"I could not find your {_ordinal_label(prompt_lookup_index)} prompt in this thread yet. "
                "Please ask after you have sent enough prompts."
            )
        else:
            assistant_response = f"Your {_ordinal_label(prompt_lookup_index)} prompt was:\n\n{recalled_prompt}"

        _save_message(request.thread_id, "assistant", assistant_response)
        _touch_thread(request.thread_id)
        yield assistant_response
        return

    existing_messages = get_thread_messages(user_id, request.thread_id)
    is_first_message = not existing_messages

    memory_items = get_recent_thread_memory(request.thread_id, user_id, limit=5)
    history = format_history_for_prompt(memory_items)

    user_message_id = _save_message(request.thread_id, "user", request.message)
    linked_attachments = link_attachments_to_message(
        user_id,
        request.thread_id,
        user_message_id,
        request.attachment_ids,
    )
    attachment_context = build_attachment_context(linked_attachments)
    
    # Retrieve RAG context from indexed PDFs
    rag_context = retrieve_pdf_context(user_id, request.thread_id, request.message)
    if rag_context:
        if attachment_context == "No attachment context.":
            attachment_context = rag_context
        else:
            attachment_context = f"{attachment_context}\n\n---\n\n{rag_context}"

    if is_first_message:
        title = await _generate_thread_title(request.message)
        _touch_thread(request.thread_id, title)

    if _is_image_generation_request(request.message):
        yield "Generating image from your prompt...\n\n"
        try:
            generated = generate_image_from_prompt(request.message, user_email=user_email)

            assistant_message_id = _save_message(request.thread_id, "assistant", "")
            attachment = create_generated_image_attachment(
                user_id=user_id,
                thread_id=request.thread_id,
                message_id=assistant_message_id,
                prompt_used=request.message,
                image_bytes=generated.image_bytes,
                mime_type=generated.mime_type,
                source_url=generated.source_url,
            )

            assistant_response = (
                "Here is your generated image:\n\n"
                f"![Generated image]({attachment.public_url})\n\n"
                f"[Download image]({attachment.public_url})"
            )
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    update public.chat_messages
                    set content = %s
                    where id = %s
                    """,
                    (assistant_response, assistant_message_id),
                )

            _touch_thread(request.thread_id)
            yield assistant_response
            logger.info("Image generation completed for thread_id=%s", request.thread_id)
            return
        except Exception:
            logger.exception("Image generation failed for thread_id=%s", request.thread_id)
            failure = "I could not generate the image right now. Please try again in a moment."
            _save_message(request.thread_id, "assistant", failure)
            _touch_thread(request.thread_id)
            yield failure
            return

    assistant_response_parts: list[str] = []
    async for chunk in stream_chat_response(request.message, history, attachment_context):
        assistant_response_parts.append(chunk)
        yield chunk

    assistant_response = "".join(assistant_response_parts)
    _save_message(request.thread_id, "assistant", assistant_response)
    _touch_thread(request.thread_id)
    logger.info("Chat stream completed")
