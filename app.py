"""DSE English / Chinese essay upload inbox (marking done by teacher's Grok assistant)."""

from __future__ import annotations

import hashlib
import json
import os
from functools import wraps
from pathlib import Path

import hmac

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from emarker import db

BASE_DIR = Path(__file__).resolve().parent
_upload_dir = os.environ.get("UPLOAD_DIR")
UPLOAD_DIR = Path(_upload_dir) if _upload_dir else BASE_DIR / "uploads"
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif"}

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-essay-marker-change-me")
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
db.init_db()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def teacher_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "teacher":
            flash("只有老師可以進入呢頁。", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)

    return wrapped


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return db.get_user_by_id(uid)


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXT


def save_uploads(files, submission_id: int, kind: str) -> list[str]:
    """Save files under uploads/<submission_id>/ as question_01.ext / essay_01.ext."""
    saved: list[str] = []
    folder = UPLOAD_DIR / str(submission_id)
    folder.mkdir(parents=True, exist_ok=True)
    index = 0
    for f in files:
        if not f or not f.filename:
            continue
        if not allowed_file(f.filename):
            continue
        index += 1
        ext = Path(secure_filename(f.filename)).suffix.lower() or ".jpg"
        if ext not in ALLOWED_EXT:
            ext = ".jpg"
        name = f"{kind}_{index:02d}{ext}"
        path = folder / name
        # Rewind stream in case the same FileStorage was read earlier.
        try:
            f.stream.seek(0)
        except Exception:
            pass
        f.save(path)
        saved.append(str(path))
    return saved


def can_view_submission(user, row) -> bool:
    if not user or not row:
        return False
    if user["role"] == "teacher":
        return True
    return row["user_id"] == user["id"]


def submission_image_urls(row) -> tuple[list[dict], list[dict]]:
    """Build {path, url, name} lists for templates."""
    q_items, e_items = [], []
    for p in db.parse_paths(row, "question_paths"):
        name = Path(p).name
        q_items.append(
            {
                "path": p,
                "name": name,
                "url": url_for(
                    "serve_upload",
                    submission_id=row["id"],
                    filename=name,
                ),
            }
        )
    for p in db.parse_paths(row, "essay_paths"):
        name = Path(p).name
        e_items.append(
            {
                "path": p,
                "name": name,
                "url": url_for(
                    "serve_upload",
                    submission_id=row["id"],
                    filename=name,
                ),
            }
        )
    return q_items, e_items


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = db.get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            next_url = request.args.get("next") or url_for("dashboard")
            return redirect(next_url)
        error = "用戶名或密碼錯誤。"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    if user["role"] == "teacher":
        submissions = db.list_all_submissions()
        students = db.list_students()
        return render_template(
            "teacher_dashboard.html",
            user=user,
            submissions=submissions,
            students=students,
            status_label=db.status_label,
        )
    submissions = db.list_submissions_for_user(user["id"])
    return render_template(
        "student_dashboard.html",
        user=user,
        submissions=submissions,
        status_label=db.status_label,
    )


@app.route("/upload", methods=["GET", "POST"])
@app.route("/mark", methods=["GET", "POST"])  # legacy alias
@login_required
def upload_new():
    user = current_user()
    if request.method == "POST":
        student_note = (request.form.get("student_note") or "").strip()
        subject = db.normalize_subject(request.form.get("subject"))
        question_files = request.files.getlist("question_images")
        essay_files = request.files.getlist("essay_images")

        # Validate before creating DB row
        raw_subject = (request.form.get("subject") or "").strip().lower()
        if raw_subject not in db.VALID_SUBJECTS:
            flash("請選擇科目：英文作文或中文作文。", "error")
            return render_template("upload_new.html", user=user)
        q_ok = any(
            f and f.filename and allowed_file(f.filename) for f in question_files
        )
        e_ok = any(
            f and f.filename and allowed_file(f.filename) for f in essay_files
        )
        if not q_ok:
            flash("請上傳至少一張題目圖片（JPG/PNG 等）。", "error")
            return render_template("upload_new.html", user=user)
        if not e_ok:
            flash("請上傳至少一張作文圖片（JPG/PNG 等）。", "error")
            return render_template("upload_new.html", user=user)

        sid = db.create_submission(
            user_id=user["id"],
            student_note=student_note,
            question_paths=[],
            essay_paths=[],
            subject=subject,
        )
        q_saved = save_uploads(question_files, sid, "question")
        e_saved = save_uploads(essay_files, sid, "essay")
        if not q_saved or not e_saved:
            flash("儲存圖片失敗，請再試一次。", "error")
            return render_template("upload_new.html", user=user)

        def _md5s(paths):
            out = []
            for p in paths:
                with open(p, "rb") as fh:
                    out.append(hashlib.md5(fh.read()).hexdigest())
            return out

        q_hashes = set(_md5s(q_saved))
        e_hashes = set(_md5s(e_saved))
        if q_hashes & e_hashes:
            flash(
                "注意：題目圖同作文圖有相同檔案。若你明明上傳咗唔同相，請重新交卷，提交前用預覽確認兩邊唔同。",
                "error",
            )

        db.update_submission_paths(sid, q_saved, e_saved)
        flash("已交卷，等候批改。本站只負責交卷；批改由老師的 Grok 助手處理。", "ok")
        return redirect(url_for("submission_detail", submission_id=sid))

    return render_template("upload_new.html", user=user)


@app.route("/submission/<int:submission_id>", methods=["GET", "POST"])
@app.route("/mark/<int:submission_id>", methods=["GET", "POST"])
@login_required
def submission_detail(submission_id: int):
    user = current_user()
    row = db.get_submission(submission_id)
    if not row:
        abort(404)
    if not can_view_submission(user, row):
        abort(403)

    if request.method == "POST":
        if user["role"] != "teacher":
            abort(403)
        action = (request.form.get("action") or "save_marking").strip()
        if action == "delete":
            ok, msg = db.delete_submission(submission_id, uploads_root=UPLOAD_DIR)
            flash(msg, "ok" if ok else "error")
            return redirect(url_for("dashboard"))
        marking_text = request.form.get("marking_text") or ""
        if db.save_marking(submission_id, marking_text):
            flash("已儲存批改結果。", "ok")
            return redirect(url_for("submission_detail", submission_id=submission_id))
        flash("批改內容唔可以留空。", "error")

    q_imgs, e_imgs = submission_image_urls(row)
    return render_template(
        "submission_detail.html",
        user=user,
        submission=row,
        question_images=q_imgs,
        essay_images=e_imgs,
        status_label=db.status_label,
    )


@app.route("/uploads/<int:submission_id>/<path:filename>")
@login_required
def serve_upload(submission_id: int, filename: str):
    user = current_user()
    row = db.get_submission(submission_id)
    if not row or not can_view_submission(user, row):
        abort(403)
    # Only allow basenames that belong to this submission
    safe_name = Path(filename).name
    folder = UPLOAD_DIR / str(submission_id)
    if not (folder / safe_name).is_file():
        abort(404)
    return send_from_directory(folder, safe_name)


@app.route("/teacher/students", methods=["GET", "POST"])
@teacher_required
def teacher_students():
    user = current_user()
    message = None
    error = None
    if request.method == "POST":
        action = (request.form.get("action") or "create").strip()
        if action == "create":
            username = request.form.get("username") or ""
            password = request.form.get("password") or ""
            ok, msg = db.create_student(username, password)
            if ok:
                message = msg
            else:
                error = msg
        elif action == "edit":
            try:
                target_id = int(request.form.get("user_id") or "0")
            except ValueError:
                target_id = 0
            target = db.get_user_by_id(target_id)
            if not target:
                error = "搵唔到呢個帳號。"
            elif target["role"] == "teacher" and target["id"] != user["id"]:
                error = "唔可以改其他老師帳號。"
            elif target["role"] not in ("student", "teacher"):
                error = "無效嘅帳號類型。"
            else:
                new_username = request.form.get("username")
                new_password = request.form.get("password")  # empty = keep
                ok, msg = db.update_user_credentials(
                    target_id,
                    username=new_username,
                    password=new_password if new_password else None,
                )
                if ok:
                    message = msg
                    # If teacher edited own username, refresh session
                    if target_id == user["id"]:
                        updated = db.get_user_by_id(user["id"])
                        if updated:
                            session["username"] = updated["username"]
                            user = updated
                else:
                    error = msg
        else:
            error = "未知操作。"

    students = db.list_students()
    # Refresh teacher row in case credentials changed
    teacher = db.get_user_by_id(user["id"])
    return render_template(
        "teacher_students.html",
        user=teacher or user,
        students=students,
        message=message,
        error=error,
    )




def _teacher_api_key() -> str:
    return (os.environ.get("TEACHER_API_KEY") or "").strip()


def teacher_api_required(view):
    """Require X-Teacher-Key header matching TEACHER_API_KEY (constant-time)."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        expected = _teacher_api_key()
        if not expected:
            return jsonify({"error": "teacher API not configured"}), 503
        provided = request.headers.get("X-Teacher-Key") or ""
        if not hmac.compare_digest(provided, expected):
            return jsonify({"error": "unauthorized"}), 401
        return view(*args, **kwargs)

    return wrapped


def _basenames(paths: list[str]) -> list[str]:
    return [Path(p).name for p in paths]


def submission_api_dict(row, *, include_marking: bool = False) -> dict:
    """Serialize a submission row for teacher API JSON responses."""
    data = {
        "id": row["id"],
        "username": row["username"],
        "student_note": row["student_note"] or "",
        "subject": db.get_subject(row),
        "subject_label": db.subject_label(db.get_subject(row)),
        "status": row["status"],
        "created_at": row["created_at"],
        "question_files": _basenames(db.parse_paths(row, "question_paths")),
        "essay_files": _basenames(db.parse_paths(row, "essay_paths")),
    }
    if include_marking:
        data["marking_text"] = row["marking_text"] or ""
    return data


def _submission_allowed_filenames(row) -> set[str]:
    names = set(_basenames(db.parse_paths(row, "question_paths")))
    names.update(_basenames(db.parse_paths(row, "essay_paths")))
    return names


@app.route("/api/pending")
@teacher_api_required
def api_pending():
    rows = db.list_pending_submissions()
    return jsonify({"submissions": [submission_api_dict(r) for r in rows]})


@app.route("/api/submission/<int:submission_id>")
@teacher_api_required
def api_submission_detail(submission_id: int):
    row = db.get_submission(submission_id)
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify(submission_api_dict(row, include_marking=True))


@app.route("/api/submission/<int:submission_id>/file/<path:filename>")
@teacher_api_required
def api_submission_file(submission_id: int, filename: str):
    row = db.get_submission(submission_id)
    if not row:
        return jsonify({"error": "not found"}), 404
    safe_name = Path(filename).name
    if safe_name not in _submission_allowed_filenames(row):
        return jsonify({"error": "file not allowed"}), 404
    folder = UPLOAD_DIR / str(submission_id)
    if not (folder / safe_name).is_file():
        return jsonify({"error": "file not found"}), 404
    return send_from_directory(folder, safe_name)


@app.route("/api/submission/<int:submission_id>/marking", methods=["POST"])
@teacher_api_required
def api_save_marking(submission_id: int):
    row = db.get_submission(submission_id)
    if not row:
        return jsonify({"error": "not found"}), 404
    payload = request.get_json(silent=True) or {}
    marking_text = payload.get("marking_text")
    if marking_text is None:
        return jsonify({"error": "marking_text required"}), 400
    if not db.save_marking(submission_id, marking_text):
        return jsonify({"error": "marking_text cannot be empty"}), 400
    return jsonify({"ok": True})


@app.context_processor
def inject_globals():
    return {
        "app_title": "DSE 作文交卷",
        "status_label": db.status_label,
        "subject_label": db.subject_label,
        "get_subject": db.get_subject,
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
