"""SQLite helpers for users and submissions (upload inbox)."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterator, Optional

from werkzeug.security import generate_password_hash

_data_dir = os.environ.get("DATA_DIR")
_database_path = os.environ.get("DATABASE_PATH")
if _data_dir:
    DB_PATH = Path(_data_dir) / "app.db"
elif _database_path:
    DB_PATH = Path(_database_path)
else:
    DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"
HK_TZ = timezone(timedelta(hours=8))

SEED_USERS = [
    ("teacher", "teacher123", "teacher"),
    ("student1", "student123", "student"),
    ("student2", "student123", "student"),
]

STATUS_LABELS = {
    "pending": "待批改",
    "marked": "已批改",
}

SUBJECT_LABELS = {
    "english": "英文",
    "chinese": "中文",
}

VALID_SUBJECTS = frozenset({"english", "chinese"})


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.now(HK_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('teacher', 'student')),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                student_note TEXT,
                subject TEXT NOT NULL DEFAULT 'english',
                question_paths TEXT NOT NULL DEFAULT '[]',
                essay_paths TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'pending',
                marking_text TEXT,
                marked_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """
        )

        # Migrate older schemas in place.
        cols = _column_names(conn, "submissions")
        if "marking_text" not in cols:
            conn.execute("ALTER TABLE submissions ADD COLUMN marking_text TEXT")
        if "marked_at" not in cols:
            conn.execute("ALTER TABLE submissions ADD COLUMN marked_at TEXT")
        if "subject" not in cols:
            conn.execute(
                "ALTER TABLE submissions ADD COLUMN subject TEXT NOT NULL DEFAULT 'english'"
            )

        # Copy legacy result_markdown → marking_text if present and empty.
        cols = _column_names(conn, "submissions")
        if "result_markdown" in cols:
            conn.execute(
                """
                UPDATE submissions
                SET marking_text = result_markdown
                WHERE (marking_text IS NULL OR marking_text = '')
                  AND result_markdown IS NOT NULL AND result_markdown != ''
                """
            )
            conn.execute(
                """
                UPDATE submissions
                SET status = 'marked',
                    marked_at = COALESCE(marked_at, completed_at, created_at)
                WHERE status IN ('done', 'completed')
                   OR (marking_text IS NOT NULL AND marking_text != '' AND status NOT IN ('pending', 'marked'))
                """
            )
            # Normalize leftover processing/error to pending if no marking
            conn.execute(
                """
                UPDATE submissions
                SET status = 'pending'
                WHERE status NOT IN ('pending', 'marked')
                  AND (marking_text IS NULL OR marking_text = '')
                """
            )

        for username, password, role in SEED_USERS:
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                    (username, generate_password_hash(password), role, now_iso()),
                )

        # The demo teacher account must remain a teacher even if an older
        # database was initialized with an incorrect role.
        conn.execute(
            "UPDATE users SET role = 'teacher' WHERE username = 'teacher'"
        )

        # Opt-in reset for demo deployments. This only touches the seeded
        # accounts and leaves all other users and submissions unchanged.
        if os.environ.get("RESET_SEED_PASSWORDS") == "1":
            for username, password, _role in SEED_USERS:
                conn.execute(
                    "UPDATE users SET password_hash = ? WHERE username = ?",
                    (generate_password_hash(password), username),
                )


def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()


def get_user_by_id(user_id: int) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()




def username_taken(username: str, exclude_user_id: Optional[int] = None) -> bool:
    """Return True if username already belongs to another user."""
    username = (username or "").strip()
    with get_db() as conn:
        if exclude_user_id is None:
            row = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id FROM users WHERE username = ? AND id != ?",
                (username, exclude_user_id),
            ).fetchone()
        return row is not None


def update_user_credentials(
    user_id: int,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> tuple[bool, str]:
    """Update username and/or password. Empty password means leave unchanged."""
    row = get_user_by_id(user_id)
    if not row:
        return False, "搵唔到呢個用戶。"

    new_username = None
    if username is not None:
        new_username = username.strip()
        if not new_username:
            return False, "用戶名唔可以留空。"
        if len(new_username) < 2:
            return False, "用戶名至少要 2 個字元。"
        if username_taken(new_username, exclude_user_id=user_id):
            return False, "呢個用戶名已經存在。"

    new_hash = None
    if password is not None and password != "":
        if len(password) < 4:
            return False, "密碼至少要 4 個字元。"
        new_hash = generate_password_hash(password)

    if new_username is None and new_hash is None:
        return False, "請輸入新用戶名，或填寫新密碼。"

    with get_db() as conn:
        if new_username is not None and new_hash is not None:
            conn.execute(
                "UPDATE users SET username = ?, password_hash = ? WHERE id = ?",
                (new_username, new_hash, user_id),
            )
            return True, f"已更新帳號「{new_username}」嘅用戶名同密碼。"
        if new_username is not None:
            conn.execute(
                "UPDATE users SET username = ? WHERE id = ?",
                (new_username, user_id),
            )
            return True, f"已更新用戶名為「{new_username}」。"
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, user_id),
        )
        return True, f"已更新「{row['username']}」嘅密碼。"


def create_student(username: str, password: str) -> tuple[bool, str]:
    username = username.strip()
    if not username or not password:
        return False, "用戶名同密碼都唔可以留空。"
    if len(username) < 2:
        return False, "用戶名至少要 2 個字元。"
    if len(password) < 4:
        return False, "密碼至少要 4 個字元。"
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'student', ?)",
                (username, generate_password_hash(password), now_iso()),
            )
        return True, f"已新增學生帳號：{username}"
    except sqlite3.IntegrityError:
        return False, "呢個用戶名已經存在。"


def list_students() -> list[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            "SELECT id, username, created_at FROM users WHERE role = 'student' ORDER BY username"
        ).fetchall()


def normalize_subject(subject: Optional[str]) -> str:
    """Return 'english' or 'chinese'; default english."""
    s = (subject or "").strip().lower()
    return s if s in VALID_SUBJECTS else "english"


def create_submission(
    user_id: int,
    student_note: str,
    question_paths: Optional[list[str]] = None,
    essay_paths: Optional[list[str]] = None,
    subject: str = "english",
) -> int:
    subject = normalize_subject(subject)
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO submissions
            (user_id, student_note, subject, question_paths, essay_paths, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                user_id,
                student_note,
                subject,
                json.dumps(question_paths or []),
                json.dumps(essay_paths or []),
                now_iso(),
            ),
        )
        return int(cur.lastrowid)


def update_submission_paths(
    submission_id: int,
    question_paths: list[str],
    essay_paths: list[str],
) -> None:
    with get_db() as conn:
        conn.execute(
            """
            UPDATE submissions
            SET question_paths = ?, essay_paths = ?
            WHERE id = ?
            """,
            (json.dumps(question_paths), json.dumps(essay_paths), submission_id),
        )


def save_marking(submission_id: int, marking_text: str) -> bool:
    """Write marking text and set status=marked. Returns False if missing."""
    text = (marking_text or "").strip()
    if not text:
        return False
    with get_db() as conn:
        cur = conn.execute(
            """
            UPDATE submissions
            SET status = 'marked',
                marking_text = ?,
                marked_at = ?
            WHERE id = ?
            """,
            (text, now_iso(), submission_id),
        )
        return cur.rowcount > 0




def delete_submission(submission_id: int, uploads_root: Optional[Path] = None) -> tuple[bool, str]:
    """Delete submission row and uploads/<id>/ folder. Returns (ok, message)."""
    import shutil

    row = get_submission(submission_id)
    if not row:
        return False, f"搵唔到交卷 #{submission_id}。"

    with get_db() as conn:
        cur = conn.execute("DELETE FROM submissions WHERE id = ?", (submission_id,))
        if cur.rowcount < 1:
            return False, f"刪除交卷 #{submission_id} 失敗。"

    root = uploads_root or Path("/workspace/essay-marker/uploads")
    folder = root / str(submission_id)
    if folder.is_dir():
        try:
            shutil.rmtree(folder)
        except OSError as e:
            return True, f"已刪除交卷 #{submission_id}，但清除圖片資料夾時出錯：{e}"

    return True, f"已刪除交卷 #{submission_id}（含上傳圖片）。"

def get_submission(submission_id: int) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            """
            SELECT s.*, u.username
            FROM submissions s
            JOIN users u ON u.id = s.user_id
            WHERE s.id = ?
            """,
            (submission_id,),
        ).fetchone()


def list_submissions_for_user(user_id: int) -> list[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            """
            SELECT s.*, u.username
            FROM submissions s
            JOIN users u ON u.id = s.user_id
            WHERE s.user_id = ?
            ORDER BY s.id DESC
            """,
            (user_id,),
        ).fetchall()


def list_all_submissions(limit: int = 200) -> list[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            """
            SELECT s.*, u.username
            FROM submissions s
            JOIN users u ON u.id = s.user_id
            ORDER BY s.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status or "—")


def subject_label(subject: Optional[str]) -> str:
    s = normalize_subject(subject)
    return SUBJECT_LABELS.get(s, "英文")


def get_subject(row: sqlite3.Row) -> str:
    """Safe subject from a submission row (legacy rows → english)."""
    try:
        raw = row["subject"]
    except (KeyError, IndexError):
        return "english"
    return normalize_subject(raw)


def parse_paths(row: sqlite3.Row, key: str) -> list[str]:
    raw = row[key] if key in row.keys() else "[]"
    try:
        data = json.loads(raw or "[]")
        return data if isinstance(data, list) else []
    except Exception:
        return []


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    return dict(row)


def list_pending_submissions(limit: int = 200) -> list[sqlite3.Row]:
    """Return submissions with status=pending, newest first."""
    with get_db() as conn:
        return conn.execute(
            """
            SELECT s.*, u.username
            FROM submissions s
            JOIN users u ON u.id = s.user_id
            WHERE s.status = 'pending'
            ORDER BY s.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
