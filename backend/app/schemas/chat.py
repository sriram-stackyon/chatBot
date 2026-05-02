from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    thread_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=10_000)
    history: list[Message] = Field(default_factory=list)


class ChatResponse(BaseModel):
    content: str
    role: str = "assistant"


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


class ChatThread(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessage(BaseModel):
    id: str
    thread_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class CreateThreadRequest(BaseModel):
    title: str = Field(default="New Chat", min_length=1, max_length=120)


class UpdateThreadRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
