# ============================================================
#  database.py — SQLite storage for Centre de Masse
# ============================================================
import sqlite3
import sys
import os
import time
from datetime import datetime


def _app_dir():
    """Return the directory where the exe (or script) lives.
    PyInstaller --onefile extracts to a temp dir (_MEIPASS) but
    we want the DB next to the real .exe."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


_DB_PATH = os.path.join(_app_dir(), "cm_data.db")


def _connect():
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _connect()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY,
            name       TEXT    UNIQUE NOT NULL,
            created_at TEXT    DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS platforms (
            id             INTEGER PRIMARY KEY,
            name           TEXT    UNIQUE NOT NULL,
            board_width_cm REAL    DEFAULT 50,
            board_height_cm REAL   DEFAULT 30,
            created_at     TEXT    DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id           INTEGER PRIMARY KEY,
            user_id      INTEGER REFERENCES users(id),
            platform_id  INTEGER REFERENCES platforms(id),
            started_at   TEXT    NOT NULL,
            ended_at     TEXT,
            duration_sec REAL,
            sample_count INTEGER DEFAULT 0,
            notes        TEXT
        );

        CREATE TABLE IF NOT EXISTS samples (
            id         INTEGER PRIMARY KEY,
            session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
            t_ms       INTEGER NOT NULL,
            w0         REAL,
            w1         REAL,
            w2         REAL,
            w3         REAL,
            com_x      REAL,
            com_y      REAL
        );

        CREATE INDEX IF NOT EXISTS idx_samples_session
            ON samples(session_id, t_ms);
    """)
    conn.commit()
    conn.close()


# ── Users ────────────────────────────────────────────────────

def add_user(name: str) -> int:
    conn = _connect()
    try:
        c = conn.execute("INSERT INTO users (name) VALUES (?)", (name,))
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def list_users() -> list:
    conn = _connect()
    rows = conn.execute("SELECT id, name FROM users ORDER BY name").fetchall()
    conn.close()
    return [(r["id"], r["name"]) for r in rows]


def delete_user(user_id: int):
    conn = _connect()
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


# ── Platforms ────────────────────────────────────────────────

def add_platform(name: str, width_cm: float = 50, height_cm: float = 30) -> int:
    conn = _connect()
    try:
        c = conn.execute(
            "INSERT INTO platforms (name, board_width_cm, board_height_cm) VALUES (?,?,?)",
            (name, width_cm, height_cm))
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def list_platforms() -> list:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, name, board_width_cm, board_height_cm FROM platforms ORDER BY name"
    ).fetchall()
    conn.close()
    return [(r["id"], r["name"], r["board_width_cm"], r["board_height_cm"]) for r in rows]


def delete_platform(platform_id: int):
    conn = _connect()
    conn.execute("DELETE FROM platforms WHERE id=?", (platform_id,))
    conn.commit()
    conn.close()


# ── Statistics (for remote monitoring) ───────────────────────

def get_stats() -> dict:
    """Return aggregate stats for remote monitoring."""
    conn = _connect()
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    plat_count = conn.execute("SELECT COUNT(*) FROM platforms").fetchone()[0]
    session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    sample_count = conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]

    # Total recording duration
    row = conn.execute(
        "SELECT COALESCE(SUM(duration_sec),0) AS total_dur FROM sessions"
    ).fetchone()
    total_duration = row[0]

    # Sessions per user
    rows = conn.execute("""
        SELECT u.name, COUNT(s.id) AS cnt,
               COALESCE(SUM(s.sample_count),0) AS samples,
               COALESCE(SUM(s.duration_sec),0) AS dur
        FROM users u
        LEFT JOIN sessions s ON s.user_id = u.id
        GROUP BY u.id ORDER BY cnt DESC
    """).fetchall()
    users_detail = [{"name": r[0], "sessions": r[1],
                     "samples": r[2], "duration_sec": r[3]} for r in rows]

    # Sessions per platform
    rows = conn.execute("""
        SELECT p.name, COUNT(s.id) AS cnt,
               COALESCE(SUM(s.sample_count),0) AS samples,
               COALESCE(SUM(s.duration_sec),0) AS dur
        FROM platforms p
        LEFT JOIN sessions s ON s.platform_id = p.id
        GROUP BY p.id ORDER BY cnt DESC
    """).fetchall()
    platforms_detail = [{"name": r[0], "sessions": r[1],
                         "samples": r[2], "duration_sec": r[3]} for r in rows]

    # Last 10 sessions
    rows = conn.execute("""
        SELECT s.id, s.started_at, s.duration_sec, s.sample_count,
               u.name AS user_name, p.name AS platform_name
        FROM sessions s
        LEFT JOIN users u ON s.user_id = u.id
        LEFT JOIN platforms p ON s.platform_id = p.id
        ORDER BY s.started_at DESC LIMIT 10
    """).fetchall()
    recent = [dict(r) for r in rows]

    conn.close()
    return {
        "user_count": user_count,
        "platform_count": plat_count,
        "session_count": session_count,
        "sample_count": sample_count,
        "total_duration_sec": total_duration,
        "users": users_detail,
        "platforms": platforms_detail,
        "recent_sessions": recent,
    }


# ── Sessions ─────────────────────────────────────────────────

def start_session(user_id: int, platform_id: int) -> int:
    conn = _connect()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c = conn.execute(
        "INSERT INTO sessions (user_id, platform_id, started_at) VALUES (?,?,?)",
        (user_id, platform_id, now))
    conn.commit()
    sid = c.lastrowid
    conn.close()
    return sid


def end_session(session_id: int, sample_count: int):
    conn = _connect()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Compute duration from started_at
    row = conn.execute(
        "SELECT started_at FROM sessions WHERE id=?", (session_id,)).fetchone()
    duration = 0.0
    if row:
        try:
            t0 = datetime.strptime(row["started_at"], "%Y-%m-%d %H:%M:%S")
            duration = (datetime.now() - t0).total_seconds()
        except Exception:
            pass
    conn.execute(
        "UPDATE sessions SET ended_at=?, duration_sec=?, sample_count=? WHERE id=?",
        (now, duration, sample_count, session_id))
    conn.commit()
    conn.close()


def get_session(session_id: int) -> dict:
    conn = _connect()
    row = conn.execute("""
        SELECT s.*, u.name AS user_name, p.name AS platform_name
        FROM sessions s
        LEFT JOIN users u ON s.user_id = u.id
        LEFT JOIN platforms p ON s.platform_id = p.id
        WHERE s.id=?
    """, (session_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def list_sessions(platform_id: int = None, user_id: int = None) -> list:
    conn = _connect()
    query = """
        SELECT s.id, s.started_at, s.ended_at, s.duration_sec, s.sample_count,
               s.notes, u.name AS user_name, p.name AS platform_name
        FROM sessions s
        LEFT JOIN users u ON s.user_id = u.id
        LEFT JOIN platforms p ON s.platform_id = p.id
        WHERE 1=1
    """
    params = []
    if platform_id is not None:
        query += " AND s.platform_id=?"
        params.append(platform_id)
    if user_id is not None:
        query += " AND s.user_id=?"
        params.append(user_id)
    query += " ORDER BY s.started_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_session(session_id: int):
    conn = _connect()
    conn.execute("DELETE FROM samples WHERE session_id=?", (session_id,))
    conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    conn.commit()
    conn.close()


# ── Samples ──────────────────────────────────────────────────

def insert_samples(session_id: int, data: list):
    """Bulk insert samples. data = list of (t_ms, w0, w1, w2, w3, com_x, com_y)."""
    if not data:
        return
    conn = _connect()
    conn.executemany(
        "INSERT INTO samples (session_id, t_ms, w0, w1, w2, w3, com_x, com_y) "
        "VALUES (?,?,?,?,?,?,?,?)",
        [(session_id, *row) for row in data])
    conn.commit()
    conn.close()


def get_samples(session_id: int) -> list:
    """Return list of (t_ms, w0, w1, w2, w3, com_x, com_y) sorted by time."""
    conn = _connect()
    rows = conn.execute(
        "SELECT t_ms, w0, w1, w2, w3, com_x, com_y "
        "FROM samples WHERE session_id=? ORDER BY t_ms",
        (session_id,)).fetchall()
    conn.close()
    return [tuple(r) for r in rows]


def get_sample_count(session_id: int) -> int:
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM samples WHERE session_id=?",
        (session_id,)).fetchone()
    conn.close()
    return row["cnt"] if row else 0


# ── Self-test ────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("[OK] Database initialized at", _DB_PATH)

    uid = add_user("Test User")
    print(f"[OK] User created: id={uid}")
    print("[OK] Users:", list_users())

    pid = add_platform("Plateforme Test", 50, 30)
    print(f"[OK] Platform created: id={pid}")
    print("[OK] Platforms:", list_platforms())

    sid = start_session(uid, pid)
    print(f"[OK] Session started: id={sid}")

    insert_samples(sid, [
        (0, 1000, 2000, 1500, 1800, 0.1, -0.05),
        (16, 1010, 2010, 1490, 1810, 0.12, -0.04),
        (32, 1020, 2020, 1480, 1820, 0.11, -0.06),
    ])
    print(f"[OK] Inserted 3 samples")

    end_session(sid, 3)
    session = get_session(sid)
    print(f"[OK] Session: {session}")

    samples = get_samples(sid)
    print(f"[OK] Samples: {samples}")

    # Clean up test data
    delete_session(sid)
    delete_user(uid)
    conn = _connect()
    conn.execute("DELETE FROM platforms WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    print("[OK] Test data cleaned up")
