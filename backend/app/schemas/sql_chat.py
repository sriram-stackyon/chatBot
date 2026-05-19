from pydantic import BaseModel, Field


class SQLChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10_000)


class SQLChatResponse(BaseModel):
    content: str
    intermediate_sql: str | None = None
