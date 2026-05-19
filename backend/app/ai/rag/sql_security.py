import re
from typing import Iterable

BLOCKED_KEYWORDS = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE",
)
BLOCKED_STATEMENTS = ("COPY", "EXECUTE", "DO", "CALL")
BLOCKED_TOKENS = ("UNION",)

# Enhanced pattern to handle FROM/JOIN with optional schema.table, aliases, and JOIN variants
_TABLE_REF_PATTERN = re.compile(
    r"\b(?:from|join|inner\s+join|left\s+join|right\s+join|full\s+join|cross\s+join)\s+(?:only\s+)?"
    r"((?:\"[^\"]+\"|[a-zA-Z_][\w$]*)(?:\s*\.\s*(?:\"[^\"]+\"|[a-zA-Z_][\w$]*))?)(?:\s+(?:as\s+)?[a-zA-Z_][\w]*)?",
    re.IGNORECASE,
)
_WITH_START_PATTERN = re.compile(r"^\s*with\b", re.IGNORECASE)
_SELECT_OR_WITH_PATTERN = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)

EXAMPLE_ALLOWED_QUERIES = [
    "SELECT COUNT(*) FROM chat_messages",
    "SELECT id, updated_at FROM chat_threads WHERE updated_at >= NOW() - INTERVAL '24 hours' ORDER BY updated_at DESC LIMIT 50",
    "SELECT t.id, COUNT(m.id) AS message_count FROM chat_threads t LEFT JOIN chat_messages m ON t.id = m.thread_id GROUP BY t.id",
    "WITH recent_threads AS (SELECT id, updated_at FROM chat_threads WHERE updated_at >= NOW() - INTERVAL '24 hours') SELECT id, updated_at FROM recent_threads ORDER BY updated_at DESC",
    "SELECT thread_id, COUNT(*) AS message_count FROM chat_messages GROUP BY thread_id ORDER BY message_count DESC LIMIT 10",
]

EXAMPLE_BLOCKED_QUERIES = [
    "DROP TABLE chat_threads",
    "DELETE FROM chat_messages WHERE id = 1",
    "SELECT * FROM chat_threads; DELETE FROM chat_threads",
    "SELECT * FROM chat_threads -- comment",
    "CALL refresh_materialized_views()",
    "COPY chat_messages TO '/tmp/messages.csv'",
    "SELECT * FROM chat_threads UNION SELECT * FROM employees",
]


class SQLSecurityError(ValueError):
    """Raised when SQL guardrails are violated."""


def normalize_sql(sql_query: str) -> str:
    """Normalize SQL query: strip whitespace, remove trailing semicolon, collapse spaces."""
    normalized = sql_query.strip()
    if normalized.endswith(";"):
        normalized = normalized[:-1].strip()
    return normalized


def _normalize_table_name(name: str) -> str:
    """Normalize table name: strip quotes, extract last part for schema.table, lowercase."""
    normalized = name.strip()
    if not normalized:
        return normalized

    parts = [part.strip().strip('"`[]').lower() for part in normalized.split(".")]
    return parts[-1] if parts else normalized.lower()


def _extract_cte_names(sql_query: str) -> set[str]:
    """Extract names of Common Table Expressions (CTEs) from WITH clause."""
    if not _WITH_START_PATTERN.match(sql_query):
        return set()

    cte_names: set[str] = set()
    sql = sql_query.strip()
    i = len("with")
    length = len(sql)

    while i < length:
        while i < length and sql[i].isspace():
            i += 1

        # Handle WITH RECURSIVE ...
        if sql[i : i + len("recursive")].lower() == "recursive":
            i += len("recursive")
            continue

        if i >= length:
            break

        name_start = i
        if sql[i] == '"':
            i += 1
            while i < length and sql[i] != '"':
                i += 1
            i += 1
        else:
            while i < length and (sql[i].isalnum() or sql[i] == "_"):
                i += 1

        cte_name = _normalize_table_name(sql[name_start:i])
        if not cte_name:
            break

        while i < length and sql[i].isspace():
            i += 1

        # Optional CTE column list: cte_name(col1, col2)
        if i < length and sql[i] == "(":
            depth = 1
            i += 1
            while i < length and depth > 0:
                if sql[i] == "(":
                    depth += 1
                elif sql[i] == ")":
                    depth -= 1
                i += 1

            while i < length and sql[i].isspace():
                i += 1

        if sql[i : i + 2].lower() != "as":
            break

        cte_names.add(cte_name)
        i += 2

        while i < length and sql[i].isspace():
            i += 1

        if i >= length or sql[i] != "(":
            break

        # Skip the CTE subquery body until matching close paren.
        depth = 1
        i += 1
        while i < length and depth > 0:
            if sql[i] == "(":
                depth += 1
            elif sql[i] == ")":
                depth -= 1
            i += 1

        while i < length and sql[i].isspace():
            i += 1

        if i < length and sql[i] == ",":
            i += 1
            continue

        break

    return cte_names


def extract_tables(sql_query: str) -> list[str]:
    """Extract actual table names from SQL query, excluding CTEs and aliases."""
    referenced = {
        _normalize_table_name(match.group(1))
        for match in _TABLE_REF_PATTERN.finditer(sql_query)
    }
    referenced -= _extract_cte_names(sql_query)
    return sorted(table for table in referenced if table)


def validate_allowed_tables(sql_query: str, allowed_tables: Iterable[str]) -> None:
    """Validate that all referenced tables are in the allowed list."""
    allowed = {_normalize_table_name(name) for name in allowed_tables if name.strip()}
    if not allowed:
        raise SQLSecurityError("SQL_AGENT_TABLES is empty; table scope must be configured")

    # Allow information_schema tables for schema introspection
    allowed.add("information_schema")
    allowed.add("tables")
    allowed.add("columns")
    allowed.add("constraint_column_usage")
    allowed.add("key_column_usage")

    referenced = set(extract_tables(sql_query))
    if not referenced:
        return

    disallowed = sorted(table for table in referenced if table not in allowed)
    if disallowed:
        raise SQLSecurityError(
            "Query references tables outside SQL_AGENT_TABLES: " + ", ".join(disallowed)
        )


def validate_blocked_keywords(sql_query: str) -> None:
    """Block dangerous SQL keywords that modify data or schema."""
    for keyword in BLOCKED_KEYWORDS:
        if re.search(rf"\b{keyword}\b", sql_query, flags=re.IGNORECASE):
            raise SQLSecurityError(f"Blocked SQL keyword detected: {keyword}")


def validate_blocked_statements(sql_query: str) -> None:
    """Block procedural/administrative SQL statements."""
    for keyword in BLOCKED_STATEMENTS:
        if re.search(rf"\b{keyword}\b", sql_query, flags=re.IGNORECASE):
            raise SQLSecurityError(f"Blocked SQL statement detected: {keyword}")


def validate_blocked_tokens(sql_query: str) -> None:
    """Block tokens commonly used in SQL injection attacks."""
    for keyword in BLOCKED_TOKENS:
        if re.search(rf"\b{keyword}\b", sql_query, flags=re.IGNORECASE):
            raise SQLSecurityError(f"Blocked SQL token detected: {keyword}")


def validate_no_comments(sql_query: str) -> None:
    """Ensure query contains no comments (SQL or block comments)."""
    if "--" in sql_query or "/*" in sql_query or "*/" in sql_query:
        raise SQLSecurityError("SQL comments are not allowed")


def validate_single_statement(sql_query: str) -> None:
    """Ensure query is a single SQL statement (no semicolon separators)."""
    if ";" in sql_query:
        raise SQLSecurityError("Multiple SQL statements are not allowed")


def validate_allowed_operation(sql_query: str) -> None:
    """Validate that query is only SELECT or WITH (read-only operations)."""
    stripped = sql_query.strip()
    if not _SELECT_OR_WITH_PATTERN.match(stripped):
        raise SQLSecurityError("Query must start with SELECT or WITH")


def enforce_sql_guardrails(sql_query: str, allowed_tables: Iterable[str]) -> None:
    """Main entry point: apply all SQL security validations."""
    normalized = normalize_sql(sql_query)
    
    validate_no_comments(normalized)
    validate_single_statement(normalized)
    validate_allowed_operation(normalized)
    validate_blocked_keywords(normalized)
    validate_blocked_statements(normalized)
    validate_blocked_tokens(normalized)
    validate_allowed_tables(normalized, allowed_tables)


# Legacy function name for backward compatibility
def validate_sql_query(sql_query: str, allowed_tables: Iterable[str]) -> None:
    """Validate SQL query against security guardrails."""
    enforce_sql_guardrails(sql_query, allowed_tables)
