import asyncio
import logging
from typing import Any

from openai import OpenAIError

from app.ai.agents.sql_agent import create_scoped_sql_agent_executor
from app.ai.rag.sql_security import (
    SQLSecurityError,
    extract_tables,
    validate_sql_query,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


def _extract_sql_from_steps(steps: list[Any]) -> str | None:
    for step in steps:
        if not isinstance(step, tuple) or len(step) == 0:
            continue

        action = step[0]
        tool_input = getattr(action, "tool_input", None)

        if isinstance(tool_input, dict):
            for key in ("query", "sql", "input"):
                value = tool_input.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        elif isinstance(tool_input, str) and tool_input.strip():
            return tool_input.strip()

    return None


async def run_sql_query(question: str, user_email: str | None) -> dict[str, str | None]:
    if not user_email:
        raise ValueError("Authenticated user email is required for SQL cost attribution")

    executor, guarded_db = create_scoped_sql_agent_executor()

    try:
        result = await asyncio.to_thread(
            executor.invoke,
            {"input": question},
            {"metadata": {"user_email": user_email}},
        )
    except OpenAIError:
        logger.exception("SQL agent OpenAI error")
        raise

    intermediate_steps = result.get("intermediate_steps", [])
    generated_sql = _extract_sql_from_steps(intermediate_steps) or guarded_db.last_query

    if generated_sql:
        validate_sql_query(generated_sql, settings.SQL_AGENT_TABLES)
        referenced_tables = extract_tables(generated_sql)
        logger.info("SQL agent generated query: %s", generated_sql)
        logger.info("SQL agent referenced tables: %s", ",".join(referenced_tables))

    output_text = result.get("output")
    content = output_text if isinstance(output_text, str) else str(output_text)

    return {
        "content": content,
        "intermediate_sql": generated_sql,
    }


async def run_sql_query_safe(question: str, user_email: str | None) -> dict[str, str | None]:
    try:
        result = await run_sql_query(question=question, user_email=user_email)
        # Include the SQL query and user-facing content in the response
        content = result.get("content")
        sql_query = result.get("intermediate_sql")

        # Format the response in a tabular form
        formatted_response = f"<table><tr><th>SQL Query</th><th>Result</th></tr>"
        formatted_response += f"<tr><td>{sql_query}</td><td>{content}</td></tr></table>"

        return {
            "content": content,
            "intermediate_sql": sql_query,
            "sql_query": sql_query,  # Adding SQL query explicitly
            "response": formatted_response,  # Tabular formatted response
        }
    except SQLSecurityError as exc:
        logger.warning("SQL security policy blocked query: %s", str(exc))
        allowed_tables = ", ".join(sorted(settings.SQL_AGENT_TABLES))
        return {
            "content": (
                "I could not run that query because it violates SQL security policy. "
                f"Reason: {str(exc)}. "
                f"Allowed tables: {allowed_tables}."
            ),
            "intermediate_sql": None,
            "sql_query": None,
            "response": (
                "<table><tr><th>SQL Query</th><th>Result</th></tr>"
                "<tr><td>BLOCKED_BY_SQL_SECURITY</td><td>"
                "I could not run that query because it violates SQL security policy. "
                f"Reason: {str(exc)}. Allowed tables: {allowed_tables}."
                "</td></tr></table>"
            ),
        }
    except ValueError as exc:
        logger.warning("SQL query rejected: %s", str(exc))
        return {
            "content": "SQL query is unavailable because user attribution is missing.",
            "intermediate_sql": None,
            "sql_query": None,
            "response": "<table><tr><th>SQL Query</th><th>Result</th></tr><tr><td>None</td><td>SQL query is unavailable because user attribution is missing.</td></tr></table>",
        }
    except RuntimeError as exc:
        logger.warning("SQL query unavailable: %s", str(exc))
        return {
            "content": "SQL query is not configured yet. Please set SQL_AGENT_TABLES in backend .env.",
            "intermediate_sql": None,
            "sql_query": None,
            "response": "<table><tr><th>SQL Query</th><th>Result</th></tr><tr><td>None</td><td>SQL query is not configured yet. Please set SQL_AGENT_TABLES in backend .env.</td></tr></table>",
        }
