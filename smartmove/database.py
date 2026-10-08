import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .config import DB, ROOT


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path=None):
    con = sqlite3.connect(str(path or DB), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=30000")
    return con


@contextmanager
def transaction(path=None):
    con = connect(path)
    try:
        con.execute("BEGIN IMMEDIATE")
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def rows(sql, params=(), con=None):
    own = con is None
    conn = con or connect()
    try:
        return [dict(x) for x in conn.execute(sql, params).fetchall()]
    finally:
        if own:
            conn.close()


def row(sql, params=(), con=None):
    found = rows(sql, params, con)
    return found[0] if found else None


def scalar(sql, params=(), con=None):
    result = row(sql, params, con)
    return next(iter(result.values())) if result else None


def schema(path=None):
    with connect(path) as con:
        con.executescript((ROOT / "sql/schema_sqlite.sql").read_text())
        con.execute("PRAGMA journal_mode=WAL")


def audit(con, user, action, entity, entity_id=None, before=None, after=None, request=None):
    def safe(value):
        if value is None:
            return None
        blocked = {"password", "password_hash", "token", "token_hash", "csrf_hash"}
        return json.dumps({k: v for k, v in value.items() if k not in blocked}, default=str)
    con.execute("INSERT INTO audit_log(user_id,actor,action,entity,entity_id,before_json,after_json,created_at,ip,user_agent) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (user.get("id") if user else None, user.get("email", "System") if user else "System", action, entity,
                 str(entity_id) if entity_id is not None else None, safe(before), safe(after), utcnow(),
                 request.client.host if request and request.client else None,
                 request.headers.get("user-agent", "")[:250] if request else None))
