# ============================================================
#  web_dashboard.py — Flask web dashboard for remote access
# ============================================================
import threading
import sys
import os
import database as db

try:
    from flask import Flask, render_template, jsonify, request
except ImportError:
    print("[WEB] Flask not installed. Run: pip install flask")
    Flask = None

_app = None
_server_thread = None


def _bundle_dir():
    """Where bundled data files live (templates/, static/).
    PyInstaller --onefile: sys._MEIPASS (temp extraction dir).
    Normal run: same as script dir."""
    if getattr(sys, '_MEIPASS', None):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


_BASE_DIR = _bundle_dir()


def _create_app():
    app = Flask(__name__,
                template_folder=os.path.join(_BASE_DIR, "templates"),
                static_folder=os.path.join(_BASE_DIR, "static"))

    @app.route("/")
    def index():
        platforms = db.list_platforms()
        users = db.list_users()
        sessions = db.list_sessions()
        return render_template("index.html",
                               platforms=platforms, users=users,
                               sessions=sessions)

    @app.route("/replay/<int:session_id>")
    def replay(session_id):
        session = db.get_session(session_id)
        if session is None:
            return "Session introuvable", 404
        # Get board dims from platform
        board_w, board_h = 50, 30
        try:
            platforms = db.list_platforms()
            for pid, pname, pw, ph in platforms:
                if pid == session.get("platform_id"):
                    board_w, board_h = pw, ph
                    break
        except Exception:
            pass
        return render_template("replay.html", session=session,
                               board_w=board_w, board_h=board_h)

    # ── API endpoints ────────────────────────────────────────

    @app.route("/api/sessions")
    def api_sessions():
        pid = request.args.get("platform_id", type=int)
        uid = request.args.get("user_id", type=int)
        sessions = db.list_sessions(platform_id=pid, user_id=uid)
        return jsonify(sessions)

    @app.route("/api/session/<int:session_id>")
    def api_session(session_id):
        session = db.get_session(session_id)
        if session is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(session)

    @app.route("/api/session/<int:session_id>/samples")
    def api_samples(session_id):
        samples = db.get_samples(session_id)
        result = []
        for t_ms, w0, w1, w2, w3, cx, cy in samples:
            result.append({
                "t": t_ms, "w0": w0, "w1": w1, "w2": w2, "w3": w3,
                "cx": cx, "cy": cy
            })
        return jsonify(result)

    @app.route("/api/platforms")
    def api_platforms():
        return jsonify(db.list_platforms())

    @app.route("/api/users")
    def api_users():
        return jsonify(db.list_users())

    return app


def start_web_server(port: int = 5000):
    """Start Flask in a daemon thread. Returns the thread."""
    global _app, _server_thread
    if Flask is None:
        raise RuntimeError("Flask n'est pas installe (pip install flask)")

    db.init_db()
    _app = _create_app()

    def run():
        _app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    _server_thread = threading.Thread(target=run, daemon=True)
    _server_thread.start()
    return _server_thread


def stop_web_server():
    """Flask dev server doesn't support clean shutdown, but since it's
    a daemon thread it will stop when the main app exits."""
    global _app
    _app = None
