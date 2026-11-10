"""Read table and column facts straight from Postgres. The database is the source of truth for the OKF bundle."""
from dataclasses import dataclass, field

import psycopg


@dataclass
class Column:
    name: str
    type: str
    not_null: bool
    comment: str | None = None


@dataclass
class ForeignKey:
    columns: list[str]
    ref_table: str
    ref_columns: list[str]


@dataclass
class Table:
    name: str
    comment: str | None = None
    columns: list[Column] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    readable: bool = True  # False when the chatbot's read-only role has no SELECT on it


_COLUMNS_SQL = """
SELECT c.relname, obj_description(c.oid, 'pg_class'),
       a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull, col_description(c.oid, a.attnum)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
WHERE n.nspname = %s AND c.relkind IN ('r', 'p')
ORDER BY c.relname, a.attnum
"""

_KEYS_SQL = """
SELECT cl.relname, con.contype,
       (SELECT array_agg(att.attname ORDER BY k.ord)
          FROM unnest(con.conkey) WITH ORDINALITY k(attnum, ord)
          JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = k.attnum),
       fcl.relname,
       (SELECT array_agg(att.attname ORDER BY k.ord)
          FROM unnest(con.confkey) WITH ORDINALITY k(attnum, ord)
          JOIN pg_attribute att ON att.attrelid = con.confrelid AND att.attnum = k.attnum)
FROM pg_constraint con
JOIN pg_class cl ON cl.oid = con.conrelid
JOIN pg_namespace n ON n.oid = cl.relnamespace
LEFT JOIN pg_class fcl ON fcl.oid = con.confrelid
WHERE n.nspname = %s AND con.contype IN ('p', 'f')
ORDER BY cl.relname, con.conname
"""

_READABLE_SQL = """
SELECT c.relname, has_table_privilege(%s::name, c.oid, 'SELECT')
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND c.relkind IN ('r', 'p')
"""


def introspect(admin_url: str, schema: str = "public", readonly_role: str | None = None) -> tuple[str, dict[str, Table]]:
    """Return (database name, {table name: Table}).

    Needs a connection that can see every table, so use an admin URL at build time only.
    With `readonly_role`, tables that role cannot SELECT are flagged `readable=False`.
    """
    tables: dict[str, Table] = {}
    with psycopg.connect(admin_url) as conn:
        dbname = conn.info.dbname
        for rel, tcomment, col, ctype, not_null, ccomment in conn.execute(_COLUMNS_SQL, (schema,)).fetchall():
            table = tables.setdefault(rel, Table(name=rel, comment=tcomment))
            table.columns.append(Column(col, ctype, bool(not_null), ccomment))
        for rel, contype, cols, ref_rel, ref_cols in conn.execute(_KEYS_SQL, (schema,)).fetchall():
            if rel not in tables:
                continue
            if contype == "p":
                tables[rel].primary_key = list(cols)
            elif ref_rel:
                tables[rel].foreign_keys.append(ForeignKey(list(cols), ref_rel, list(ref_cols)))
        if readonly_role:
            for rel, can_read in conn.execute(_READABLE_SQL, (readonly_role, schema)).fetchall():
                if rel in tables:
                    tables[rel].readable = bool(can_read)
    return dbname, tables
