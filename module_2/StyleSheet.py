# module_2/StyleSheet.py

import colorsys
import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QSlider, QLineEdit, QWidget,
    QMenu, QAction, QApplication
)
from PyQt5.QtCore import Qt, QPoint, pyqtSignal, QRect
from PyQt5.QtGui import (
    QColor, QPainter, QLinearGradient, QBrush,
    QPen, QPixmap, QCursor
)
from typing import Final, Any, Optional, Dict
# ─────────────────────────────────────────────
#  THEME FILE
# ─────────────────────────────────────────────
def get_theme_file_path() -> str:
    try:
        from module_1.root_path import get_app_data_dir, resource_path
        app_data_file = os.path.join(get_app_data_dir(), "theme.txt")
        if os.path.exists(app_data_file):
            return app_data_file
        bundled = resource_path("module_2/theme.txt")
        if os.path.exists(bundled):
            try:
                import shutil
                shutil.copy2(bundled, app_data_file)
                return app_data_file
            except Exception:
                pass
        return app_data_file
    except Exception:
        app_data = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or os.path.expanduser('~')
        base_dir = os.path.join(app_data, 'MBC_Vision_Inspector')
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, "theme.txt")

THEME_FILE = get_theme_file_path()

def save_theme_color(hex_color: str):
    try:
        theme_path = get_theme_file_path()
        os.makedirs(os.path.dirname(theme_path), exist_ok=True)
        with open(theme_path, 'w', encoding='utf-8') as f:
            json.dump({"bg_color": hex_color}, f)
    except Exception:
        pass

def load_theme_color() -> str:
    theme_path = get_theme_file_path()
    if os.path.exists(theme_path):
        try:
            with open(theme_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("bg_color", "#aedecc")
        except Exception:
            pass
    return "#aedecc"  # màu mặc định

# ─────────────────────────────────────────────
#  COLOR UTILS
# ─────────────────────────────────────────────
def hex_to_hsl(hex_color):
    hex_color = hex_color.lstrip('#')
    r, g, b = (int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h, s, l

def hsl_to_hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return '#{:02x}{:02x}{:02x}'.format(
        int(r * 255), int(g * 255), int(b * 255)
    )

def clamp(value, min_val=0.0, max_val=1.0):
    return max(min_val, min(max_val, value))

def generateTheme(bg_hex: str) -> dict:
    h, s, l = hex_to_hsl(bg_hex)

    surface      = hsl_to_hex(h, clamp(s * 0.4),  0.91)
    surface_mid  = hsl_to_hex(h, clamp(s * 0.5),  0.87)
    tab_inactive = hsl_to_hex(h, clamp(s * 0.6),  0.84)
    combo_bg     = hsl_to_hex(h, clamp(s * 0.15), 0.99)

    border_strong = hsl_to_hex(h, clamp(s * 0.75), 0.54)
    border_soft   = hsl_to_hex(h, clamp(s * 0.55), 0.68)

    btn_normal   = hsl_to_hex(h, clamp(s * 0.85), 0.46)
    btn_hover    = hsl_to_hex(h, clamp(s * 0.85), 0.36)
    btn_pressed  = hsl_to_hex(h, clamp(s * 0.85), 0.26)
    btn_ghost_bg = hsl_to_hex(h, clamp(s * 0.55), 0.82)
    btn_ghost_hov= hsl_to_hex(h, clamp(s * 0.55), 0.72)

    text_primary = hsl_to_hex(h, clamp(s * 0.70), 0.11)
    text_title   = hsl_to_hex(h, clamp(s * 0.80), 0.18)
    text_on_btn  = '#ffffff'

    return {
        'bg': bg_hex, 'surface': surface, 'surface_mid': surface_mid,
        'tab_inactive': tab_inactive, 'combo_bg': combo_bg,
        'border_strong': border_strong, 'border_soft': border_soft,
        'btn_normal': btn_normal, 'btn_hover': btn_hover,
        'btn_pressed': btn_pressed, 'btn_ghost_bg': btn_ghost_bg,
        'btn_ghost_hover': btn_ghost_hov,
        'text_primary': text_primary, 'text_title': text_title,
        'text_on_btn': text_on_btn,
    }

def buildStyleSheetforDashboard(bg_color: str = None) -> str:
    if bg_color is None:
        bg_color = load_theme_color()
        bg_color = "#f3f3f3"
    t = generateTheme(bg_color)
    return f"""
QMainWindow {{
    background-color: {t['bg']};
}}
QWidget#centralwidget {{
    background-color: {t['bg']};
}}
QLabel#heading {{
    color: {t['text_title']};
    background-color: transparent;
}}
QGroupBox {{
    background-color: {t['surface']};
    border: 1px solid {t['border_soft']};
    border-radius: 8px;
    margin-top: 15px;
    font-weight: bold;
    color: {t['text_primary']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    left: 15px;
    top: 0px;
    color: {t['btn_normal']};
}}
QLabel {{
    color: {t['text_primary']};
    font-weight: 500;
}}
QLineEdit, QSpinBox {{
    background-color: {t['combo_bg']};
    border: 1px solid {t['border_soft']};
    border-radius: 6px;
    padding: 5px 10px;
    color: {t['text_primary']};
}}
QLineEdit:focus, QSpinBox:focus {{
    border: 1px solid {t['btn_normal']};
    background-color: {t['surface']};
}}
QPushButton {{
    background-color: {t['surface']};
    border: 1px solid {t['border_soft']};
    border-radius: 6px;
    color: {t['text_primary']};
    padding: 6px 12px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {t['btn_ghost_bg']};
    border-color: {t['border_strong']};
}}
QPushButton:pressed {{
    background-color: {t['btn_ghost_hover']};
}}
QPushButton#pushButton_5, QPushButton#pushButton {{
    background-color: {t['btn_normal']};
    color: {t['text_on_btn']};
    border: none;
}}
QPushButton#pushButton_5:hover, QPushButton#pushButton:hover {{
    background-color: {t['btn_hover']};
}}
QPushButton#pushButton_5:pressed, QPushButton#pushButton:pressed {{
    background-color: {t['btn_pressed']};
}}
QPushButton#pushButton_5 {{
    background-color: #10B981;
    color: white;
    border: none;
}}
QPushButton#pushButton_5:hover {{
    background-color: #059669;
}}
QPushButton#pushButton_5:pressed {{
    background-color: #047857;
}}
QPushButton#pushButton {{
    background-color: #10B981;
    color: white;
    border: none;
}}
QPushButton#pushButton:hover {{
    background-color: #059669;
}}
QPushButton#pushButton:pressed {{
    background-color: #047857;
}}
QPushButton#pushButton_2 {{
    background-color: #10B981;
    color: white;
    border: none;
}}
QPushButton#pushButton_2:hover {{
    background-color: #059669;
}}
QPushButton#pushButton_2:pressed {{
    background-color: #047857;
}}
QTabWidget::pane {{
    border: 1px solid {t['border_soft']};
    background: {t['surface']};
    border-radius: 8px;
}}
QTabBar::tab {{
    background: {t['tab_inactive']};
    border: 1px solid {t['border_soft']};
    padding: 8px 20px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: {t['text_primary']};
    font-weight: bold;
}}
QTabBar::tab:selected {{
    background: {t['surface']};
    border-bottom-color: {t['surface']};
    color: {t['text_title']};
}}
QTabBar::tab:hover:!selected {{
    background: {t['surface_mid']};
}}
"""

def buildStyleSheet(bg_color: str) -> str:
    t = generateTheme(bg_color)
    return f"""
QMainWindow, QWidget#centralwidget {{
    background-color: {t['bg']};
    color: {t['text_primary']};
}}
QGroupBox {{
    background-color: {t['surface']};
    color: {t['text_primary']};
}}
QGroupBox::title {{
    color: {t['text_title']};
    background-color: {t['surface']};
}}
QPushButton {{
    background-color: {t['btn_normal']};
    color: {t['text_on_btn']};
}}
QPushButton:hover {{
    background-color: {t['btn_hover']};
}}
QPushButton:pressed {{
    background-color: {t['btn_pressed']};
}}
QComboBox {{
    background-color: {t['combo_bg']};
    color: {t['text_primary']};
}}
QRadioButton, QCheckBox {{
    color: {t['text_primary']};
}}
QLabel {{
    color: {t['text_primary']};
}}
QLineEdit {{
    background-color: {t['combo_bg']};
    color: {t['text_primary']};
}}
QTabWidget::pane {{
    background-color: {t['surface']};
}}
QTabBar::tab {{
    background: {t['tab_inactive']};
    color: {t['text_primary']};
}}
QTabBar::tab:selected {{
    background: {t['surface']};
    color: {t['text_title']};
}}
QSpinBox {{
    background-color: {t['surface_mid']};
    color: {t['text_primary']};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {t['tab_inactive']};
}}
QFrame {{
    background-color: {t['surface_mid']};
}}
"""

def setStyleSheet(main, bg_color: str = None):
    if bg_color is None:
        bg_color = load_theme_color()
    main.setStyleSheet(buildStyleSheet(bg_color))

# ─────────────────────────────────────────────
#  COLOR PICKER WIDGETS
# ─────────────────────────────────────────────
class ColorSquare(QWidget):
    """Ô vuông chọn Saturation (X) và Value/Brightness (Y)"""
    colorChanged = pyqtSignal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 200)
        self._hue = 120
        self._cursor_pos = QPoint(220, 0)

    def setHue(self, hue: int):
        self._hue = hue
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()

        # Gradient ngang: trắng → màu hue
        grad_h = QLinearGradient(0, 0, w, 0)
        grad_h.setColorAt(0, QColor(255, 255, 255))
        grad_h.setColorAt(1, QColor.fromHsv(self._hue, 255, 255))
        painter.fillRect(0, 0, w, h, QBrush(grad_h))

        # Gradient dọc: trong suốt → đen
        grad_v = QLinearGradient(0, 0, 0, h)
        grad_v.setColorAt(0, QColor(0, 0, 0, 0))
        grad_v.setColorAt(1, QColor(0, 0, 0, 255))
        painter.fillRect(0, 0, w, h, QBrush(grad_v))

        # Con trỏ
        painter.setPen(QPen(Qt.white, 2))
        x, y = self._cursor_pos.x(), self._cursor_pos.y()
        painter.drawEllipse(x - 6, y - 6, 12, 12)
        painter.setPen(QPen(Qt.black, 1))
        painter.drawEllipse(x - 7, y - 7, 14, 14)

    def _pick(self, pos):
        w, h = self.width(), self.height()
        x = clamp(pos.x(), 0, w - 1)
        y = clamp(pos.y(), 0, h - 1)
        self._cursor_pos = QPoint(int(x), int(y))
        s = int(x / w * 255)
        v = int((1 - y / h) * 255)
        color = QColor.fromHsv(self._hue, s, v)
        self.colorChanged.emit(color)
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._pick(e.pos())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self._pick(e.pos())

    def setColorFromHSV(self, h, s, v):
        self._hue = h
        w, h_ = self.width(), self.height()
        self._cursor_pos = QPoint(int(s / 255 * w), int((1 - v / 255) * h_))
        self.update()


class HueBar(QWidget):
    """Thanh kéo chọn Hue"""
    hueChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(18)
        self._hue = 120
        self._x = 0

    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, w, 0)
        for i in range(7):
            grad.setColorAt(i / 6, QColor.fromHsv(int(i * 60), 255, 255))
        painter.fillRect(0, 0, w, h, QBrush(grad))
        painter.setPen(QPen(Qt.white, 2))
        painter.drawLine(self._x, 0, self._x, h)

    def _pick(self, pos):
        w = self.width()
        x = clamp(pos.x(), 0, w - 1)
        self._x = int(x)
        self._hue = int(x / w * 360)
        self.hueChanged.emit(self._hue)
        self.update()

    def setHue(self, hue: int):
        self._hue = hue
        self._x = int(hue / 360 * self.width())
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._pick(e.pos())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self._pick(e.pos())


class ColorPickerDialog(QDialog):
    """Dialog chọn màu hoàn chỉnh"""

    def __init__(self, current_color: str = "#aedecc", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chọn màu giao diện")
        self.setFixedSize(300, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._color = QColor(current_color)
        self._result_color = current_color
        self._updating = False

        self._build_ui()
        self._apply_color(self._color)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # --- Ô vuông màu ---
        self.color_square = ColorSquare()
        self.color_square.colorChanged.connect(self._on_square_changed)
        layout.addWidget(self.color_square)

        # --- Thanh Hue ---
        self.hue_bar = HueBar()
        self.hue_bar.hueChanged.connect(self._on_hue_changed)
        layout.addWidget(self.hue_bar)

        # --- Sliders R, G, B ---
        slider_grid = QGridLayout()
        slider_grid.setSpacing(4)
        self._sliders = {}
        self._spin_edits = {}
        colors_labels = [('R', 'red'), ('G', 'green'), ('B', 'blue')]
        for row, (lbl, ch) in enumerate(colors_labels):
            label = QLabel(lbl)
            label.setFixedWidth(14)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 255)
            slider.setFixedHeight(16)
            edit = QLineEdit()
            edit.setFixedWidth(40)
            edit.setAlignment(Qt.AlignCenter)
            slider.valueChanged.connect(lambda v, c=ch: self._on_slider_changed(c, v))
            edit.editingFinished.connect(lambda c=ch: self._on_edit_finished(c))
            self._sliders[ch] = slider
            self._spin_edits[ch] = edit
            slider_grid.addWidget(label, row, 0)
            slider_grid.addWidget(slider, row, 1)
            slider_grid.addWidget(edit, row, 2)
        layout.addLayout(slider_grid)

        # --- Preview + HEX ---
        preview_row = QHBoxLayout()
        self.preview_box = QLabel()
        self.preview_box.setFixedSize(48, 32)
        self.preview_box.setStyleSheet("border: 1px solid #888; border-radius: 4px;")
        self.hex_edit = QLineEdit()
        self.hex_edit.setPlaceholderText("#aedecc")
        self.hex_edit.editingFinished.connect(self._on_hex_changed)
        preview_row.addWidget(self.preview_box)
        preview_row.addWidget(self.hex_edit)
        layout.addLayout(preview_row)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        self.btn_cancel = QPushButton("Hủy")
        self.btn_preview = QPushButton("Xem thử")
        self.btn_save = QPushButton("Lưu")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_preview.clicked.connect(self._emit_preview)
        self.btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_preview)
        btn_row.addWidget(self.btn_save)
        layout.addLayout(btn_row)

    # ── Internal helpers ──────────────────────────────────
    def _apply_color(self, color: QColor):
        """Đồng bộ toàn bộ UI từ một QColor"""
        self._updating = True
        r, g, b = color.red(), color.green(), color.blue()
        h, s, v = color.hsvHue(), color.hsvSaturation(), color.value()
        if h < 0:
            h = 0

        self._sliders['red'].setValue(r)
        self._sliders['green'].setValue(g)
        self._sliders['blue'].setValue(b)
        self._spin_edits['red'].setText(str(r))
        self._spin_edits['green'].setText(str(g))
        self._spin_edits['blue'].setText(str(b))

        hex_str = '#{:02x}{:02x}{:02x}'.format(r, g, b)
        self.hex_edit.setText(hex_str)
        self._result_color = hex_str

        self.preview_box.setStyleSheet(
            f"background-color: {hex_str}; border: 1px solid #888; border-radius: 4px;"
        )

        self.hue_bar.setHue(h)
        self.color_square.setHue(h)
        self.color_square.setColorFromHSV(h, s, v)
        self._color = color
        self._updating = False

    def _on_square_changed(self, color: QColor):
        if not self._updating:
            self._apply_color(color)

    def _on_hue_changed(self, hue: int):
        if not self._updating:
            self.color_square.setHue(hue)
            hsv = self._color.toHsv()
            new_color = QColor.fromHsv(hue, hsv.hsvSaturation(), hsv.value())
            self._apply_color(new_color)

    def _on_slider_changed(self, channel: str, value: int):
        if self._updating:
            return
        self._spin_edits[channel].setText(str(value))
        r = self._sliders['red'].value()
        g = self._sliders['green'].value()
        b = self._sliders['blue'].value()
        self._apply_color(QColor(r, g, b))

    def _on_edit_finished(self, channel: str):
        try:
            v = int(self._spin_edits[channel].text())
            v = clamp(v, 0, 255)
            self._sliders[channel].setValue(v)
        except ValueError:
            pass

    def _on_hex_changed(self):
        text = self.hex_edit.text().strip()
        if not text.startswith('#'):
            text = '#' + text
        color = QColor(text)
        if color.isValid():
            self._apply_color(color)

    def _emit_preview(self):
        self.previewRequested.emit(self._result_color)

    def _on_save(self):
        save_theme_color(self._result_color)
        self.accept()

    # ── Public ───────────────────────────────────────────
    previewRequested = pyqtSignal(str)

    def selectedColor(self) -> str:
        return self._result_color


# ─────────────────────────────────────────────
#  CONTEXT MENU MIXIN — gắn vào bất kỳ QMainWindow nào
# ─────────────────────────────────────────────
class ThemeMenuMixin:
    """
    Kế thừa mixin này cùng với QMainWindow để có
    context menu đổi theme khi click chuột phải.

    Ví dụ:
        class MyWindow(ThemeMenuMixin, QMainWindow):
            def __init__(self):
                super().__init__()
                self.init_theme_menu()
    """

    def init_theme_menu(self):
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_theme_menu)

    def _show_theme_menu(self, pos: QPoint):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #f5f5f5;
                border: 1px solid #aaa;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #d0ece4;
            }
        """)
        action_theme = QAction("🎨  Thay đổi theme màu", self)
        action_theme.triggered.connect(self._open_color_picker)
        menu.addAction(action_theme)
        menu.exec_(self.mapToGlobal(pos))

    def _open_color_picker(self):
        current = load_theme_color()
        dialog = ColorPickerDialog(current_color=current, parent=self)

        # Xem thử realtime
        dialog.previewRequested.connect(
            lambda hex_c: self.setStyleSheet(buildStyleSheet(hex_c))
        )

        if dialog.exec_() == QDialog.Accepted:
            # Lưu và áp dụng màu mới
            new_color = dialog.selectedColor()
            save_theme_color(new_color)
            self.setStyleSheet(buildStyleSheet(new_color))
        else:
            # Hủy → khôi phục màu cũ
            self.setStyleSheet(buildStyleSheet(load_theme_color()))

HTML5 = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Computer Vision Tools Interface</title>
<style>
body {
margin: 0;
padding: 0;
width: 1920px;
height: 1080px;
background: radial-gradient(ellipse at center, #1a2332 0%, #0f1419 70%, #000000 100%);
overflow: hidden;
font-family: 'Arial', sans-serif;
position: relative;
}

/* Grid pattern background */
.grid-bg {
position: absolute;
width: 100%;
height: 100%;
background-image: 
linear-gradient(rgba(0, 255, 255, 0.1) 1px, transparent 1px),
linear-gradient(90deg, rgba(0, 255, 255, 0.1) 1px, transparent 1px);
background-size: 50px 50px;
opacity: 0.3;
}

/* Soft edge blur effect */
.blur-overlay {
position: absolute;
top: 0;
left: 0;
width: 100%;
height: 100%;
box-shadow: inset 0 0 200px 100px rgba(0, 0, 0, 0.4);
pointer-events: none;
}

.container {
position: relative;
width: 100%;
height: 100%;
display: flex;
flex-direction: column;
align-items: center;
justify-content: center;
z-index: 10;
}

.main-title {
font-size: 4em;
font-weight: bold;
color: #00ffff;
text-align: center;
margin-bottom: 200px;
text-shadow: 
0 0 20px rgba(0, 255, 255, 0.8),
0 0 40px rgba(0, 255, 255, 0.4);
animation: glow-pulse 3s ease-in-out infinite alternate;
}

.central-hub {
position: relative;
width: 400px;
height: 400px;
margin: 0 auto;
display: flex;
align-items: center;
justify-content: center;
}

.core-circle {
width: 200px;
height: 200px;
border: 3px solid #00ffff;
border-radius: 50%;
position: relative;
animation: rotate 20s linear infinite;
box-shadow: 
0 0 30px rgba(0, 255, 255, 0.6),
inset 0 0 30px rgba(0, 255, 255, 0.2);
}

.inner-circle {
width: 120px;
height: 120px;
border: 2px solid #00cccc;
border-radius: 50%;
position: absolute;
top: 50%;
left: 50%;
transform: translate(-50%, -50%);
animation: rotate-reverse 15s linear infinite;
}

.pulse-ring {
position: absolute;
width: 300px;
height: 300px;
border: 2px solid rgba(0, 255, 255, 0.3);
border-radius: 50%;
top: 50%;
left: 50%;
transform: translate(-50%, -50%);
animation: pulse-ring 4s ease-in-out infinite;
}

.tool-node {
position: absolute;
padding: 15px 30px;
background: linear-gradient(135deg, rgba(0, 255, 255, 0.2), rgba(0, 200, 200, 0.4));
border: 2px solid #00ffff;
border-radius: 25px;
color: #ffffff;
font-weight: bold;
font-size: 1.1em;
text-shadow: 0 0 10px rgba(0, 255, 255, 0.8);
backdrop-filter: blur(10px);
box-shadow: 
0 0 20px rgba(0, 255, 255, 0.4),
inset 0 0 20px rgba(0, 255, 255, 0.1);
animation: float 6s ease-in-out infinite;
transition: all 0.3s ease;
cursor: pointer;
}

.tool-node:hover {
transform: scale(1.1);
box-shadow: 
0 0 30px rgba(0, 255, 255, 0.8),
inset 0 0 30px rgba(0, 255, 255, 0.2);
}

/* Positioning for tool nodes */
.opencv { top: -90px; left: -600px ; animation-delay: 0s; }
.cuda { top: -90px; left: -400px ; animation-delay: 0.5s; }
.simplecv { left: -200px; top: -90px; animation-delay: 1s; }
.yolo { left: 0px; top: -90px; animation-delay: 1.5s; }
.tensorflow { left: 200px; top: -90px; animation-delay: 2s; }
.pytorch { left: 400px; top: -90px; animation-delay: 2.5s; }
.yolov5 { left: 600px; top: -90px; animation-delay: 3s; }
.kerascv { top: -90px; left: 800px; animation-delay: 3.5s; }

/* Decorative particles */
.particle {
position: absolute;
width: 4px;
height: 4px;
background: #00ffff;
border-radius: 50%;
box-shadow: 0 0 10px rgba(0, 255, 255, 0.8);
animation: particle-float 8s linear infinite;
}

.particle:nth-child(odd) { animation-duration: 12s; }
.particle:nth-child(even) { animation-duration: 10s; }

/* Animations */
@keyframes glow-pulse {
0% { text-shadow: 0 0 20px rgba(0, 255, 255, 0.8), 0 0 40px rgba(0, 255, 255, 0.4); }
100% { text-shadow: 0 0 30px rgba(0, 255, 255, 1), 0 0 60px rgba(0, 255, 255, 0.6); }
}

@keyframes rotate {
0% { transform: rotate(0deg); }
100% { transform: rotate(360deg); }
}

@keyframes rotate-reverse {
0% { transform: translate(-50%, -50%) rotate(0deg); }
100% { transform: translate(-50%, -50%) rotate(-360deg); }
}

@keyframes pulse-ring {
0% { transform: translate(-50%, -50%) scale(1); opacity: 0.8; }
50% { transform: translate(-50%, -50%) scale(1.2); opacity: 0.4; }
100% { transform: translate(-50%, -50%) scale(1); opacity: 0.8; }
}

@keyframes float {
0%, 100% { transform: translateY(0px) scale(1); }
50% { transform: translateY(-10px) scale(1.02); }
}

@keyframes particle-float {
0% { transform: translateY(1080px) translateX(0px); opacity: 0; }
10% { opacity: 1; }
90% { opacity: 1; }
100% { transform: translateY(-100px) translateX(100px); opacity: 0; }
}

/* Additional decorative elements */
.tech-accent {
position: absolute;
font-size: 0.8em;
color: rgba(0, 255, 255, 0.6);
font-family: 'Courier New', monospace;
}

.version-info {
position: absolute;
bottom: 40px;
right: 40px;
color: rgba(0, 255, 255, 0.6);
font-size: 0.9em;
font-family: 'Courier New', monospace;
}
</style>
</head>
<body>
<div class="grid-bg"></div>
<div class="blur-overlay"></div>

<!-- Floating particles -->
<div class="particle" style="left: 10%; animation-delay: 0s;"></div>
<div class="particle" style="left: 20%; animation-delay: 2s;"></div>
<div class="particle" style="left: 30%; animation-delay: 4s;"></div>
<div class="particle" style="left: 40%; animation-delay: 6s;"></div>
<div class="particle" style="left: 50%; animation-delay: 1s;"></div>
<div class="particle" style="left: 60%; animation-delay: 3s;"></div>
<div class="particle" style="left: 70%; animation-delay: 5s;"></div>
<div class="particle" style="left: 80%; animation-delay: 7s;"></div>
<div class="particle" style="left: 90%; animation-delay: 8s;"></div>

<div class="container">
<h1 class="main-title">Computer Vision Tools</h1>

<div class="central-hub">
<div class="pulse-ring"></div>
<div class="core-circle">
<div class="inner-circle"></div>
</div>

<!-- Tool nodes positioned around the central hub -->
<div class="tool-node opencv">OpenCV</div>
<div class="tool-node cuda">CUDA</div>
<div class="tool-node simplecv">SimpleCV</div>
<div class="tool-node yolo">YOLO</div>
<div class="tool-node bootcv">BoofCV</div>
<div class="tool-node pytorch">PyTorch</div>
<div class="tool-node yolov5">YOLOv8</div>
<div class="tool-node kerascv">KerasCV</div>
<div class="tool-node tensorflow">TensorFlow</div>
</div>

<!-- Tech accents -->
<div class="tech-accent" style="top: 20%; left: 5%;">&gt;&gt;&gt; AI_VISION.init()</div>
<div class="tech-accent" style="top: 25%; left: 5%;">&gt;&gt;&gt; im = np.stack(self.pre_transform(im))</div>
<div class="tech-accent" style="top: 30%; left: 5%;">&gt;&gt;&gt; im = im[..., ::-1].transpose((0, 3, 1, 2))</div>
<div class="tech-accent" style="top: 35%; left: 5%;">&gt;&gt;&gt; im = np.ascontiguousarray(im)</div>
<div class="tech-accent" style="top: 40%; left: 5%;">&gt;&gt;&gt; im = torch.from_numpy(im)</div>
<div class="tech-accent" style="top: 25%; right: 5%;">neural_network.status: ACTIVE</div>
<div class="tech-accent" style="bottom: 20%; left: 5%;">processing_rate: 60fps</div>

<div class="version-info">
CV_TOOLKIT v2.4.1<br>
STATUS: ONLINE
</div>
</div>
</body>
</html>"""


pushButton_config_history_style = """
QPushButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
}
QPushButton:hover {
    background-color: rgba(0, 0, 0, 25);
}
QPushButton:pressed {
    background-color: rgba(0, 0, 0, 50);
}
"""

save_button_btn_setStyleSheet = """
            QPushButton {
                background-color: #C3DBFF;
                color: #000000;
                font-weight: 600;
                font-size: 11px;
                border: 1px solid #0b5ed7;
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: #72ABFF;
                border-color: #0a58ca;
            }
            QPushButton:pressed {
                background-color: #325A97;
            }
            QPushButton:disabled {
                background-color: #e9ecef;
                color: #6c757d;
                border: 1px solid #ced4da;
            }
        """

detect_button_setStyleSheet = """
            QPushButton {
                background-color: #C3E5D5;
                color: #000000;
                font-weight: 600;
                font-size: 11px;
                border: 1px solid #157347;
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: #A4DBC1;
                border-color: #146c43;
            }
            QPushButton:pressed {
                background-color: #7BCAA5;
            }
            QPushButton:disabled {
                background-color: #e9ecef;
                color: #6c757d;
                border: 1px solid #ced4da;
            }
        """

show_save_success_effect = """
            QPushButton {
                background-color: #198754;
                color: #ffffff;
                font-weight: 700;
                font-size: 11px;
                border: 1px solid #146c43;
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 22px;
            }
        """

ChangeReasonDialog_Style = """
            QDialog {
                background-color: #f8fafc;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QFrame#headerFrame {
                background-color: #ffffff;
                border-bottom: 1px solid #cbd5e1;
                padding: 12px;
            }
            QLabel#lblTitle {
                color: #0f172a;
                font-size: 15px;
                font-weight: bold;
            }
            QLabel#lblSub {
                color: #64748b;
                font-size: 12px;
            }
            QFrame#badgeFrame {
                background-color: #f1f5f9;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QTextEdit {
                background-color: #ffffff;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
                color: #0f172a;
            }
            QTextEdit:focus {
                border-color: #2563eb;
                background-color: #ffffff;
            }
            QCheckBox {
                font-size: 13px;
                font-weight: 600;
                color: #1e293b;
            }
            QPushButton#btnSave {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #1d4ed8;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton#btnSave:hover {
                background-color: #1d4ed8;
            }
            QPushButton#btnSave:disabled {
                background-color: #94a3b8;
                border-color: #cbd5e1;
                color: #f1f5f9;
            }
            QPushButton#btnCancel {
                background-color: #ffffff;
                color: #475569;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 18px;
            }
            QPushButton#btnCancel:hover {
                background-color: #f1f5f9;
                color: #1e293b;
            }
        """


RollbackPasswordDialog_style = """
            QDialog {
                background-color: #f8fafc;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QFrame#headerFrame {
                background-color: #ffffff;
                border-bottom: 1px solid #cbd5e1;
                padding: 10px;
            }
            QLabel#lblTitle {
                color: #b91c1c;
                font-size: 15px;
                font-weight: bold;
            }
            QLabel#lblSub {
                color: #64748b;
                font-size: 12px;
            }
            QFrame#warnBox {
                background-color: #fef2f2;
                border: 1px solid #fecaca;
                border-radius: 6px;
                padding: 8px;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 14px;
                color: #0f172a;
            }
            QLineEdit:focus {
                border-color: #dc2626;
            }
            QPushButton#btnConfirm {
                background-color: #dc2626;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #b91c1c;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton#btnConfirm:hover {
                background-color: #b91c1c;
            }
            QPushButton#btnCancel {
                background-color: #ffffff;
                color: #475569;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 18px;
            }
            QPushButton#btnCancel:hover {
                background-color: #f1f5f9;
                color: #1e293b;
            }
        """
        

ConfigHistoryDialog_style = """
            QDialog {
                background-color: #f1f5f9;
                color: #0f172a;
                font-family: 'Segoe UI';
            }
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 14px;
                font-weight: bold;
                font-size: 13px;
                color: #0f172a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 8px;
                background-color: #ffffff;
                color: #1e293b;
            }
            QFrame#filterFrame, QFrame#bottomFrame {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
            QLabel {
                color: #334155;
                font-size: 13px;
                font-weight: 500;
            }
            QComboBox, QLineEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 12px;
                color: #0f172a;
            }
            QComboBox:focus, QLineEdit:focus {
                border: 1.5px solid #2563eb;
            }
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                gridline-color: #f1f5f9;
                font-size: 12px;
                color: #1e293b;
            }
            QTableWidget::item {
                padding: 4px 6px;
                border-bottom: 1px solid #f1f5f9;
            }
            QTableWidget::item:selected {
                background-color: #dbeafe;
                color: #1e40af;
                font-weight: bold;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #334155;
                padding: 6px;
                border: 1px solid #e2e8f0;
                font-weight: bold;
                font-size: 12px;
            }
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                background-color: #ffffff;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #e2e8f0;
                color: #475569;
                padding: 8px 16px;
                font-weight: bold;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #2563eb;
                border-bottom: 2px solid #2563eb;
            }
            QPushButton {
                background-color: #ffffff;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                color: #0f172a;
                border-color: #94a3b8;
            }
            QPushButton#btnRollback {
                background-color: #ea580c;
                color: #ffffff !important;
                border: 1px solid #c2410c;
                padding: 8px 20px;
                font-size: 13px;
            }
            QPushButton#btnRollback:hover {
                background-color: #c2410c;
            }
            QPushButton#btnGolden {
                background-color: #fef3c7;
                color: #b45309 !important;
                border: 1px solid #fcd34d;
            }
            QPushButton#btnGolden:hover {
                background-color: #fde68a;
            }
        """

CellSliderPopup_style = """
            QFrame#sliderPopupContainer {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1E293B, stop:1 #0F172A);
                border: 1px solid #38BDF8;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #334155;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #06B6D4, stop:1 #3B82F6);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                border: 2px solid #0EA5E9;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #38BDF8;
                border: 2px solid #FFFFFF;
            }
            QPushButton {
                background: #1E293B;
                border: 1px solid #475569;
                border-radius: 4px;
                color: #E2E8F0;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: bold;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background: #0EA5E9;
                border-color: #38BDF8;
                color: #FFFFFF;
            }
            QPushButton#closeBtn {
                background: transparent;
                border: none;
                color: #94A3B8;
                font-size: 11pt;
                font-weight: bold;
                padding: 0;
            }
            QPushButton#closeBtn:hover {
                color: #EF4444;
            }
            QPushButton.chipBtn {
                background: #1E293B;
                border: 1px solid #475569;
                border-radius: 9px;
                color: #94A3B8;
                font-size: 8pt;
                font-weight: bold;
                padding: 1px 7px;
            }
            QPushButton.chipBtn:hover {
                background: #0284C7;
                border-color: #38BDF8;
                color: #FFFFFF;
            }
        """



# ─────────────────────────────────────────────────────────────────────────────
# CẤU HÌNH BỘ ĐIỀU KHIỂN SLIDER CHO CÁC CỘT THÔNG SỐ (TỪ QTY ĐẾN CONFIDENCE)
# ─────────────────────────────────────────────────────────────────────────────
SLIDER_COLUMN_CONFIGS: Final[dict[str, dict[str, Any]]] = {
    "Qty": {
        "min": 1,
        "max": 100,
        "step": 1,
        "unit": "",
        "prefix": "",
        "presets": [1, 2, 5, 10, 20],
        "title": "🔢 Số lượng (Qty)",
    },
    "Min Width": {
        "min": 1,
        "max": 10000,
        "step": 1,
        "unit": " px",
        "prefix": "",
        "presets": [1, 50, 100, 500, 2000, 10000],
        "title": "📏 Chiều rộng tối thiểu (Min Width)",
    },
    "Max Width": {
        "min": 1,
        "max": 10000,
        "step": 1,
        "unit": " px",
        "prefix": "",
        "presets": [1, 50, 100, 500, 2000, 10000],
        "title": "📏 Chiều rộng tối đa (Max Width)",
    },
    "Min Height": {
        "min": 1,
        "max": 10000,
        "step": 1,
        "unit": " px",
        "prefix": "",
        "presets": [1, 50, 100, 500, 2000, 10000],
        "title": "📐 Chiều cao tối thiểu (Min Height)",
    },
    "Max Height": {
        "min": 1,
        "max": 10000,
        "step": 1,
        "unit": " px",
        "prefix": "",
        "presets": [1, 50, 100, 500, 2000, 10000],
        "title": "📐 Chiều cao tối đa (Max Height)",
    },
    "Register": {
        "min": 0,
        "max": 9999,
        "step": 1,
        "unit": "",
        "prefix": "",
        "presets": [1000, 1010, 2000, 2001, 3000],
        "title": "🔌 Thanh ghi PLC (Register)",
    },
    "Value State": {
        "min": 0,
        "max": 1000,
        "step": 1,
        "unit": "",
        "prefix": "",
        "presets": [0, 1, 2, 5, 10, 100],
        "title": "🎯 Giá trị trạng thái (Value State)",
    },
    "Value OK": {
        "min": 0,
        "max": 1000,
        "step": 1,
        "unit": "",
        "prefix": "",
        "presets": [0, 1, 2, 5, 10, 100],
        "title": "✔ Giá trị OK (Value OK)",
    },
    "Value NG": {
        "min": 0,
        "max": 1000,
        "step": 1,
        "unit": "",
        "prefix": "",
        "presets": [0, 1, 2, 5, 10, 100],
        "title": "✘ Giá trị NG (Value NG)",
    },
    "Value": {
        "min": 0,
        "max": 1000,
        "step": 1,
        "unit": "",
        "prefix": "",
        "presets": [0, 1, 2, 5, 10, 100],
        "title": "🎯 Giá trị ghi (Value)",
    },
    "Confidence": {
        "min": 1,
        "max": 100,
        "step": 1,
        "unit": "%",
        "prefix": "",
        "presets": [15, 30, 50, 70, 90],
        "title": "⚡ Độ tin cậy (Confidence)",
    },
}


Process_Model_pushButton_config_history = """
                    QPushButton {
                        background-color: transparent;
                        border: none;
                        border-radius: 6px;
                    }
                    QPushButton:hover {
                        background-color: rgba(0, 0, 0, 25);
                    }
                    QPushButton:pressed {
                        background-color: rgba(0, 0, 0, 50);
                    }
                """

setup_table = """
            /* Khung chính của bảng TableView */
            QTableView {
                background-color: #F7FFFA;
                border: 1px solid #325C62;
                border-radius: 4px;
                gridline-color: #d0ebd5;
                font-family: 'Segoe UI';
                font-size: 11pt;
            }
            /* Header tiêu đề cột và hàng */
            QHeaderView::section {
                background-color: #EAF7EF;
                color: #1F4E78;
                font-family: 'Segoe UI';
                font-size: 11pt;
                font-weight: bold;
                border: 1px solid #d0ebd5;
                padding: 4px;
            }
            /* Ô dữ liệu bên trong bảng */
            QTableView::item {
                background-color: #F7FFFA;
                color: #2c3e50;
                font-family: 'Segoe UI';
                font-size: 11pt;
                font-weight: bold;
            }
            /* Hiệu ứng khi di chuột qua */
            QTableView::item:hover {
                background-color: #88FF7A;
            }
            /* Hiệu ứng khi chọn dòng */
            QTableView::item:selected {
                background-color: #1DB20D;
                color: black;
            }
        """

lbl_value_style = """
            background-color: #334155;
            color: #38BDF8;
            border-radius: 4px;
            padding: 1px 8px;
            font-weight: bold;
            font-size: 10pt;
        """

show_table_context_menu_style = """
            QMenu {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 4px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #89b4fa;
                color: #11111b;
                font-weight: bold;
            }
        """

palette = [
    {"bg": "#CAD2DA", "border": "#364554"},  # Xanh xám thép (Slate Blue)
    {"bg": "#CAD4CB", "border": "#354A3A"},  # Xanh rêu xám (Sage Green)
    {"bg": "#D3CCC5", "border": "#4D423B"},  # Nâu xám ấm (Warm Taupe)
    {"bg": "#C6D2D4", "border": "#284449"},  # Xanh cổ vịt trầm (Petrol Teal)
    {"bg": "#CBCDE0", "border": "#373C54"},  # Xanh chàm tro (Dusk Indigo)
    {"bg": "#CCD0C2", "border": "#424A35"},  # Rêu đá trầm (Muted Olive)
    {"bg": "#D0D4D8", "border": "#3D464F"},  # Xám than chì (Charcoal Slate)
    {"bg": "#CFC7CF", "border": "#443743"},  # Xám tro ánh tím trầm (Dusk Plum)
    {"bg": "#C4CDD3", "border": "#2D3E49"},  # Xanh xám bão trầm (Storm Slate)
    {"bg": "#C8CDD0", "border": "#343E43"},  # Xám thép kim loại (Pewter Steel)
]


pushButton_config_history_DataProcessSignal = """
                    QPushButton {
                        background-color: #0284c7;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        font-weight: 600;
                        padding: 4px 10px;
                    }
                    QPushButton:hover {
                        background-color: #0369a1;
                    }
                """

setup_shotxmodel_table_style = """
            /* Khung chính của bảng TableView */
            QTableView {
                background-color: #F7FFFA;
                border: 1px solid #325C62;
                border-radius: 4px;
                gridline-color: #d0ebd5;
            }
            /* Header tiêu đề bảng */
            QHeaderView::section {
                background-color: #EAF7EF;
                color: #1F4E78;
                font-family: 'Segoe UI';
                font-size: 11pt;
                font-weight: bold;
                border: 1px solid #d0ebd5;
                padding: 4px;
            }
            /* Ô dữ liệu bên trong bảng */
            QTableView::item {
                background-color: #F7FFFA;
                color: #2c3e50;
                font-family: 'Segoe UI';
                font-size: 11pt;
                font-weight: bold;
            }
            /* Hiệu ứng di chuột */
            QTableView::item:hover {
                background-color: #F5FFE1;
            }
            /* Hiệu ứng khi chọn dòng */
            QTableView::item:selected {
                background-color: #E9F8FF;
                color: black;
            }
        """

create_model_combobox = """
            QComboBox { 
                background-color: #F7FFFA; 
                color: black; 
                font-family: 'Segoe UI'; 
                font-size: 11pt; 
                font-weight: bold;
                border: 1px solid #d0ebd5;
                border-radius: 3px;
                padding: 2px;
            }
            QComboBox QAbstractItemView {
                text-align: center;
                font-family: 'Segoe UI';
                font-size: 11pt;
                font-weight: bold;
                selection-background-color: #E9F8FF;
                selection-color: black;
            }
        """

setup_config_status_log_ui = """
            QTextBrowser {
                background-color: #FFFFFF;
                border: 1px solid #000000;
                border-radius: 4px;
                padding: 8px;
            }
        """

add_dma_combobox_to_row = """
            QComboBox { 
                background-color: #F7FFFA; 
                color: black; 
                font-family: 'Segoe UI'; 
                font-size: 11pt; 
                font-weight: bold;
            }
            QComboBox QAbstractItemView {
                text-align: center;
                font-family: 'Segoe UI';
                font-size: 11pt;
                font-weight: bold;
            }
        """

TaskRuleEditorDialog_Style = """
            QDialog {
                background-color: #f1f5f9;
                color: #1e293b;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QGroupBox {
                background-color: #F0F9FF;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 16px;
                font-weight: bold;
                font-size: 13px;
                color: #0f172a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 0 8px;
                background-color: #ffffff;
                color: #0f172a;
                font-weight: bold;
            }
            QLabel {
                color: #334155;
                font-size: 13px;
                font-weight: 500;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                color: #0f172a;
                font-size: 13px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1.5px solid #2563eb;
                background-color: #f8fafc;
            }

            /* COMBOBOX CHUYÊN NGHIỆP: NỀN TRẮNG SẠCH, CHỮ ĐẬM RÕ NÉT, HOVER/FOCUS XANH DỊU */
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                color: #0f172a;
                font-size: 13px;
                font-weight: 500;
            }
            QComboBox:hover {
                border: 1px solid #3b82f6;
                background-color: #f8fafc;
                color: #0f172a;
            }
            QComboBox:focus {
                border: 1.5px solid #2563eb;
                background-color: #ffffff;
                color: #0f172a;
            }
            QComboBox:editable {
                background-color: #ffffff;
                color: #0f172a;
            }
            QComboBox:editable:hover {
                background-color: #f8fafc;
                border: 1px solid #3b82f6;
                color: #0f172a;
            }
            QComboBox:editable:focus {
                background-color: #ffffff;
                border: 1.5px solid #2563eb;
                color: #0f172a;
            }
            QComboBox QLineEdit {
                background-color: transparent;
                color: #0f172a;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
                border: none;
                padding: 0px 4px;
            }
            QComboBox QLineEdit:hover {
                background-color: transparent;
                color: #0f172a;
            }
            QComboBox QLineEdit:focus {
                background-color: transparent;
                color: #0f172a;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 26px;
                border-left: 1px solid #cbd5e1;
                background-color: #f1f5f9;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }
            QComboBox::down-arrow {
                width: 0;
                height: 0;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #475569;
            }
            QComboBox QAbstractItemView, QComboBox QListView {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item, QComboBox QListView::item {
                min-height: 28px;
                padding: 4px 10px;
                color: #1e293b;
                background-color: transparent;
                border-radius: 4px;
            }
            QComboBox QAbstractItemView::item:hover, QComboBox QListView::item:hover {
                background-color: #e2e8f0;
                color: #0f172a;
            }
            QComboBox QAbstractItemView::item:selected, QComboBox QListView::item:selected {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
            }

            /* CÁC NÚT THAO TÁC CƠ BẢN */
            QPushButton {
                background-color: #f8fafc;
                color: #334155;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                border: 1px solid #cbd5e1;
                padding: 7px 15px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                color: #0f172a;
                border-color: #94a3b8;
            }
            QPushButton:pressed {
                background-color: #cbd5e1;
                color: #0f172a;
            }

            /* CÁC NÚT THAO TÁC NỔI BẬT: CHỮ TRẮNG TƯƠNG PHẢN CAO, NỀN MÀU RÕ RÀNG */
            QPushButton#btnSave {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #1d4ed8;
                border-radius: 6px;
                padding: 9px 24px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btnSave:hover {
                background-color: #1d4ed8;
                border: 1px solid #1e40af;
                color: #ffffff;
            }
            QPushButton#btnSave:pressed {
                background-color: #1e40af;
                color: #ffffff;
            }

            QPushButton#btnAddRule {
                background-color: #16a34a;
                color: #ffffff;
                border: 1px solid #15803d;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btnAddRule:hover {
                background-color: #15803d;
                border: 1px solid #166534;
                color: #ffffff;
            }
            QPushButton#btnAddRule:pressed {
                background-color: #166534;
                color: #ffffff;
            }

            QPushButton#btnUpdateRule {
                background-color: #ea580c;
                color: #ffffff;
                border: 1px solid #c2410c;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btnUpdateRule:hover {
                background-color: #c2410c;
                border: 1px solid #9a3412;
                color: #ffffff;
            }
            QPushButton#btnUpdateRule:pressed {
                background-color: #9a3412;
                color: #ffffff;
            }

            QPushButton#btnDeleteRule {
                background-color: #dc2626;
                color: #ffffff;
                border: 1px solid #b91c1c;
                border-radius: 6px;
                padding: 9px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btnDeleteRule:hover {
                background-color: #b91c1c;
                border: 1px solid #991b1b;
                color: #ffffff;
            }
            QPushButton#btnDeleteRule:pressed {
                background-color: #991b1b;
                color: #ffffff;
            }

            QPushButton#btnCancel {
                background-color: #ffffff;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 9px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btnCancel:hover {
                background-color: #f1f5f9;
                color: #1e293b;
                border-color: #94a3b8;
            }
            QPushButton#btnCancel:pressed {
                background-color: #e2e8f0;
            }

            QPushButton#btnResetCanvas {
                background-color: #ffffff;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#btnResetCanvas:hover {
                background-color: #eff6ff;
                border: 1px solid #3b82f6;
                color: #1d4ed8;
            }
            QPushButton#btnResetCanvas:pressed {
                background-color: #dbeafe;
            }

            /* BẢNG DANH SÁCH RULES */
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                gridline-color: #e2e8f0;
                color: #0f172a;
                border-radius: 6px;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }
            QTableWidget::item {
                color: #0f172a;
                padding: 6px;
                border-bottom: 1px solid #e2e8f0;
            }
            QTableWidget::item:hover {
                background-color: #e0f2fe;
                color: #0369a1;
            }
            QTableWidget::item:selected {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #1e293b;
                padding: 7px;
                border: 1px solid #cbd5e1;
                font-weight: bold;
                font-size: 12px;
            }

            /* THÔNG BÁO HỘP THOẠI MESSAGEBOX */
            QMessageBox {
                background-color: #f1f5f9;
            }
            QMessageBox QLabel {
                color: #1e293b;
                font-size: 13px;
            }
            QMessageBox QPushButton {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 18px;
                font-size: 13px;
                font-weight: bold;
            }
            QMessageBox QPushButton:hover {
                background-color: #e2e8f0;
            }
        """


TaskRuleEditorDialog_Style_init_ui = """
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #f1f5f9;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #cbd5e1;
                min-height: 30px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #94a3b8;
            }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """

btn_reset_canvas_setStyleSheet = """
            QPushButton#btnResetCanvas {
                background-color: #ffffff;
                color: #334155 !important;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#btnResetCanvas:hover {
                background-color: #eff6ff;
                border: 1px solid #3b82f6;
                color: #1d4ed8 !important;
            }
            QPushButton#btnResetCanvas:pressed {
                background-color: #dbeafe;
            }
        """

btn_add_rule_setStyleSheet = """
            QPushButton#btnAddRule {
                background-color: #16a34a;
                color: #ffffff !important;
                border: 1px solid #15803d;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#btnAddRule:hover {
                background-color: #15803d;
                border: 1px solid #166534;
                color: #ffffff !important;
            }
            QPushButton#btnAddRule:pressed {
                background-color: #166534;
                color: #ffffff !important;
            }
        """

btn_update_rule_setStyleSheet = """
            QPushButton#btnUpdateRule {
                background-color: #ea580c;
                color: #ffffff !important;
                border: 1px solid #c2410c;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#btnUpdateRule:hover {
                background-color: #c2410c;
                border: 1px solid #9a3412;
                color: #ffffff !important;
            }
            QPushButton#btnUpdateRule:pressed {
                background-color: #9a3412;
                color: #ffffff !important;
            }
        """

expr_frame_setStyleSheet = """
            QFrame#exprFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 6px;
            }
        """

bottom_frame_setStyleSheet = """
            QFrame#bottomFrame {
                background-color: #e2e8f0;
                border-top: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px;
            }
        """

btn_delete_rule_setStyleSheet = """
            QPushButton#btnDeleteRule {
                background-color: #dc2626;
                color: #ffffff !important;
                border: 1px solid #b91c1c;
                border-radius: 6px;
                padding: 6px 18px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btnDeleteRule:hover {
                background-color: #b91c1c;
                border: 1px solid #991b1b;
                color: #ffffff !important;
            }
            QPushButton#btnDeleteRule:pressed {
                background-color: #991b1b;
                color: #ffffff !important;
            }
        """

btn_cancel_setStyleSheet = """
            QPushButton#btnCancel {
                background-color: #ffffff;
                color: #475569 !important;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btnCancel:hover {
                background-color: #f1f5f9;
                color: #1e293b !important;
                border-color: #94a3b8;
            }
            QPushButton#btnCancel:pressed {
                background-color: #e2e8f0;
            }
        """

btn_save_setStyleSheet = """
            QPushButton#btnSave {
                background-color: #2563eb;
                color: #ffffff !important;
                border: 1px solid #1d4ed8;
                border-radius: 6px;
                padding: 6px 24px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btnSave:hover {
                background-color: #1d4ed8;
                border: 1px solid #1e40af;
                color: #ffffff !important;
            }
            QPushButton#btnSave:pressed {
                background-color: #1e40af;
                color: #ffffff !important;
            }
        """
TaskWorkspaceDialog_style = """
            QDialog {
                background-color: #F0F9FF;
                color: #0f172a;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QGroupBox {
                background-color: #F0F9FF;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 14px;
                font-weight: bold;
                color: #0f172a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                background-color: #ffffff;
                color: #0f172a;
            }
            QLabel {
                color: #334155;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 7px 15px;
                color: #334155;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #f8fafc;
                border-color: #94a3b8;
                color: #0f172a;
            }
            QPushButton#btnAddTask {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #1d4ed8;
            }
            QPushButton#btnAddTask:hover {
                background-color: #1d4ed8;
            }
            QPushButton#btnEditTask {
                background-color: #d97706;
                color: #ffffff;
                border: 1px solid #b45309;
            }
            QPushButton#btnEditTask:hover {
                background-color: #b45309;
            }
            QPushButton#btnDeleteTask {
                background-color: #dc2626;
                color: #ffffff;
                border: 1px solid #b91c1c;
            }
            QPushButton#btnDeleteTask:hover {
                background-color: #b91c1c;
            }
            QPushButton#btnCloneTask {
                background-color: #7c3aed;
                color: #ffffff;
                border: 1px solid #6d28d9;
            }
            QPushButton#btnCloneTask:hover {
                background-color: #6d28d9;
            }
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                gridline-color: #e2e8f0;
                color: #0f172a;
                border-radius: 8px;
                font-size: 13px;
                selection-background-color: #dbeafe;
                selection-color: #1e40af;
            }
            QTableWidget::item:hover {
                background-color: #f1f5f9;
                color: #0f172a;
            }
            QTableWidget::item:selected {
                background-color: #dbeafe;
                color: #1e40af;
                font-weight: bold;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #334155;
                padding: 8px 6px;
                border: 1px solid #e2e8f0;
                font-weight: bold;
                font-size: 13px;
            }
        """

btn_history_setStyleSheet = """
            QPushButton {
                background-color: #f1f5f9;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                font-weight: 600;
                padding: 6px 14px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                border-color: #94a3b8;
            }
        """

btn_row_edit_setStyleSheet = """
                QPushButton {
                    background-color: #eff6ff;
                    color: #2563eb;
                    border: 1px solid #bfdbfe;
                    border-radius: 4px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #dbeafe;
                    border-color: #3b82f6;
                }
            """

btn_row_del_setStyleSheet = """
                QPushButton {
                    background-color: #fef2f2;
                    color: #dc2626;
                    border: 1px solid #fecaca;
                    border-radius: 4px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #fee2e2;
                    border-color: #ef4444;
                }
            """