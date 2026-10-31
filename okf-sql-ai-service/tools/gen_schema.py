"""Generate db/02_init_extra.sql and okf_tables/*.md from tools/schema_spec.py.

Run from okf-sql-ai-service/:  python tools/gen_schema.py
Deterministic (seeded), so re-running produces identical output.
"""
import json
import random
from pathlib import Path

from schema_spec import EXISTING, RESTRICTED, SPEC

ROOT = Path(__file__).resolve().parent.parent
SEED_ROWS = 6
rng = random.Random(42)

SQL_TYPES = {"int": "INT", "text": "TEXT", "num": "NUMERIC(12,2)", "ts": "TIMESTAMP", "date": "DATE", "bool": "BOOLEAN"}
OKF_TYPES = {"pk": "integer", "int": "integer", "text": "text", "num": "numeric(12,2)", "ts": "timestamp", "date": "date", "bool": "boolean"}
COUNTRIES = ["India", "USA", "Singapore", "Germany", "UK"]
CITIES = ["Chennai", "Austin", "Singapore", "Berlin", "London", "Mumbai"]


def parse_col(s: str) -> dict:
    name, typ, desc = s.split("|", 2)
    col = {"name": name, "desc": desc, "enum": None, "fk": None}
    if typ.startswith("fk:"):
        col["kind"], col["fk"] = "fk", typ[3:]
    elif typ.startswith("text:"):
        col["kind"], col["enum"] = "text", typ[5:].split("/")
    else:
        col["kind"] = typ
    col["nullable"] = "null" in desc.lower()
    return col


TABLES = {t: {"desc": d, "tags": tg.split(), "cols": [parse_col(c) for c in cols], "notes": n}
          for t, (d, tg, cols, n) in SPEC.items()}
COUNTS = dict(EXISTING) | {t: SEED_ROWS for t in TABLES}


def order_tables() -> list[str]:
    done, out = set(EXISTING), []
    pending = dict(TABLES)
    while pending:
        progressed = False
        for t in list(pending):
            deps = {c["fk"] for c in pending[t]["cols"] if c["fk"] and c["fk"] != t}
            if deps <= done:
                out.append(t); done.add(t); del pending[t]; progressed = True
        if not progressed:
            raise SystemExit(f"FK cycle among: {list(pending)}")
    return out


def sql_lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    return v[1:] if isinstance(v, str) and v.startswith("=") else "'" + str(v).replace("'", "''") + "'"


def seed_value(table: str, c: dict, i: int):
    n, k = c["name"], c["kind"]
    if c["nullable"] and i % 3 == 0:
        return None
    if k == "fk":
        if c["fk"] == table:
            return None if i == 1 else 1
        return rng.randint(1, COUNTS[c["fk"]])
    if c["enum"]:
        return c["enum"][(i - 1) % len(c["enum"])]
    if k == "bool":
        return i % 4 != 0
    if k == "ts":
        return f"=now() - interval '{rng.randint(1, 120)} days'"
    if k == "date":
        if n == "start_date":
            return f"=current_date - {40 - i * 3}"
        if n == "end_date":
            return f"=current_date - {37 - i * 3}"
        if n in ("due_on", "valid_until"):
            return f"=current_date + {rng.randint(5, 60)}"
        return f"=current_date - {rng.randint(1, 365)}"
    if k == "num":
        if "rating" in n:
            return round(rng.uniform(2, 5), 1)
        if "percent" in n:
            return round(rng.uniform(2, 30), 1)
        return round(rng.uniform(10, 1000), 2)
    if k == "int":
        if n in ("rating", "score"):
            return rng.randint(1, 5)
        if n == "fiscal_year":
            return 2025 + (i % 2)
        if n in ("grade", "tier"):
            return rng.randint(1, 3)
        if "quantity" in n or n in ("quantity_on_hand", "reorder_level", "views"):
            return rng.randint(1, 50)
        return rng.randint(1, 100)
    # text
    if "email" in n:
        return f"{table}{i}@example.com"
    if n == "country":
        return COUNTRIES[(i - 1) % len(COUNTRIES)]
    if n == "city":
        return CITIES[(i - 1) % len(CITIES)]
    if n == "code":
        return f"CODE{i:03d}"
    return f"{table} {n} {i}"


def ddl(table: str) -> str:
    cols = []
    for c in TABLES[table]["cols"]:
        if c["kind"] == "pk":
            cols.append(f"{c['name']} SERIAL PRIMARY KEY")
        elif c["kind"] == "fk":
            cols.append(f"{c['name']} INT REFERENCES {c['fk']}(id)")
        else:
            cols.append(f"{c['name']} {SQL_TYPES[c['kind']]}")
    return f"CREATE TABLE {table} ({', '.join(cols)});"


def inserts(table: str) -> str:
    cols = [c for c in TABLES[table]["cols"] if c["kind"] != "pk"]
    names = ", ".join(c["name"] for c in cols)
    rows = [", ".join(sql_lit(seed_value(table, c, i)) for c in cols) for i in range(1, SEED_ROWS + 1)]
    return f"INSERT INTO {table} ({names}) VALUES\n " + ",\n ".join(f"({r})" for r in rows) + ";"


def okf(table: str) -> str:
    t = TABLES[table]
    lines = ["---", f"table: {table}", "schema: public", f"description: {json.dumps(t['desc'])}",
             f"tags: [{', '.join(json.dumps(x) for x in t['tags'])}]", "columns:"]  # quoted: bare 'off'/'no'/'on' parse as booleans
    for c in t["cols"]:
        key = {"pk": ", key: primary", "fk": ", key: foreign"}.get(c["kind"], "")
        typ = OKF_TYPES.get(c["kind"], "integer")
        desc = c["desc"] + (f" (one of: {', '.join(c['enum'])})" if c["enum"] else "")
        lines.append(f"  - {{name: {c['name']}, type: {json.dumps(typ)}{key}, description: {json.dumps(desc)}}}")
    rels = [f"{table}.{c['name']} -> {c['fk']}.id" for c in t["cols"] if c["fk"]]
    rels += [f"{o}.{c['name']} -> {table}.id" for o, ot in TABLES.items() for c in ot["cols"] if c["fk"] == table and o != table]
    if rels:
        lines.append("relationships:")
        lines += [f"  - {r}" for r in rels]
    lines += ["---", f"# {table}", t["notes"] or t["desc"], ""]
    return "\n".join(lines)


def main() -> None:
    order = order_tables()
    sql = ["-- GENERATED by tools/gen_schema.py -- do not edit by hand.", "-- Must run after 01_init.sql: the numeric prefix forces that order (Docker runs the folder in sorted order).", ""]
    sql += [ddl(t) for t in order] + [""]
    sql += [inserts(t) for t in order] + [""]
    granted = [t for t in order if t not in RESTRICTED]
    sql.append("-- okf_readonly: SELECT on every table except RESTRICTED: " + ", ".join(sorted(RESTRICTED)))
    sql.append(f"GRANT SELECT ON {', '.join(granted)} TO okf_readonly;")
    (ROOT / "db" / "02_init_extra.sql").write_text("\n".join(sql) + "\n", encoding="utf-8")
    for t in order:
        (ROOT / "okf_tables" / f"{t}.md").write_text(okf(t), encoding="utf-8")
    print(f"generated {len(order)} tables; granted {len(granted)}; restricted {sorted(RESTRICTED)}")


if __name__ == "__main__":
    main()
