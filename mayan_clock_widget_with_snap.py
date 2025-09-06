#!/usr/bin/env python3
\"\"\"Mayan Clock Widget with optional Snap-to-Taskbar (Windows)
--------------------------------------------------------------
- Requires: Python 3.8+ and PySide6 (UI) on Windows
- Run: python mayan_clock_widget_with_snap.py
- Build EXE: use the provided mayan_clock_widget.spec with PyInstaller
\"\"\"

import sys, os, math, ctypes, time
from datetime import datetime, date
from ctypes import wintypes
from functools import partial

# UI imports
try:
    from PySide6 import QtCore, QtGui, QtWidgets
except Exception as e:
    raise SystemExit(\"PySide6 required. Install with: pip install PySide6\") from e

# ---------- Mayan calendar conversions (GMT correlation) ----------
MAYAN_EPOCH_JDN = 584283  # JDN for 0.0.0.0.0 (GMT correlation)

TZOLKIN_NAMES = [
    \"Imix\", \"Ik'\", \"Ak'b'al\", \"K'an\", \"Chikchan\", \"Kimi\", \"Manik'\", \"Lamat\", \"Muluk\", \"Ok\",
    \"Chuwen\", \"Eb'\", \"B'en\", \"Ix\", \"Men\", \"Kib'\", \"Kab'an\", \"Etz'nab'\", \"Kawak\", \"Ajaw\"
]

HAAB_MONTHS = [
    \"Pop\", \"Wo'\", \"Sip\", \"Sotz'\", \"Sek\", \"Xul\", \"Yaxk'in'\", \"Mol\", \"Ch'en\", \"Yax\",
    \"Sak'\", \"Keh\", \"Mak\", \"K'ank'in\", \"Muwan\", \"Pax\", \"K'ayab\", \"Kumk'u\", \"Wayeb'\"
]

def gregorian_to_jdn(year, month, day):
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    jdn = day + ((153 * m + 2) // 5) + 365 * y + (y // 4) - (y // 100) + (y // 400) - 32045
    return jdn

def days_since_mayan_epoch(dt: date):
    jdn = gregorian_to_jdn(dt.year, dt.month, dt.day)
    return jdn - MAYAN_EPOCH_JDN

def long_count_from_days(days):
    baktun = days // 144000
    days %= 144000
    katun = days // 7200
    days %= 7200
    tun = days // 360
    days %= 360
    uinal = days // 20
    kin = days % 20
    return (baktun, katun, tun, uinal, kin)

def tzolkin_from_days(days):
    tz_num = (4 + days) % 13
    if tz_num == 0:
        tz_num = 13
    tz_name = TZOLKIN_NAMES[(19 + days) % 20]
    return (tz_num, tz_name)

def haab_from_days(days):
    haab_day_of_cycle = (8 + days) % 365
    month = haab_day_of_cycle // 20
    day = haab_day_of_cycle % 20
    if month >= 18:
        month = 18
        day = haab_day_of_cycle - 18*20
    return (day, HAAB_MONTHS[month])

def format_long_count(lc_tuple):
    return f\"{lc_tuple[0]}.{lc_tuple[1]}.{lc_tuple[2]}.{lc_tuple[3]}.{lc_tuple[4]}\"

# ---------- Windows taskbar helpers (ctypes) ----------
if sys.platform == 'win32':
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

    FindWindow = user32.FindWindowW
    FindWindow.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    FindWindow.restype = wintypes.HWND

    GetWindowRect = user32.GetWindowRect
    GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    GetWindowRect.restype = wintypes.BOOL

    GetSystemMetrics = user32.GetSystemMetrics
    GetSystemMetrics.argtypes = [wintypes.INT]
    SM_CXSCREEN = 0
    SM_CYSCREEN = 1

    # Utility to get rect of a window class/name
    def get_window_rect_by_class(class_name, window_name=None):
        hwnd = FindWindow(class_name, window_name)
        if not hwnd:
            return None
        rect = wintypes.RECT()
        if not GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        return (rect.left, rect.top, rect.right, rect.bottom)

    def get_taskbar_rect():
        # Find the Shell_TrayWnd (taskbar)
        rect = get_window_rect_by_class('Shell_TrayWnd', None)
        return rect

else:
    def get_taskbar_rect():
        return None

# ---------- Main widget ----------
class MayanWidget(QtWidgets.QWidget):
    def __init__(self, settings):
        flags = QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.settings = settings
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setWindowFlag(QtCore.Qt.WindowType.Tool)  # avoid taskbar
        self.drag_pos = None
        self.snap_enabled = False
        self.overlay_mode = True  # overlay the clock (user chose option A)
        self.setup_ui()
        self.create_tray_icon()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)  # update every second
        self.snap_timer = QtCore.QTimer(self)
        self.snap_timer.timeout.connect(self._maybe_snap_to_taskbar)
        self.snap_timer.start(1500)  # check taskbar every 1.5s when snap enabled
        self.update_clock()
        self.show()

    def setup_ui(self):
        self.resize(360, 140)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.frame = QtWidgets.QFrame()
        layout.addWidget(self.frame)
        f_layout = QtWidgets.QVBoxLayout(self.frame)
        f_layout.setContentsMargins(12, 10, 12, 12)
        f_layout.setSpacing(4)

        self.greg_label = QtWidgets.QLabel(\"\", alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        self.greg_label.setFont(QtGui.QFont(\"Segoe UI\", 10, QtGui.QFont.Weight.Bold))
        f_layout.addWidget(self.greg_label)

        self.lc_label = QtWidgets.QLabel(\"Long Count:\", alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        self.lc_label.setFont(QtGui.QFont(\"Segoe UI\", 13, QtGui.QFont.Weight.Bold))
        f_layout.addWidget(self.lc_label)

        bottom_row = QtWidgets.QHBoxLayout()
        self.tz_label = QtWidgets.QLabel(\"Tzolk'in:\") 
        self.tz_label.setFont(QtGui.QFont(\"Segoe UI\", 9))
        bottom_row.addWidget(self.tz_label)
        self.haab_label = QtWidgets.QLabel(\"Haab:\")
        self.haab_label.setFont(QtGui.QFont(\"Segoe UI\", 9))
        bottom_row.addWidget(self.haab_label)
        bottom_row.addStretch()
        f_layout.addLayout(bottom_row)

        footer = QtWidgets.QHBoxLayout()
        self.snap_btn = QtWidgets.QPushButton(\"Snap: Off\")
        self.snap_btn.clicked.connect(self.toggle_snap)
        footer.addWidget(self.snap_btn)
        self.topmost_btn = QtWidgets.QPushButton(\"Top\")
        self.topmost_btn.clicked.connect(self.toggle_topmost)
        footer.addWidget(self.topmost_btn)
        self.settings_btn = QtWidgets.QPushButton(\"⚙\")
        self.settings_btn.setFixedWidth(28)
        self.settings_btn.clicked.connect(self.open_settings)
        footer.addWidget(self.settings_btn)
        footer.addStretch()
        self.hide_btn = QtWidgets.QPushButton(\"Hide\")
        self.hide_btn.clicked.connect(self.hide_widget)
        footer.addWidget(self.hide_btn)
        f_layout.addLayout(footer)

        accent = self.settings.get('accent', '#4CAF50')
        bg_color = self.settings.get('bg', '#0f1720')
        text_color = self.settings.get('text', '#ffffff')
        panel_alpha = int(self.settings.get('alpha', 220))
        bg_rgba = f'rgba(15,23,32,{panel_alpha/255:.3f})'

        css = f\"\"\"#main_frame {{ 
            background: {bg_rgba};
            border-radius: 12px;
        }}
        QLabel {{ color: {text_color}; }}
        QPushButton {{ background: transparent; color: {text_color}; border: 1px solid rgba(255,255,255,0.06); padding:4px 8px; border-radius:6px; }}
        \"\"\"
        self.setStyleSheet(css)

    def paintEvent(self, event):
        path = QtGui.QPainterPath()
        rect = self.rect().adjusted(4, 4, -4, -4)
        path.addRoundedRect(rect, 12, 12)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.fillPath(path, QtGui.QColor(15,23,32,220))
        super().paintEvent(event)

    def update_clock(self):
        now = datetime.now()
        self.greg_label.setText(now.strftime('%a %d %b %Y  %H:%M:%S'))
        days = days_since_mayan_epoch(now.date())
        lc = long_count_from_days(days)
        tz = tzolkin_from_days(days)
        haab = haab_from_days(days)
        self.lc_label.setText(f\"Long Count: {format_long_count(lc)}\")
        self.tz_label.setText(f\"Tzolk'in: {tz[0]} {tz[1]}\")
        self.haab_label.setText(f\"Haab: {haab[0]} {haab[1]}\")

    # Mouse interactions for drag + right-click
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == QtCore.Qt.MouseButton.RightButton:
            self.open_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if self.drag_pos is not None and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.toggle_topmost()

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    def toggle_topmost(self):
        cur = bool(self.windowFlags() & QtCore.Qt.WindowType.WindowStaysOnTopHint)
        if cur:
            self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, False)
        else:
            self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)
        self.show()

    def hide_widget(self):
        self.hide()
        self.tray_icon.showMessage(\"Mayan Clock\", \"Widget hidden. Use tray icon to restore.\", QtWidgets.QSystemTrayIcon.MessageIcon.Information, 2000)

    # ---------- Snap functionality ----------
    def toggle_snap(self):
        self.snap_enabled = not self.snap_enabled
        self.snap_btn.setText(\"Snap: On\" if self.snap_enabled else \"Snap: Off\")
        if self.snap_enabled:
            self._maybe_snap_to_taskbar()

    def _maybe_snap_to_taskbar(self):
        if not self.snap_enabled or sys.platform != 'win32':
            return
        rect = get_taskbar_rect()
        if not rect:
            return
        left, top, right, bottom = rect
        screen_w = GetSystemMetrics(SM_CXSCREEN)
        screen_h = GetSystemMetrics(SM_CYSCREEN)
        w = self.width()
        h = self.height()
        margin = 6
        # Determine taskbar orientation: bottom if top > screen_h/2 is false? simpler check
        # If taskbar height small and near bottom -> bottom
        tb_height = bottom - top
        tb_width = right - left
        # default place near bottom-right of taskbar
        if tb_width >= tb_height:
            # horizontal taskbar
            if bottom > screen_h/2:
                # bottom taskbar -> position overlapping clock area (overlay)
                x = right - w - margin
                if self.overlay_mode:
                    y = bottom - h - margin  # overlap lower area (overlay)
                else:
                    y = top - h - margin  # sit above taskbar
            else:
                # top taskbar
                x = right - w - margin
                if self.overlay_mode:
                    y = top + margin  # overlay at top
                else:
                    y = bottom + margin  # sit below top taskbar
        else:
            # vertical taskbar (left or right)
            if left < screen_w/2:
                # left
                if self.overlay_mode:
                    x = left + margin
                else:
                    x = left + tb_width + margin
            else:
                # right
                if self.overlay_mode:
                    x = right - w - margin
                else:
                    x = left - w - margin
            # center vertically near clock area
            y = bottom - h - margin
            if y < 0:
                y = margin
        # move widget
        self.move(int(x), int(y))

    # ---------- Tray icon ----------
    def create_tray_icon(self):
        self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        icon = QtGui.QIcon()
        pix = QtGui.QPixmap(64,64)
        pix.fill(QtCore.Qt.GlobalColor.transparent)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setBrush(QtGui.QBrush(QtGui.QColor(self.settings.get('accent', '#4CAF50'))))
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.drawEllipse(4,4,56,56)
        p.end()
        icon.addPixmap(pix)
        self.tray_icon.setIcon(icon)
        menu = QtWidgets.QMenu()
        show_action = menu.addAction(\"Show/Hide\")
        show_action.triggered.connect(self.toggle_visibility_from_tray)
        snap_action = menu.addAction(\"Toggle Snap to Taskbar\")
        snap_action.triggered.connect(self.toggle_snap)
        settings_action = menu.addAction(\"Settings...\")
        settings_action.triggered.connect(self.open_settings)
        autostart_action = menu.addAction(\"Toggle Start with Windows\")
        autostart_action.triggered.connect(self.toggle_autostart)
        quit_action = menu.addAction(\"Quit\")
        quit_action.triggered.connect(QtWidgets.QApplication.instance().quit)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visibility_from_tray()

    def toggle_visibility_from_tray(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()

    # ---------- Settings (simple dialog) ----------
    def open_settings(self):
        dlg = SettingsDialog(self, self.settings)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.settings.update(dlg.get_settings())
            # minimally reapply accent
            self.create_tray_icon()
            self.update_clock()

    def open_context_menu(self, pos):
        menu = QtWidgets.QMenu()
        hide_act = menu.addAction(\"Hide\"); hide_act.triggered.connect(self.hide_widget)
        top_act = menu.addAction(\"Toggle Topmost\"); top_act.triggered.connect(self.toggle_topmost)
        menu.exec(QtGui.QCursor.pos())

    # ---------- Autostart (Windows only) ----------
    def toggle_autostart(self):
        try:
            import winreg
            exe_path = os.path.abspath(sys.argv[0])
            name = \"MayanClockWidget\"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r\"Software\\Microsoft\\Windows\\CurrentVersion\\Run\", 0, winreg.KEY_READ) as key:
                try:
                    val, _ = winreg.QueryValueEx(key, name)
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r\"Software\\Microsoft\\Windows\\CurrentVersion\\Run\", 0, winreg.KEY_SET_VALUE) as keyw:
                        winreg.DeleteValue(keyw, name)
                    QtWidgets.QMessageBox.information(self, \"Autostart\", \"Autostart disabled.\")
                    return
                except FileNotFoundError:
                    pass
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r\"Software\\Microsoft\\Windows\\CurrentVersion\\Run\", 0, winreg.KEY_SET_VALUE) as keyw:
                winreg.SetValueEx(keyw, name, 0, winreg.REG_SZ, f'\"{exe_path}\"')
            QtWidgets.QMessageBox.information(self, \"Autostart\", \"Autostart enabled (current user).\" )
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, \"Autostart error\", f\"Could not toggle autostart: {e}\")

# ---------- Settings Dialog ----------
class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.setWindowTitle(\"Mayan Widget Settings\")
        self.settings = dict(settings)
        self.setup_ui()

    def setup_ui(self):
        layout = QtWidgets.QFormLayout(self)
        self.accent_input = QtWidgets.QLineEdit(self.settings.get('accent','#4CAF50'))
        self.bg_input = QtWidgets.QLineEdit(self.settings.get('bg','#0f1720'))
        self.text_input = QtWidgets.QLineEdit(self.settings.get('text','#ffffff'))
        self.alpha_input = QtWidgets.QSpinBox(); self.alpha_input.setRange(0,255); self.alpha_input.setValue(self.settings.get('alpha',220))
        self.overlay_checkbox = QtWidgets.QCheckBox(\"Overlay (cover clock)\"); self.overlay_checkbox.setChecked(True)
        layout.addRow('Accent color (CSS hex):', self.accent_input)
        layout.addRow('Background color (CSS hex):', self.bg_input)
        layout.addRow('Text color (CSS hex):', self.text_input)
        layout.addRow('Panel opacity (0-255):', self.alpha_input)
        layout.addRow(self.overlay_checkbox)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_settings(self):
        out = {
            'accent': self.accent_input.text().strip(),
            'bg': self.bg_input.text().strip(),
            'text': self.text_input.text().strip(),
            'alpha': self.alpha_input.value()
        }
        out['overlay'] = self.overlay_checkbox.isChecked()
        return out

# ---------- Main ----------
def main():
    app = QtWidgets.QApplication(sys.argv)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    settings_file = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'mayan_widget_settings.json')
    settings = {}
    try:
        import json
        if os.path.exists(settings_file):
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
    except Exception:
        settings = {}
    defaults = {'accent':'#4CAF50', 'bg':'#0f1720', 'text':'#ffffff', 'alpha':220, 'overlay': True}
    for k,v in defaults.items():
        settings.setdefault(k,v)

    w = MayanWidget(settings)
    # Apply overlay preference
    w.overlay_mode = settings.get('overlay', True)
    # place initially near bottom-right
    try:
        rect = get_taskbar_rect()
        if rect:
            screen_w = GetSystemMetrics(SM_CXSCREEN)
            screen_h = GetSystemMetrics(SM_CYSCREEN)
            w.move(screen_w - w.width() - 16, screen_h - w.height() - 64)
        else:
            w.move(100,100)
    except Exception:
        w.move(100,100)

    exit_code = app.exec()
    # save settings
    try:
        import json
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
