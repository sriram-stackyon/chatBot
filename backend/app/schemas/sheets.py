from typing import Any

from pydantic import BaseModel, Field, field_validator


class SheetQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=10_000)
    source_type: str = Field(..., min_length=1, max_length=32)
    source_value: str = Field(..., min_length=1, max_length=4096)

    @field_validator("source_type")
    @classmethod
    def normalize_source_type(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("source_value")
    @classmethod
    def normalize_source_value(cls, value: str) -> str:
        return value.strip()


class SheetSourceMetadata(BaseModel):
    columns: list[str]
    row_count: int = Field(..., ge=0)


class SheetQueryResponse(BaseModel):
    content: str
    intermediate_steps: list[str] | None = None
    preview_rows: list[dict[str, object | None]] | None = None
    source_metadata: SheetSourceMetadata


class SheetPreviewRequest(BaseModel):
    source_type: str = Field(..., min_length=1, max_length=32)
    source_value: str = Field(..., min_length=1, max_length=4096)

    @field_validator("source_type")
    @classmethod
    def normalize_source_type(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("source_value")
    @classmethod
    def normalize_source_value(cls, value: str) -> str:
        return value.strip()


class SheetPreviewResponse(BaseModel):
    columns: list[str]
    row_count: int
    preview_rows: list[dict[str, Any]]
    source_name: str


class SheetUploadResponse(BaseModel):
    file_path: str
    source_type: str
    original_filename: str
