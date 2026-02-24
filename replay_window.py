# ============================================================
#  replay_window.py — Session browser + replay viewer
# ============================================================
import tkinter as tk
from tkinter import ttk, messagebox
import database as db


class SessionBrowser(tk.Toplevel):
    """Window listing all recorded sessions with filters."""

    def __init__(self, master, themes, current_theme, settings_funcs):
        super().__init__(master)
        self.title("Historique des sessions")
        self.geometry("820x520")
        self.minsize(600, 400)

        self._themes = themes
        self._current_theme = current_theme
        self._load_settings, self._save_settings = settings_funcs

        t = themes[current_theme]
        self.configure(bg=t["bg"])

        self._build_ui(t)
        self._refresh_filters()
        self._refresh_list()

    def _build_ui(self, t):
        # ── Filter bar ───────────────────────────────────────
        fbar = tk.Frame(self, bg=t["bg_card"], padx=10, pady=8)
        fbar.pack(fill="x", padx=10, pady=(10, 4))

        tk.Label(fbar, text="Utilisateur:", font=("Segoe UI", 10),
                 fg=t["text_secondary"], bg=t["bg_card"]).pack(side="left")
        self._user_var = tk.StringVar(value="-- Tous --")
        self._user_combo = ttk.Combobox(fbar, textvariable=self._user_var,
                                         state="readonly", width=20)
        self._user_combo.pack(side="left", padx=(4, 12))
        self._user_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_list())

        tk.Label(fbar, text="Plateforme:", font=("Segoe UI", 10),
                 fg=t["text_secondary"], bg=t["bg_card"]).pack(side="left")
        self._plat_var = tk.StringVar(value="-- Toutes --")
        self._plat_combo = ttk.Combobox(fbar, textvariable=self._plat_var,
                                         state="readonly", width=22)
        self._plat_combo.pack(side="left", padx=(4, 12))
        self._plat_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_list())

        btn_refresh = tk.Button(fbar, text="Actualiser", font=("Segoe UI", 9),
                                fg=t["text_primary"], bg=t["tare_bg"],
                                activebackground=t["tare_hover"],
                                relief="flat", cursor="hand2", padx=8,
                                command=self._refresh_list)
        btn_refresh.pack(side="left")

        self._lbl_count = tk.Label(fbar, text="", font=("Segoe UI", 9),
                                    fg=t["text_dim"], bg=t["bg_card"])
        self._lbl_count.pack(side="right")

        # ── Session list ─────────────────────────────────────
        list_frame = tk.Frame(self, bg=t["bg"])
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ("id", "date", "user", "platform", "duration", "samples")
        self._tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                                   selectmode="browse")
        self._tree.heading("id", text="ID")
        self._tree.heading("date", text="Date")
        self._tree.heading("user", text="Utilisateur")
        self._tree.heading("platform", text="Plateforme")
        self._tree.heading("duration", text="Duree")
        self._tree.heading("samples", text="Samples")

        self._tree.column("id", width=50, anchor="center")
        self._tree.column("date", width=160, anchor="w")
        self._tree.column("user", width=140, anchor="w")
        self._tree.column("platform", width=160, anchor="w")
        self._tree.column("duration", width=90, anchor="center")
        self._tree.column("samples", width=80, anchor="center")

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical",
                                   command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._tree.bind("<Double-1>", self._on_double_click)

        # ── Bottom buttons ───────────────────────────────────
        bbar = tk.Frame(self, bg=t["bg"])
        bbar.pack(fill="x", padx=10, pady=(0, 10))

        btn_replay = tk.Button(bbar, text="RELECTURE", font=("Segoe UI", 10, "bold"),
                               fg=t["text_primary"], bg=t["accent_blue"],
                               activebackground=t["accent_teal"],
                               relief="flat", cursor="hand2", padx=14, pady=6,
                               command=self._open_replay)
        btn_replay.pack(side="left")

        btn_delete = tk.Button(bbar, text="SUPPRIMER", font=("Segoe UI", 10, "bold"),
                               fg=t["text_primary"], bg=t["accent_red"],
                               activebackground=t["accent_amber"],
                               relief="flat", cursor="hand2", padx=14, pady=6,
                               command=self._delete_session)
        btn_delete.pack(side="right")

    def _refresh_filters(self):
        users = db.list_users()
        self._users_map = {u[1]: u[0] for u in users}
        self._user_combo["values"] = ["-- Tous --"] + [u[1] for u in users]

        platforms = db.list_platforms()
        self._plats_map = {p[1]: p[0] for p in platforms}
        self._plat_combo["values"] = ["-- Toutes --"] + [p[1] for p in platforms]

    def _refresh_list(self):
        for row in self._tree.get_children():
            self._tree.delete(row)

        user_name = self._user_var.get()
        plat_name = self._plat_var.get()
        uid = self._users_map.get(user_name)
        pid = self._plats_map.get(plat_name)

        sessions = db.list_sessions(platform_id=pid, user_id=uid)
        for s in sessions:
            dur = s.get("duration_sec") or 0
            if dur >= 60:
                dur_str = f"{int(dur // 60)}m {int(dur % 60)}s"
            else:
                dur_str = f"{dur:.1f}s"
            self._tree.insert("", "end", values=(
                s["id"],
                s.get("started_at", ""),
                s.get("user_name", "?"),
                s.get("platform_name", "?"),
                dur_str,
                s.get("sample_count", 0),
            ))
        self._lbl_count.config(text=f"{len(sessions)} session(s)")

    def _get_selected_id(self) -> int:
        sel = self._tree.selection()
        if not sel:
            return None
        values = self._tree.item(sel[0], "values")
        return int(values[0])

    def _on_double_click(self, event):
        self._open_replay()

    def _open_replay(self):
        sid = self._get_selected_id()
        if sid is None:
            return
        ReplayViewer(self, sid, self._themes, self._current_theme)

    def _delete_session(self):
        sid = self._get_selected_id()
        if sid is None:
            return
        if messagebox.askyesno("Supprimer", f"Supprimer la session #{sid} ?",
                               parent=self):
            db.delete_session(sid)
            self._refresh_list()


# ============================================================
#  Replay Viewer
# ============================================================

SENSOR_NAMES = ["Haut-Droit", "Haut-Gauche", "Bas-Droit", "Bas-Gauche"]


class ReplayViewer(tk.Toplevel):
    """Replay a recorded session with animated board."""

    def __init__(self, master, session_id: int, themes: dict, current_theme: str):
        super().__init__(master)
        self._themes = themes
        self._theme = current_theme
        self._session_id = session_id

        session = db.get_session(session_id)
        if session is None:
            messagebox.showerror("Erreur", "Session introuvable", parent=self)
            self.destroy()
            return

        self._session = session
        self._samples = db.get_samples(session_id)
        if not self._samples:
            messagebox.showinfo("Vide", "Aucun echantillon dans cette session",
                               parent=self)
            self.destroy()
            return

        self.title(f"Relecture — Session #{session_id}")
        self.geometry("1000x700")
        self.minsize(700, 500)

        t = themes[current_theme]
        self.configure(bg=t["bg"])

        self._playing = False
        self._frame_idx = 0
        self._speed = 1.0
        self._trail = []
        self.TRAIL_LENGTH = 15
        self._after_id = None

        self._board_w_cm = session.get("board_width_cm") or 50
        self._board_h_cm = session.get("board_height_cm") or 30

        # Try to get board dims from platform
        try:
            platforms = db.list_platforms()
            for pid, pname, pw, ph in platforms:
                if pid == session.get("platform_id"):
                    self._board_w_cm = pw
                    self._board_h_cm = ph
                    break
        except Exception:
            pass

        self._board_ratio = self._board_w_cm / self._board_h_cm

        self._build_ui(t)
        self._draw_board()
        self._show_frame(0)

    def _build_ui(self, t):
        # ── Info bar ─────────────────────────────────────────
        info = tk.Frame(self, bg=t["bg_card"], padx=10, pady=6)
        info.pack(fill="x", padx=8, pady=(8, 4))

        user_name = self._session.get("user_name", "?")
        plat_name = self._session.get("platform_name", "?")
        date_str  = self._session.get("started_at", "")
        n_samples = len(self._samples)
        dur = self._session.get("duration_sec") or 0

        tk.Label(info, text=f"Session #{self._session_id}",
                 font=("Segoe UI", 12, "bold"),
                 fg=t["accent_blue"], bg=t["bg_card"]).pack(side="left")
        tk.Label(info, text=f"  {user_name}  |  {plat_name}  |  {date_str}"
                           f"  |  {n_samples} samples  |  {dur:.1f}s",
                 font=("Segoe UI", 9),
                 fg=t["text_secondary"], bg=t["bg_card"]).pack(side="left", padx=10)

        # ── Main area ────────────────────────────────────────
        main = tk.Frame(self, bg=t["bg"])
        main.pack(fill="both", expand=True, padx=8, pady=0)

        # Left: weight display
        left = tk.Frame(main, bg=t["bg"], width=200)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        sensor_colors = t["sensor_colors"]
        self._weight_labels = []
        for i in range(4):
            card = tk.Frame(left, bg=t["bg_card"], padx=8, pady=4,
                            highlightbackground=sensor_colors[i],
                            highlightthickness=1)
            card.pack(fill="x", pady=2)
            tk.Label(card, text=SENSOR_NAMES[i], font=("Segoe UI", 9),
                     fg=sensor_colors[i], bg=t["bg_card"]).pack(side="left")
            lbl = tk.Label(card, text="0.000 kg", font=("Consolas", 14, "bold"),
                           fg=t["text_primary"], bg=t["bg_card"])
            lbl.pack(side="right")
            self._weight_labels.append(lbl)

        total_card = tk.Frame(left, bg=t["bg_card"], padx=8, pady=6,
                              highlightbackground=t["accent_blue"],
                              highlightthickness=2)
        total_card.pack(fill="x", pady=(8, 4))
        tk.Label(total_card, text="TOTAL", font=("Segoe UI", 9),
                 fg=t["text_secondary"], bg=t["bg_card"]).pack(side="left")
        self._total_label = tk.Label(total_card, text="0.000 kg",
                                      font=("Consolas", 14, "bold"),
                                      fg=t["accent_blue"], bg=t["bg_card"])
        self._total_label.pack(side="right")

        self._coord_label = tk.Label(left, text="X: 0.0%   Y: 0.0%",
                                      font=("Segoe UI", 10),
                                      fg=t["accent_teal"], bg=t["bg"])
        self._coord_label.pack(pady=(8, 0))

        self._time_label = tk.Label(left, text="0.000 s",
                                     font=("Consolas", 12),
                                     fg=t["text_secondary"], bg=t["bg"])
        self._time_label.pack(pady=(4, 0))

        self._frame_label = tk.Label(left, text=f"0 / {len(self._samples)}",
                                      font=("Segoe UI", 9),
                                      fg=t["text_dim"], bg=t["bg"])
        self._frame_label.pack(pady=(2, 0))

        # Right: canvas
        self._canvas = tk.Canvas(main, bg=t["bg_canvas"], highlightthickness=1,
                                  highlightbackground=t["board_outline"])
        self._canvas.pack(side="right", fill="both", expand=True)

        self._com_h = self._canvas.create_line(0, 0, 0, 0,
                                                fill=t["cross_color"], width=2)
        self._com_v = self._canvas.create_line(0, 0, 0, 0,
                                                fill=t["cross_color"], width=2)
        self._com_lbl = self._canvas.create_text(0, 0, text="CoM",
                                                   fill=t["com_color"],
                                                   font=("Segoe UI", 9, "bold"))

        self._canvas.bind("<Configure>", lambda e: self._draw_board())

        # ── Control bar ──────────────────────────────────────
        ctrl = tk.Frame(self, bg=t["bg_card"], padx=10, pady=6)
        ctrl.pack(fill="x", padx=8, pady=(4, 8))

        self._btn_play = tk.Button(ctrl, text="PLAY", font=("Segoe UI", 10, "bold"),
                                    fg=t["text_primary"], bg=t["accent_green"],
                                    activebackground=t["accent_teal"],
                                    relief="flat", cursor="hand2", padx=12,
                                    command=self._toggle_play)
        self._btn_play.pack(side="left")

        btn_reset = tk.Button(ctrl, text="DEBUT", font=("Segoe UI", 9),
                              fg=t["text_primary"], bg=t["tare_bg"],
                              activebackground=t["tare_hover"],
                              relief="flat", cursor="hand2", padx=8,
                              command=lambda: self._seek(0))
        btn_reset.pack(side="left", padx=(8, 4))

        # Speed buttons
        for spd, label in [(0.25, "0.25x"), (0.5, "0.5x"), (1.0, "1x"),
                           (2.0, "2x"), (4.0, "4x")]:
            b = tk.Button(ctrl, text=label, font=("Segoe UI", 9),
                          fg=t["text_secondary"], bg=t["tare_bg"],
                          activebackground=t["tare_hover"],
                          relief="flat", cursor="hand2", padx=6,
                          command=lambda s=spd: self._set_speed(s))
            b.pack(side="left", padx=2)

        # Slider
        self._slider_var = tk.IntVar(value=0)
        self._slider = tk.Scale(ctrl, from_=0, to=max(0, len(self._samples) - 1),
                                 orient="horizontal", variable=self._slider_var,
                                 showvalue=False, bg=t["bg_card"], fg=t["text_primary"],
                                 troughcolor=t["bg"], highlightthickness=0,
                                 command=self._on_slider)
        self._slider.pack(side="left", fill="x", expand=True, padx=(10, 0))

    # ── Board drawing ────────────────────────────────────────

    def _draw_board(self):
        t = self._themes[self._theme]
        c = self._canvas
        cw = c.winfo_width()
        ch = c.winfo_height()
        if cw < 80 or ch < 80:
            return

        c.delete("board_static")

        margin = 50
        avail_w = cw - 2 * margin
        avail_h = ch - 2 * margin
        ratio = self._board_ratio

        if avail_w / avail_h > ratio:
            bh = avail_h
            bw = bh * ratio
        else:
            bw = avail_w
            bh = bw / ratio

        cx, cy = cw / 2, ch / 2
        self._bl = cx - bw / 2
        self._br = cx + bw / 2
        self._bt = cy - bh / 2
        self._bb = cy + bh / 2
        self._bcx = cx
        self._bcy = cy

        # Board fill
        c.create_rectangle(self._bl, self._bt, self._br, self._bb,
                           fill=t["board_fill"], outline="", tags="board_static")

        # Grid
        n_cols = int(self._board_w_cm // 5)
        n_rows = int(self._board_h_cm // 5)
        sx = bw / n_cols
        sy = bh / n_rows
        for i in range(1, n_cols):
            gx = self._bl + i * sx
            c.create_line(gx, self._bt, gx, self._bb,
                          fill=t["grid_color"], tags="board_static")
        for i in range(1, n_rows):
            gy = self._bt + i * sy
            c.create_line(self._bl, gy, self._br, gy,
                          fill=t["grid_color"], tags="board_static")

        # Center cross
        c.create_line(cx, self._bt, cx, self._bb,
                      fill=t["board_outline"], dash=(6, 4), tags="board_static")
        c.create_line(self._bl, cy, self._br, cy,
                      fill=t["board_outline"], dash=(6, 4), tags="board_static")

        # Board outline
        c.create_rectangle(self._bl, self._bt, self._br, self._bb,
                           outline=t["board_outline"], width=2, tags="board_static")

        # Corner sensors
        corners = [(self._br, self._bt), (self._bl, self._bt),
                   (self._br, self._bb), (self._bl, self._bb)]
        sensor_colors = t["sensor_colors"]
        cap_r = 12
        self._sensor_texts = []
        for idx, (sx, sy) in enumerate(corners):
            c.create_oval(sx - cap_r, sy - cap_r, sx + cap_r, sy + cap_r,
                          fill=sensor_colors[idx], outline=t["text_primary"],
                          width=1, tags="board_static")
            tx_off = -24 if idx % 2 == 0 else 24
            ty_off = -16 if idx < 2 else 16
            txt = c.create_text(sx + tx_off, sy + ty_off, text="0.00 kg",
                                fill=sensor_colors[idx], font=("Consolas", 8),
                                tags="board_static")
            self._sensor_texts.append(txt)
            c.create_text(sx, sy, text=str(idx + 1), fill="white",
                          font=("Segoe UI", 8, "bold"), tags="board_static")

        c.tag_raise(self._com_h)
        c.tag_raise(self._com_v)
        c.tag_raise(self._com_lbl)

    # ── Playback ─────────────────────────────────────────────

    def _show_frame(self, idx):
        if idx < 0 or idx >= len(self._samples):
            return
        self._frame_idx = idx
        self._slider_var.set(idx)

        t_ms, w0, w1, w2, w3, com_x, com_y = self._samples[idx]
        t = self._themes[self._theme]

        weights = [w0, w1, w2, w3]
        total = sum(weights)

        for i in range(4):
            self._weight_labels[i].config(text=f"{weights[i]/1000:.3f} kg")
        self._total_label.config(text=f"{total/1000:.3f} kg")
        self._time_label.config(text=f"{t_ms / 1000:.3f} s")
        self._frame_label.config(text=f"{idx + 1} / {len(self._samples)}")
        self._coord_label.config(text=f"X: {com_x*100:+.1f}%   Y: {com_y*100:+.1f}%")

        # Canvas sensor values
        if hasattr(self, "_sensor_texts"):
            for i in range(4):
                self._canvas.itemconfig(self._sensor_texts[i],
                                        text=f"{weights[i]/1000:.2f} kg")

        # CoM position on canvas
        if hasattr(self, "_bl"):
            if total > 1:
                x_pos = self._bcx + com_x * (self._br - self._bl) / 2
                y_pos = self._bcy + com_y * (self._bb - self._bt) / 2
                x_pos = max(self._bl, min(self._br, x_pos))
                y_pos = max(self._bt, min(self._bb, y_pos))
            else:
                x_pos, y_pos = self._bcx, self._bcy

            # Trail
            self._trail.append((x_pos, y_pos))
            if len(self._trail) > self.TRAIL_LENGTH:
                self._trail = self._trail[-self.TRAIL_LENGTH:]

            self._canvas.delete("trail")
            bg_rgb = _hex_to_rgb(t["bg_canvas"])
            cr_rgb = _hex_to_rgb(t["cross_color"])
            for ti, (tx, ty) in enumerate(self._trail[:-1]):
                alpha = ti / self.TRAIL_LENGTH
                r = int(bg_rgb[0] + (cr_rgb[0] - bg_rgb[0]) * alpha)
                g = int(bg_rgb[1] + (cr_rgb[1] - bg_rgb[1]) * alpha)
                b = int(bg_rgb[2] + (cr_rgb[2] - bg_rgb[2]) * alpha)
                sz = 1.5 + alpha * 3
                self._canvas.create_oval(tx - sz, ty - sz, tx + sz, ty + sz,
                                         fill=f"#{r:02x}{g:02x}{b:02x}",
                                         outline="", tags="trail")

            cross_sz = 14
            self._canvas.coords(self._com_h, x_pos - cross_sz, y_pos,
                                x_pos + cross_sz, y_pos)
            self._canvas.coords(self._com_v, x_pos, y_pos - cross_sz,
                                x_pos, y_pos + cross_sz)
            self._canvas.coords(self._com_lbl, x_pos, y_pos - cross_sz - 10)
            self._canvas.tag_raise(self._com_h)
            self._canvas.tag_raise(self._com_v)
            self._canvas.tag_raise(self._com_lbl)

    def _toggle_play(self):
        t = self._themes[self._theme]
        if self._playing:
            self._playing = False
            self._btn_play.config(text="PLAY", bg=t["accent_green"])
            if self._after_id:
                self.after_cancel(self._after_id)
                self._after_id = None
        else:
            if self._frame_idx >= len(self._samples) - 1:
                self._frame_idx = 0
                self._trail = []
            self._playing = True
            self._btn_play.config(text="PAUSE", bg=t["accent_amber"])
            self._play_step()

    def _play_step(self):
        if not self._playing:
            return
        if self._frame_idx >= len(self._samples) - 1:
            self._playing = False
            t = self._themes[self._theme]
            self._btn_play.config(text="PLAY", bg=t["accent_green"])
            return

        self._show_frame(self._frame_idx)

        # Calculate delay based on actual sample timing
        curr_t = self._samples[self._frame_idx][0]
        next_idx = self._frame_idx + 1
        if next_idx < len(self._samples):
            next_t = self._samples[next_idx][0]
            delay_ms = max(1, int((next_t - curr_t) / self._speed))
        else:
            delay_ms = 16

        self._frame_idx += 1
        self._after_id = self.after(delay_ms, self._play_step)

    def _set_speed(self, speed):
        self._speed = speed

    def _seek(self, idx):
        self._trail = []
        self._show_frame(int(idx))

    def _on_slider(self, val):
        if not self._playing:
            self._trail = []
            self._show_frame(int(val))

    def destroy(self):
        self._playing = False
        if self._after_id:
            self.after_cancel(self._after_id)
        super().destroy()


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
