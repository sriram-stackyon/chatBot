from __future__ import annotations

from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ResearchQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    max_papers: int = Field(12, ge=3, le=20)
    conversation_history: list[ConversationMessage] = Field(default_factory=list)
