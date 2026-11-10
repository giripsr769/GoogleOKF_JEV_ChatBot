"""Command line entry point: `okf-chat build | serve | ask` ."""
import argparse
import os
import sys
from pathlib import Path


def _build(args: argparse.Namespace) -> int:
    from okf_chat.builder.build_from_db import build_bundle

    admin_url = args.admin_url or os.getenv("ADMIN_DATABASE_URL")
    if not admin_url:
        print("Pass --admin-url or set ADMIN_DATABASE_URL (a login that can see every table; used at build time only).")
        return 2
    r = build_bundle(
        admin_url=admin_url,
        out_dir=Path(args.out),
        schema=args.schema,
        readonly_role=args.readonly_role or None,
        seed_dir=Path(args.seed_dir) if args.seed_dir else None,
        domains_file=Path(args.domains) if args.domains else None,
    )
    print(f"OKF bundle written to {args.out}")
    print(f"  created {len(r.created)}, updated {len(r.updated)}, unchanged {len(r.unchanged)}, removed {len(r.removed)}")
    if r.sensitive:
        print(f"  sensitive (not readable by '{args.readonly_role}'): {', '.join(r.sensitive)}")
    if r.undescribed:
        print(f"  {len(r.undescribed)} tables still have an automatic description; edit them for better answers.")
    return 0


def _check(args: argparse.Namespace) -> int:
    from okf_chat.core.okf_loader import check_bundle

    report = check_bundle(args.bundle)
    for line in report.errors:
        print(f"ERROR   {line}")
    for line in report.warnings:
        print(f"warning {line}")
    verdict = "conforms to OKF v0.2" if report.ok else f"has {len(report.errors)} error(s)"
    print(f"{args.bundle}: {verdict} ({report.concepts} concepts, {report.links} links, {len(report.warnings)} warnings)")
    return 0 if report.ok else 1


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("okf_chat.api.main:app_factory", factory=True, host=args.host, port=args.port)
    return 0


def _ask(args: argparse.Namespace) -> int:
    import asyncio

    from okf_chat import OKFChat
    from okf_chat.core.pipeline import Refusal
    from okf_chat.core.sql_executor import UnsafeDatabaseRole

    chat = OKFChat()
    try:
        result = asyncio.run(chat.ask(args.question))
    except Refusal as r:
        print(f"Refused ({r.status_code}): {r.message}")
        print(f"  {r.detail}")
        return 1
    except UnsafeDatabaseRole as e:
        print(f"Unsafe DATABASE_URL: {e}")
        return 2
    print(result.answer)
    print()
    print(f"SQL: {result.sql}")
    print(f"rows: {result.row_count}  tables: {', '.join(result.tables_used)}  timings_ms: {result.timings_ms}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="okf-chat", description="Chat with your database, guided by an OKF bundle.")
    sub = parser.add_subparsers(dest="command")

    b = sub.add_parser("build", help="Generate or refresh the OKF bundle from the database")
    b.add_argument("--admin-url", help="Postgres URL that can see every table (build time only). Env: ADMIN_DATABASE_URL")
    b.add_argument("--out", default=os.getenv("OKF_BUNDLE_DIR", "okf_bundle"), help="Bundle folder (default: okf_bundle)")
    b.add_argument("--schema", default="public")
    b.add_argument("--readonly-role", default="okf_readonly", help="Tables this role cannot SELECT are marked sensitive")
    b.add_argument("--seed-dir", help="Folder of older OKF-style files to take descriptions and tags from")
    b.add_argument("--domains", help="YAML file grouping tables into folders")
    b.set_defaults(func=_build)

    c = sub.add_parser("check", help="Check a bundle against the OKF v0.2 spec")
    c.add_argument("bundle", nargs="?", default=os.getenv("OKF_BUNDLE_DIR", "okf_bundle"))
    c.set_defaults(func=_check)

    s = sub.add_parser("serve", help="Run the HTTP API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=int(os.getenv("PORT", "8001")))
    s.set_defaults(func=_serve)

    a = sub.add_parser("ask", help="Ask one question from the command line")
    a.add_argument("question")
    a.set_defaults(func=_ask)

    args = parser.parse_args()
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
