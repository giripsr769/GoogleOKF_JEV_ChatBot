"""Create and seed the `shop` database on an existing PostgreSQL server (no Docker, no psql needed).

Runs db/01_init.sql (4 base tables + the read-only role) then db/02_init_extra.sql (46 more tables), which is
exactly what the Docker image does on first start. Safe to re-run: if the database is already set up it
only verifies it. Use --reset to drop and rebuild it.

Admin connection (needs a role that can CREATE DATABASE and CREATE ROLE, normally `postgres`):
  --host/--port/--user/--password, or the standard PGHOST / PGPORT / PGUSER / PGPASSWORD variables.

Usage (from okf-sql-ai-service/):
  python scripts/db_setup.py
  python scripts/db_setup.py --host localhost --port 5432 --user postgres --password secret
  python scripts/db_setup.py --reset --yes
"""
import argparse
import getpass
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import errors, sql

ROOT = Path(__file__).resolve().parent.parent
SQL_FILES = ["01_init.sql", "02_init_extra.sql"]  # numbered: the Docker image runs them in sorted order and "init_extra" sorts before "init"
DB_NAME = "shop"  # fixed: 01_init.sql grants CONNECT ON DATABASE shop
APP_ROLE = "okf_readonly"
APP_PASSWORD = "okf_readonly"  # local-development default; see README before real use
EXPECTED_TABLES = 50


def die(msg: str, code: int = 1):
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def connect(args, dbname: str, user: str | None = None, password: str | None = None):
    return psycopg2.connect(
        host=args.host, port=args.port, dbname=dbname,
        user=user or args.user, password=password if password is not None else args.password,
        connect_timeout=5,
    )


def admin_connect(args, dbname: str):
    """Connect as the admin role; if the server asks for a password and none was given, prompt once."""
    try:
        return connect(args, dbname)
    except psycopg2.OperationalError as e:
        text = str(e).lower()
        if "password" in text and args.password is None and sys.stdin.isatty():
            args.password = getpass.getpass(f"Password for PostgreSQL user '{args.user}' on {args.host}:{args.port}: ")
            return connect(args, dbname)
        if "password" in text:
            die(f"PostgreSQL rejected the login for user '{args.user}'.\n"
                "Pass the password with --password or the PGPASSWORD environment variable.")
        if "does not exist" in text and "role" in text:
            die(f"PostgreSQL has no role '{args.user}'. Pass an admin role with --user (it must be able to CREATE DATABASE and CREATE ROLE).")
        die(f"Cannot reach PostgreSQL at {args.host}:{args.port}.\n"
            "  - Is PostgreSQL installed and running? (Windows: Services > postgresql-x64-NN; macOS: brew services start postgresql; Linux: systemctl start postgresql)\n"
            "  - Different host or port? Use --host / --port.\n"
            f"  Driver said: {str(e).strip()}")


def has_tables(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")
        return cur.fetchone()[0] > 0


def confirm_reset(args):
    if args.yes:
        return
    if not sys.stdin.isatty():
        die("--reset deletes the whole database. Re-run with --yes to confirm in a non-interactive shell.")
    answer = input(f"--reset will DROP the database '{DB_NAME}' and all its data. Type '{DB_NAME}' to continue: ")
    if answer.strip() != DB_NAME:
        die("Cancelled. Nothing was changed.", 0)


def run_sql_files(conn):
    for name in SQL_FILES:
        path = ROOT / "db" / name
        if not path.exists():
            die(f"{path} not found. Run this from a complete checkout of the project.")
        print(f"  running db/{name} ...")
        with conn.cursor() as cur:
            cur.execute(path.read_text(encoding="utf-8"))  # no params, so '%' in the SQL is left alone
        conn.commit()


def verify(args) -> bool:
    """Check the setup the way the API will use it: as okf_readonly."""
    ok = True
    with connect(args, DB_NAME).cursor() as cur:
        cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")
        n = cur.fetchone()[0]
    good = n == EXPECTED_TABLES
    ok &= good
    print(f"  tables in '{DB_NAME}': {n} {'(expected %d)' % EXPECTED_TABLES if good else '<-- expected %d' % EXPECTED_TABLES}")
    try:
        app = connect(args, DB_NAME, user=APP_ROLE, password=APP_PASSWORD)
    except psycopg2.OperationalError as e:
        print(f"  could not log in as {APP_ROLE}: {str(e).strip()}")
        return False
    with app:
        with app.cursor() as cur:
            cur.execute("SELECT count(*) FROM customers")
            print(f"  {APP_ROLE} can read customers: {cur.fetchone()[0]} rows")
        app.rollback()
        for label, stmt in (("write blocked", "UPDATE customers SET city = city"), ("salaries hidden", "SELECT * FROM salaries")):
            with app.cursor() as cur:
                try:
                    cur.execute(stmt)
                    print(f"  {label}: NO <-- {APP_ROLE} should not be able to do this")
                    ok = False
                except (errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction):
                    print(f"  {label}: yes")
            app.rollback()
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default=os.getenv("PGHOST", "localhost"))
    ap.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "5432")))
    ap.add_argument("--user", default=os.getenv("PGUSER", "postgres"))
    ap.add_argument("--password", default=os.getenv("PGPASSWORD"))
    ap.add_argument("--reset", action="store_true", help=f"drop and rebuild the '{DB_NAME}' database (deletes its data)")
    ap.add_argument("--yes", action="store_true", help="confirm --reset without asking")
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # keep stdout and stderr in order when piped

    print(f"Connecting to PostgreSQL at {args.host}:{args.port} as '{args.user}' ...")
    admin = admin_connect(args, "postgres")
    admin.autocommit = True

    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        exists = cur.fetchone() is not None

    if exists:
        with connect(args, DB_NAME) as probe:
            populated = has_tables(probe)
        if args.reset:
            confirm_reset(args)
            print(f"Dropping database '{DB_NAME}' ...")
            with admin.cursor() as cur:
                cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()", (DB_NAME,))
                cur.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(DB_NAME)))
            exists = populated = False
        elif populated:
            print(f"Database '{DB_NAME}' is already set up; leaving it unchanged (use --reset to rebuild). Verifying:")
            sys.exit(0 if verify(args) else 1)

    if not exists:
        print(f"Creating database '{DB_NAME}' ...")
        with admin.cursor() as cur:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME)))
    admin.close()

    print("Loading schema and sample data ...")
    with connect(args, DB_NAME) as conn:
        try:
            run_sql_files(conn)
        except psycopg2.Error as e:
            conn.rollback()
            die(f"SQL failed: {str(e).strip()}\nThe database may be half-built; re-run with --reset --yes to start clean.")

    print("Verifying:")
    if not verify(args):
        die("Verification failed (see above).")
    print(f"\nDone. In .env set:\n  DATABASE_URL=postgresql://{APP_ROLE}:{APP_PASSWORD}@{args.host}:{args.port}/{DB_NAME}")


if __name__ == "__main__":
    main()
