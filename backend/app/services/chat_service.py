import logging
from typing import AsyncIterator

from fastapi import HTTPException, status
from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.chains.chat_chain import stream_chat_response
from app.ai.llm import get_chat_llm
from app.ai.memory.conversation import build_message_history
from app.db.postgres import get_db_cursor
from app.schemas.chat import ChatMessage, ChatRequest, ChatThread, Message

logger = logging.getLogger(__name__)


def _thread_from_row(row: dict) -> ChatThread:
    return ChatThread(
        id=str(row["id"]),
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _message_from_row(row: dict) -> ChatMessage:
    return ChatMessage(
        id=str(row["id"]),
        thread_id=str(row["thread_id"]),
        role=row["role"],
        content=row["content"],
        created_at=row["created_at"],
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
            """,
            (thread_id, user_id),
        )
        data = cursor.fetchall()

    return [_message_from_row(item) for item in data]


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


def _save_message(thread_id: str, role: str, content: str) -> None:
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            insert into public.chat_messages(thread_id, role, content)
            values (%s, %s, %s)
            """,
            (thread_id, role, content),
        )


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


async def process_chat_stream(user_id: str, request: ChatRequest) -> AsyncIterator[str]:
    """
    Service layer — owns all business logic for a chat turn.
    Converts request history to LangChain messages and streams response chunks.
    """
    logger.info("Chat request received: message_len=%d", len(request.message))
    _assert_thread_owner(user_id, request.thread_id)

    existing_messages = get_thread_messages(user_id, request.thread_id)
    history_items = [Message(role=msg.role, content=msg.content) for msg in existing_messages]
    history = build_message_history(history_items)

    _save_message(request.thread_id, "user", request.message)
    if not existing_messages:
        title = await _generate_thread_title(request.message)
        _touch_thread(request.thread_id, title)

    assistant_response_parts: list[str] = []
    async for chunk in stream_chat_response(request.message, history):
        assistant_response_parts.append(chunk)
        yield chunk

    assistant_response = "".join(assistant_response_parts)
    _save_message(request.thread_id, "assistant", assistant_response)
    _touch_thread(request.thread_id)
    logger.info("Chat stream completed")
