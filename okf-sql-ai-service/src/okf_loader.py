"""OKF markdown parser and FAISS index builder/searcher."""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import faiss
import numpy as np
import yaml
from openai import AsyncOpenAI

from .join_paths import build_graph

BASE = Path(__file__).resolve().parent.parent
OKF_DIR = BASE / "okf_tables"
STORE_DIR = BASE / "vector_store"
EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
SEARCH_K = int(os.getenv("SEARCH_K", "8"))  # candidates passed from FAISS to the Jev reranker


@dataclass
class OKFTable:
    table: str
    description: str
    tags: list[str] = field(default_factory=list)
    columns: list[dict] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)
    body: str = ""

    def search_text(self) -> str:
        cols = ", ".join(f"{c['name']} ({c.get('description', '')})" for c in self.columns)
        return f"Table {self.table}: {self.description} Tags: {', '.join(self.tags)}. Columns: {cols}"

    def to_prompt(self) -> str:
        lines = [f"TABLE {self.table} -- {self.description}"]
        for c in self.columns:
            key = f" [{c['key']} key]" if c.get("key") else ""
            lines.append(f"  - {c['name']} {c['type']}{key}: {c.get('description', '')}")
        for r in self.relationships:
            lines.append(f"  REL {r}")
        return "\n".join(lines)


def parse_okf(path: Path) -> OKFTable:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path.name}: missing YAML frontmatter")
    _, front, body = text.split("---", 2)
    meta = yaml.safe_load(front)
    return OKFTable(
        table=meta["table"],
        description=meta.get("description", ""),
        tags=meta.get("tags", []),
        columns=meta.get("columns", []),
        relationships=meta.get("relationships", []),
        body=body.strip(),
    )


def load_tables() -> list[OKFTable]:
    return [parse_okf(p) for p in sorted(OKF_DIR.glob("*.md"))]


def _signature() -> dict:
    return {p.name: p.stat().st_mtime_ns for p in sorted(OKF_DIR.glob("*.md"))} | {"model": EMBED_MODEL}


class SchemaIndex:
    def __init__(self, client: AsyncOpenAI):
        self.client = client
        self.tables: list[OKFTable] = []
        self.index: faiss.Index | None = None
        self.graph: dict[str, set[str]] = {}

    async def _embed(self, texts: list[str]) -> np.ndarray:
        resp = await self.client.embeddings.create(model=EMBED_MODEL, input=texts)
        vecs = np.array([d.embedding for d in resp.data], dtype="float32")
        faiss.normalize_L2(vecs)
        return vecs

    async def build_or_load(self) -> None:
        self.tables = load_tables()
        self.graph = build_graph(self.tables)
        STORE_DIR.mkdir(exist_ok=True)
        idx_file, sig_file = STORE_DIR / "okf.faiss", STORE_DIR / "okf.json"
        if idx_file.exists() and sig_file.exists():
            if json.loads(sig_file.read_text()) == _signature():
                self.index = faiss.read_index(str(idx_file))
                return
        vecs = await self._embed([t.search_text() for t in self.tables])
        self.index = faiss.IndexFlatIP(vecs.shape[1])
        self.index.add(vecs)
        faiss.write_index(self.index, str(idx_file))
        sig_file.write_text(json.dumps(_signature()))

    async def search(self, query: str, k: int = SEARCH_K) -> list[OKFTable]:
        q = await self._embed([query])
        _, ids = self.index.search(q, min(k, len(self.tables)))
        return [self.tables[i] for i in ids[0] if i >= 0]
