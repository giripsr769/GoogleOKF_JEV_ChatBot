"""Read an OKF v0.2 bundle (a folder of Markdown files with YAML frontmatter) and check it against the spec.

Pure Python, no agent framework and no database. Follows the spec's consumer rules: a bundle is never
rejected for unknown types, unknown keys, broken links or a missing index.md. Those become warnings.
"""
from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

SUPPORTED_OKF_VERSION = "0.2"
TABLE_TYPE = "Postgres Table"
RESERVED = {"index", "log"}  # filenames the spec reserves; never concept documents

_FRONT = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.S)
_PIPE = re.compile(r"(?<!\\)\|")
_LINK = re.compile(r"\]\(([^)\s]+)\)")
_INDEX_LINE = re.compile(r"^\s*[*-]\s+\[([^\]]+)\]\(([^)\s]+)\)\s*(?:-\s*(.*))?$")
_LOG_DATE = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")


# ---------------------------------------------------------------- parsing helpers (shared with the builder)
def split_front(text: str) -> tuple[dict, str]:
    """Split a Markdown file into (frontmatter dict, body). No frontmatter, or YAML that does not parse -> ({}, text)."""
    text = text.replace("\r\n", "\n")
    m = _FRONT.match(text)
    if not m:
        return {}, text
    try:
        front = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}, text
    return (front if isinstance(front, dict) else {}), m.group(2)


def section(body: str, heading: str) -> str:
    """The text under a `# Heading` line, up to the next `# ` heading."""
    m = re.search(rf"^# {re.escape(heading)}\s*\n(.*?)(?=^# |\Z)", body, re.S | re.M)
    return m.group(1).strip() if m else ""


@dataclass
class ColumnDoc:
    name: str
    type: str
    key: str
    description: str


def parse_schema(body: str) -> list[ColumnDoc]:
    """Rows of the `# Schema` Markdown table: | Column | Type | Key | Description |."""
    rows = []
    for line in section(body, "Schema").splitlines():
        if not line.startswith("|") or set(line) <= set("|- :"):
            continue
        cells = [c.strip() for c in _PIPE.split(line.strip().strip("|"))]
        if len(cells) >= 4 and cells[0] not in ("Column", ""):
            rows.append(ColumnDoc(cells[0].strip("`"), cells[1], cells[2], cells[3].replace("\\|", "|")))
    return rows


def parse_time(value) -> datetime | None:
    """ISO 8601 text or a datetime (YAML turns unquoted timestamps into one) -> aware UTC datetime."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        try:
            dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- the model
@dataclass
class Concept:
    path: str  # bundle-relative, e.g. /tables/ecommerce/orders.md
    type: str
    title: str
    description: str
    resource: str
    tags: list[str]
    status: str
    stale_after: datetime | None
    generated: dict
    verified: list[dict]
    sensitive: bool
    column_names: list[str]  # the `columns` list from the frontmatter
    columns: list[ColumnDoc]  # parsed from the `# Schema` table
    links: list[str]  # outgoing links, resolved to bundle paths
    body: str
    front: dict = field(repr=False, default_factory=dict)  # every frontmatter key, unknown ones included

    @property
    def trust_tier(self) -> str:
        """unverified, machine-confirmed or human-reviewed, derived only from `verified` (spec section 5)."""
        if not self.verified:
            return "unverified"
        by = [str(v.get("by", "")) for v in self.verified if isinstance(v, dict)]
        return "human-reviewed" if any(b.startswith("human:") for b in by) else "machine-confirmed"

    def is_stale(self, now: datetime | None = None) -> bool:
        return bool(self.stale_after and (now or datetime.now(timezone.utc)) >= self.stale_after)


@dataclass
class IndexEntry:
    title: str
    url: str  # bundle path
    description: str
    section: str


@dataclass
class Bundle:
    root: Path
    okf_version: str | None = None
    concepts: dict[str, Concept] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    _backlinks: dict[str, list[str]] = field(default_factory=dict, repr=False)

    # --- loading
    @classmethod
    def load(cls, root: str | Path) -> "Bundle":
        root = Path(root)
        if not root.is_dir():
            raise FileNotFoundError(f"OKF bundle folder not found: {root}")
        bundle = cls(root=root)
        root_index = root / "index.md"
        if root_index.exists():
            front, _ = split_front(root_index.read_text(encoding="utf-8"))
            if front.get("okf_version") is not None:
                bundle.okf_version = str(front["okf_version"])
                if bundle.okf_version != SUPPORTED_OKF_VERSION:
                    bundle.warnings.append(
                        f"bundle declares OKF {bundle.okf_version}; this reader targets {SUPPORTED_OKF_VERSION} (best effort)")
        for path in sorted(root.rglob("*.md")):
            if path.stem in RESERVED:
                continue
            rel = "/" + path.relative_to(root).as_posix()
            text = path.read_text(encoding="utf-8")
            front, body = split_front(text)
            if not front:
                bundle.warnings.append(f"{rel}: no parseable frontmatter, skipped")
                continue
            bundle.concepts[rel] = _make_concept(rel, front, body)
        for c in bundle.concepts.values():
            for target in c.links:
                if target not in bundle.concepts and not (root / target.lstrip("/")).exists():
                    bundle.warnings.append(f"{c.path}: broken link {target}")
                bundle._backlinks.setdefault(target, []).append(c.path)
        return bundle

    # --- lookups
    def get(self, path: str) -> Concept | None:
        return self.concepts.get(path)

    def by_type(self, type_name: str) -> list[Concept]:
        return [c for c in self.concepts.values() if c.type == type_name]

    def tables(self) -> dict[str, Concept]:
        """Postgres Table concepts keyed by table name (the concept title)."""
        return {c.title: c for c in self.by_type(TABLE_TYPE)}

    def table(self, name: str) -> Concept | None:
        return self.tables().get(name)

    def sensitive_tables(self) -> set[str]:
        return {name for name, c in self.tables().items() if c.sensitive}

    def backlinks(self, path: str) -> list[str]:
        return sorted(set(self._backlinks.get(path, [])))

    def related_tables(self, name: str) -> set[str]:
        """Tables one link away, in either direction: the join candidates."""
        concept = self.table(name)
        if not concept:
            return set()
        by_path = {c.path: n for n, c in self.tables().items()}
        paths = set(concept.links) | set(self.backlinks(concept.path))
        return {by_path[p] for p in paths if p in by_path and p != concept.path}

    def index_entries(self, directory: str = "/") -> list[IndexEntry]:
        """Entries of <directory>/index.md (progressive disclosure). A missing index.md gives an empty list."""
        path = self.root / directory.strip("/") / "index.md"
        if not path.exists():
            return []
        _, body = split_front(path.read_text(encoding="utf-8"))
        entries, current = [], ""
        for line in body.splitlines():
            if line.startswith("# "):
                current = line[2:].strip()
                continue
            m = _INDEX_LINE.match(line)
            if m:
                entries.append(IndexEntry(m.group(1), _resolve(m.group(2), directory.rstrip("/") + "/x"), (m.group(3) or "").strip(), current))
        return entries


def _resolve(url: str, from_path: str) -> str:
    """A link target as a bundle path; relative links are resolved from the linking file's folder."""
    url = url.split("#", 1)[0]
    if url.startswith("/"):
        return posixpath.normpath(url)
    return posixpath.normpath(posixpath.join(posixpath.dirname(from_path), url))


def _links(body: str, from_path: str) -> list[str]:
    out = []
    for url in _LINK.findall(body):
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", url) or url.startswith("#"):
            continue  # external URL or in-page anchor
        target = _resolve(url, from_path)
        if target.endswith(".md") and target not in out:
            out.append(target)
    return out


def _make_concept(rel: str, front: dict, body: str) -> Concept:
    verified = front.get("verified") or []
    if isinstance(verified, dict):  # a bare mapping means one verifier (spec section 5)
        verified = [verified]
    generated = front.get("generated") if isinstance(front.get("generated"), dict) else {}
    cols = front.get("columns") or []
    return Concept(
        path=rel,
        type=str(front.get("type") or "").strip(),
        title=str(front.get("title") or Path(rel).stem),
        description=str(front.get("description") or ""),
        resource=str(front.get("resource") or ""),
        tags=[str(t) for t in front.get("tags") or []],
        status=str(front.get("status") or "stable"),
        stale_after=parse_time(front.get("stale_after")),
        generated=generated,
        verified=[v for v in verified if isinstance(v, dict)],
        sensitive=bool(front.get("sensitive")),
        column_names=[str(c) for c in cols] if isinstance(cols, list) else [],
        columns=parse_schema(body),
        links=_links(body, rel),
        body=body,
        front=front,
    )


# ---------------------------------------------------------------- conformance check
@dataclass
class CheckReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    concepts: int = 0
    links: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def check_bundle(root: str | Path, now: datetime | None = None) -> CheckReport:
    """Check a folder against OKF v0.2.

    Errors are the producer rules of spec section 11: every concept file has parseable frontmatter with a
    non-empty `type`, and index.md / log.md follow their formats. Everything else is a warning.
    """
    root = Path(root)
    report = CheckReport()
    if not root.is_dir():
        report.errors.append(f"not a folder: {root}")
        return report

    for path in sorted(root.rglob("*.md")):
        rel = "/" + path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        front, body = split_front(text)
        if path.stem == "index":
            if front and rel != "/index.md":
                report.errors.append(f"{rel}: only the bundle-root index.md may have frontmatter")
            if front and rel == "/index.md" and set(front) - {"okf_version"}:
                report.warnings.append(f"{rel}: index frontmatter should only hold okf_version")
        elif path.stem == "log":
            for line in body.splitlines():
                if line.startswith("## ") and not _LOG_DATE.match(line):
                    report.errors.append(f"{rel}: log date heading must be '## YYYY-MM-DD', found {line!r}")
        elif not front:
            report.errors.append(f"{rel}: missing or unparseable YAML frontmatter")
        elif not str(front.get("type") or "").strip():
            report.errors.append(f"{rel}: frontmatter has no `type`")

    bundle = Bundle.load(root) if root.is_dir() else None
    report.concepts = len(bundle.concepts)
    report.warnings += bundle.warnings
    report.links = sum(len(c.links) for c in bundle.concepts.values())
    if not (root / "index.md").exists():
        report.warnings.append("/index.md is missing (allowed, but agents navigate better with one)")
    elif bundle.okf_version is None:
        report.warnings.append('/index.md has no okf_version (add okf_version: "0.2")')

    seen: dict[tuple[str, str], str] = {}
    for c in bundle.concepts.values():
        if c.type == TABLE_TYPE and (c.title, c.type) in seen:
            report.warnings.append(f"{c.path}: duplicate table title {c.title!r} (also {seen[(c.title, c.type)]})")
        seen[(c.title, c.type)] = c.path
        if not c.description:
            report.warnings.append(f"{c.path}: no description")
        if c.status not in ("draft", "stable", "deprecated"):
            report.warnings.append(f"{c.path}: status {c.status!r} is not draft, stable or deprecated")
        if c.status == "deprecated":
            report.warnings.append(f"{c.path}: deprecated")
        if c.is_stale(now):
            report.warnings.append(f"{c.path}: stale since {c.stale_after.isoformat()}")
        if "generated" in c.front and not c.generated.get("by"):
            report.warnings.append(f"{c.path}: `generated` needs a `by` actor")
        for v in c.verified:
            if not v.get("by") or not v.get("at"):
                report.warnings.append(f"{c.path}: each `verified` entry needs `by` and `at`")
        if c.type == TABLE_TYPE:
            if not c.resource:
                report.warnings.append(f"{c.path}: table has no `resource`")
            if c.column_names and [x.name for x in c.columns] != c.column_names:
                report.warnings.append(f"{c.path}: frontmatter `columns` does not match the # Schema table")
    return report
