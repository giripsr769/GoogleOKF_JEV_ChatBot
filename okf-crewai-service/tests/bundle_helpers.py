"""Shared helpers for tests that need a small OKF bundle on disk."""
from pathlib import Path


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_bundle(root: Path, spec: dict[str, dict]):
    """spec: {table: {links: [...], sensitive: bool}}. Also writes a flat /tables/index.md. Returns the loaded Bundle."""
    from okf_chat.core.okf_loader import Bundle

    for name, opts in spec.items():
        write(root, f"tables/{name}.md", table_md(name, **opts))
    write(root, "index.md", '---\nokf_version: "0.2"\n---\n# x\n')
    entries = "\n".join(f"* [{n}](/tables/{n}.md) - The {n} table." for n in spec)
    write(root, "tables/index.md", f"# Tables\n\n{entries}\n")
    return Bundle.load(root)


# customers <- orders <- order_items -> products ; salaries (sensitive) links employees and customers
SHOP = {
    "customers": {}, "orders": {"links": ["customers"]}, "order_items": {"links": ["orders", "products"]},
    "products": {}, "employees": {}, "salaries": {"links": ["employees", "customers"], "sensitive": True},
}


def table_md(name: str, links=(), cols=("id",), sensitive=False, description=None) -> str:
    """A table concept that links to each table named in `links` (bundle-relative, flat /tables/<name>.md)."""
    rels = "".join(f"- references [{t}](/tables/{t}.md).\n" for t in links)
    rows = "\n".join(f"| `{c}` | integer |  | the {c} |" for c in cols)
    return (
        f'---\ntype: "Postgres Table"\ntitle: "{name}"\ndescription: "{description or f"The {name} table."}"\n'
        f'resource: "postgres://db/public/{name}"\ntags: ["{name}"]\ncolumns: [{", ".join(cols)}]\n'
        f'{"sensitive: true" + chr(10) if sensitive else ""}---\n\n'
        f"{description or f'The {name} table.'}\n\n# Schema\n\n| Column | Type | Key | Description |\n|---|---|---|---|\n{rows}\n\n"
        + (f"# Relationships\n\n{rels}\n" if rels else "")
    )
