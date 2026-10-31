"""sqlglot validation: read-only SELECT enforcement, table allow-list, LIMIT injection."""
import re

import sqlglot
from sqlglot import exp

_IDENT = re.compile(r"[a-z_][a-z0-9_$]*")

MAX_LIMIT = 100
_FORBIDDEN = tuple(
    getattr(exp, n)
    for n in ("Insert", "Update", "Delete", "Drop", "Create", "Alter", "Command",
              "TruncateTable", "Merge", "Copy", "Set", "Into", "AlterTable")
    if hasattr(exp, n)
)


# sqlglot parses common functions (SUM, COUNT, LOWER, ...) into typed nodes; anything it does not
# recognise (pg_sleep, pg_read_file, dblink, ...) is exp.Anonymous and must be explicitly allowed.
_ALLOWED_ANON_FUNCS = {"date_trunc", "to_char", "age", "now", "extract", "round", "coalesce", "nullif"}


class SQLValidationError(ValueError):
    pass


class SQLParseError(SQLValidationError):
    """Output was not parseable SQL (empty or garbled). Safe to regenerate, unlike a policy rejection."""


def validate_and_limit(sql: str, allowed_tables: set[str]) -> str:
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except sqlglot.errors.SqlglotError as e:
        raise SQLParseError(f"Unparseable SQL: {e}") from e
    if not statements:
        raise SQLParseError("Empty SQL output")
    if len(statements) != 1:
        raise SQLValidationError("Exactly one SQL statement is allowed")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union)):
        raise SQLValidationError("Only SELECT statements are allowed")
    for node in tree.walk():
        if isinstance(node, _FORBIDDEN):
            raise SQLValidationError(f"Forbidden operation: {type(node).__name__}")
    for fn in tree.find_all(exp.Anonymous):
        if str(fn.this).lower() not in _ALLOWED_ANON_FUNCS:
            raise SQLValidationError(f"Function '{fn.this}' is not permitted")
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for t in tree.find_all(exp.Table):
        name = t.name.lower()
        if not _IDENT.fullmatch(name):
            raise SQLParseError(f"Garbled table name: {t.name!r}")  # stray characters glued to an identifier
        if name not in allowed_tables and name not in ctes:
            raise SQLValidationError(f"Table '{t.name}' is not permitted for this question")
    limit = tree.args.get("limit")
    if limit is not None:
        try:
            current = int(limit.expression.name)
        except (ValueError, AttributeError):
            current = MAX_LIMIT + 1
        if current > MAX_LIMIT:
            tree.set("limit", exp.Limit(expression=exp.Literal.number(MAX_LIMIT)))
    else:
        tree = tree.limit(MAX_LIMIT)
    return tree.sql(dialect="postgres")
