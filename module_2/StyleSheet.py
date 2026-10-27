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
