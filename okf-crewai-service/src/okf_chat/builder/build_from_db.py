"""Build an OKF v0.2 bundle from a Postgres database.

Facts (columns, types, keys, who can read what) come from the database. Human knowledge (descriptions,
tags, notes) is merged in this order, first one wins:
    1. the existing bundle   (so hand edits survive a rebuild)
    2. an optional seed dir  (older OKF-style files, used once to bootstrap descriptions)
    3. database COMMENTs
    4. an automatic fallback
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from okf_chat import __version__
from okf_chat.builder.introspect import Table, introspect
from okf_chat.core.okf_loader import RESERVED, TABLE_TYPE as TYPE_NAME, parse_schema, section, split_front

OKF_VERSION = "0.2"
GENERATOR = f"okf-chat/{__version__}"


# ---------------------------------------------------------------- reading existing knowledge
@dataclass
class Knowledge:
    description: str = ""
    tags: list[str] = field(default_factory=list)
    columns: dict[str, str] = field(default_factory=dict)  # column name -> description
    notes: str = ""
    examples: str = ""
    auto_description: bool = False
    generated_at: str = ""


def _read_existing(path: Path) -> Knowledge:
    """Read a file this builder wrote earlier (possibly hand-edited)."""
    front, body = split_front(path.read_text(encoding="utf-8"))
    return Knowledge(
        description=str(front.get("description") or ""),
        tags=[str(t) for t in front.get("tags") or []],
        columns={c.name: c.description for c in parse_schema(body)},
        notes=section(body, "Notes"),
        examples=section(body, "Examples"),
        auto_description=bool(front.get("auto_description")),
        generated_at=str((front.get("generated") or {}).get("at") or ""),
    )


def _read_seed(path: Path) -> Knowledge:
    """Read an older OKF-style file: frontmatter with description, tags, columns[]; the body is a note."""
    front, body = split_front(path.read_text(encoding="utf-8"))
    k = Knowledge(description=str(front.get("description") or ""), tags=[str(t) for t in front.get("tags") or []])
    for col in front.get("columns") or []:
        if isinstance(col, dict) and col.get("name"):
            k.columns[str(col["name"])] = str(col.get("description") or "")
    lines = [ln for ln in body.strip().splitlines() if not re.match(r"^# \S", ln)]
    k.notes = "\n".join(lines).strip()
    return k


def _load_dir(root: Path, reader) -> dict[str, Knowledge]:
    found: dict[str, Knowledge] = {}
    if not root.is_dir():
        return found
    for path in sorted(root.rglob("*.md")):
        if path.stem in RESERVED:
            continue
        front, _ = split_front(path.read_text(encoding="utf-8"))
        name = str(front.get("title") or front.get("table") or path.stem)
        found[name] = reader(path)
    return found


# ---------------------------------------------------------------- domains
def load_domains(path: Path | None) -> dict[str, dict]:
    """domains.yaml: `name: [tables]` or `name: {title: ..., tables: [...]}`. Returns {name: {title, tables}}."""
    if not path:
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = {}
    for name, spec in raw.items():
        spec = {"tables": spec} if isinstance(spec, list) else dict(spec)
        spec.setdefault("title", str(name).replace("_", " ").title())
        out[str(name)] = spec
    return out


# ---------------------------------------------------------------- rendering helpers
def _q(value) -> str:
    """JSON is valid YAML, so JSON quoting keeps every value safe and unambiguous."""
    import json
    return json.dumps(value, ensure_ascii=False)


def _flow(items) -> str:
    return "[" + ", ".join(_q(i) for i in items) + "]"


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def _file_stem(table: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", table)
    return f"{stem}_table" if stem.lower() in RESERVED else stem


def _fallback_description(table: Table) -> str:
    return f"Table `{table.name}` with {len(table.columns)} columns. Add a one-sentence description."


def _render_table(table: Table, k: Knowledge, dbname: str, schema: str, link_for, referenced_by, now: str) -> str:
    sensitive = not table.readable or "sensitive" in {t.lower() for t in k.tags}
    desc = k.description or table.comment or _fallback_description(table)
    auto = not (k.description or table.comment)
    fk_by_col = {c: fk for fk in table.foreign_keys for c in fk.columns}

    front = [
        "---",
        f"type: {_q(TYPE_NAME)}",
        f"title: {_q(table.name)}",
        f"description: {_q(desc)}",
        f"resource: {_q(f'postgres://{dbname}/{schema}/{table.name}')}",
        f"tags: {_flow(k.tags)}",
        f"columns: {_flow([c.name for c in table.columns])}",
    ]
    if sensitive:
        front.append("sensitive: true")
    if auto:
        front.append("auto_description: true")
    front += ["generated:", f"  by: {_q(GENERATOR)}", f"  at: {_q(now)}", "---", ""]

    body = [desc, ""]
    if sensitive:
        body += ["> **Sensitive table.** The chatbot's database role cannot read it, so questions about it are refused.", ""]
    body += ["# Schema", "", "| Column | Type | Key | Description |", "|---|---|---|---|"]
    for col in table.columns:
        keys = []
        if col.name in table.primary_key:
            keys.append("PK")
        fk = fk_by_col.get(col.name)
        if fk and fk.ref_table in link_for:
            keys.append(f"FK → [{fk.ref_table}]({link_for[fk.ref_table]})")
        elif fk:
            keys.append(f"FK → {fk.ref_table}")
        cdesc = k.columns.get(col.name) or col.comment or ""
        body.append(f"| `{col.name}` | {col.type} | {', '.join(keys)} | {_cell(cdesc)} |")
    body.append("")

    rels = []
    for fk in table.foreign_keys:
        target = f"[{fk.ref_table}]({link_for[fk.ref_table]})" if fk.ref_table in link_for else fk.ref_table
        rels.append(f"- `{', '.join(fk.columns)}` references {target} (`{', '.join(fk.ref_columns)}`).")
    for other, cols in referenced_by.get(table.name, []):
        if other in link_for and other != table.name:
            rels.append(f"- Referenced by [{other}]({link_for[other]}) through `{', '.join(cols)}`.")
    if rels:
        body += ["# Relationships", "", *rels, ""]
    if k.notes:
        body += ["# Notes", "", k.notes, ""]
    if k.examples:
        body += ["# Examples", "", k.examples, ""]
    return "\n".join(front + body)


def _index_entry(title: str, url: str, description: str) -> str:
    return f"* [{title}]({url}) - {' '.join(description.split())}"


def _with_now(text: str, now: str) -> str:
    return re.sub(r'(?m)^(  at: ).*$', lambda m: f'{m.group(1)}"{now}"', text, count=1)


# ---------------------------------------------------------------- the build
@dataclass
class BuildResult:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    sensitive: list[str] = field(default_factory=list)
    undescribed: list[str] = field(default_factory=list)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def build_bundle(
    admin_url: str,
    out_dir: Path,
    schema: str = "public",
    readonly_role: str | None = "okf_readonly",
    seed_dir: Path | None = None,
    domains_file: Path | None = None,
) -> BuildResult:
    out_dir = Path(out_dir)
    dbname, tables = introspect(admin_url, schema, readonly_role)
    if not tables:
        raise SystemExit(f"No tables found in schema '{schema}'.")

    existing = _load_dir(out_dir / "tables", _read_existing)
    seeds = _load_dir(Path(seed_dir), _read_seed) if seed_dir else {}
    domains = load_domains(domains_file)
    domain_of = {t: d for d, spec in domains.items() for t in spec.get("tables", [])}

    # where each table lives, as a bundle-relative link
    rel_path = {t: "/".join(p for p in ("tables", domain_of.get(t), _file_stem(t) + ".md") if p) for t in tables}
    link_for = {t: "/" + p for t, p in rel_path.items()}
    referenced_by: dict[str, list[tuple[str, list[str]]]] = {}
    for t in tables.values():
        for fk in t.foreign_keys:
            referenced_by.setdefault(fk.ref_table, []).append((t.name, fk.columns))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = BuildResult()
    log_entries: list[str] = []
    descriptions: dict[str, str] = {}

    for name in sorted(tables):
        table = tables[name]
        k = Knowledge()
        old, seed = existing.get(name), seeds.get(name)
        # hand edits win, except an auto-generated placeholder description, which never sticks
        layers = [x for x in (old, seed) if x]
        k.description = next((x.description for x in layers if x.description and not x.auto_description), "")
        k.tags = next((x.tags for x in layers if x.tags), [])
        k.notes = next((x.notes for x in layers if x.notes), "")
        k.examples = next((x.examples for x in layers if x.examples), "")
        for x in reversed(layers):
            k.columns.update({c: d for c, d in x.columns.items() if d})

        path = out_dir / rel_path[name]
        text = _render_table(table, k, dbname, schema, link_for, referenced_by, now)
        if path.exists():
            old_text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
            if _with_now(old_text, now) == text:
                result.unchanged.append(name)
            else:
                result.updated.append(name)
                _write(path, text)
                log_entries.append(f"* **Update**: [{name}]({link_for[name]}) regenerated from the database.")
        else:
            result.created.append(name)
            _write(path, text)
            log_entries.append(f"* **Creation**: [{name}]({link_for[name]}) generated from the database.")
        front, _ = split_front(path.read_text(encoding="utf-8"))
        descriptions[name] = front["description"]
        if front.get("sensitive"):
            result.sensitive.append(name)
        if front.get("auto_description"):
            result.undescribed.append(name)

    # tables dropped from the database: remove only files this tool generated
    for name, k in existing.items():
        if name in tables:
            continue
        for path in (out_dir / "tables").rglob("*.md"):
            front, _ = split_front(path.read_text(encoding="utf-8"))
            if front.get("title") == name and str((front.get("generated") or {}).get("by", "")).startswith("okf-chat/"):
                path.unlink()
                result.removed.append(name)
                log_entries.append(f"* **Deprecation**: `{name}` no longer exists in the database; its file was removed.")

    _write_indexes(out_dir, dbname, tables, domains, domain_of, link_for, descriptions)
    _write_log(out_dir, _summarise(log_entries, result), now[:10])
    return result


def _write_indexes(out_dir, dbname, tables, domains, domain_of, link_for, descriptions) -> None:
    tdir = out_dir / "tables"

    def entries(names):
        return [_index_entry(n, link_for[n], descriptions[n]) for n in sorted(names)]

    sections = []
    for dname, spec in domains.items():
        members = [t for t in spec.get("tables", []) if t in tables]
        if not members:
            continue
        sections += [f"# {spec['title']}", "", *entries(members), ""]
        _write(tdir / dname / "index.md", "\n".join([f"# {spec['title']} tables", "", *entries(members), ""]))
    loose = [t for t in tables if t not in domain_of]
    if loose:
        sections += ["# Other tables", "", *entries(loose), ""]
    _write(tdir / "index.md", "\n".join(["# Tables", "", *sections]))

    root = [
        "---", f"okf_version: {_q(OKF_VERSION)}", "---", "",
        f"# {dbname} database", "",
        f"Knowledge about the `{dbname}` Postgres database: {len(tables)} tables, one concept file each. "
        "Start at the tables index, open only the tables a question needs, and follow links to join them.", "",
        "# Sections", "",
        _index_entry("Tables", "/tables/index.md", "Every table with its columns, keys and relationships"), "",
    ]
    _write(out_dir / "index.md", "\n".join(root))


BULK_LOG_LIMIT = 10


def _summarise(entries: list[str], result: BuildResult) -> list[str]:
    """One line per change for a few tables; one summary line when a build touches many."""
    if len(entries) <= BULK_LOG_LIMIT:
        return entries
    parts = [f"{len(items)} {word}" for items, word in
             ((result.created, "created"), (result.updated, "updated"), (result.removed, "removed")) if items]
    return [f"* **Update**: [Tables](/tables/index.md) regenerated from the database ({', '.join(parts)})."]


def _write_log(out_dir: Path, new_entries: list[str], today: str) -> None:
    if not new_entries:
        if not (out_dir / "log.md").exists():
            _write(out_dir / "log.md", "# Directory Update Log\n\n## " + today + "\n* **Initialization**: Bundle created.\n")
        return
    path = out_dir / "log.md"
    sections: dict[str, list[str]] = {}
    if path.exists():
        current = None
        for line in path.read_text(encoding="utf-8").replace("\r\n", "\n").splitlines():
            if line.startswith("## "):
                current = line[3:].strip()
                sections[current] = []
            elif current and line.strip():
                sections[current].append(line)
    merged = sections.get(today, [])
    sections[today] = merged + [e for e in new_entries if e not in merged]
    out = ["# Directory Update Log", ""]
    for date in sorted(sections, reverse=True):  # newest first
        out += [f"## {date}", *sections[date], ""]
    _write(path, "\n".join(out))
