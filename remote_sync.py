# ============================================================
#  remote_sync.py — Send stats + auto-update from Hostinger
# ============================================================
import threading
import time
import json
import platform
import uuid
import os
import sys
import tempfile
import subprocess

try:
    from urllib.request import Request, urlopen
    from urllib.error import URLError
except ImportError:
    Request = urlopen = URLError = None

import database as db


def _app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


_SETTINGS_PATH = os.path.join(_app_dir(), "cm_settings.json")

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL = 60
# Check for updates every N heartbeats (= every 5 min)
UPDATE_CHECK_EVERY = 5


def _load_settings():
    try:
        with open(_SETTINGS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_settings(data):
    try:
        current = _load_settings()
        current.update(data)
        with open(_SETTINGS_PATH, "w") as f:
            json.dump(current, f)
    except Exception:
        pass


def _get_app_id():
    """Unique ID for this installation, persisted in settings."""
    settings = _load_settings()
    app_id = settings.get("app_id")
    if not app_id:
        app_id = str(uuid.uuid4())[:12]
        _save_settings({"app_id": app_id})
    return app_id


def _get_app_name():
    """Human-readable name for this installation."""
    settings = _load_settings()
    return settings.get("app_name", platform.node())


def build_payload(app_version, is_recording=False, connected=False):
    """Build the JSON payload to send to the remote server."""
    stats = db.get_stats()
    return {
        "app_id": _get_app_id(),
        "app_name": _get_app_name(),
        "app_version": app_version,
        "hostname": platform.node(),
        "os": f"{platform.system()} {platform.release()}",
        "status": "online",
        "is_recording": is_recording,
        "connected": connected,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),

        # Aggregate stats
        "user_count": stats["user_count"],
        "platform_count": stats["platform_count"],
        "session_count": stats["session_count"],
        "sample_count": stats["sample_count"],
        "total_duration_sec": stats["total_duration_sec"],

        # Detail
        "users": stats["users"],
        "platforms": stats["platforms"],
        "recent_sessions": stats["recent_sessions"],
    }


# ── Auto-update logic ────────────────────────────────────────

def _check_for_update(base_url, api_key, current_version):
    """Check if a newer version is available on the server.
    Returns (new_version, download_url) or (None, None)."""
    if Request is None:
        return None, None
    try:
        # base_url = https://ibenji.fr/plancheadmin/cm_api.php
        # version endpoint = https://ibenji.fr/plancheadmin/cm_api.php?action=version
        url = base_url + "?action=version"
        req = Request(url, headers={"X-Api-Key": api_key})
        resp = urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))
        server_ver = int(data.get("version", 0))
        download_url = data.get("download_url", "")
        print(f"[UPDATE] Server version: {server_ver}, current: {current_version}")
        if server_ver > current_version and download_url:
            return server_ver, download_url
    except Exception as e:
        print(f"[UPDATE] check failed: {e}")
    return None, None


def _download_and_apply(download_url, api_key):
    """Download new exe, create a .bat that swaps it, and exit."""
    if not getattr(sys, 'frozen', False):
        print("[UPDATE] Skipped: not running as .exe")
        return False

    current_exe = sys.executable
    app_dir = os.path.dirname(current_exe)
    exe_name = os.path.basename(current_exe)
    new_exe = os.path.join(app_dir, exe_name + ".new")
    bat_path = os.path.join(app_dir, "_update.bat")

    try:
        # Download new exe
        print(f"[UPDATE] Downloading from {download_url}...")
        req = Request(download_url, headers={"X-Api-Key": api_key})
        resp = urlopen(req, timeout=120)
        data = resp.read()

        if len(data) < 100000:
            print(f"[UPDATE] Download too small ({len(data)} bytes), aborting")
            return False

        # Validate PE header (Windows executable must start with MZ)
        if data[:2] != b"MZ":
            print(f"[UPDATE] Downloaded file is not a valid .exe "
                  f"(header: {data[:20]}), aborting")
            return False

        with open(new_exe, "wb") as f:
            f.write(data)
        print(f"[UPDATE] Downloaded {len(data)} bytes -> {new_exe}")

        # Create .bat that waits, replaces, restarts
        bat_content = f'''@echo off
echo Mise a jour en cours...
timeout /t 3 /nobreak >nul
:retry
del "{current_exe}" >nul 2>&1
if exist "{current_exe}" (
    timeout /t 1 /nobreak >nul
    goto retry
)
move "{new_exe}" "{current_exe}"
echo Mise a jour terminee. Redemarrage...
timeout /t 5 /nobreak >nul
start "" "{current_exe}"
del "%~f0"
'''
        with open(bat_path, "w") as f:
            f.write(bat_content)

        print("[UPDATE] Launching updater and exiting...")
        subprocess.Popen(
            ["cmd", "/c", bat_path],
            creationflags=subprocess.CREATE_NO_WINDOW,
            cwd=app_dir)
        return True

    except Exception as e:
        print(f"[UPDATE] Failed: {e}")
        # Cleanup
        try:
            if os.path.exists(new_exe):
                os.remove(new_exe)
        except Exception:
            pass
        return False


class RemoteSync:
    """Background thread: periodic heartbeats + auto-update check."""

    def __init__(self, server_url=None, api_key=None, app_version=1):
        self._server_url = server_url
        self._api_key = api_key or ""
        self._app_version = app_version
        self._running = False
        self._thread = None
        self._is_recording = False
        self._connected = False
        self._last_error = ""
        self._last_success = ""
        self._heartbeat_count = 0
        # Callback called when an update is ready (app should exit)
        self.on_update_ready = None

    @property
    def is_running(self):
        return self._running

    @property
    def last_error(self):
        return self._last_error

    @property
    def last_success(self):
        return self._last_success

    @property
    def server_url(self):
        return self._server_url

    def update_state(self, is_recording=False, connected=False):
        """Update live state (called from main app)."""
        self._is_recording = is_recording
        self._connected = connected

    def start(self, server_url=None, api_key=None):
        if server_url:
            self._server_url = server_url
        if api_key:
            self._api_key = api_key
        if not self._server_url:
            self._last_error = "URL serveur non configuree"
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        # Check for updates immediately at startup
        self._try_update()

        while self._running:
            self._send()
            self._heartbeat_count += 1

            # Check for updates periodically
            if self._heartbeat_count % UPDATE_CHECK_EVERY == 0:
                self._try_update()

            time.sleep(HEARTBEAT_INTERVAL)

        # Send offline status on stop
        try:
            payload = build_payload(self._app_version,
                                    self._is_recording, self._connected)
            payload["status"] = "offline"
            self._post(payload)
        except Exception:
            pass

    def _send(self):
        try:
            payload = build_payload(self._app_version,
                                    self._is_recording, self._connected)
            self._post(payload)
            self._last_success = time.strftime("%H:%M:%S")
            self._last_error = ""
            return True
        except Exception as e:
            self._last_error = str(e)[:80]
            return False

    def _post(self, payload):
        if Request is None:
            raise RuntimeError("urllib not available")
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self._api_key,
        }
        req = Request(self._server_url, data=data, headers=headers, method="POST")
        try:
            resp = urlopen(req, timeout=10)
            resp.read()
        except URLError as e:
            raise RuntimeError(f"Connexion echouee: {e.reason}")

    def _try_update(self):
        """Check server for a newer version and apply if found."""
        try:
            new_ver, dl_url = _check_for_update(
                self._server_url, self._api_key, self._app_version)
            if new_ver is not None:
                print(f"[UPDATE] New version {new_ver} available (current: {self._app_version})")
                success = _download_and_apply(dl_url, self._api_key)
                if success and self.on_update_ready:
                    self._new_version = new_ver
                    self.on_update_ready()
        except Exception as e:
            print(f"[UPDATE] Error: {e}")
