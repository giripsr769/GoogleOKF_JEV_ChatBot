"""One-command local setup, no Docker: virtual environment, dependencies, .env and the database.

Run from okf-sql-ai-service/ with any Python 3.10+ (3.11 is what the project is tested on):
  python scripts/setup_local.py                  # set everything up
  python scripts/setup_local.py --start          # ...and start the API afterwards
  python scripts/setup_local.py --skip-db        # database already prepared by hand
  python scripts/setup_local.py --reset-db --yes # rebuild the database from scratch

Any --pg-host / --pg-port / --pg-user / --pg-password options are passed to scripts/db_setup.py.
It is safe to run again: existing environment, .env and database are reused, never overwritten.
"""
import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_KEYS = ("TYPESAFE_API_KEY", "OPENAI_API_KEY")


def step(n, total, text):
    print(f"\n[{n}/{total}] {text}")


def die(msg):
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def read_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip().strip("'\"")
    return values


def missing_keys(env_path: Path) -> list[str]:
    env = read_env(env_path)
    return [k for k in REQUIRED_KEYS if not env.get(k) or env[k].startswith("your-")]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--venv", default=".venv", help="virtual environment folder (default .venv)")
    ap.add_argument("--skip-db", action="store_true", help="do not touch PostgreSQL")
    ap.add_argument("--reset-db", action="store_true", help="drop and rebuild the 'shop' database (deletes its data)")
    ap.add_argument("--yes", action="store_true", help="confirm --reset-db without asking")
    ap.add_argument("--start", action="store_true", help="start the API when setup finishes")
    ap.add_argument("--pg-host")
    ap.add_argument("--pg-port")
    ap.add_argument("--pg-user")
    ap.add_argument("--pg-password")
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # keep our output in order with the child processes' when piped to a file

    total = 4 if args.skip_db else 5
    if sys.version_info < (3, 10):
        die(f"Python 3.10 or newer is required (you have {sys.version.split()[0]}). 3.11 is recommended.")
    print(f"Project: {ROOT}\nPython {sys.version.split()[0]}" + ("" if sys.version_info[:2] == (3, 11) else "  (the project is tested on 3.11)"))

    # 1. virtual environment
    step(1, total, "Virtual environment")
    venv_dir = (ROOT / args.venv).resolve()
    py = venv_python(venv_dir)
    if os.name == "nt" and len(str(venv_dir)) > 110:
        print(f"  WARNING: this path is {len(str(venv_dir))} characters long; Windows limits paths to 260 and some packages unpack deep folders.")
        print("  If pip fails with 'filename or extension is too long', use a shorter folder (see --venv).")
    if py.exists():
        print(f"  reusing {venv_dir}")
    else:
        print(f"  creating {venv_dir}")
        venv.EnvBuilder(with_pip=True).create(venv_dir)
        if not py.exists():
            die("The virtual environment was created but has no Python. On Debian/Ubuntu install it with: sudo apt install python3-venv")

    # 2. dependencies
    step(2, total, "Installing dependencies (a few minutes the first time)")
    result = subprocess.run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(ROOT / "requirements.txt")])
    if result.returncode:
        die(
            "pip install failed (see above). Common causes:\n"
            "  - Windows 'filename or extension is too long' (WinError 206): the folder path is too deep. Move the project to a\n"
            "    shorter path, or keep it and use a short environment: python scripts/setup_local.py --venv C:/okf-venv\n"
            "  - a Python version without prebuilt packages for faiss-cpu or psycopg2-binary: try Python 3.11\n"
            "  - no internet access, or a proxy that pip is not configured for"
        )

    # 3. .env
    step(3, total, "Configuration (.env)")
    env_path, example = ROOT / ".env", ROOT / ".env.example"
    if env_path.exists():
        print("  .env already exists; leaving it as it is")
    else:
        shutil.copy(example, env_path)
        print("  created .env from .env.example")
    missing = missing_keys(env_path)
    if missing:
        print(f"  ACTION NEEDED: open {env_path} and set {', '.join(missing)}")

    # 4. database
    if not args.skip_db:
        step(4, total, "Database (PostgreSQL must already be installed and running)")
        cmd = [str(py), str(ROOT / "scripts" / "db_setup.py")]
        for flag, value in (("--host", args.pg_host), ("--port", args.pg_port), ("--user", args.pg_user), ("--password", args.pg_password)):
            if value:
                cmd += [flag, value]
        if args.reset_db:
            cmd.append("--reset")
        if args.yes:
            cmd.append("--yes")
        if subprocess.run(cmd, cwd=ROOT).returncode:
            die("Database setup did not finish. Fix the problem above and run this script again (it is safe to re-run).")

    step(total, total, "Ready")
    run = f'"{py}" -m uvicorn src.main:app --reload'
    print(f"  Start the API (from {ROOT}):\n    {run}\n  Then open http://localhost:8000/docs  (health check: http://localhost:8000/health)")
    print("  Chat UI: see okf-chat-ui/README.md (npm install, then npm start).")

    if args.start:
        if missing:
            die(f"Not starting the API: set {', '.join(missing)} in .env first, then run: {run}")
        print("\nStarting the API (Ctrl+C to stop) ...")
        try:
            subprocess.run([str(py), "-m", "uvicorn", "src.main:app", "--reload"], cwd=ROOT)
        except KeyboardInterrupt:
            pass
    elif missing:
        print(f"\nRemember: set {', '.join(missing)} in .env before starting.")


if __name__ == "__main__":
    main()
