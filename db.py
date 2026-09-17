import sqlite3
from pathlib import Path
import bcrypt

DB = Path(__file__).parent / "users.db"


def _con():
    return sqlite3.connect(DB)


def init():
    con = _con()
    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            pw_hash TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS login_events (
            id INTEGER PRIMARY KEY,
            ts TEXT DEFAULT CURRENT_TIMESTAMP,
            email TEXT,
            ok INTEGER,
            ip TEXT,
            ua TEXT
        )
    """)
    con.commit()
    con.close()


def add_user(email: str, password: str) -> None:
    pw = password.encode("utf-8")[:72]
    h = bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")
    con = _con()
    con.execute(
        "INSERT OR REPLACE INTO users(email, pw_hash) VALUES (?,?)",
        (email, h),
    )
    con.commit()
    con.close()


def verify(email: str, password: str) -> bool:
    con = _con()
    row = con.execute(
        "SELECT pw_hash FROM users WHERE email=?", (email,)
    ).fetchone()
    con.close()
    if not row:
        return False
    pw = password.encode("utf-8")[:72]
    return bcrypt.checkpw(pw, row[0].encode("utf-8"))


def log_event(email: str, ok: bool, ip: str, ua: str) -> None:
    con = _con()
    con.execute(
        "INSERT INTO login_events(email, ok, ip, ua) VALUES (?,?,?,?)",
        (email, int(ok), ip, ua),
    )
    con.commit()
    con.close()