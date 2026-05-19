import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import get_current_user
from app.core.config import settings
from app.schemas.auth import AuthUser
from app.schemas.sheets import (
    SheetPreviewRequest,
    SheetPreviewResponse,
    SheetQueryRequest,
    SheetQueryResponse,
    SheetUploadResponse,
)
from app.services.sheets_query_service import (
    SheetsQueryError,
    build_preview_rows,
    get_source_name,
    load_dataframe_for_source,
    run_sheets_query,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sheets"])

_SHEET_UPLOAD_DIR = Path("uploads") / "sheets"
_ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post("/sheets/query", response_model=SheetQueryResponse)
async def query_sheets(
    request: SheetQueryRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> SheetQueryResponse:
    try:
        return await run_sheets_query(request=request, user_email=current_user.email)
    except SheetsQueryError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.code, "message": exc.message},
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected sheets API error")
        raise HTTPException(
            status_code=500,
            detail={"error": "unexpected", "message": str(exc)},
        ) from exc


@router.post("/sheets/preview", response_model=SheetPreviewResponse)
async def preview_sheet(
    request: SheetPreviewRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> SheetPreviewResponse:
    try:
        df, metadata = load_dataframe_for_source(
            source_type=request.source_type,
            source_value=request.source_value,
        )
        return SheetPreviewResponse(
            columns=metadata.columns,
            row_count=metadata.row_count,
            preview_rows=build_preview_rows(df),
            source_name=get_source_name(request.source_type, request.source_value),
        )
    except SheetsQueryError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": exc.code, "message": exc.message},
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected sheets preview error")
        raise HTTPException(
            status_code=500,
            detail={"error": "unexpected", "message": str(exc)},
        ) from exc


@router.post("/sheets/upload", response_model=SheetUploadResponse)
async def upload_sheet_file(
    file: UploadFile = File(...),
    current_user: AuthUser = Depends(get_current_user),
) -> SheetUploadResponse:
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail={"error": "invalid_file", "message": "Only CSV and XLSX files are allowed"})

    dest_dir = _SHEET_UPLOAD_DIR / current_user.user_id / uuid.uuid4().hex
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename

    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail={"error": "file_too_large", "message": "File exceeds 20 MB limit"})

    dest_path.write_bytes(content)

    source_type = "xlsx" if ext == ".xlsx" else "csv"
    return SheetUploadResponse(
        file_path=str(dest_path),
        source_type=source_type,
        original_filename=filename,
    )
