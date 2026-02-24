# ============================================================
#  Centre de Masse — Plateforme de Force
#  pip install pyserial flask
# ============================================================
import serial
import serial.tools.list_ports
import json, threading, time, math, os, sys, webbrowser
import tkinter as tk
from tkinter import font as tkfont, ttk, simpledialog

import database as db
from recorder import SessionRecorder
from replay_window import SessionBrowser
from remote_sync import RemoteSync


def _app_dir():
    """Real app directory (next to .exe or script)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

# ============================================================
# CONFIG
# ============================================================
APP_VERSION         = 4
NEAR_ZERO_THRESHOLD = 50
TARGET_NAME         = "ForcePlatform"
BOARD_WIDTH_CM      = 50
BOARD_HEIGHT_CM     = 30
BOARD_RATIO         = BOARD_WIDTH_CM / BOARD_HEIGHT_CM

# ============================================================
# THEMES
# ============================================================
THEMES = {
    "dark": {
        "bg":            "#0f172a",
        "bg_card":       "#1e293b",
        "bg_canvas":     "#0f172a",
        "accent_blue":   "#38bdf8",
        "accent_teal":   "#2dd4bf",
        "accent_green":  "#4ade80",
        "accent_amber":  "#fbbf24",
        "accent_red":    "#fb7185",
        "text_primary":  "#f1f5f9",
        "text_secondary":"#94a3b8",
        "text_dim":      "#475569",
        "grid_color":    "#1e293b",
        "board_outline": "#334155",
        "board_fill":    "#1e293b",
        "cross_color":   "#f85149",
        "com_color":     "#f85149",
        "tare_bg":       "#1e293b",
        "tare_hover":    "#334155",
        "cal_bg":        "#172554",
        "cal_hover":     "#1e3a5f",
        "btn_connect_bg":"#166534",
        "btn_connect_hv":"#15803d",
        "sensor_colors": ["#38bdf8", "#fb7185", "#4ade80", "#fbbf24"],
    },
    "light": {
        "bg":            "#f1f5f9",
        "bg_card":       "#ffffff",
        "bg_canvas":     "#f8fafc",
        "accent_blue":   "#2563eb",
        "accent_teal":   "#0d9488",
        "accent_green":  "#16a34a",
        "accent_amber":  "#d97706",
        "accent_red":    "#dc2626",
        "text_primary":  "#0f172a",
        "text_secondary":"#475569",
        "text_dim":      "#94a3b8",
        "grid_color":    "#e2e8f0",
        "board_outline": "#94a3b8",
        "board_fill":    "#ffffff",
        "cross_color":   "#dc2626",
        "com_color":     "#dc2626",
        "tare_bg":       "#e2e8f0",
        "tare_hover":    "#cbd5e1",
        "cal_bg":        "#dbeafe",
        "cal_hover":     "#bfdbfe",
        "btn_connect_bg":"#16a34a",
        "btn_connect_hv":"#15803d",
        "sensor_colors": ["#2563eb", "#dc2626", "#16a34a", "#d97706"],
    },
}

# ============================================================
# PREFERENCES (fichier JSON a cote du script)
# ============================================================
_SETTINGS_PATH = os.path.join(_app_dir(), "cm_settings.json")

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

# ============================================================
# THEME ACTIF — variables globales utilisees partout
# ============================================================
current_theme = _load_settings().get("theme", "dark")
if current_theme not in THEMES:
    current_theme = "dark"

def _sync_colors():
    global BG_DARK, BG_CARD, BG_CANVAS
    global ACCENT_BLUE, ACCENT_TEAL, ACCENT_GREEN, ACCENT_AMBER, ACCENT_RED
    global TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM
    global GRID_COLOR, BOARD_OUTLINE, BOARD_FILL
    global CROSS_COLOR, COM_COLOR
    global TARE_BG, TARE_HOVER, CAL_BG, CAL_HOVER
    global BTN_CONNECT_BG, BTN_CONNECT_HV
    global SENSOR_COLORS
    t = THEMES[current_theme]
    BG_DARK        = t["bg"]
    BG_CARD        = t["bg_card"]
    BG_CANVAS      = t["bg_canvas"]
    ACCENT_BLUE    = t["accent_blue"]
    ACCENT_TEAL    = t["accent_teal"]
    ACCENT_GREEN   = t["accent_green"]
    ACCENT_AMBER   = t["accent_amber"]
    ACCENT_RED     = t["accent_red"]
    TEXT_PRIMARY   = t["text_primary"]
    TEXT_SECONDARY = t["text_secondary"]
    TEXT_DIM       = t["text_dim"]
    GRID_COLOR     = t["grid_color"]
    BOARD_OUTLINE  = t["board_outline"]
    BOARD_FILL     = t["board_fill"]
    CROSS_COLOR    = t["cross_color"]
    COM_COLOR      = t["com_color"]
    TARE_BG        = t["tare_bg"]
    TARE_HOVER     = t["tare_hover"]
    CAL_BG         = t["cal_bg"]
    CAL_HOVER      = t["cal_hover"]
    BTN_CONNECT_BG = t["btn_connect_bg"]
    BTN_CONNECT_HV = t["btn_connect_hv"]
    SENSOR_COLORS  = list(t["sensor_colors"])

_sync_colors()

SENSOR_NAMES = ["Haut-Droit", "Haut-Gauche", "Bas-Droit", "Bas-Gauche"]

# ============================================================
# UTILITAIRES THEME
# ============================================================
def _hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def _build_color_map(old_name, new_name):
    old_t, new_t = THEMES[old_name], THEMES[new_name]
    cmap = {}
    for key in old_t:
        ov, nv = old_t[key], new_t[key]
        if isinstance(ov, str) and ov.startswith("#"):
            cmap[ov] = nv
        elif isinstance(ov, list):
            for o, n in zip(ov, nv):
                cmap[o] = n
    return cmap

def _retheme_widgets(widget, cmap):
    for prop in ("bg", "fg", "activebackground", "activeforeground",
                 "highlightbackground", "insertbackground"):
        try:
            val = str(widget.cget(prop))
            if val in cmap:
                widget.config(**{prop: cmap[val]})
        except Exception:
            pass
    for child in widget.winfo_children():
        _retheme_widgets(child, cmap)

# ============================================================
# ÉTAT
# ============================================================
raw_w         = [0, 0, 0, 0]
freq          = 0.0
last_received = time.time()
com_trail     = []
calib_offsets = [0] * 4
calib_scales  = [0.0] * 4
response_queue = []
resp_lock      = threading.Lock()
serial_conn    = None

# ── Database + Recorder + Remote Sync ────────────────────────
db.init_db()
recorder = SessionRecorder()
web_server_thread = None
web_server_running = False

# Remote sync (hardcoded — always on)
_REMOTE_URL = "https://ibenji.fr/plancheadmin/cm_api.php"
_REMOTE_KEY = "c4d1146e19f391e0b6901bcb88c32d10e7f6e5174d12f179bd7a1018b4c9c8e0"
remote_sync = RemoteSync(server_url=_REMOTE_URL, api_key=_REMOTE_KEY,
                         app_version=APP_VERSION)

# ============================================================
# LECTURE SÉRIE (thread daemon)
# ============================================================
def _read_loop():
    global serial_conn, freq, last_received
    while True:
        if serial_conn is None:
            time.sleep(0.05)
            continue
        try:
            line = serial_conn.readline().decode(errors="ignore").strip()
            if not line:
                continue
            data = json.loads(line)
            if "weight1" in data:
                raw_w[0] = max(0, data["weight1"])
                raw_w[1] = max(0, data["weight2"])
                raw_w[2] = max(0, data["weight3"])
                raw_w[3] = max(0, data["weight4"])
                now = time.time()
                d   = now - last_received
                if d > 0:
                    freq = 1.0 / d
                last_received = now
            elif "status" in data:
                with resp_lock:
                    response_queue.append(data)
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"[READ] {e}")
            serial_conn = None
            time.sleep(0.5)

threading.Thread(target=_read_loop, daemon=True).start()

def send_json(obj: dict):
    if serial_conn is None:
        return
    try:
        serial_conn.write((json.dumps(obj) + "\n").encode())
    except Exception as e:
        print(f"[SEND] {e}")

# ============================================================
# DETECTION DES PORTS
# ============================================================
def _is_target(port_info) -> bool:
    name = TARGET_NAME.lower()
    desc = (port_info.description or "").lower()
    hwid = (port_info.hwid or "").lower()
    mfr  = (getattr(port_info, "manufacturer", "") or "").lower()
    return name in desc or name in hwid or name in mfr

def _try_port(device: str, baud: int, timeout: float = 2.5):
    try:
        s = serial.Serial(device, baud, timeout=0.5)
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = s.readline().decode(errors="ignore").strip()
            if not raw:
                continue
            try:
                d = json.loads(raw)
                if "weight1" in d or "status" in d:
                    return s
            except json.JSONDecodeError:
                pass
        s.close()
    except Exception:
        pass
    return None

def list_ports():
    result = []
    for p in serial.tools.list_ports.comports():
        desc      = p.description or ""
        is_bt     = ("bluetooth" in desc.lower() or
                     "bth" in (p.hwid or "").lower() or
                     "standard serial" in desc.lower())
        is_target = _is_target(p)
        if is_target:
            label = f"[ForcePlatform] {p.device}  --  {desc}"
        elif is_bt:
            label = f"[BT] {p.device}  --  {desc}"
        else:
            label = f"{p.device}  --  {desc}"
        result.append((p.device, label, is_bt, is_target))
    result.sort(key=lambda x: (not x[3], not x[2], x[0]))
    return result

# ============================================================
# INTERFACE TKINTER
# ============================================================
root = tk.Tk()
root.title("Centre de Masse -- Plateforme de Force")
root.geometry("1280x800")
root.configure(bg=BG_DARK)
root.resizable(True, True)

# ── App icon ──
def _find_icon():
    """Locate icon.ico in bundle or next to script."""
    candidates = []
    if getattr(sys, 'frozen', False):
        candidates.append(os.path.join(sys._MEIPASS, 'icon.ico'))
        candidates.append(os.path.join(os.path.dirname(sys.executable), 'icon.ico'))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico'))
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None

_icon_path = _find_icon()
if _icon_path:
    try:
        root.iconbitmap(_icon_path)
    except Exception:
        pass

try:
    root.state("zoomed")
except Exception:
    pass

try:
    title_font  = tkfont.Font(family="Segoe UI", size=18, weight="bold")
    header_font = tkfont.Font(family="Segoe UI", size=12, weight="bold")
    value_font  = tkfont.Font(family="Consolas", size=18, weight="bold")
    label_font  = tkfont.Font(family="Segoe UI", size=10)
    small_font  = tkfont.Font(family="Segoe UI", size=9)
    btn_font    = tkfont.Font(family="Segoe UI", size=10, weight="bold")
    mono_small  = tkfont.Font(family="Consolas", size=8)
except Exception:
    title_font  = ("Arial", 18, "bold")
    header_font = ("Arial", 12, "bold")
    value_font  = ("Courier", 18, "bold")
    label_font  = ("Arial", 10)
    small_font  = ("Arial", 9)
    btn_font    = ("Arial", 10, "bold")
    mono_small  = ("Courier", 8)

# Style ttk
style = ttk.Style()
style.theme_use("clam")

def _update_ttk_style():
    style.configure("TCombobox",
                    fieldbackground=BG_CARD, background=BG_CARD,
                    foreground=TEXT_PRIMARY, selectbackground=ACCENT_BLUE,
                    selectforeground=BG_DARK, arrowcolor=TEXT_SECONDARY)
    style.map("TCombobox",
              fieldbackground=[("readonly", BG_CARD)],
              foreground=[("readonly", TEXT_PRIMARY)])

_update_ttk_style()

def _update_notebook_style():
    style.configure("LeftPanel.TNotebook", background=BG_DARK, borderwidth=0)
    style.configure("LeftPanel.TNotebook.Tab",
                    background=BG_CARD, foreground=TEXT_SECONDARY,
                    padding=[10, 5])
    style.map("LeftPanel.TNotebook.Tab",
              background=[("selected", BG_DARK)],
              foreground=[("selected", ACCENT_BLUE)])

_update_notebook_style()

# ── TITRE ────────────────────────────────────────────────────
title_frame = tk.Frame(root, bg=BG_DARK)
title_frame.pack(fill="x", padx=20, pady=(15, 5))
tk.Label(title_frame, text="CENTRE DE MASSE", font=title_font,
         fg=ACCENT_BLUE, bg=BG_DARK).pack(side="left")

btn_theme = tk.Button(
    title_frame,
    text=("\u2600" if current_theme == "dark" else "\u263e"),
    font=btn_font, fg=TEXT_SECONDARY, bg=BG_DARK,
    activebackground=BG_DARK, activeforeground=TEXT_PRIMARY,
    relief="flat", cursor="hand2", bd=0, padx=8)
btn_theme.pack(side="left", padx=(14, 0))

label_freq = tk.Label(title_frame, text="-- Hz",
                      font=label_font, fg=TEXT_SECONDARY, bg=BG_DARK)
label_freq.pack(side="right", padx=10)
label_status = tk.Label(title_frame, text="DECONNECTE",
                         font=small_font, fg=ACCENT_RED, bg=BG_DARK)
label_status.pack(side="right", padx=10)

# ── BARRE UTILISATEUR / PLATEFORME ────────────────────────────
user_plat_bar = tk.Frame(root, bg=BG_CARD, padx=14, pady=8,
                          highlightbackground=BOARD_OUTLINE, highlightthickness=1)
user_plat_bar.pack(fill="x", padx=20, pady=(0, 4))

up_row = tk.Frame(user_plat_bar, bg=BG_CARD)
up_row.pack(fill="x")

tk.Label(up_row, text="UTILISATEUR", font=btn_font,
         fg=TEXT_SECONDARY, bg=BG_CARD).pack(side="left", padx=(0, 6))

user_var = tk.StringVar()
user_combo = ttk.Combobox(up_row, textvariable=user_var,
                           state="readonly", width=18, font=label_font)
user_combo.pack(side="left", padx=(0, 4))

def _refresh_users():
    users = db.list_users()
    _user_id_map.clear()
    names = []
    for uid, uname in users:
        names.append(uname)
        _user_id_map[uname] = uid
    user_combo["values"] = names
    # Restore last selection
    saved = _load_settings().get("last_user", "")
    if saved in names:
        user_var.set(saved)
    elif names:
        user_combo.current(0)

_user_id_map = {}

def _add_user():
    name = simpledialog.askstring("Nouvel utilisateur", "Nom :",
                                   parent=root)
    if name and name.strip():
        try:
            db.add_user(name.strip())
        except Exception:
            pass
        _refresh_users()
        user_var.set(name.strip())

btn_add_user = tk.Button(up_row, text="+", command=_add_user,
                          font=btn_font, fg=ACCENT_GREEN, bg=TARE_BG,
                          activebackground=TARE_HOVER, relief="flat",
                          cursor="hand2", padx=6, pady=2)
btn_add_user.pack(side="left", padx=(2, 2))

def _del_user():
    uname = user_var.get()
    uid = _user_id_map.get(uname)
    if uid is None:
        return
    from tkinter import messagebox
    # Count sessions for this user
    sessions = db.list_sessions(user_id=uid)
    msg = f"Supprimer l'utilisateur \"{uname}\" ?"
    if sessions:
        msg += f"\n\n{len(sessions)} session(s) associee(s) seront aussi supprimees."
    if messagebox.askyesno("Supprimer utilisateur", msg, parent=root):
        for s in sessions:
            db.delete_session(s["id"])
        db.delete_user(uid)
        _refresh_users()

btn_del_user = tk.Button(up_row, text="-", command=_del_user,
                          font=btn_font, fg=ACCENT_RED, bg=TARE_BG,
                          activebackground=TARE_HOVER, relief="flat",
                          cursor="hand2", padx=6, pady=2)
btn_del_user.pack(side="left", padx=(0, 16))

tk.Label(up_row, text="PLATEFORME", font=btn_font,
         fg=TEXT_SECONDARY, bg=BG_CARD).pack(side="left", padx=(0, 6))

plat_var = tk.StringVar()
plat_combo = ttk.Combobox(up_row, textvariable=plat_var,
                           state="readonly", width=22, font=label_font)
plat_combo.pack(side="left", padx=(0, 4))

def _refresh_platforms():
    platforms = db.list_platforms()
    _plat_id_map.clear()
    names = []
    for pid, pname, pw, ph in platforms:
        names.append(pname)
        _plat_id_map[pname] = pid
    plat_combo["values"] = names
    saved = _load_settings().get("last_platform", "")
    if saved in names:
        plat_var.set(saved)
    elif names:
        plat_combo.current(0)

_plat_id_map = {}

def _add_platform():
    name = simpledialog.askstring("Nouvelle plateforme", "Nom :",
                                   parent=root)
    if name and name.strip():
        try:
            db.add_platform(name.strip(), BOARD_WIDTH_CM, BOARD_HEIGHT_CM)
        except Exception:
            pass
        _refresh_platforms()
        plat_var.set(name.strip())

btn_add_plat = tk.Button(up_row, text="+", command=_add_platform,
                          font=btn_font, fg=ACCENT_GREEN, bg=TARE_BG,
                          activebackground=TARE_HOVER, relief="flat",
                          cursor="hand2", padx=6, pady=2)
btn_add_plat.pack(side="left", padx=(2, 2))

def _del_platform():
    pname = plat_var.get()
    pid = _plat_id_map.get(pname)
    if pid is None:
        return
    from tkinter import messagebox
    sessions = db.list_sessions(platform_id=pid)
    msg = f"Supprimer la plateforme \"{pname}\" ?"
    if sessions:
        msg += f"\n\n{len(sessions)} session(s) associee(s) seront aussi supprimees."
    if messagebox.askyesno("Supprimer plateforme", msg, parent=root):
        for s in sessions:
            db.delete_session(s["id"])
        db.delete_platform(pid)
        _refresh_platforms()

btn_del_plat = tk.Button(up_row, text="-", command=_del_platform,
                          font=btn_font, fg=ACCENT_RED, bg=TARE_BG,
                          activebackground=TARE_HOVER, relief="flat",
                          cursor="hand2", padx=6, pady=2)
btn_del_plat.pack(side="left", padx=(0, 0))

# Save selection on change
def _on_user_change(event=None):
    _save_settings({"last_user": user_var.get()})
def _on_plat_change(event=None):
    _save_settings({"last_platform": plat_var.get()})
user_combo.bind("<<ComboboxSelected>>", _on_user_change)
plat_combo.bind("<<ComboboxSelected>>", _on_plat_change)

_refresh_users()
_refresh_platforms()

# ── PANNEAU CONNEXION ─────────────────────────────────────────
conn_panel = tk.Frame(root, bg=BG_CARD, padx=14, pady=10,
                      highlightbackground=BOARD_OUTLINE, highlightthickness=1)
conn_panel.pack(fill="x", padx=20, pady=(0, 8))

conn_row = tk.Frame(conn_panel, bg=BG_CARD)
conn_row.pack(fill="x")

tk.Label(conn_row, text="PORT", font=btn_font,
         fg=TEXT_SECONDARY, bg=BG_CARD).pack(side="left", padx=(0, 8))

port_var   = tk.StringVar()
port_combo = ttk.Combobox(conn_row, textvariable=port_var,
                           state="readonly", width=46, font=label_font)
port_combo.pack(side="left", padx=(0, 6))

baud_var   = tk.StringVar(value="921600")
baud_combo = ttk.Combobox(conn_row, textvariable=baud_var,
                           state="readonly", width=9, font=label_font,
                           values=["9600", "115200", "921600"])
baud_combo.pack(side="left", padx=(0, 6))

btn_refresh = tk.Button(conn_row, text="Actualiser", command=lambda: refresh_ports(),
                        font=small_font, fg=TEXT_SECONDARY, bg=TARE_BG,
                        activebackground=TARE_HOVER, activeforeground=TEXT_PRIMARY,
                        relief="flat", cursor="hand2", padx=8, pady=4)
btn_refresh.pack(side="left", padx=(0, 6))

label_conn_info = tk.Label(conn_row, text="", font=mono_small,
                            fg=TEXT_DIM, bg=BG_CARD)
label_conn_info.pack(side="right", padx=(10, 0))

btn_disconnect = tk.Button(conn_row, text="Deconnecter",
                            font=btn_font, fg=ACCENT_RED, bg=TARE_BG,
                            activebackground=TARE_HOVER, activeforeground=TEXT_PRIMARY,
                            relief="flat", cursor="hand2", padx=10, pady=4)
btn_disconnect.pack(side="right", padx=(6, 0))

btn_connect = tk.Button(conn_row, text="Connecter",
                        font=btn_font, fg=TEXT_PRIMARY, bg=BTN_CONNECT_BG,
                        activebackground=BTN_CONNECT_HV, activeforeground=TEXT_PRIMARY,
                        relief="flat", cursor="hand2", padx=12, pady=4)
btn_connect.pack(side="right", padx=(0, 0))

_port_list = []

def refresh_ports():
    global _port_list
    _port_list = list_ports()
    labels = [lbl for _, lbl, _, _ in _port_list]
    port_combo["values"] = labels if labels else ["-- Aucun port --"]

    target_idx = next((i for i, (_, _, _, t) in enumerate(_port_list) if t), None)
    bt_idx     = next((i for i, (_, _, bt, _) in enumerate(_port_list) if bt), None)

    if target_idx is not None:
        port_combo.current(target_idx)
        n_bt = sum(1 for _, _, bt, _ in _port_list if bt)
        if n_bt > 1:
            label_conn_info.config(
                text=f"{n_bt} ports BT -- auto-detection a la connexion",
                fg=ACCENT_AMBER)
        else:
            label_conn_info.config(text="ForcePlatform detecte", fg=ACCENT_GREEN)
    elif bt_idx is not None:
        port_combo.current(bt_idx)
        n_bt = sum(1 for _, _, bt, _ in _port_list if bt)
        if n_bt > 1:
            label_conn_info.config(
                text=f"{n_bt} ports BT -- auto-detection a la connexion",
                fg=ACCENT_AMBER)
        else:
            label_conn_info.config(text="1 port BT detecte", fg=ACCENT_GREEN)
    elif labels:
        port_combo.current(0)
        label_conn_info.config(
            text=f"{len(labels)} port(s) -- aucun BT trouve", fg=ACCENT_AMBER)
    else:
        label_conn_info.config(text="Aucun port", fg=ACCENT_RED)

def do_connect():
    global serial_conn, _port_list
    if not _port_list:
        label_conn_info.config(text="Aucun port disponible", fg=ACCENT_RED)
        return

    sel_label = port_var.get()
    device, is_bt, is_target = None, False, False
    for dev, lbl, bt, tgt in _port_list:
        if lbl == sel_label:
            device, is_bt, is_target = dev, bt, tgt
            break
    if not device:
        label_conn_info.config(text="Selectionne un port", fg=ACCENT_RED)
        return

    if serial_conn:
        try: serial_conn.close()
        except: pass
        serial_conn = None

    baud = int(baud_var.get())

    if is_bt or is_target:
        candidates = [device]
        for dev, lbl, bt, tgt in _port_list:
            if bt and dev != device:
                candidates.append(dev)

        label_conn_info.config(
            text=f"Test de {len(candidates)} port(s) BT...", fg=ACCENT_AMBER)
        root.update_idletasks()

        found = None
        for cand in candidates:
            label_conn_info.config(text=f"Test {cand}...", fg=ACCENT_AMBER)
            root.update_idletasks()
            s = _try_port(cand, baud)
            if s:
                found = (cand, s)
                break

        if not found:
            label_conn_info.config(
                text="Aucun port ne repond -- verifier le jumelage BT",
                fg=ACCENT_RED)
            return

        device, s = found
        working_dev = device
        _port_list = [(dev, lbl, bt, tgt) for dev, lbl, bt, tgt in _port_list
                      if not (bt and dev != working_dev)]
        labels = [lbl for _, lbl, _, _ in _port_list]
        port_combo["values"] = labels
        for i, (dev, _, _, _) in enumerate(_port_list):
            if dev == working_dev:
                port_combo.current(i)
                break
    else:
        label_conn_info.config(text="Connexion...", fg=ACCENT_AMBER)
        root.update_idletasks()
        try:
            s = serial.Serial(device, baud, timeout=1)
        except Exception as e:
            label_conn_info.config(text=f"Erreur: {e}", fg=ACCENT_RED)
            return

    serial_conn = s
    mode = "Bluetooth" if is_bt else "USB"
    label_conn_info.config(text=f"Connecte  {mode}  {device}", fg=ACCENT_GREEN)
    root.after(1000, get_calib)

def do_disconnect():
    global serial_conn
    if serial_conn:
        try: serial_conn.close()
        except: pass
        serial_conn = None
    label_conn_info.config(text="Deconnecte", fg=TEXT_DIM)

btn_connect.config(command=do_connect)
btn_disconnect.config(command=do_disconnect)
refresh_ports()

# ============================================================
# CONTENU PRINCIPAL
# ============================================================
main_frame = tk.Frame(root, bg=BG_DARK)
main_frame.pack(fill="both", expand=True, padx=20, pady=0)

# ── Panneau gauche ───────────────────────────────────────────
left_panel = tk.Frame(main_frame, bg=BG_DARK, width=315)
left_panel.pack(side="left", fill="y", padx=(0, 15))
left_panel.pack_propagate(False)

# ── Onglets panneau gauche ──────────────────────────────────
notebook = ttk.Notebook(left_panel, style="LeftPanel.TNotebook")
notebook.pack(fill="both", expand=True)

tab_capteurs = tk.Frame(notebook, bg=BG_DARK)
tab_calibration = tk.Frame(notebook, bg=BG_DARK)
tab_outils = tk.Frame(notebook, bg=BG_DARK)

notebook.add(tab_capteurs, text="  Capteurs  ")
notebook.add(tab_calibration, text="  Calibration  ")
notebook.add(tab_outils, text="  Outils  ")

# ── Tab Capteurs ─────────────────────────────────────────────
tk.Label(tab_capteurs, text="CAPTEURS", font=header_font,
         fg=TEXT_SECONDARY, bg=BG_DARK).pack(anchor="w", pady=(6, 6))

weight_labels = []
weight_bars   = []
bar_canvases  = []

for i in range(4):
    card = tk.Frame(tab_capteurs, bg=BG_CARD, padx=10, pady=6,
                    highlightbackground=SENSOR_COLORS[i], highlightthickness=1)
    card.pack(fill="x", pady=3)
    top_row = tk.Frame(card, bg=BG_CARD)
    top_row.pack(fill="x")
    tk.Label(top_row, text=f"{SENSOR_NAMES[i]}",
             font=label_font, fg=SENSOR_COLORS[i], bg=BG_CARD).pack(side="left")
    val_lbl = tk.Label(top_row, text="0.000 kg", font=value_font,
                       fg=TEXT_PRIMARY, bg=BG_CARD)
    val_lbl.pack(side="right")
    weight_labels.append(val_lbl)
    bar_cv = tk.Canvas(card, height=4, bg=BG_DARK, highlightthickness=0)
    bar_cv.pack(fill="x", pady=(4, 0))
    bar_rect = bar_cv.create_rectangle(0, 0, 0, 4, fill=SENSOR_COLORS[i], outline="")
    bar_canvases.append(bar_cv)
    weight_bars.append(bar_rect)

total_frame = tk.Frame(tab_capteurs, bg=BG_CARD, padx=10, pady=8,
                       highlightbackground=ACCENT_BLUE, highlightthickness=2)
total_frame.pack(fill="x", pady=(10, 4))
tk.Label(total_frame, text="POIDS TOTAL", font=label_font,
         fg=TEXT_SECONDARY, bg=BG_CARD).pack(anchor="w")
label_total = tk.Label(total_frame, text="0.000 kg", font=value_font,
                       fg=ACCENT_BLUE, bg=BG_CARD)
label_total.pack(anchor="e")

def send_tare():
    send_json({"cmd": "tare"})
    btn_tare.config(text="TARE ENVOYE", fg=ACCENT_GREEN)
    root.after(1500, lambda: btn_tare.config(text="TARE", fg=TEXT_PRIMARY))

btn_tare = tk.Button(tab_capteurs, text="TARE", command=send_tare,
                     font=btn_font, fg=TEXT_PRIMARY, bg=TARE_BG,
                     activebackground=TARE_HOVER, activeforeground=TEXT_PRIMARY,
                     relief="flat", cursor="hand2", padx=10, pady=7)
btn_tare.pack(fill="x", pady=(4, 0))

# ── Tab Calibration ──────────────────────────────────────────
tk.Label(tab_calibration, text="CALIBRATION", font=header_font,
         fg=TEXT_SECONDARY, bg=BG_DARK).pack(anchor="w", pady=(6, 6))

ref_frame = tk.Frame(tab_calibration, bg=BG_DARK)
ref_frame.pack(fill="x", pady=(6, 4))
tk.Label(ref_frame, text="Poids ref :", font=label_font,
         fg=TEXT_SECONDARY, bg=BG_DARK).pack(side="left")
entry_ref_weight = tk.Entry(ref_frame, width=7, bg=BG_CARD, fg=TEXT_PRIMARY,
                             insertbackground=TEXT_PRIMARY, relief="flat",
                             font=btn_font, justify="center")
entry_ref_weight.insert(0, "1")
entry_ref_weight.pack(side="left", padx=(6, 2))
tk.Label(ref_frame, text="kg", font=label_font, fg=TEXT_DIM, bg=BG_DARK).pack(side="left")

log_frame = tk.Frame(tab_calibration, bg=BG_CARD, highlightbackground=BOARD_OUTLINE,
                     highlightthickness=1)
log_frame.pack(fill="x", pady=(2, 6))
label_cal_log = tk.Label(log_frame, text="-- en attente --", font=mono_small,
                          fg=TEXT_DIM, bg=BG_CARD, wraplength=290,
                          justify="left", padx=6, pady=4)
label_cal_log.pack(fill="x")

cal_btn_frame = tk.Frame(tab_calibration, bg=BG_DARK)
cal_btn_frame.pack(fill="x")
cal_buttons = []

def make_cal_callback(idx):
    def cb():
        try:
            ref = float(entry_ref_weight.get())
        except ValueError:
            label_cal_log.config(text="Poids invalide", fg=ACCENT_RED)
            return
        send_json({"cmd": "cal", "sensor": idx + 1, "weight": ref * 1000})
        cal_buttons[idx].config(
            text=f"CAL {idx+1}  {SENSOR_NAMES[idx]} ...", fg=ACCENT_AMBER)
        label_cal_log.config(
            text=f"Calibration capteur {idx+1}...\nPose {ref:.3f} kg dessus.",
            fg=ACCENT_AMBER)
    return cb

for i in range(4):
    btn = tk.Button(cal_btn_frame, text=f"CAL {i+1}  {SENSOR_NAMES[i]}",
                    command=make_cal_callback(i),
                    font=btn_font, fg=SENSOR_COLORS[i], bg=CAL_BG,
                    activebackground=CAL_HOVER, activeforeground=TEXT_PRIMARY,
                    relief="flat", cursor="hand2", anchor="w", padx=8, pady=5)
    btn.pack(fill="x", pady=2)
    cal_buttons.append(btn)

def get_calib():
    send_json({"cmd": "get_calib"})
    label_cal_log.config(text="Recuperation des valeurs...", fg=ACCENT_TEAL)

btn_get_calib = tk.Button(tab_calibration, text="Lire calibration ESP",
                           command=get_calib,
                           font=btn_font, fg=ACCENT_TEAL, bg=TARE_BG,
                           activebackground=TARE_HOVER, activeforeground=TEXT_PRIMARY,
                           relief="flat", cursor="hand2", padx=10, pady=6)
btn_get_calib.pack(fill="x", pady=(4, 0))

calib_display_labels = []
for i in range(4):
    lbl = tk.Label(tab_calibration, text=f"C{i+1}: off=--  sc=--",
                   font=mono_small, fg=SENSOR_COLORS[i], bg=BG_DARK, anchor="w")
    lbl.pack(fill="x")
    calib_display_labels.append(lbl)

# ── Tab Outils ───────────────────────────────────────────────
def _open_history():
    SessionBrowser(root, THEMES, current_theme,
                   (_load_settings, _save_settings))

btn_history = tk.Button(tab_outils, text="HISTORIQUE SESSIONS",
                        command=_open_history,
                        font=btn_font, fg=ACCENT_BLUE, bg=TARE_BG,
                        activebackground=TARE_HOVER, activeforeground=TEXT_PRIMARY,
                        relief="flat", cursor="hand2", padx=10, pady=7)
btn_history.pack(fill="x", pady=(10, 4))

_dashboard_url = ""

def _toggle_dashboard():
    global web_server_thread, web_server_running, _dashboard_url
    if web_server_running:
        web_server_running = False
        _dashboard_url = ""
        btn_dashboard.config(text="DASHBOARD WEB : OFF", fg=TEXT_SECONDARY)
        lbl_dashboard_url.config(text="", cursor="")
    else:
        try:
            from web_dashboard import start_web_server, stop_web_server
            import socket
            port = 5000
            web_server_thread = start_web_server(port)
            web_server_running = True
            # Get local IP
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
            except Exception:
                local_ip = "localhost"
            _dashboard_url = f"http://{local_ip}:{port}"
            btn_dashboard.config(text="DASHBOARD WEB : ON", fg=ACCENT_GREEN)
            lbl_dashboard_url.config(
                text=_dashboard_url, fg=ACCENT_TEAL, cursor="hand2")
            # Open browser automatically
            webbrowser.open(_dashboard_url)
        except Exception as e:
            lbl_dashboard_url.config(text=f"Erreur: {e}", fg=ACCENT_RED)

def _open_dashboard_url(event=None):
    if _dashboard_url:
        webbrowser.open(_dashboard_url)

btn_dashboard = tk.Button(tab_outils, text="DASHBOARD WEB : OFF",
                          command=_toggle_dashboard,
                          font=btn_font, fg=TEXT_SECONDARY, bg=TARE_BG,
                          activebackground=TARE_HOVER, activeforeground=TEXT_PRIMARY,
                          relief="flat", cursor="hand2", padx=10, pady=7)
btn_dashboard.pack(fill="x", pady=(0, 2))

lbl_dashboard_url = tk.Label(tab_outils, text="", font=mono_small,
                              fg=ACCENT_TEAL, bg=BG_DARK)
lbl_dashboard_url.pack(fill="x")
lbl_dashboard_url.bind("<Button-1>", _open_dashboard_url)
lbl_dashboard_url.bind("<Enter>",
    lambda e: lbl_dashboard_url.config(font=("Consolas", 8, "underline"))
    if _dashboard_url else None)
lbl_dashboard_url.bind("<Leave>",
    lambda e: lbl_dashboard_url.config(font=mono_small))

# ── Remote sync auto-start (invisible, always on) ────────────
def _on_update_ready():
    """Called from remote_sync thread when a new .exe is downloaded.
    Show notification then schedule a clean app exit on the main thread."""
    def _show_and_close():
        from tkinter import messagebox
        new_ver = getattr(remote_sync, '_new_version', '?')
        messagebox.showinfo(
            "Mise a jour",
            f"Nouvelle version (v{new_ver}) telechargee !\n\n"
            "L'application va redemarrer pour\n"
            "appliquer la mise a jour.")
        _on_close()
    root.after(0, _show_and_close)

remote_sync.on_update_ready = _on_update_ready
remote_sync.start()

# ── Panneau droit : canvas ────────────────────────────────────
right_panel = tk.Frame(main_frame, bg=BG_DARK)
right_panel.pack(side="right", fill="both", expand=True)

# ── Recording controls ────────────────────────────────────────
rec_bar = tk.Frame(right_panel, bg=BG_DARK)
rec_bar.pack(fill="x", pady=(0, 6))

_rec_blink_state = False

def _toggle_recording():
    global _rec_blink_state
    if recorder.is_recording:
        sid = recorder.stop()
        btn_rec.config(text="DEMARRER ENREGISTREMENT", fg=TEXT_PRIMARY,
                       bg=BTN_CONNECT_BG, activebackground=BTN_CONNECT_HV)
        lbl_rec_time.config(text="")
        lbl_rec_samples.config(text=f"Session #{sid} sauvegardee" if sid else "")
        _rec_blink_state = False
    else:
        # Need user + platform
        uname = user_var.get()
        pname = plat_var.get()
        uid = _user_id_map.get(uname)
        pid = _plat_id_map.get(pname)
        if uid is None:
            lbl_rec_samples.config(text="Selectionner un utilisateur", fg=ACCENT_RED)
            return
        if pid is None:
            lbl_rec_samples.config(text="Selectionner une plateforme", fg=ACCENT_RED)
            return
        recorder.start(uid, pid)
        btn_rec.config(text="ARRETER ENREGISTREMENT", fg=TEXT_PRIMARY,
                       bg=ACCENT_RED, activebackground=ACCENT_AMBER)

btn_rec = tk.Button(rec_bar, text="DEMARRER ENREGISTREMENT",
                    command=_toggle_recording,
                    font=btn_font, fg=TEXT_PRIMARY, bg=BTN_CONNECT_BG,
                    activebackground=BTN_CONNECT_HV,
                    relief="flat", cursor="hand2", padx=14, pady=6)
btn_rec.pack(side="left")

lbl_rec_time = tk.Label(rec_bar, text="", font=("Consolas", 11, "bold"),
                         fg=ACCENT_RED, bg=BG_DARK)
lbl_rec_time.pack(side="left", padx=(10, 0))

lbl_rec_samples = tk.Label(rec_bar, text="", font=small_font,
                            fg=TEXT_DIM, bg=BG_DARK)
lbl_rec_samples.pack(side="left", padx=(10, 0))

visu_header = tk.Frame(right_panel, bg=BG_DARK)
visu_header.pack(fill="x", pady=(0, 8))
tk.Label(visu_header, text="VISUALISATION", font=header_font,
         fg=TEXT_SECONDARY, bg=BG_DARK).pack(side="left")
tk.Label(visu_header, text=f"Planche {BOARD_WIDTH_CM}x{BOARD_HEIGHT_CM} cm",
         font=small_font, fg=TEXT_DIM, bg=BG_DARK).pack(side="left", padx=(12, 0))
label_coords = tk.Label(visu_header, text="X: 0.0%  Y: 0.0%",
                         font=label_font, fg=ACCENT_TEAL, bg=BG_DARK)
label_coords.pack(side="right")

canvas = tk.Canvas(right_panel, bg=BG_CANVAS, highlightthickness=1,
                   highlightbackground=BOARD_OUTLINE)
canvas.pack(fill="both", expand=True)

MARGIN = 50
CAP_R  = 14
CROSS_SIZE = 14
board_left = board_right = board_top = board_bottom = 0
board_cx = board_cy = 0
sensor_val_texts = []
_last_board_size = (0, 0)

trail_items  = []
TRAIL_LENGTH = 15
com_h_line = canvas.create_line(0, 0, 0, 0, fill=CROSS_COLOR, width=2)
com_v_line = canvas.create_line(0, 0, 0, 0, fill=CROSS_COLOR, width=2)
com_label  = canvas.create_text(0, 0, text="CoM", fill=COM_COLOR,
                                 font=("Segoe UI", 9, "bold"))

def draw_board(event=None):
    global board_left, board_right, board_top, board_bottom
    global board_cx, board_cy, sensor_val_texts, _last_board_size

    cw = canvas.winfo_width()
    ch = canvas.winfo_height()
    if cw < 120 or ch < 120:
        return
    if (cw, ch) == _last_board_size:
        return
    _last_board_size = (cw, ch)

    canvas.delete("board_static")
    sensor_val_texts = []

    avail_w = cw - 2 * MARGIN
    avail_h = ch - 2 * MARGIN
    if avail_w / avail_h > BOARD_RATIO:
        board_h = avail_h
        board_w = board_h * BOARD_RATIO
    else:
        board_w = avail_w
        board_h = board_w / BOARD_RATIO

    cx_canvas = cw / 2
    cy_canvas = ch / 2
    board_left   = cx_canvas - board_w / 2
    board_right  = cx_canvas + board_w / 2
    board_top    = cy_canvas - board_h / 2
    board_bottom = cy_canvas + board_h / 2
    board_cx     = cx_canvas
    board_cy     = cy_canvas

    canvas.create_rectangle(board_left, board_top, board_right, board_bottom,
                            fill=BOARD_FILL, outline="", tags="board_static")

    n_cols = BOARD_WIDTH_CM // 5
    n_rows = BOARD_HEIGHT_CM // 5
    step_x = board_w / n_cols
    step_y = board_h / n_rows
    for i in range(1, n_cols):
        gx = board_left + i * step_x
        canvas.create_line(gx, board_top, gx, board_bottom,
                           fill=GRID_COLOR, tags="board_static")
    for i in range(1, n_rows):
        gy = board_top + i * step_y
        canvas.create_line(board_left, gy, board_right, gy,
                           fill=GRID_COLOR, tags="board_static")

    canvas.create_line(board_cx, board_top, board_cx, board_bottom,
                       fill=BOARD_OUTLINE, dash=(6, 4), tags="board_static")
    canvas.create_line(board_left, board_cy, board_right, board_cy,
                       fill=BOARD_OUTLINE, dash=(6, 4), tags="board_static")

    canvas.create_rectangle(board_left, board_top, board_right, board_bottom,
                            outline=BOARD_OUTLINE, width=2, tags="board_static")

    canvas.create_line(board_cx - 6, board_cy, board_cx + 6, board_cy,
                       fill=TEXT_DIM, tags="board_static")
    canvas.create_line(board_cx, board_cy - 6, board_cx, board_cy + 6,
                       fill=TEXT_DIM, tags="board_static")

    # 0=Haut-Droit, 1=Haut-Gauche, 2=Bas-Droit, 3=Bas-Gauche
    corners = [(board_right, board_top),  (board_left, board_top),
               (board_right, board_bottom), (board_left, board_bottom)]
    for idx, (cx, cy) in enumerate(corners):
        canvas.create_oval(cx - CAP_R, cy - CAP_R, cx + CAP_R, cy + CAP_R,
                           fill=SENSOR_COLORS[idx], outline=TEXT_PRIMARY, width=1,
                           tags="board_static")
        tx_off = -28 if idx % 2 == 0 else 28
        ty_off = -18 if idx < 2 else 18
        txt = canvas.create_text(cx + tx_off, cy + ty_off, text="0.00 kg",
                                 fill=SENSOR_COLORS[idx], font=("Consolas", 9),
                                 tags="board_static")
        sensor_val_texts.append(txt)
        canvas.create_text(cx, cy, text=str(idx + 1), fill="white",
                           font=("Segoe UI", 9, "bold"), tags="board_static")

    canvas.create_text(board_cx, board_bottom + 22,
                       text="Gauche                    Droite",
                       fill=TEXT_DIM, font=("Segoe UI", 9), tags="board_static")
    canvas.create_text(board_left - 28, board_cy,
                       text="Haut\n|\n|\nBas",
                       fill=TEXT_DIM, font=("Segoe UI", 8),
                       justify="center", tags="board_static")
    canvas.create_text(board_cx, board_top - 14,
                       text=f"{BOARD_WIDTH_CM} cm",
                       fill=TEXT_DIM, font=("Segoe UI", 8), tags="board_static")
    canvas.create_text(board_right + 22, board_cy,
                       text=f"{BOARD_HEIGHT_CM}\ncm",
                       fill=TEXT_DIM, font=("Segoe UI", 8),
                       justify="center", tags="board_static")

    canvas.tag_raise(com_h_line)
    canvas.tag_raise(com_v_line)
    canvas.tag_raise(com_label)

canvas.bind("<Configure>", draw_board)

# ============================================================
# TOGGLE THEME
# ============================================================
def toggle_theme():
    global current_theme, _last_board_size
    old_name = current_theme
    current_theme = "light" if current_theme == "dark" else "dark"

    # Color map old -> new
    cmap = _build_color_map(old_name, current_theme)

    # Update module-level color vars
    _sync_colors()

    # Recursive retheme on all tk widgets
    _retheme_widgets(root, cmap)

    # ttk combobox style
    _update_ttk_style()
    _update_notebook_style()

    # Canvas dynamic items
    canvas.itemconfig(com_h_line, fill=CROSS_COLOR)
    canvas.itemconfig(com_v_line, fill=CROSS_COLOR)
    canvas.itemconfig(com_label, fill=COM_COLOR)

    # Bar fill colors (sensor colors)
    for i in range(4):
        bar_canvases[i].itemconfig(weight_bars[i], fill=SENSOR_COLORS[i])

    # Force board redraw (recreates all board_static items with new colors)
    _last_board_size = (0, 0)
    draw_board()

    # Toggle button text
    btn_theme.config(text=("\u2600" if current_theme == "dark" else "\u263e"))

    # Save preference
    _save_settings({"theme": current_theme})

btn_theme.config(command=toggle_theme)

# ============================================================
# PROCESS REPONSES
# ============================================================
def process_responses():
    with resp_lock:
        responses = list(response_queue)
        response_queue.clear()
    for data in responses:
        status = data.get("status", "")
        if status == "tare_ok":
            label_cal_log.config(text="Tare effectuee", fg=ACCENT_GREEN)
        elif status == "cal_ok":
            s  = data["sensor"] - 1
            sc, off = data["scale"], data["offset"]
            calib_scales[s]  = sc
            calib_offsets[s] = off
            cal_buttons[s].config(text=f"CAL {s+1}  {SENSOR_NAMES[s]}",
                                  fg=SENSOR_COLORS[s])
            calib_display_labels[s].config(text=f"C{s+1}: off={off}  sc={sc:.4f}")
            label_cal_log.config(
                text=f"Capteur {s+1} calibre\nScale={sc:.4f}", fg=ACCENT_GREEN)
        elif status == "cal_error":
            label_cal_log.config(text=f"{data.get('msg','erreur')}", fg=ACCENT_RED)
            for i in range(4):
                cal_buttons[i].config(text=f"CAL {i+1}  {SENSOR_NAMES[i]}",
                                      fg=SENSOR_COLORS[i])
        elif status == "calib_values":
            for i in range(4):
                off = data.get(f"off{i+1}", 0)
                sc  = data.get(f"sc{i+1}",  0.0)
                calib_offsets[i] = off
                calib_scales[i]  = sc
                calib_display_labels[i].config(
                    text=f"C{i+1}: off={off}  sc={sc:.4f}")
            label_cal_log.config(text="Valeurs recuperees", fg=ACCENT_GREEN)

# ============================================================
# UPDATE UI (~60 fps)
# ============================================================
def update_ui():
    global freq, com_trail

    process_responses()

    weight = list(raw_w)
    total  = sum(weight)

    for i in range(4):
        weight_labels[i].config(text=f"{weight[i]/1000:.3f} kg")
        bar_cv    = bar_canvases[i]
        bar_width = bar_cv.winfo_width() or 1
        fill_w    = (weight[i] / max(total, 1)) * bar_width if total > 1 else 0
        bar_cv.coords(weight_bars[i], 0, 0, fill_w, 4)
    if sensor_val_texts:
        for i in range(4):
            canvas.itemconfig(sensor_val_texts[i],
                              text=f"{weight[i]/1000:.2f} kg")

    label_total.config(text=f"{total/1000:.3f} kg")
    label_freq.config(text=f"{freq:.1f} Hz")

    if all(w < NEAR_ZERO_THRESHOLD for w in weight) or total <= 1:
        x_pos, y_pos, x_pct, y_pct = board_cx, board_cy, 0.0, 0.0
    else:
        xr    = (weight[0]+weight[2]-weight[1]-weight[3]) / total
        yr    = (weight[2]+weight[3]-weight[0]-weight[1]) / total
        x_pos = max(board_left, min(board_right,
                    board_cx + xr*(board_right-board_left)/2))
        y_pos = max(board_top, min(board_bottom,
                    board_cy + yr*(board_bottom-board_top)/2))
        x_pct, y_pct = xr*100, yr*100

    label_coords.config(text=f"X: {x_pct:+.1f}%   Y: {y_pct:+.1f}%")

    # ── Recording ────────────────────────────────────────────
    if recorder.is_recording:
        t_ms = int((time.time() - recorder.start_time) * 1000)
        recorder.record(t_ms, weight[0], weight[1], weight[2], weight[3],
                        x_pct / 100.0, y_pct / 100.0)
        elapsed = recorder.elapsed
        mins = int(elapsed // 60)
        secs = elapsed % 60
        lbl_rec_time.config(text=f"{mins:02d}:{secs:05.2f}")
        lbl_rec_samples.config(text=f"{recorder.sample_count} samples",
                               fg=TEXT_SECONDARY)

    # Trail (couleurs adaptees au theme)
    com_trail.append((x_pos, y_pos))
    if len(com_trail) > TRAIL_LENGTH:
        com_trail = com_trail[-TRAIL_LENGTH:]
    for item in trail_items:
        canvas.delete(item)
    trail_items.clear()

    bg_rgb    = _hex_to_rgb(BG_CANVAS)
    cross_rgb = _hex_to_rgb(CROSS_COLOR)
    for idx, (tx, ty) in enumerate(com_trail[:-1]):
        alpha = idx / TRAIL_LENGTH
        r = int(bg_rgb[0] + (cross_rgb[0] - bg_rgb[0]) * alpha)
        g = int(bg_rgb[1] + (cross_rgb[1] - bg_rgb[1]) * alpha)
        b = int(bg_rgb[2] + (cross_rgb[2] - bg_rgb[2]) * alpha)
        sz = 1.5 + alpha * 3
        trail_items.append(canvas.create_oval(
            tx - sz, ty - sz, tx + sz, ty + sz,
            fill=f"#{r:02x}{g:02x}{b:02x}", outline=""))

    # Croix du centre de masse
    canvas.coords(com_h_line, x_pos - CROSS_SIZE, y_pos,
                  x_pos + CROSS_SIZE, y_pos)
    canvas.coords(com_v_line, x_pos, y_pos - CROSS_SIZE,
                  x_pos, y_pos + CROSS_SIZE)
    canvas.coords(com_label, x_pos, y_pos - CROSS_SIZE - 10)
    canvas.tag_raise(com_h_line)
    canvas.tag_raise(com_v_line)
    canvas.tag_raise(com_label)

    # Status connexion
    elapsed = time.time() - last_received
    is_connected = False
    if serial_conn is None:
        label_status.config(text="DECONNECTE", fg=ACCENT_RED)
    elif elapsed < 2:
        label_status.config(text="CONNECTE",   fg=ACCENT_GREEN)
        is_connected = True
    elif elapsed < 5:
        label_status.config(text="ATTENTE...",  fg=ACCENT_AMBER)
    else:
        label_status.config(text="TIMEOUT",     fg=ACCENT_RED)

    # Update remote sync state (silent, no UI)
    remote_sync.update_state(
        is_recording=recorder.is_recording,
        connected=is_connected)

    root.after(16, update_ui)

def _on_close():
    """Clean shutdown: stop recording, remote sync, close serial."""
    global serial_conn
    if recorder.is_recording:
        recorder.stop()
    if remote_sync.is_running:
        remote_sync.stop()
    if serial_conn:
        try:
            serial_conn.close()
        except Exception:
            pass
        serial_conn = None
    root.destroy()

root.protocol("WM_DELETE_WINDOW", _on_close)

update_ui()
root.mainloop()
