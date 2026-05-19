import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import parse_qs, urlparse

import gspread
import pandas as pd
from gspread.exceptions import APIError, GSpreadException, SpreadsheetNotFound
from openai import OpenAIError

from app.ai.agents.sheets_agent import create_sheets_dataframe_agent
from app.core.config import settings
from app.schemas.sheets import SheetQueryRequest, SheetQueryResponse, SheetSourceMetadata

logger = logging.getLogger(__name__)

_ALLOWED_SOURCE_TYPES: frozenset[str] = frozenset({"csv", "xlsx", "gsheet"})
_SPREADSHEET_ID_PATTERN = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")
_PREVIEW_ROWS_LIMIT = 5


@dataclass(frozen=True)
class SheetsQueryError(Exception):
    code: str
    message: str
    status_code: int


class InvalidSourceError(SheetsQueryError):
    def __init__(self, message: str):
        super().__init__(code="invalid_source", message=message, status_code=400)


class SourceFileNotFoundError(SheetsQueryError):
    def __init__(self, message: str):
        super().__init__(code="file_not_found", message=message, status_code=404)


class GoogleSheetAccessError(SheetsQueryError):
    def __init__(self, message: str):
        super().__init__(code="google_auth_share_failure", message=message, status_code=403)


class LLMInvocationError(SheetsQueryError):
    def __init__(self, message: str):
        super().__init__(code="llm_error", message=message, status_code=502)


class UnexpectedSheetsError(SheetsQueryError):
    def __init__(self, message: str):
        super().__init__(code="unexpected", message=message, status_code=500)


def _extract_spreadsheet_id(source_value: str) -> str:
    source_value_clean = source_value.strip()
    parsed = urlparse(source_value_clean)

    if parsed.scheme and parsed.netloc:
        match = _SPREADSHEET_ID_PATTERN.search(parsed.path)
        if match:
            return match.group(1)

        query = parse_qs(parsed.query)
        key_values = query.get("key")
        if key_values and key_values[0].strip():
            return key_values[0].strip()

        raise InvalidSourceError("Google Sheet URL is invalid or missing spreadsheet id")

    if re.fullmatch(r"[a-zA-Z0-9-_]+", source_value_clean):
        return source_value_clean

    raise InvalidSourceError("Google Sheet source_value must be a valid URL or spreadsheet id")


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = [str(column).strip() for column in normalized.columns]
    normalized = normalized.dropna(how="all").reset_index(drop=True)

    if settings.SHEETS_MAX_ROWS > 0 and len(normalized) > settings.SHEETS_MAX_ROWS:
        normalized = normalized.head(settings.SHEETS_MAX_ROWS).copy()

    return normalized


def _load_csv_dataframe(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _load_xlsx_dataframe(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, engine="openpyxl")


def _load_gsheet_dataframe(source_value: str) -> pd.DataFrame:
    if not settings.GOOGLE_SERVICE_ACCOUNT_JSON.strip():
        raise GoogleSheetAccessError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not configured for Google Sheets access"
        )

    try:
        credentials = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
        if not isinstance(credentials, dict):
            raise ValueError("Service account JSON must be an object")
    except (json.JSONDecodeError, ValueError) as exc:
        raise GoogleSheetAccessError("GOOGLE_SERVICE_ACCOUNT_JSON is invalid JSON") from exc

    spreadsheet_id = _extract_spreadsheet_id(source_value)

    try:
        client = gspread.service_account_from_dict(credentials)
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.get_worksheet(0)
        if worksheet is None:
            raise GoogleSheetAccessError("Google Sheet has no worksheets")
        records = worksheet.get_all_records()
    except SpreadsheetNotFound as exc:
        raise GoogleSheetAccessError(
            "Google Sheet not found or not shared with service account"
        ) from exc
    except (APIError, GSpreadException, PermissionError) as exc:
        raise GoogleSheetAccessError(str(exc)) from exc

    return pd.DataFrame(records)


def _build_source_metadata(df: pd.DataFrame) -> SheetSourceMetadata:
    return SheetSourceMetadata(columns=[str(column) for column in df.columns], row_count=len(df))


def _to_json_compatible(value: object) -> object | None:
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if pd.isna(value):
        return None

    return str(value)


def _build_preview_rows(df: pd.DataFrame) -> list[dict[str, object | None]] | None:
    if df.empty:
        return None

    preview_df = df.head(_PREVIEW_ROWS_LIMIT)
    rows: list[dict[str, object | None]] = []

    for record in preview_df.to_dict(orient="records"):
        typed_record: dict[str, object | None] = {
            str(column): _to_json_compatible(cell_value)
            for column, cell_value in record.items()
        }
        rows.append(typed_record)

    return rows


def _extract_intermediate_steps(result: Mapping[str, object]) -> list[str] | None:
    raw_steps = result.get("intermediate_steps")
    if not isinstance(raw_steps, list):
        return None

    extracted: list[str] = []
    for step in raw_steps:
        extracted.append(str(step))

    return extracted or None


def get_source_name(source_type: str, source_value: str) -> str:
    """Return a human-readable name for the data source."""
    if source_type == "gsheet":
        try:
            sid = _extract_spreadsheet_id(source_value)
            return f"Google Sheet ({sid[:12]}…)"
        except Exception:
            return "Google Sheet"
    return Path(source_value).name


def build_preview_rows(df: pd.DataFrame) -> list[dict[str, object | None]]:
    """Public alias for the preview builder."""
    return _build_preview_rows(df) or []


def load_dataframe_for_source(source_type: str, source_value: str) -> tuple[pd.DataFrame, SheetSourceMetadata]:
    normalized_source_type = source_type.strip().lower()
    source_value_clean = source_value.strip()

    if normalized_source_type not in _ALLOWED_SOURCE_TYPES:
        raise InvalidSourceError(
            f"source_type must be one of: {', '.join(sorted(_ALLOWED_SOURCE_TYPES))}"
        )

    if normalized_source_type in {"csv", "xlsx"}:
        file_path = Path(source_value_clean)
        if not file_path.exists() or not file_path.is_file():
            raise SourceFileNotFoundError(f"Source file not found: {source_value_clean}")

        if normalized_source_type == "csv":
            loaded = _load_csv_dataframe(file_path)
        else:
            loaded = _load_xlsx_dataframe(file_path)
    else:
        loaded = _load_gsheet_dataframe(source_value_clean)

    normalized = _normalize_dataframe(loaded)
    return normalized, _build_source_metadata(normalized)


def validate_google_sheet_has_rows(source_value: str) -> bool:
    df = _normalize_dataframe(_load_gsheet_dataframe(source_value))
    if df.empty:
        raise InvalidSourceError("Google Sheet has zero non-empty rows")
    return True


async def run_sheets_query(
    request: SheetQueryRequest,
    user_email: str | None,
) -> SheetQueryResponse:
    try:
        df, source_metadata = load_dataframe_for_source(
            source_type=request.source_type,
            source_value=request.source_value,
        )
    except SheetsQueryError:
        raise
    except Exception as exc:
        logger.exception("Unexpected source loading error")
        raise UnexpectedSheetsError(str(exc)) from exc

    agent = create_sheets_dataframe_agent(df)

    invoke_payload: dict[str, str] = {"input": request.question}
    invoke_config: dict[str, dict[str, str]] = {}
    if user_email:
        invoke_config = {"metadata": {"user_email": user_email}}

    try:
        result = await asyncio.to_thread(agent.invoke, invoke_payload, invoke_config)
    except OpenAIError as exc:
        logger.exception("Sheets query LLM error")
        raise LLMInvocationError(str(exc)) from exc
    except Exception as exc:
        logger.exception("Sheets query unexpected invoke error")
        raise UnexpectedSheetsError(str(exc)) from exc

    output = result.get("output") if isinstance(result, dict) else result
    content = output if isinstance(output, str) else str(output)

    return SheetQueryResponse(
        content=content.strip(),
        intermediate_steps=_extract_intermediate_steps(result if isinstance(result, dict) else {}),
        preview_rows=_build_preview_rows(df),
        source_metadata=source_metadata,
    )
