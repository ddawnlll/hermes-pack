"""
db.connection: Postgres connection adapter for Hephaestus v0.6 (DL-1, #95).

Single point of read/write for the Postgres side of the v0.6 state.
Phase A of the file -> Postgres cutover (A-4 #79): this adapter mirrors
file state into DB. Phase B: it becomes the source of truth and exports
to file on read.

Two main operations:
  - connect(): returns a psycopg2 connection (or compatible).
  - migrate(): applies pending migrations from db/migrations/.

Configuration is loaded from:
  - Environment variables: PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE.
  - OR the per-adapter config at adapters/<adapter>/db/config.yaml.

Usage:
    from db.connection import connect, migrate
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT mode FROM hephaestus.control_state")
            mode = cur.fetchone()[0]
    migrate()  # apply pending migrations
"""

from __future__ import annotations

import hashlib
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:
    import psycopg2
except ImportError:  # pragma: no cover
    psycopg2 = None

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"
ADAPTERS_DIR = REPO_ROOT / "adapters"

# The migration_id -> filename mapping. Add new migrations here as
# they are created; migrate() will apply them in order.
MIGRATIONS = (
    ("000_initial", "000_initial.sql"),
)


def _load_adapter_config(adapter: str | None) -> dict:
    """Load config from adapters/<adapter>/db/config.yaml, if it exists.

    Returns {} if the file is missing or the adapter is None. The
    config is small: a few keys (host, port, dbname, user, password_file).
    """
    if not adapter:
        return {}
    cfg_path = ADAPTERS_DIR / adapter / "db" / "config.yaml"
    if not cfg_path.exists():
        return {}
    # Minimal YAML parsing — no external dep. The file is flat key:value.
    out: dict = {}
    for line in cfg_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def connect(adapter: str | None = None):
    """Return a psycopg2 connection.

    Precedence:
      1. Adapter config (adapters/<adapter>/db/config.yaml).
      2. Environment variables (PGHOST, PGPORT, ...).
      3. Defaults: localhost:5432, user=postgres, db=hephaestus.
    """
    if psycopg2 is None:
        raise RuntimeError(
            "psycopg2 not installed. Install with `pip install psycopg2-binary`."
        )

    cfg = _load_adapter_config(adapter)
    host = cfg.get("host") or os.environ.get("PGHOST", "localhost")
    port = int(cfg.get("port") or os.environ.get("PGPORT", "5432"))
    user = cfg.get("user") or os.environ.get("PGUSER", "postgres")
    password = cfg.get("password") or os.environ.get("PGPASSWORD", "")
    dbname = cfg.get("dbname") or os.environ.get("PGDATABASE", "hephaestus")

    return psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname,
    )


@contextmanager
def transaction(adapter: str | None = None) -> Iterator:
    """Yield a connection inside a transaction; commit on success, rollback on error."""
    conn = connect(adapter)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _checksum_sql(sql: str) -> str:
    return "sha256:" + hashlib.sha256(sql.encode("utf-8")).hexdigest()


def _is_applied(conn, migration_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM hephaestus.migration_log WHERE migration_id = %s",
            (migration_id,),
        )
        return cur.fetchone() is not None


def _record_applied(conn, migration_id: str, checksum: str, applied_by: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO hephaestus.migration_log (migration_id, applied_by, checksum) "
            "VALUES (%s, %s, %s) ON CONFLICT (migration_id) DO NOTHING",
            (migration_id, applied_by, checksum),
        )


def migrate(adapter: str | None = None, applied_by: str = "db.connection") -> list[str]:
    """Apply pending migrations in order. Returns the list of applied migration_ids.

    Idempotent: re-running migrate() on an up-to-date DB is a no-op.
    """
    applied: list[str] = []
    with transaction(adapter) as conn:
        for migration_id, filename in MIGRATIONS:
            if _is_applied(conn, migration_id):
                continue
            sql_path = MIGRATIONS_DIR / filename
            if not sql_path.exists():
                raise FileNotFoundError(f"Migration file not found: {sql_path}")
            sql = sql_path.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
            _record_applied(conn, migration_id, _checksum_sql(sql), applied_by)
            applied.append(migration_id)
    return applied


def get_control_mode(adapter: str | None = None) -> str:
    """Read the current mode from hephaestus.control_state. Returns one of
    'live', 'paused', 'frozen', 'killed'. The caller MUST OR this with
    templates/control.yaml:mode per A-4 #79.
    """
    with transaction(adapter) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT mode FROM hephaestus.control_state WHERE id = 1")
            row = cur.fetchone()
            if row is None:
                return "live"  # bootstrap default
            return row[0]


def set_control_mode(mode: str, *, observed_by: str, adapter: str | None = None) -> None:
    """Update hephaestus.control_state. Validates mode is in the enum.

    A-4 #79 invariant: the DB write here is half of the OR'ling. The
    file side (templates/control.yaml:mode) MUST be read separately and
    OR'd with this value.
    """
    if mode not in ("live", "paused", "frozen", "killed"):
        raise ValueError(f"invalid mode: {mode!r}")
    with transaction(adapter) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE hephaestus.control_state "
                "SET mode = %s, last_observed_at = now(), last_observed_by = %s "
                "WHERE id = 1",
                (mode, observed_by),
            )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print("usage: python3 -m db.connection [migrate|get-mode|set-mode] ...", file=sys.stderr)
        return 0

    cmd = args[0]
    if cmd == "migrate":
        applied = migrate()
        print(f"applied: {applied or 'none (already up to date)'}")
        return 0
    if cmd == "get-mode":
        print(get_control_mode())
        return 0
    if cmd == "set-mode":
        if len(args) < 2:
            print("usage: set-mode <mode> [--by <actor>]", file=sys.stderr)
            return 2
        mode = args[1]
        by = "cli"
        if "--by" in args:
            by = args[args.index("--by") + 1]
        set_control_mode(mode, observed_by=by)
        print(f"set mode={mode} by={by}")
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
