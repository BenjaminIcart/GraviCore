# ============================================================
#  Centre de Masse — Plateforme de Force  (Dear PyGui GPU)
#  pip install pyserial dearpygui
# ============================================================
import dearpygui.dearpygui as dpg
import serial
import serial.tools.list_ports
import json, threading, time, math, os, sys, webbrowser
from collections import deque

import database as db
from recorder import SessionRecorder
from remote_sync import RemoteSync


def _app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

# ============================================================
# CONFIG
# ============================================================
APP_VERSION         = 13
NEAR_ZERO_THRESHOLD = 50
TARGET_NAME         = "GraviCore"
BOARD_WIDTH_MM      = 50
BOARD_HEIGHT_MM     = 40
BOARD_RATIO         = BOARD_WIDTH_MM / BOARD_HEIGHT_MM
TRAIL_LENGTH        = 15
MARGIN              = 55
CAP_R               = 14
CROSS_SIZE          = 14

# ============================================================
# THEMES  (hex — kept for replay_window compat)
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
# PREFERENCES
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

current_theme = _load_settings().get("theme", "dark")
if current_theme not in THEMES:
    current_theme = "dark"

SENSOR_NAMES = ["Haut-Droit", "Haut-Gauche", "Bas-Droit", "Bas-Gauche"]

# ============================================================
# COLOR HELPERS
# ============================================================
def _hex_rgba(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)

# Pre-computed theme color cache (avoids hex parsing per-frame)
_tc = {}
_tc_sc = []
_trail_colors = []
_trail_sizes = []

def _refresh_theme_cache():
    global _trail_colors, _trail_sizes
    _tc.clear()
    t = THEMES[current_theme]
    for k, v in t.items():
        if isinstance(v, str):
            _tc[k] = _hex_rgba(v)
    _tc_sc.clear()
    _tc_sc.extend(_hex_rgba(c) for c in t["sensor_colors"])
    # Pre-compute trail gradient
    bg = _tc["bg_canvas"]
    cr = _tc["cross_color"]
    _trail_colors = []
    _trail_sizes = []
    for idx in range(TRAIL_LENGTH):
        a = idx / TRAIL_LENGTH
        _trail_colors.append((
            int(bg[0] + (cr[0] - bg[0]) * a),
            int(bg[1] + (cr[1] - bg[1]) * a),
            int(bg[2] + (cr[2] - bg[2]) * a), 255))
        _trail_sizes.append(1.5 + a * 3)

def _t(key):
    """Current theme color as RGBA (cached)."""
    return _tc.get(key) or _hex_rgba(THEMES[current_theme][key])

def _sc(i):
    """Sensor color i as RGBA (cached)."""
    return _tc_sc[i] if _tc_sc else _hex_rgba(THEMES[current_theme]["sensor_colors"][i])

_refresh_theme_cache()

# ============================================================
# STATE
# ============================================================
raw_w         = [0, 0, 0, 0]
freq          = 0.0
last_received = time.time()
_freq_times   = deque(maxlen=50)
_sensor_bufs  = [deque(maxlen=5) for _ in range(4)]
_sensor_prev  = [0.0] * 4
_MAX_DELTA    = 3000
com_trail     = deque(maxlen=TRAIL_LENGTH)
calib_offsets = [0] * 4
calib_scales  = [0.0] * 4
response_queue = []
resp_lock      = threading.Lock()
serial_conn    = None

db.init_db()
recorder = SessionRecorder()
web_server_thread  = None
web_server_running = False

_REMOTE_URL = "https://gravicore.ibenji.fr/cm_api.php"
_REMOTE_KEY = "c4d1146e19f391e0b6901bcb88c32d10e7f6e5174d12f179bd7a1018b4c9c8e0"
remote_sync = RemoteSync(server_url=_REMOTE_URL, api_key=_REMOTE_KEY,
                         app_version=APP_VERSION)

_update_ready_flag = False   # set by remote_sync thread
_prev_weights  = [None] * 4
_prev_total    = None
_prev_freq_str = None

# Board geometry (updated on resize)
_board = {
    "left": 0, "right": 0, "top": 0, "bottom": 0,
    "cx": 0, "cy": 0, "last_size": (0, 0),
    "trail_ids": [], "cross_ids": {},
}

# ============================================================
# SERIAL THREAD
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
                for _si, _sk in enumerate(("weight1","weight2","weight3","weight4")):
                    v = max(0, data[_sk])
                    _sensor_bufs[_si].append(v)
                    med = sorted(_sensor_bufs[_si])[len(_sensor_bufs[_si]) // 2]
                    prev = _sensor_prev[_si]
                    if abs(med - prev) > _MAX_DELTA:
                        med = prev + _MAX_DELTA if med > prev else prev - _MAX_DELTA
                    _sensor_prev[_si] = med
                    raw_w[_si] = med
                now = time.time()
                _freq_times.append(now)
                if len(_freq_times) >= 2:
                    span = _freq_times[-1] - _freq_times[0]
                    if span > 0:
                        freq = (len(_freq_times) - 1) / span
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
# PORT DETECTION
# ============================================================
def _is_target(port_info) -> bool:
    name = TARGET_NAME.lower()
    desc = (port_info.description or "").lower()
    hwid = (port_info.hwid or "").lower()
    mfr  = (getattr(port_info, "manufacturer", "") or "").lower()
    return name in desc or name in hwid or name in mfr

def _try_port(device, baud, timeout=2.5):
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
# DPG CONTEXT
# ============================================================
dpg.create_context()

# ============================================================
# FONTS
# ============================================================
_font_dir = "C:/Windows/Fonts"
font_default = font_title = font_header = font_small = font_coords = None
font_mono = font_mono_large = None

with dpg.font_registry():
    segoe = os.path.join(_font_dir, "segoeui.ttf")
    segoe_b = os.path.join(_font_dir, "segoeuib.ttf")
    consola = os.path.join(_font_dir, "consola.ttf")
    consola_b = os.path.join(_font_dir, "consolab.ttf")
    if os.path.exists(segoe):
        font_default = dpg.add_font(segoe, 20)
        dpg.add_font_range(0x2600, 0x2700, parent=font_default)
        font_small   = dpg.add_font(segoe, 16)
    if os.path.exists(segoe_b):
        font_title  = dpg.add_font(segoe_b, 30)
        font_header = dpg.add_font(segoe_b, 20)
        font_coords = dpg.add_font(segoe_b, 24)
    if os.path.exists(consola):
        font_mono = dpg.add_font(consola, 16)
    if os.path.exists(consola_b):
        font_mono_large = dpg.add_font(consola_b, 28)

if font_default:
    dpg.bind_font(font_default)

# ============================================================
# THEME ENGINE
# ============================================================
_theme_cache = {}

def _txt_theme(rgba):
    key = ("t", tuple(rgba))
    if key not in _theme_cache:
        with dpg.theme() as t:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_Text, rgba)
        _theme_cache[key] = t
    return _theme_cache[key]

def _btn_theme(bg, hv=None, text=(241, 245, 249, 255)):
    hv = hv or tuple(min(c + 30, 255) for c in bg[:3]) + (bg[3],)
    key = ("b", tuple(bg), tuple(hv), tuple(text))
    if key not in _theme_cache:
        with dpg.theme() as t:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, bg)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, hv)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, hv)
                dpg.add_theme_color(dpg.mvThemeCol_Text, text)
        _theme_cache[key] = t
    return _theme_cache[key]

def _bar_theme(rgba):
    key = ("bar", tuple(rgba))
    if key not in _theme_cache:
        with dpg.theme() as t:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_PlotHistogram, rgba)
        _theme_cache[key] = t
    return _theme_cache[key]

def _build_global_theme(name):
    t = THEMES[name]
    bg     = _hex_rgba(t["bg"])
    card   = _hex_rgba(t["bg_card"])
    txt    = _hex_rgba(t["text_primary"])
    sec    = _hex_rgba(t["text_secondary"])
    border = _hex_rgba(t["board_outline"])
    accent = _hex_rgba(t["accent_blue"])
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, bg)
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, bg)
            dpg.add_theme_color(dpg.mvThemeCol_PopupBg, card)
            dpg.add_theme_color(dpg.mvThemeCol_Text, txt)
            dpg.add_theme_color(dpg.mvThemeCol_Border, border)
            dpg.add_theme_color(dpg.mvThemeCol_BorderShadow, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, card)
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, border)
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, border)
            dpg.add_theme_color(dpg.mvThemeCol_Button, card)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, border)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, accent)
            dpg.add_theme_color(dpg.mvThemeCol_Tab, card)
            dpg.add_theme_color(dpg.mvThemeCol_TabHovered, accent)
            dpg.add_theme_color(dpg.mvThemeCol_TabActive, bg)
            dpg.add_theme_color(dpg.mvThemeCol_TabUnfocused, card)
            dpg.add_theme_color(dpg.mvThemeCol_TabUnfocusedActive, bg)
            dpg.add_theme_color(dpg.mvThemeCol_Separator, border)
            dpg.add_theme_color(dpg.mvThemeCol_TitleBg, card)
            dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, border)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, bg)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, border)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabHovered, sec)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrabActive, accent)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 4)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 12, 8)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 8, 5)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 4)
    return theme

_global_themes = {
    "dark":  _build_global_theme("dark"),
    "light": _build_global_theme("light"),
}
dpg.bind_theme(_global_themes[current_theme])

# ============================================================
# UI STATE
# ============================================================
_port_list   = []
_user_id_map = {}
_plat_id_map = {}
_prev_status = ("", "")

# ============================================================
# CALLBACKS  (defined before UI layout)
# ============================================================
def _refresh_users():
    users = db.list_users()
    _user_id_map.clear()
    names = []
    for uid, uname in users:
        names.append(uname)
        _user_id_map[uname] = uid
    dpg.configure_item("user_combo", items=names)
    saved = _load_settings().get("last_user", "")
    if saved in names:
        dpg.set_value("user_combo", saved)
    elif names:
        dpg.set_value("user_combo", names[0])

def _refresh_platforms():
    platforms = db.list_platforms()
    _plat_id_map.clear()
    names = []
    for pid, pname, pw, ph in platforms:
        names.append(pname)
        _plat_id_map[pname] = pid
    dpg.configure_item("plat_combo", items=names)
    saved = _load_settings().get("last_platform", "")
    if saved in names:
        dpg.set_value("plat_combo", saved)
    elif names:
        dpg.set_value("plat_combo", names[0])

def _on_user_change(s, a, u):
    _save_settings({"last_user": dpg.get_value("user_combo")})

def _on_plat_change(s, a, u):
    _save_settings({"last_platform": dpg.get_value("plat_combo")})

def _show_add_user(s=None, a=None, u=None):
    dpg.set_value("add_user_input", "")
    dpg.configure_item("add_user_modal", show=True)

def _do_add_user(s=None, a=None, u=None):
    name = dpg.get_value("add_user_input").strip()
    if name:
        try:
            db.add_user(name)
        except Exception:
            pass
        _refresh_users()
        dpg.set_value("user_combo", name)
    dpg.configure_item("add_user_modal", show=False)

def _show_del_user(s=None, a=None, u=None):
    uname = dpg.get_value("user_combo")
    if uname and uname in _user_id_map:
        sessions = db.list_sessions(user_id=_user_id_map[uname])
        msg = f'Supprimer "{uname}" ?'
        if sessions:
            msg += f"\n{len(sessions)} session(s) seront supprimees."
        dpg.set_value("del_confirm_text", msg)
        dpg.set_item_user_data("del_confirm_ok", ("user", uname))
        dpg.configure_item("del_confirm_modal", show=True)

def _show_add_plat(s=None, a=None, u=None):
    dpg.set_value("add_plat_input", "")
    dpg.configure_item("add_plat_modal", show=True)

def _do_add_plat(s=None, a=None, u=None):
    name = dpg.get_value("add_plat_input").strip()
    if name:
        try:
            db.add_platform(name, BOARD_WIDTH_MM, BOARD_HEIGHT_MM)
        except Exception:
            pass
        _refresh_platforms()
        dpg.set_value("plat_combo", name)
    dpg.configure_item("add_plat_modal", show=False)

def _show_del_plat(s=None, a=None, u=None):
    pname = dpg.get_value("plat_combo")
    if pname and pname in _plat_id_map:
        sessions = db.list_sessions(platform_id=_plat_id_map[pname])
        msg = f'Supprimer "{pname}" ?'
        if sessions:
            msg += f"\n{len(sessions)} session(s) seront supprimees."
        dpg.set_value("del_confirm_text", msg)
        dpg.set_item_user_data("del_confirm_ok", ("platform", pname))
        dpg.configure_item("del_confirm_modal", show=True)

def _do_delete_confirmed(s=None, a=None, u=None):
    kind, name = dpg.get_item_user_data("del_confirm_ok")
    if kind == "user":
        uid = _user_id_map.get(name)
        if uid:
            for ses in db.list_sessions(user_id=uid):
                db.delete_session(ses["id"])
            db.delete_user(uid)
            _refresh_users()
    elif kind == "platform":
        pid = _plat_id_map.get(name)
        if pid:
            for ses in db.list_sessions(platform_id=pid):
                db.delete_session(ses["id"])
            db.delete_platform(pid)
            _refresh_platforms()
    dpg.configure_item("del_confirm_modal", show=False)

def _refresh_ports(s=None, a=None, u=None):
    global _port_list
    _port_list = list_ports()
    labels = [lbl for _, lbl, _, _ in _port_list]
    dpg.configure_item("port_combo", items=labels if labels else ["-- Aucun port --"])
    target_idx = next((i for i, (_, _, _, t) in enumerate(_port_list) if t), None)
    bt_idx     = next((i for i, (_, _, bt, _) in enumerate(_port_list) if bt), None)
    if target_idx is not None:
        dpg.set_value("port_combo", labels[target_idx])
        dpg.set_value("label_conn_info", "ForcePlatform detecte")
    elif bt_idx is not None:
        dpg.set_value("port_combo", labels[bt_idx])
        n_bt = sum(1 for _, _, bt, _ in _port_list if bt)
        dpg.set_value("label_conn_info",
                      f"{n_bt} ports BT" if n_bt > 1 else "1 port BT")
    elif labels:
        dpg.set_value("port_combo", labels[0])
        dpg.set_value("label_conn_info", f"{len(labels)} port(s)")
    else:
        dpg.set_value("label_conn_info", "Aucun port")

def _do_connect(s=None, a=None, u=None):
    global serial_conn, _port_list
    if not _port_list:
        dpg.set_value("label_conn_info", "Aucun port disponible")
        return
    sel = dpg.get_value("port_combo")
    device, is_bt, is_target = None, False, False
    for dev, lbl, bt, tgt in _port_list:
        if lbl == sel:
            device, is_bt, is_target = dev, bt, tgt
            break
    if not device:
        dpg.set_value("label_conn_info", "Selectionne un port")
        return
    if serial_conn:
        try: serial_conn.close()
        except: pass
        serial_conn = None
    baud = int(dpg.get_value("baud_combo"))
    if is_bt or is_target:
        candidates = [device]
        for dev, lbl, bt, tgt in _port_list:
            if bt and dev != device:
                candidates.append(dev)
        dpg.set_value("label_conn_info", f"Test de {len(candidates)} port(s)...")
        found = None
        for cand in candidates:
            dpg.set_value("label_conn_info", f"Test {cand}...")
            conn = _try_port(cand, baud)
            if conn:
                found = (cand, conn)
                break
        if not found:
            dpg.set_value("label_conn_info", "Aucun port ne repond")
            return
        device, conn = found
        serial_conn = conn
    else:
        dpg.set_value("label_conn_info", "Connexion...")
        try:
            serial_conn = serial.Serial(device, baud, timeout=1)
        except Exception as e:
            dpg.set_value("label_conn_info", f"Erreur: {e}")
            return
    mode = "BT" if is_bt else "USB"
    dpg.set_value("label_conn_info", f"Connecte {mode} {device}")

def _do_disconnect(s=None, a=None, u=None):
    global serial_conn
    if serial_conn:
        try: serial_conn.close()
        except: pass
        serial_conn = None
    dpg.set_value("label_conn_info", "Deconnecte")

def _send_tare(s=None, a=None, u=None):
    send_json({"cmd": "tare"})

def _make_cal_cb(idx):
    def cb(s=None, a=None, u=None):
        try:
            ref = dpg.get_value("entry_ref_weight")
        except Exception:
            return
        send_json({"cmd": "cal", "sensor": idx + 1, "weight": ref * 1000})
        dpg.set_value("label_cal_log", f"Calibration capteur {idx+1}...")
    return cb

def _get_calib(s=None, a=None, u=None):
    send_json({"cmd": "get_calib"})
    dpg.set_value("label_cal_log", "Recuperation...")

def _toggle_recording(s=None, a=None, u=None):
    if recorder.is_recording:
        sid = recorder.stop()
        dpg.set_item_label("btn_rec", "DEMARRER ENREGISTREMENT")
        dpg.bind_item_theme("btn_rec", _btn_theme(_t("btn_connect_bg"),
                            _t("btn_connect_hv")))
        dpg.set_value("lbl_rec_time", "")
        dpg.set_value("lbl_rec_samples",
                      f"Session #{sid} sauvegardee" if sid else "")
    else:
        uname = dpg.get_value("user_combo")
        pname = dpg.get_value("plat_combo")
        uid = _user_id_map.get(uname)
        pid = _plat_id_map.get(pname)
        if uid is None:
            dpg.set_value("lbl_rec_samples", "Selectionner un utilisateur")
            return
        if pid is None:
            dpg.set_value("lbl_rec_samples", "Selectionner une plateforme")
            return
        recorder.start(uid, pid)
        dpg.set_item_label("btn_rec", "ARRETER ENREGISTREMENT")
        dpg.bind_item_theme("btn_rec", _btn_theme(_t("accent_red"),
                            _t("accent_amber")))

def _open_history(s=None, a=None, u=None):
    """Launch tkinter SessionBrowser in a separate thread."""
    def _run():
        import tkinter as tk
        from replay_window import SessionBrowser
        root = tk.Tk()
        root.withdraw()
        SessionBrowser(root, THEMES, current_theme,
                       (_load_settings, _save_settings))
        root.mainloop()
    threading.Thread(target=_run, daemon=True).start()

def _toggle_dashboard(s=None, a=None, u=None):
    global web_server_thread, web_server_running
    if web_server_running:
        web_server_running = False
        dpg.set_item_label("btn_dashboard", "DASHBOARD WEB : OFF")
        dpg.set_value("lbl_dashboard_url", "")
    else:
        try:
            from web_dashboard import start_web_server
            import socket
            port = 5000
            web_server_thread = start_web_server(port)
            web_server_running = True
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.connect(("8.8.8.8", 80))
                local_ip = sock.getsockname()[0]
                sock.close()
            except Exception:
                local_ip = "localhost"
            url = f"http://{local_ip}:{port}"
            dpg.set_item_label("btn_dashboard", "DASHBOARD WEB : ON")
            dpg.set_value("lbl_dashboard_url", url)
            webbrowser.open(url)
        except Exception as e:
            dpg.set_value("lbl_dashboard_url", f"Erreur: {e}")

def _toggle_theme(s=None, a=None, u=None):
    global current_theme
    current_theme = "light" if current_theme == "dark" else "dark"
    _refresh_theme_cache()
    dpg.bind_theme(_global_themes[current_theme])
    dpg.set_item_label("btn_theme", "\u2600" if current_theme == "dark" else "\u263e")
    _apply_accent_colors()
    _force_board_redraw()
    _save_settings({"theme": current_theme})

# ============================================================
# UI LAYOUT
# ============================================================
with dpg.window(tag="main_window", no_title_bar=True, no_move=True,
                no_resize=True, no_scrollbar=True):

    # ── Title bar (table: title left, freq/status right) ────
    with dpg.table(header_row=False, borders_innerH=False,
                   borders_innerV=False, borders_outerH=False,
                   borders_outerV=False):
        dpg.add_table_column(width_fixed=True)
        dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)
        dpg.add_table_column(width_fixed=True)
        with dpg.table_row():
            with dpg.group(horizontal=True):
                t_title = dpg.add_text("GraviCore", tag="title_text")
                if font_title:
                    dpg.bind_item_font(t_title, font_title)
                dpg.add_spacer(width=10)
                with dpg.group():
                    dpg.add_spacer(height=4)
                    dpg.add_button(label="\u2600" if current_theme == "dark" else "\u263e",
                                   tag="btn_theme", callback=_toggle_theme,
                                   width=36, height=36)
            dpg.add_spacer()
            with dpg.group():
                dpg.add_spacer(height=7)
                with dpg.group(horizontal=True):
                    t_freq = dpg.add_text("-- Hz", tag="label_freq")
                    if font_small:
                        dpg.bind_item_font(t_freq, font_small)
                    dpg.add_spacer(width=15)
                    t_status = dpg.add_text("DECONNECTE", tag="label_status")
                    if font_small:
                        dpg.bind_item_font(t_status, font_small)

    dpg.add_separator()

    # ── User / Platform bar ──────────────────────────────────
    with dpg.group(horizontal=True):
        dpg.add_text("UTILISATEUR")
        dpg.add_combo([], tag="user_combo", width=160, callback=_on_user_change)
        dpg.add_button(label="+ Ajouter", callback=_show_add_user)
        dpg.add_button(label="Suppr.", callback=_show_del_user)
        dpg.add_spacer(width=30)
        dpg.add_text("PLATEFORME")
        dpg.add_combo([], tag="plat_combo", width=200, callback=_on_plat_change)
        dpg.add_button(label="+ Ajouter", callback=_show_add_plat)
        dpg.add_button(label="Suppr.", callback=_show_del_plat)

    dpg.add_separator()

    # ── Connection bar ───────────────────────────────────────
    with dpg.group(horizontal=True):
        dpg.add_text("PORT")
        dpg.add_combo([], tag="port_combo", width=380)
        dpg.add_combo(["9600", "115200", "921600"], tag="baud_combo",
                       default_value="921600", width=100)
        dpg.add_button(label="Actualiser", callback=_refresh_ports)
        btn_conn = dpg.add_button(label="Connecter", tag="btn_connect",
                                  callback=_do_connect)
        dpg.bind_item_theme(btn_conn, _btn_theme(_t("btn_connect_bg"),
                            _t("btn_connect_hv")))
        dpg.add_button(label="Deconnecter", callback=_do_disconnect)
        dpg.add_spacer(width=10)
        ci = dpg.add_text("", tag="label_conn_info")
        if font_mono:
            dpg.bind_item_font(ci, font_mono)

    dpg.add_separator()
    dpg.add_spacer(height=2)

    # ── Main content ─────────────────────────────────────────
    with dpg.group(horizontal=True, tag="main_content"):

        # ── LEFT PANEL ───────────────────────────────────────
        with dpg.child_window(width=280, tag="left_panel", border=False):
            with dpg.tab_bar():

                # TAB: Capteurs
                with dpg.tab(label="  Capteurs  "):
                    t_cap = dpg.add_text("CAPTEURS")
                    if font_header:
                        dpg.bind_item_font(t_cap, font_header)
                    dpg.bind_item_theme(t_cap, _txt_theme(_t("text_secondary")))
                    dpg.add_spacer(height=4)

                    for i in range(4):
                        with dpg.group(horizontal=True):
                            sn = dpg.add_text(SENSOR_NAMES[i],
                                              tag=f"sensor_name_{i}")
                            dpg.bind_item_theme(sn, _txt_theme(_sc(i)))
                            dpg.add_spacer(width=20)
                            wt = dpg.add_text("0.00 kg", tag=f"weight_{i}")
                            if font_mono_large:
                                dpg.bind_item_font(wt, font_mono_large)
                        bar = dpg.add_progress_bar(default_value=0,
                                                   tag=f"bar_{i}", width=-1)
                        dpg.bind_item_theme(bar, _bar_theme(_sc(i)))
                        dpg.add_spacer(height=2)

                    dpg.add_separator()
                    dpg.add_spacer(height=4)

                    with dpg.group(horizontal=True):
                        tl = dpg.add_text("POIDS TOTAL")
                        dpg.bind_item_theme(tl, _txt_theme(_t("text_secondary")))
                        dpg.add_spacer(width=20)
                        tt = dpg.add_text("0.00 kg", tag="label_total")
                        if font_mono_large:
                            dpg.bind_item_font(tt, font_mono_large)
                        dpg.bind_item_theme(tt, _txt_theme(_t("accent_blue")))

                    dpg.add_spacer(height=6)
                    btn_tare = dpg.add_button(label="TARE", callback=_send_tare,
                                              width=-1, height=32)
                    dpg.bind_item_theme(btn_tare, _btn_theme(_t("tare_bg"),
                                        _t("tare_hover"), _t("text_primary")))

                # TAB: Calibration
                with dpg.tab(label="  Calibration  "):
                    t_cal = dpg.add_text("CALIBRATION")
                    if font_header:
                        dpg.bind_item_font(t_cal, font_header)
                    dpg.bind_item_theme(t_cal, _txt_theme(_t("text_secondary")))
                    dpg.add_spacer(height=4)

                    with dpg.group(horizontal=True):
                        dpg.add_text("Poids ref :")
                        dpg.add_input_float(tag="entry_ref_weight",
                                            default_value=1.0, width=80,
                                            format="%.3f", step=0)
                        dpg.add_text("kg")

                    dpg.add_spacer(height=4)
                    cl = dpg.add_text("-- en attente --", tag="label_cal_log",
                                      wrap=240)
                    if font_mono:
                        dpg.bind_item_font(cl, font_mono)
                    dpg.add_spacer(height=4)

                    for i in range(4):
                        b = dpg.add_button(label=f"CAL {i+1}  {SENSOR_NAMES[i]}",
                                           tag=f"btn_cal_{i}",
                                           callback=_make_cal_cb(i), width=-1)
                        dpg.bind_item_theme(b, _btn_theme(_t("cal_bg"),
                                            _t("cal_hover"), _sc(i)))
                        dpg.add_spacer(height=2)

                    dpg.add_spacer(height=4)
                    dpg.add_button(label="Lire calibration ESP",
                                   callback=_get_calib, width=-1)
                    dpg.add_spacer(height=4)

                    for i in range(4):
                        cdl = dpg.add_text(f"C{i+1}: off=--  sc=--",
                                           tag=f"calib_lbl_{i}")
                        if font_mono:
                            dpg.bind_item_font(cdl, font_mono)
                        dpg.bind_item_theme(cdl, _txt_theme(_sc(i)))

                # TAB: Outils
                with dpg.tab(label="  Outils  "):
                    dpg.add_spacer(height=8)
                    dpg.add_button(label="HISTORIQUE SESSIONS",
                                   callback=_open_history, width=-1, height=35)
                    dpg.add_spacer(height=4)
                    dpg.add_button(label="DASHBOARD WEB : OFF",
                                   tag="btn_dashboard",
                                   callback=_toggle_dashboard, width=-1,
                                   height=35)
                    dpg.add_spacer(height=4)
                    durl = dpg.add_text("", tag="lbl_dashboard_url")
                    if font_mono:
                        dpg.bind_item_font(durl, font_mono)

        # ── RIGHT PANEL ──────────────────────────────────────
        with dpg.child_window(tag="right_panel", border=False):
            # Recording controls
            with dpg.group(horizontal=True):
                btn_r = dpg.add_button(label="DEMARRER ENREGISTREMENT",
                                       tag="btn_rec",
                                       callback=_toggle_recording, height=32)
                dpg.bind_item_theme(btn_r, _btn_theme(_t("btn_connect_bg"),
                                    _t("btn_connect_hv")))
                dpg.add_spacer(width=10)
                rt = dpg.add_text("", tag="lbl_rec_time")
                if font_mono:
                    dpg.bind_item_font(rt, font_mono)
                dpg.bind_item_theme(rt, _txt_theme(_t("accent_red")))
                dpg.add_spacer(width=10)
                dpg.add_text("", tag="lbl_rec_samples")

            dpg.add_spacer(height=2)

            # Visualisation header
            with dpg.group(horizontal=True):
                dpg.add_text("VISUALISATION")
                dpg.add_spacer(width=10)
                td = dpg.add_text(
                    f"Planche {BOARD_WIDTH_MM}x{BOARD_HEIGHT_MM} mm")
                dpg.bind_item_theme(td, _txt_theme(_t("text_dim")))
                dpg.add_spacer(width=30)
                tc = dpg.add_text("X: 0.0 mm  Y: 0.0 mm",
                                  tag="label_coords")
                dpg.bind_item_theme(tc, _txt_theme(_t("accent_teal")))
                if font_coords:
                    dpg.bind_item_font(tc, font_coords)

            dpg.add_spacer(height=4)

            # Drawlist (initial size, resized each frame)
            dpg.add_drawlist(width=800, height=500, tag="board_drawlist")

# ── Modal dialogs ────────────────────────────────────────────
with dpg.window(modal=True, show=False, tag="add_user_modal",
                label="Nouvel utilisateur", width=300, height=100,
                no_resize=True):
    dpg.add_input_text(tag="add_user_input", hint="Nom...", width=-1,
                       on_enter=True, callback=_do_add_user)
    with dpg.group(horizontal=True):
        dpg.add_button(label="OK", callback=_do_add_user, width=120)
        dpg.add_button(label="Annuler", width=120,
                       callback=lambda s, a, u: dpg.configure_item(
                           "add_user_modal", show=False))

with dpg.window(modal=True, show=False, tag="add_plat_modal",
                label="Nouvelle plateforme", width=300, height=100,
                no_resize=True):
    dpg.add_input_text(tag="add_plat_input", hint="Nom...", width=-1,
                       on_enter=True, callback=_do_add_plat)
    with dpg.group(horizontal=True):
        dpg.add_button(label="OK", callback=_do_add_plat, width=120)
        dpg.add_button(label="Annuler", width=120,
                       callback=lambda s, a, u: dpg.configure_item(
                           "add_plat_modal", show=False))

with dpg.window(modal=True, show=False, tag="del_confirm_modal",
                label="Confirmer suppression", width=350, height=120,
                no_resize=True):
    dpg.add_text("", tag="del_confirm_text", wrap=320)
    dpg.add_spacer(height=8)
    with dpg.group(horizontal=True):
        dpg.add_button(label="Supprimer", tag="del_confirm_ok",
                       callback=_do_delete_confirmed, width=140)
        dpg.add_button(label="Annuler", width=140,
                       callback=lambda s, a, u: dpg.configure_item(
                           "del_confirm_modal", show=False))

# ============================================================
# ACCENT COLOR APPLICATION
# ============================================================
def _apply_accent_colors():
    dpg.bind_item_theme("title_text", _txt_theme(_t("accent_blue")))
    dpg.bind_item_theme("label_coords", _txt_theme(_t("accent_teal")))
    dpg.bind_item_theme("label_total", _txt_theme(_t("accent_blue")))
    dpg.bind_item_theme("lbl_rec_time", _txt_theme(_t("accent_red")))
    dpg.bind_item_theme("btn_connect",
                        _btn_theme(_t("btn_connect_bg"), _t("btn_connect_hv")))
    for i in range(4):
        dpg.bind_item_theme(f"sensor_name_{i}", _txt_theme(_sc(i)))
        dpg.bind_item_theme(f"bar_{i}", _bar_theme(_sc(i)))
        dpg.bind_item_theme(f"calib_lbl_{i}", _txt_theme(_sc(i)))
        dpg.bind_item_theme(f"btn_cal_{i}",
                            _btn_theme(_t("cal_bg"), _t("cal_hover"), _sc(i)))

_apply_accent_colors()

# ============================================================
# BOARD DRAWING
# ============================================================
def _force_board_redraw():
    _board["last_size"] = (0, 0)

def _create_dynamic_items():
    """Create trail dots + cross once (moved each frame)."""
    b = _board
    dl = "board_drawlist"
    b["trail_ids"] = []
    for i in range(TRAIL_LENGTH):
        tid = dpg.draw_circle(center=(0, 0), radius=2, fill=(0, 0, 0, 0),
                              color=(0, 0, 0, 0), parent=dl, show=False)
        b["trail_ids"].append(tid)
    b["cross_ids"] = {
        "h": dpg.draw_line(p1=(0, 0), p2=(0, 0), color=_t("cross_color"),
                           thickness=2, parent=dl),
        "v": dpg.draw_line(p1=(0, 0), p2=(0, 0), color=_t("cross_color"),
                           thickness=2, parent=dl),
        "txt": dpg.draw_text(pos=(0, 0), text="CoM", color=_t("com_color"),
                             size=16, parent=dl),
    }

def _draw_static_board():
    """Draw grid, outline, sensors, labels."""
    b = _board
    dl = "board_drawlist"
    left, right = b["left"], b["right"]
    top, bottom = b["top"], b["bottom"]
    cx, cy      = b["cx"], b["cy"]
    bw, bh      = right - left, bottom - top

    # Board fill
    dpg.draw_rectangle(pmin=(left, top), pmax=(right, bottom),
                       fill=_t("board_fill"), color=(0, 0, 0, 0), parent=dl)
    # Grid
    gc = _t("grid_color")
    n_cols = BOARD_WIDTH_MM // 5
    n_rows = BOARD_HEIGHT_MM // 5
    sx, sy = bw / n_cols, bh / n_rows
    for i in range(1, n_cols):
        gx = left + i * sx
        dpg.draw_line((gx, top), (gx, bottom), color=gc, parent=dl)
    for i in range(1, n_rows):
        gy = top + i * sy
        dpg.draw_line((left, gy), (right, gy), color=gc, parent=dl)

    # Center dashes
    oc = _t("board_outline")
    dpg.draw_line((cx, top), (cx, bottom), color=oc, thickness=1, parent=dl)
    dpg.draw_line((left, cy), (right, cy), color=oc, thickness=1, parent=dl)

    # Outline
    dpg.draw_rectangle(pmin=(left, top), pmax=(right, bottom),
                       color=oc, thickness=2, parent=dl)

    # Center mark
    dim = _t("text_dim")
    dpg.draw_line((cx - 6, cy), (cx + 6, cy), color=dim, parent=dl)
    dpg.draw_line((cx, cy - 6), (cx, cy + 6), color=dim, parent=dl)

    # Sensor circles: 0=HD, 1=HG, 2=BD, 3=BG
    corners = [(right, top), (left, top), (right, bottom), (left, bottom)]
    tp = _t("text_primary")
    b["sensor_val_ids"] = []
    for idx, (sx, sy) in enumerate(corners):
        sc = _sc(idx)
        dpg.draw_circle(center=(sx, sy), radius=CAP_R, fill=sc, color=tp,
                        thickness=1, parent=dl)
        # kg values: placed clearly outside circles
        is_right = idx % 2 == 0   # 0=HD, 2=BD are right side
        is_top   = idx < 2        # 0=HD, 1=HG are top
        if is_right:
            kx = sx - 75  # text ends before the circle (left of it)
        else:
            kx = sx + CAP_R + 8  # text starts after the circle (right of it)
        if is_top:
            ky = sy - CAP_R - 22  # above the circle
        else:
            ky = sy + CAP_R + 6   # below the circle
        vid = dpg.draw_text(pos=(kx, ky),
                            text="0.00 kg", color=sc, size=18, parent=dl)
        b["sensor_val_ids"].append(vid)
        # Sensor number: centered in circle (approx char width=8, height=14 at size 14)
        dpg.draw_text(pos=(sx - 4, sy - 8), text=str(idx + 1),
                      color=(255, 255, 255, 255), size=14, parent=dl)

    # Dimension labels
    dpg.draw_text(pos=(cx - 70, bottom + 30),
                  text="Gauche              Droite", color=dim,
                  size=14, parent=dl)
    dpg.draw_text(pos=(left - 50, cy - 35),
                  text="Haut\n  |\n  |\nBas", color=dim, size=13, parent=dl)
    dpg.draw_text(pos=(cx - 20, top - 42),
                  text=f"{BOARD_WIDTH_MM} mm", color=dim, size=13, parent=dl)
    dpg.draw_text(pos=(right + 14, cy - 12),
                  text=f"{BOARD_HEIGHT_MM}\nmm", color=dim, size=13, parent=dl)

def _update_board_size():
    """Check if drawlist needs resizing; recalculate geometry."""
    b = _board
    try:
        rp_w, rp_h = dpg.get_item_rect_size("right_panel")
    except Exception:
        return False
    dl_w = max(200, int(rp_w) - 16)
    dl_h = max(200, int(rp_h) - 95)
    if dl_w < 200 or dl_h < 200:
        return False
    if (dl_w, dl_h) == b["last_size"]:
        return False
    b["last_size"] = (dl_w, dl_h)
    dpg.configure_item("board_drawlist", width=dl_w, height=dl_h)

    avail_w = dl_w - 2 * MARGIN
    avail_h = dl_h - 2 * MARGIN
    if avail_w <= 0 or avail_h <= 0:
        return False
    if avail_w / avail_h > BOARD_RATIO:
        board_h = avail_h
        board_w = board_h * BOARD_RATIO
    else:
        board_w = avail_w
        board_h = board_w / BOARD_RATIO
    ccx, ccy = dl_w / 2, dl_h / 2
    b["left"]   = ccx - board_w / 2
    b["right"]  = ccx + board_w / 2
    b["top"]    = ccy - board_h / 2
    b["bottom"] = ccy + board_h / 2
    b["cx"], b["cy"] = ccx, ccy

    dpg.delete_item("board_drawlist", children_only=True)
    _draw_static_board()
    _create_dynamic_items()
    return True

# ============================================================
# PROCESS RESPONSES
# ============================================================
def _process_responses():
    with resp_lock:
        responses = list(response_queue)
        response_queue.clear()
    for data in responses:
        status = data.get("status", "")
        if status == "tare_ok":
            dpg.set_value("label_cal_log", "Tare effectuee")
        elif status == "cal_ok":
            s  = data["sensor"] - 1
            sc, off = data["scale"], data["offset"]
            calib_scales[s]  = sc
            calib_offsets[s] = off
            dpg.set_item_label(f"btn_cal_{s}",
                               f"CAL {s+1}  {SENSOR_NAMES[s]}")
            dpg.set_value(f"calib_lbl_{s}",
                          f"C{s+1}: off={off}  sc={sc:.4f}")
            dpg.set_value("label_cal_log",
                          f"Capteur {s+1} calibre  Scale={sc:.4f}")
        elif status == "cal_error":
            dpg.set_value("label_cal_log", data.get("msg", "erreur"))
        elif status == "calib_values":
            for i in range(4):
                off = data.get(f"off{i+1}", 0)
                sc  = data.get(f"sc{i+1}", 0.0)
                calib_offsets[i] = off
                calib_scales[i]  = sc
                dpg.set_value(f"calib_lbl_{i}",
                              f"C{i+1}: off={off}  sc={sc:.4f}")
            dpg.set_value("label_cal_log", "Valeurs recuperees")

# ============================================================
# FRAME UPDATE  (called every frame — GPU vsync)
# ============================================================
def _frame_update():
    global _update_ready_flag, _prev_status, _prev_total, _prev_freq_str

    _process_responses()
    _update_board_size()

    weight = list(raw_w)
    total  = sum(weight)
    total_gt = total >= 1000

    # Weights + bars (conditional updates)
    sv_ids = _board.get("sensor_val_ids")
    for i in range(4):
        if _prev_weights[i] != weight[i]:
            _prev_weights[i] = weight[i]
            w_str = f"{weight[i]/1000:.2f} kg"
            dpg.set_value(f"weight_{i}", w_str)
            if sv_ids:
                dpg.configure_item(sv_ids[i], text=w_str)
        bar_val = (weight[i] / max(total, 1)) if total_gt and weight[i] >= 1000 else 0
        dpg.set_value(f"bar_{i}", bar_val)

    if _prev_total != total:
        _prev_total = total
        dpg.set_value("label_total", f"{total/1000:.2f} kg")
    f_str = f"{freq:.0f} Hz"
    if f_str != _prev_freq_str:
        _prev_freq_str = f_str
        dpg.set_value("label_freq", f_str)

    # Center of mass
    b = _board
    if not total_gt:
        x_pos, y_pos = b["cx"], b["cy"]
        x_mm, y_mm = 0.0, 0.0
        xr, yr = 0.0, 0.0
    else:
        xr = (weight[0]+weight[2]-weight[1]-weight[3]) / total
        yr = (weight[2]+weight[3]-weight[0]-weight[1]) / total
        half_w = (b["right"] - b["left"]) / 2
        half_h = (b["bottom"] - b["top"]) / 2
        x_pos = max(b["left"], min(b["right"], b["cx"] + xr * half_w))
        y_pos = max(b["top"], min(b["bottom"], b["cy"] + yr * half_h))
        x_mm = xr * BOARD_WIDTH_MM / 2
        y_mm = yr * BOARD_HEIGHT_MM / 2

    dpg.set_value("label_coords", f"X: {x_mm:+.1f} mm   Y: {y_mm:+.1f} mm")

    # Recording
    if recorder.is_recording:
        t_ms = int((time.time() - recorder.start_time) * 1000)
        recorder.record(t_ms, weight[0], weight[1], weight[2], weight[3],
                        xr, yr)
        elapsed = recorder.elapsed
        mins = int(elapsed // 60)
        secs = elapsed % 60
        dpg.set_value("lbl_rec_time", f"{mins:02d}:{secs:05.2f}")
        dpg.set_value("lbl_rec_samples", f"{recorder.sample_count} samples")

    # Trail (pre-computed colors/sizes from _trail_colors/_trail_sizes)
    com_trail.append((x_pos, y_pos))
    trail_ids = b["trail_ids"]
    if trail_ids:
        n_trail = len(com_trail) - 1
        for idx in range(TRAIL_LENGTH):
            tid = trail_ids[idx]
            if idx < n_trail:
                tx, ty = com_trail[idx]
                c = _trail_colors[idx]
                dpg.configure_item(tid, center=(tx, ty),
                                   radius=_trail_sizes[idx],
                                   fill=c, color=c, show=True)
            else:
                dpg.configure_item(tid, show=False)

    # Cross
    if b["cross_ids"]:
        cc = _t("cross_color")
        dpg.configure_item(b["cross_ids"]["h"],
                           p1=(x_pos - CROSS_SIZE, y_pos),
                           p2=(x_pos + CROSS_SIZE, y_pos), color=cc)
        dpg.configure_item(b["cross_ids"]["v"],
                           p1=(x_pos, y_pos - CROSS_SIZE),
                           p2=(x_pos, y_pos + CROSS_SIZE), color=cc)
        dpg.configure_item(b["cross_ids"]["txt"],
                           pos=(x_pos - 10, y_pos - CROSS_SIZE - 16),
                           color=_t("com_color"))

    # Status
    elapsed_t = time.time() - last_received
    is_connected = False
    if serial_conn is None:
        st = ("DECONNECTE", "accent_red")
    elif elapsed_t < 2:
        st = ("CONNECTE", "accent_green")
        is_connected = True
    elif elapsed_t < 5:
        st = ("ATTENTE...", "accent_amber")
    else:
        st = ("TIMEOUT", "accent_red")

    if st != _prev_status:
        _prev_status = st
        dpg.set_value("label_status", st[0])
        dpg.bind_item_theme("label_status", _txt_theme(_t(st[1])))

    remote_sync.update_state(is_recording=recorder.is_recording,
                             connected=is_connected)

    # Remote update
    if _update_ready_flag:
        _update_ready_flag = False
        dpg.set_value("label_conn_info",
                      "Mise a jour telechargee — redemarrer l'app")

# ============================================================
# VIEWPORT + MAIN LOOP
# ============================================================
_icon_path = None
for _p in ([os.path.join(getattr(sys, '_MEIPASS', ''), 'icon.ico')] if getattr(sys, 'frozen', False) else []) + \
          [os.path.join(_app_dir(), 'icon.ico')]:
    if os.path.isfile(_p):
        _icon_path = _p
        break

dpg.create_viewport(title="Centre de Masse -- Plateforme de Force",
                    width=1280, height=800,
                    small_icon=_icon_path or "",
                    large_icon=_icon_path or "")
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("main_window", True)
dpg.maximize_viewport()

_refresh_users()
_refresh_platforms()
_refresh_ports()

def _on_update_ready():
    global _update_ready_flag
    _update_ready_flag = True

remote_sync.on_update_ready = _on_update_ready
remote_sync.start()

# Main render loop — runs at GPU vsync (60-144+ fps)
while dpg.is_dearpygui_running():
    _frame_update()
    dpg.render_dearpygui_frame()

# ── Clean shutdown ───────────────────────────────────────────
if recorder.is_recording:
    recorder.stop()
if remote_sync.is_running:
    remote_sync.stop()
if serial_conn:
    try:
        serial_conn.close()
    except Exception:
        pass
dpg.destroy_context()
