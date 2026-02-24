# ============================================================
#  recorder.py — Session recording engine
# ============================================================
import time
import threading
import database as db

FLUSH_THRESHOLD = 500  # flush buffer every N samples


class SessionRecorder:
    """Records force platform samples into the database."""

    def __init__(self):
        self._session_id = None
        self._user_id = None
        self._platform_id = None
        self._start_time = 0.0
        self._buffer = []
        self._total_samples = 0
        self._lock = threading.Lock()
        self._recording = False

    # ── Properties ───────────────────────────────────────────

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def session_id(self) -> int:
        return self._session_id

    @property
    def start_time(self) -> float:
        return self._start_time

    @property
    def elapsed(self) -> float:
        if not self._recording:
            return 0.0
        return time.time() - self._start_time

    @property
    def sample_count(self) -> int:
        return self._total_samples

    # ── Control ──────────────────────────────────────────────

    def start(self, user_id: int, platform_id: int) -> int:
        """Start a new recording session. Returns session_id."""
        if self._recording:
            self.stop()

        db.init_db()
        self._session_id = db.start_session(user_id, platform_id)
        self._user_id = user_id
        self._platform_id = platform_id
        self._start_time = time.time()
        self._buffer = []
        self._total_samples = 0
        self._recording = True
        return self._session_id

    def record(self, t_ms: int, w0: float, w1: float, w2: float, w3: float,
               com_x: float, com_y: float):
        """Add a sample to the buffer. Call from the UI update loop."""
        if not self._recording:
            return
        with self._lock:
            self._buffer.append((t_ms, w0, w1, w2, w3, com_x, com_y))
            self._total_samples += 1
            if len(self._buffer) >= FLUSH_THRESHOLD:
                self._flush_locked()

    def flush(self):
        """Flush buffer to database."""
        with self._lock:
            self._flush_locked()

    def _flush_locked(self):
        """Internal flush (caller must hold the lock)."""
        if not self._buffer or self._session_id is None:
            return
        try:
            db.insert_samples(self._session_id, self._buffer)
        except Exception as e:
            print(f"[RECORDER] flush error: {e}")
        self._buffer = []

    def stop(self) -> int:
        """Stop recording and finalize the session. Returns session_id."""
        if not self._recording:
            return None
        self._recording = False
        self.flush()
        sid = self._session_id
        if sid is not None:
            try:
                db.end_session(sid, self._total_samples)
            except Exception as e:
                print(f"[RECORDER] end_session error: {e}")
        self._session_id = None
        return sid
