# ============================================================
#  web_dashboard.py — Flask web dashboard for remote access
# ============================================================
import threading
import sys
import os
import database as db

try:
    from flask import Flask, render_template, jsonify, request, Response
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

    # ── Export endpoints ──────────────────────────────────────

    def _format_timecode(t_ms):
        total_s = t_ms / 1000.0
        h = int(total_s // 3600)
        m = int((total_s % 3600) // 60)
        s = total_s % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}"

    @app.route("/api/session/<int:session_id>/export/csv")
    def api_export_csv(session_id):
        session = db.get_session(session_id)
        if session is None:
            return jsonify({"error": "not found"}), 404
        samples = db.get_samples(session_id)
        if not samples:
            return jsonify({"error": "no samples"}), 404

        import io, csv
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=";")
        buf.write(f"# Session #{session_id}\n")
        buf.write(f"# Utilisateur: {session.get('user_name', '?')}\n")
        buf.write(f"# Plateforme: {session.get('platform_name', '?')}\n")
        buf.write(f"# Date: {session.get('started_at', '')}\n")
        buf.write(f"# Duree: {session.get('duration_sec', 0):.1f}s\n")
        buf.write(f"# Samples: {len(samples)}\n")
        writer.writerow(["timecode", "t_ms", "t_sec",
                         "w0_g", "w1_g", "w2_g", "w3_g", "total_g",
                         "com_x", "com_y"])
        for t_ms, w0, w1, w2, w3, cx, cy in samples:
            total = w0 + w1 + w2 + w3
            writer.writerow([
                _format_timecode(t_ms), t_ms, round(t_ms / 1000.0, 3),
                round(w0, 1), round(w1, 1), round(w2, 1), round(w3, 1),
                round(total, 1), round(cx, 6), round(cy, 6),
            ])

        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition":
                      f"attachment; filename=session_{session_id}.csv"})

    @app.route("/api/session/<int:session_id>/export/txt")
    def api_export_txt(session_id):
        session = db.get_session(session_id)
        if session is None:
            return jsonify({"error": "not found"}), 404
        samples = db.get_samples(session_id)
        if not samples:
            return jsonify({"error": "no samples"}), 404

        lines = []
        lines.append(f"Session #{session_id}")
        lines.append(f"Utilisateur: {session.get('user_name', '?')}")
        lines.append(f"Plateforme: {session.get('platform_name', '?')}")
        lines.append(f"Date: {session.get('started_at', '')}")
        lines.append(f"Duree: {session.get('duration_sec', 0):.1f}s")
        lines.append(f"Samples: {len(samples)}")
        lines.append("-" * 90)
        header = ["timecode", "t_ms", "t_sec",
                   "w0_g", "w1_g", "w2_g", "w3_g", "total_g",
                   "com_x", "com_y"]
        lines.append("\t".join(header))
        lines.append("-" * 90)
        for t_ms, w0, w1, w2, w3, cx, cy in samples:
            total = w0 + w1 + w2 + w3
            lines.append("\t".join(str(v) for v in [
                _format_timecode(t_ms), t_ms, round(t_ms / 1000.0, 3),
                round(w0, 1), round(w1, 1), round(w2, 1), round(w3, 1),
                round(total, 1), round(cx, 6), round(cy, 6),
            ]))

        return Response(
            "\n".join(lines),
            mimetype="text/plain",
            headers={"Content-Disposition":
                      f"attachment; filename=session_{session_id}.txt"})

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
