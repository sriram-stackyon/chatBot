import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.schemas.auth import AuthUser
from app.schemas.chat import (
    AttachmentUploadResponse,
    ChatMessage,
    ChatRequest,
    ChatThread,
    CreateThreadRequest,
    ErrorResponse,
    UpdateThreadRequest,
)
from app.services.attachment_service import upload_attachments
from app.services.chat_service import (
    create_thread,
    delete_thread,
    get_thread_messages,
    list_threads,
    process_chat_stream,
    rename_thread,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/chat/attachments/upload", response_model=AttachmentUploadResponse)
async def upload_chat_attachments(
    thread_id: str = Form(...),
    files: list[UploadFile] = File(...),
    current_user: AuthUser = Depends(get_current_user),
) -> AttachmentUploadResponse:
    attachments = await upload_attachments(current_user.user_id, thread_id, files)
    return AttachmentUploadResponse(attachments=attachments)


@router.get("/threads", response_model=list[ChatThread])
async def get_threads(current_user: AuthUser = Depends(get_current_user)) -> list[ChatThread]:
    return list_threads(current_user.user_id)


@router.post("/threads", response_model=ChatThread)
async def post_thread(
    request: CreateThreadRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> ChatThread:
    return create_thread(current_user.user_id, request.title)


@router.patch("/threads/{thread_id}", response_model=ChatThread)
async def patch_thread(
    thread_id: str,
    request: UpdateThreadRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> ChatThread:
    return rename_thread(current_user.user_id, thread_id, request.title)


@router.put("/threads/{thread_id}", response_model=ChatThread)
async def put_thread(
    thread_id: str,
    request: UpdateThreadRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> ChatThread:
    return rename_thread(current_user.user_id, thread_id, request.title)


@router.post("/threads/{thread_id}/rename", response_model=ChatThread)
async def post_rename_thread(
    thread_id: str,
    request: UpdateThreadRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> ChatThread:
    return rename_thread(current_user.user_id, thread_id, request.title)


@router.get("/threads/{thread_id}/messages", response_model=list[ChatMessage])
async def get_messages(
    thread_id: str,
    current_user: AuthUser = Depends(get_current_user),
) -> list[ChatMessage]:
    return get_thread_messages(current_user.user_id, thread_id)


@router.delete("/threads/{thread_id}", status_code=204)
async def delete_thread_route(
    thread_id: str,
    current_user: AuthUser = Depends(get_current_user),
) -> None:
    delete_thread(current_user.user_id, thread_id)


@router.post(
    "/chat",
    response_class=StreamingResponse,
    responses={500: {"model": ErrorResponse}},
    summary="Stream a chat response and persist both user and assistant messages",
)
async def chat(
    request: ChatRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> StreamingResponse:
    async def event_generator():
        try:
            async for chunk in process_chat_stream(current_user.user_id, request, current_user.email):
                safe_chunk = chunk.replace("\n", "\\n")
                yield f"data: {safe_chunk}\n\n"
            yield "data: [DONE]\n\n"
        except HTTPException as exc:
            logger.warning("Chat stream denied: %s", exc.detail)
            payload = json.dumps({"error": exc.detail, "status_code": exc.status_code})
            yield f"data: [ERROR] {payload}\n\n"
        except Exception as exc:
            logger.exception("Unhandled error during chat stream")
            payload = json.dumps({"error": str(exc)})
            yield f"data: [ERROR] {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
