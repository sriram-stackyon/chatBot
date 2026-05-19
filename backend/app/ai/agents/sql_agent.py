import logging
from typing import Any

from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI

from app.ai.rag.sql_security import validate_sql_query
from app.core.config import settings
from app.db.postgres import _build_sync_db_url

logger = logging.getLogger(__name__)


def _build_sql_generation_prefix(allowed_tables: list[str]) -> str:
    tables_csv = ", ".join(sorted(allowed_tables))
    return (
        "You are a secure read-only PostgreSQL assistant. "
        "Use ONLY these allowed tables: "
        f"{tables_csv}. "
        "When the request is safe and in scope, generate one safe SQL query, execute it, and return a concise "
        "user-facing answer based on the result rows. "
        "When the result contains multiple rows/columns, format it as a GitHub-flavored markdown table with headers. "
        "When the result is a single scalar value, return a concise sentence. "
        "Do not return SQL unless the user explicitly asks for SQL. "
        "When returning data, include the most relevant fields from the query result. "
        "If the request is out of scope or unsafe, return exactly: SQL_SECURITY_VIOLATION. "
        "Never use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE, COPY, EXECUTE, CALL, DO, "
        "comments, procedural SQL, UNION-based injection, or multiple statements. "
        "Queries must be a single statement that starts with SELECT or WITH."
    )


class GuardedSQLDatabase(SQLDatabase):
    """SQLDatabase that validates generated SQL before execution."""

    def __init__(self, *args: Any, allowed_tables: list[str], **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._allowed_tables = allowed_tables
        self._last_query: str | None = None

    @property
    def last_query(self) -> str | None:
        return self._last_query

    def _validate_and_track(self, command: str) -> None:
        validate_sql_query(command, self._allowed_tables)
        self._last_query = command.strip()

    def run(self, command: str, fetch: str = "all", include_columns: bool = False, **kwargs: Any) -> str:
        self._validate_and_track(command)
        return super().run(command, fetch=fetch, include_columns=include_columns, **kwargs)

    def run_no_throw(
        self,
        command: str,
        fetch: str = "all",
        include_columns: bool = False,
        **kwargs: Any,
    ) -> str:
        self._validate_and_track(command)
        return super().run_no_throw(command, fetch=fetch, include_columns=include_columns, **kwargs)


def create_scoped_sql_agent_executor() -> tuple[Any, GuardedSQLDatabase]:
    """Create a read-only SQL agent executor scoped to configured tables."""
    sync_db_url = _build_sync_db_url()
    allowed_tables = settings.SQL_AGENT_TABLES

    if not allowed_tables:
        raise RuntimeError("SQL_AGENT_TABLES must be configured before using SQL agent")

    database = GuardedSQLDatabase.from_uri(
        sync_db_url,
        include_tables=allowed_tables,
        sample_rows_in_table_info=2,
        allowed_tables=allowed_tables,
    )

    logger.info("SQL agent schema scope: tables=%s", ",".join(sorted(allowed_tables)))

    llm = ChatOpenAI(
        model="gpt-4o",
        openai_api_key=settings.LITELLM_API_KEY,
        openai_api_base=settings.LITELLM_PROXY_URL,
        temperature=0,
        max_tokens=settings.LLM_MAX_TOKENS,
    )

    executor = create_sql_agent(
        llm=llm,
        db=database,
        agent_type="openai-tools",
        verbose=False,
        return_intermediate_steps=True,
        handle_parsing_errors=True,
        prefix=_build_sql_generation_prefix(allowed_tables),
    )

    return executor, database
