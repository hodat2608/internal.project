
import torch
from module_2 import root
from PyQt5.QtWidgets import (QMessageBox,QFileDialog)
import sys
from PyQt5.QtWidgets import (QFileDialog)
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QStyledItemDelegate, QStyleOptionButton, QStyle
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QStandardItem
from mysql.connector import Error
import cv2, numpy as np
from pathlib import Path
from typing import Final, Any, Optional, Dict
COLUMN_MAPPING: Final[dict[str, str]] = {
    "Label Name":     "`Label_Name`",
    "Enable":        "`Join`",
    "OK 🟢":             "`OK`",
    "NG 🔴":             "`NG`",
    "Qty":       "`Quantity`",
    "Min Width":      "`Width_Min`",
    "Max Width":      "`Width_Max`",
    "Min Height":     "`Height_Min`",
    "Max Height":     "`Height_Max`",
    "Register": "`Assign_Value`",
    "Value": "`Value`",
    "Confidence":     "`Confidence`",
}

# CẤU HÌNH GIÁ TRỊ MẶC ĐỊNH CHO BẢNG THÔNG SỐ MODEL
DEFAULT_ROW_VALUES: Final[dict[str, Any]] = {
    "Enable": True,       # Mặc định có tích vào ô
    "OK 🟢": False,          # Mặc định bỏ tích
    "NG 🔴": False,          # Mặc định bỏ tích
    "Qty": "1",               # Mặc định là 1
    "Min Width": "1",         # Mặc định là 1
    "Max Width": "10000",     # Mặc định là 10000
    "Min Height": "1",        # Mặc định là 1
    "Max Height": "10000",    # Mặc định là 10000
    "Register": "DM",         # Mặc định có 2 chữ cái đầu là DM
    "Value": "1",             # Mặc định là 1
    "Confidence": "30",       # Mặc định là 30
}
import time
from module_3.yolo_factory import YoloFactory

from app_logger.app_logger import get_logger as _get_logger
from module_1.root_path import resource_path
import os
import shutil
import sys
import hashlib

_log = _get_logger('module_3.handle_option_models')

# -- CẤU HÌNH THƯ MỤC TRUNG GIAN --
if getattr(sys, 'frozen', False):
    app_data = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or os.path.expanduser('~')
    BASE_DIR = os.path.join(app_data, 'MBC_Vision_Inspector')
else:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

WEIGHTS_DIR = os.path.join(BASE_DIR, 'workspace_weights')
os.makedirs(WEIGHTS_DIR, exist_ok=True)

class CheckboxDelegate(QStyledItemDelegate):
    """
    Delegate tùy chỉnh vẽ duy nhất 1 ô checkbox căn giữa tuyệt đối cho các cột Enabled, OK, NG:
    - Loại bỏ hoàn toàn cờ HasCheckIndicator khi vẽ nền để tránh bị trùng lặp (double) 2 ô checkbox.
    - Vẽ 1 ô checkbox căn giữa với đầy đủ trạng thái hover, selected và tương tác nhấp chuột mượt mà.
    """
    def paint(self, painter, option, index):
        value = index.data(Qt.CheckStateRole)
        if value is None:
            super().paint(painter, option, index)
            return

        # 1. Vẽ nền (hover, selected, alternating colors) mà KHÔNG vẽ indicator mặc định ở lề trái
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.features &= ~QtWidgets.QStyleOptionViewItem.HasCheckIndicator
        opt.checkState = Qt.Unchecked
        opt.text = ""

        style = self.parent().style() if (self.parent() and self.parent().style()) else QtWidgets.QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter)

        # 2. Vẽ duy nhất 1 ô checkbox căn giữa tuyệt đối
        checkbox_style_option = QStyleOptionButton()
        if option.state & QStyle.State_Enabled:
            checkbox_style_option.state |= QStyle.State_Enabled
        if option.state & QStyle.State_MouseOver:
            checkbox_style_option.state |= QStyle.State_MouseOver
        if int(value) == Qt.Checked:
            checkbox_style_option.state |= QStyle.State_On
        else:
            checkbox_style_option.state |= QStyle.State_Off

        checkbox_rect = style.subElementRect(QStyle.SE_CheckBoxIndicator, checkbox_style_option, None)
        checkbox_style_option.rect = QRect(
            option.rect.x() + (option.rect.width() - checkbox_rect.width()) // 2,
            option.rect.y() + (option.rect.height() - checkbox_rect.height()) // 2,
            checkbox_rect.width(),
            checkbox_rect.height()
        )
        style.drawControl(QStyle.CE_CheckBox, checkbox_style_option, painter)

    def editorEvent(self, event, model, option, index):
        flags = index.flags()
        if not (flags & Qt.ItemIsEnabled) or not (flags & Qt.ItemIsUserCheckable):
            return False

        # Nhấp chuột trái để đổi trạng thái checkbox
        if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            current_value = index.data(Qt.CheckStateRole)
            new_value = Qt.Unchecked if current_value == Qt.Checked else Qt.Checked
            model.setData(index, new_value, Qt.CheckStateRole)
            return True

        # Nhấn phím Space khi đang focus vào ô để đổi trạng thái
        if event.type() == QtCore.QEvent.KeyPress and event.key() == Qt.Key_Space:
            current_value = index.data(Qt.CheckStateRole)
            new_value = Qt.Unchecked if current_value == Qt.Checked else Qt.Checked
            model.setData(index, new_value, Qt.CheckStateRole)
            return True

        return False


class CenteredItemDelegate(QStyledItemDelegate):
    """Delegate tùy chỉnh cho các ô dữ liệu trong tableView:
    - Khi sửa trực tiếp (createEditor): ô nhập tự động cỡ 11, Segoe UI, in đậm, căn giữa.
    """
    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QtWidgets.QLineEdit):
            editor.setAlignment(Qt.AlignCenter)
            font = QtGui.QFont("Segoe UI", 11)
            font.setBold(True)
            editor.setFont(font)
        return editor


class RegisterDelegate(QStyledItemDelegate):
    """
    Delegate cho cột Register (thanh ghi PLC).
    Tự động chuẩn hóa tiền tố 'DM', cỡ chữ 11, font Segoe UI in đậm và căn giữa.
    """
    def createEditor(self, parent, option, index):
        editor = QtWidgets.QLineEdit(parent)
        editor.setPlaceholderText("VD: 1009 hoặc DM1009")
        editor.setAlignment(Qt.AlignCenter)
        font = QtGui.QFont("Segoe UI", 11)
        font.setBold(True)
        editor.setFont(font)
        return editor

    def setEditorData(self, editor, index):
        val = str(index.data() or "").strip()
        if not val:
            val = "DM"
        editor.setText(val)
        editor.setCursorPosition(len(val))

    def setModelData(self, editor, model, index):
        raw = editor.text().strip()
        if not raw:
            formatted = "DM"
        else:
            upper = raw.upper()
            if not upper.startswith("DM"):
                formatted = f"DM{upper}"
            else:
                formatted = upper
        model.setData(index, formatted, Qt.EditRole)


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
        "prefix": "DM",
        "presets": [1000, 1010, 2000, 2001, 3000],
        "title": "🔌 Thanh ghi PLC (Register)",
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


class CellSliderPopup(QtWidgets.QWidget):
    """
    Popup thanh trượt (Slider) nổi chuyên nghiệp xuất hiện khi người dùng
    trỏ chuột hoặc chọn ô của các cột thông số (Qty -> Confidence):
    - Tự động định vị ngay dưới (hoặc trên) ô được trỏ.
    - Cho phép kéo thanh slider để cập nhật thông số ô trong thời gian thực.
    - Cung cấp nút tăng giảm tinh chỉnh (-) / (+) và các phím chọn nhanh (presets).
    - Không cản trở việc click đúp vào ô để nhập số trực tiếp bằng bàn phím.
    """
    def __init__(self, table):
        super().__init__(table.window(), Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.table = table
        self.current_index = None
        self.current_col_name = None
        self.is_pinned = False
        self._is_updating = False

        self._init_ui()

    def _init_ui(self):
        outer_layout = QtWidgets.QVBoxLayout(self)
        outer_layout.setContentsMargins(8, 8, 8, 8)

        self.container = QtWidgets.QFrame(self)
        self.container.setObjectName("sliderPopupContainer")
        self.container.setStyleSheet("""
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
        """)

        # Đổ bóng Drop Shadow cao cấp
        shadow = QtWidgets.QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(16)
        shadow.setColor(QtGui.QColor(0, 0, 0, 160))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        inner_layout = QtWidgets.QVBoxLayout(self.container)
        inner_layout.setContentsMargins(10, 8, 10, 8)
        inner_layout.setSpacing(6)

        # 1. Tiêu đề + Giá trị + Nút đóng
        top_row = QtWidgets.QHBoxLayout()
        self.lbl_title = QtWidgets.QLabel("Thông số")
        self.lbl_title.setStyleSheet("font-weight: bold; color: #38BDF8; font-size: 10pt;")

        self.lbl_value = QtWidgets.QLabel("0")
        self.lbl_value.setStyleSheet("""
            background-color: #334155;
            color: #38BDF8;
            border-radius: 4px;
            padding: 1px 8px;
            font-weight: bold;
            font-size: 10pt;
        """)

        self.btn_close = QtWidgets.QPushButton("✕")
        self.btn_close.setObjectName("closeBtn")
        self.btn_close.setFixedSize(18, 18)
        self.btn_close.setToolTip("Đóng thanh trượt (Esc)")
        self.btn_close.clicked.connect(self.hide)

        top_row.addWidget(self.lbl_title)
        top_row.addStretch()
        top_row.addWidget(self.lbl_value)
        top_row.addSpacing(6)
        top_row.addWidget(self.btn_close)
        inner_layout.addLayout(top_row)

        # 2. Thanh trượt Slider và nút [-] / [+]
        mid_row = QtWidgets.QHBoxLayout()
        self.btn_minus = QtWidgets.QPushButton("-")
        self.btn_minus.setFixedSize(22, 22)
        self.btn_minus.setToolTip("Giảm giá trị")
        self.btn_minus.clicked.connect(self._step_down)

        self.slider = QtWidgets.QSlider(Qt.Horizontal)
        self.slider.setFixedWidth(175)
        self.slider.valueChanged.connect(self._on_slider_value_changed)

        self.btn_plus = QtWidgets.QPushButton("+")
        self.btn_plus.setFixedSize(22, 22)
        self.btn_plus.setToolTip("Tăng giá trị")
        self.btn_plus.clicked.connect(self._step_up)

        mid_row.addWidget(self.btn_minus)
        mid_row.addWidget(self.slider)
        mid_row.addWidget(self.btn_plus)
        inner_layout.addLayout(mid_row)

        # 3. Phím bấm chọn nhanh (presets)
        self.preset_widget = QtWidgets.QWidget()
        self.preset_layout = QtWidgets.QHBoxLayout(self.preset_widget)
        self.preset_layout.setContentsMargins(0, 0, 0, 0)
        self.preset_layout.setSpacing(4)
        inner_layout.addWidget(self.preset_widget)

        outer_layout.addWidget(self.container)

    def attach_to_cell(self, index, col_name, pinned=False):
        if not index.isValid() or col_name not in SLIDER_COLUMN_CONFIGS:
            self.hide()
            return
        if not self.table.isEnabled():
            self.hide()
            return

        cfg = SLIDER_COLUMN_CONFIGS[col_name]
        self.current_index = QtCore.QPersistentModelIndex(index)
        self.current_col_name = col_name
        self.is_pinned = pinned
        self.lbl_title.setText(cfg.get("title", col_name))

        # Đọc và phân tích giá trị hiện tại từ ô
        raw_val = str(index.data() or "").strip()
        num_val = cfg["min"]
        if col_name == "Register":
            clean_str = raw_val.upper().replace("DM", "").strip()
            if clean_str.isdigit():
                num_val = int(clean_str)
        else:
            digits = "".join([c for c in raw_val if c.isdigit()])
            if digits:
                num_val = int(digits)

        slider_max = max(cfg["max"], num_val)
        slider_min = min(cfg["min"], num_val)
        self.slider.setRange(slider_min, slider_max)
        self.slider.setSingleStep(cfg.get("step", 1))

        self._is_updating = True
        self.slider.setValue(num_val)
        self._update_display(num_val, cfg)
        self._is_updating = False

        # Cập nhật các nút chọn nhanh (presets)
        while self.preset_layout.count():
            child = self.preset_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        presets = cfg.get("presets", [])
        pfx = cfg.get("prefix", "")
        unit = cfg.get("unit", "")
        for p in presets:
            btn = QtWidgets.QPushButton(f"{pfx}{p}{unit}")
            btn.setProperty("class", "chipBtn")
            btn.setFixedHeight(18)
            btn.clicked.connect(lambda checked=False, val=p: self.slider.setValue(val))
            self.preset_layout.addWidget(btn)

        self.adjustSize()
        self._reposition()
        self.show()

    def _update_display(self, val, cfg):
        prefix = cfg.get("prefix", "")
        unit = cfg.get("unit", "")
        self.lbl_value.setText(f"{prefix}{val}{unit}")

    def _step_down(self):
        cfg = SLIDER_COLUMN_CONFIGS.get(self.current_col_name, {})
        step = cfg.get("step", 1)
        self.slider.setValue(self.slider.value() - step)

    def _step_up(self):
        cfg = SLIDER_COLUMN_CONFIGS.get(self.current_col_name, {})
        step = cfg.get("step", 1)
        self.slider.setValue(self.slider.value() + step)

    def _on_slider_value_changed(self, val):
        if self._is_updating or not self.current_index or not self.current_index.isValid():
            return
        cfg = SLIDER_COLUMN_CONFIGS.get(self.current_col_name, {})
        self._update_display(val, cfg)

        prefix = cfg.get("prefix", "")
        formatted = f"{prefix}{val}"
        model = self.table.model()
        if model:
            idx = QtCore.QModelIndex(self.current_index)
            model.setData(idx, formatted, Qt.EditRole)

    def _reposition(self):
        if not self.current_index or not self.current_index.isValid():
            return
        rect = self.table.visualRect(QtCore.QModelIndex(self.current_index))
        if not rect.isValid():
            return

        global_bottom_left = self.table.viewport().mapToGlobal(rect.bottomLeft())
        pop_w = self.width() if self.width() > 10 else 240
        pop_h = self.height() if self.height() > 10 else 85

        x = global_bottom_left.x() + (rect.width() - pop_w) // 2
        y = global_bottom_left.y() + 2

        desktop = QtWidgets.QApplication.desktop()
        screen_geo = desktop.availableGeometry(global_bottom_left)
        if y + pop_h > screen_geo.bottom():
            global_top_left = self.table.viewport().mapToGlobal(rect.topLeft())
            y = global_top_left.y() - pop_h - 2

        if x < screen_geo.left():
            x = screen_geo.left() + 10
        elif x + pop_w > screen_geo.right():
            x = screen_geo.right() - pop_w - 10

        self.move(x, y)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

    def leaveEvent(self, event):
        if not self.is_pinned:
            cursor_pos = QtGui.QCursor.pos()
            if not self.geometry().contains(cursor_pos):
                self.hide()
        super().leaveEvent(event)


class TableSliderController(QtCore.QObject):
    """
    Bộ điều khiển kết nối giữa tableView và CellSliderPopup:
    - Lắng nghe sự kiện click hoặc trỏ chuột (hover) trên ô để hiển thị thanh trượt.
    - Ẩn thanh trượt khi cuộn trang, đổi tab, click ra ngoài hoặc click đúp vào ô để gõ phím.
    """
    def __init__(self, table, model_column):
        super().__init__(table)
        self.table = table
        self.model_column = model_column
        self.popup = CellSliderPopup(table)

        self.hover_timer = QtCore.QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.setInterval(280)
        self.hover_timer.timeout.connect(self._on_hover_timeout)
        self.pending_hover_index = None

        self.table.setMouseTracking(True)
        self.table.viewport().setMouseTracking(True)

        self.table.clicked.connect(self._on_cell_clicked)
        self.table.doubleClicked.connect(self._on_cell_double_clicked)
        if self.table.selectionModel():
            self.table.selectionModel().currentChanged.connect(self._on_current_changed)

        self.table.viewport().installEventFilter(self)

        self.table.verticalScrollBar().valueChanged.connect(self.popup.hide)
        self.table.horizontalScrollBar().valueChanged.connect(self.popup.hide)

    def _get_col_name(self, col):
        if 0 <= col < len(self.model_column):
            return self.model_column[col]
        return None

    def _on_cell_clicked(self, index):
        if not self.table.isEnabled():
            self.popup.hide()
            return
        col_name = self._get_col_name(index.column())
        if col_name in SLIDER_COLUMN_CONFIGS:
            self.popup.attach_to_cell(index, col_name, pinned=True)
        else:
            self.popup.hide()

    def _on_cell_double_clicked(self, index):
        self.popup.hide()

    def _on_current_changed(self, current, previous):
        if not self.table.isEnabled() or not current.isValid():
            self.popup.hide()
            return
        col_name = self._get_col_name(current.column())
        if col_name in SLIDER_COLUMN_CONFIGS:
            self.popup.attach_to_cell(current, col_name, pinned=True)
        else:
            self.popup.hide()

    def _on_hover_timeout(self):
        if not self.table.isEnabled():
            return
        if self.pending_hover_index and self.pending_hover_index.isValid():
            col_name = self._get_col_name(self.pending_hover_index.column())
            if col_name in SLIDER_COLUMN_CONFIGS:
                self.popup.attach_to_cell(QtCore.QModelIndex(self.pending_hover_index), col_name, pinned=False)

    def eventFilter(self, obj, event):
        if obj == self.table.viewport():
            if event.type() == QtCore.QEvent.MouseMove:
                if not self.table.isEnabled():
                    return super().eventFilter(obj, event)
                pos = event.pos()
                index = self.table.indexAt(pos)
                if index.isValid():
                    col_name = self._get_col_name(index.column())
                    if col_name in SLIDER_COLUMN_CONFIGS:
                        if self.popup.isVisible() and self.popup.current_index == index:
                            pass
                        elif self.popup.isVisible() and self.popup.is_pinned:
                            pass
                        else:
                            self.pending_hover_index = QtCore.QPersistentModelIndex(index)
                            self.hover_timer.start()
                    else:
                        self.hover_timer.stop()
                        if self.popup.isVisible() and not self.popup.is_pinned:
                            cursor_pos = QtGui.QCursor.pos()
                            if not self.popup.geometry().contains(cursor_pos):
                                self.popup.hide()
                else:
                    self.hover_timer.stop()
            elif event.type() in (QtCore.QEvent.Leave, QtCore.QEvent.Wheel):
                self.hover_timer.stop()
                if self.popup.isVisible() and not self.popup.is_pinned:
                    cursor_pos = QtGui.QCursor.pos()
                    if not self.popup.geometry().contains(cursor_pos):
                        self.popup.hide()
        return super().eventFilter(obj, event)


class Process_Model:
    dict_active_tasks = {}

    def __init__(self,uic):
        self.model = None
        self.file_path = None
        self.uic = uic
        self.list_layer = []
        self.list_layer_save = []
        self.keys_mapping = list(COLUMN_MAPPING.keys())
        self.file_path_detect = None
        self.model_loader = None
        self.path_object = None
        self.parametes_model = None
        self.result_model = None
        self.process_image_func = None
        
        self.is_unlocked = False
        self.camera_id = None
        self.camera_name = ""
        self.item_code = ""
        self.model_number = None
        self.model_id = None
        self.cursor = None
        self.connect_db = None
        self.active_tasks = {}
        
        # Inject standard properties into the generated UI object
        self.uic.processor = self
        self.uic.ui_child = None 
        self.uic.i_code = None
        self.uic.db = None
        self.uic.connect_db = None
        self.uic.cursor = None
        self.uic.model_column = list(COLUMN_MAPPING.keys())
        self.uic.model = QStandardItemModel(0, len(self.uic.model_column))
        self.uic.model.setHorizontalHeaderLabels(self.uic.model_column)
        if hasattr(self.uic, 'tableView'):
            self.uic.tableView.setModel(self.uic.model)
            self.uic.tableView.setContextMenuPolicy(Qt.CustomContextMenu)
            self.uic.tableView.customContextMenuRequested.connect(self.show_table_context_menu)
            
            # Cài đặt phong cách thiết kế đồng bộ đẹp mắt cho tableView
            self._setup_table_view_style()

            # Cài đặt Delegates mặc định
            self._setup_table_delegates()

            # Định dạng toàn bộ ô và header
            self.format_all_table_items()

            # Kích hoạt bộ điều khiển Slider thông minh cho các cột từ Qty đến Confidence
            self.slider_controller = TableSliderController(self.uic.tableView, self.uic.model_column)

        self.uic.model.itemChanged.connect(self._on_table_item_changed)
        self.uic.is_unlocked = False

        self.set_ui_enabled(False)

    def _setup_table_view_style(self):
        """Thiết lập phong cách đồ hoạ sang trọng, font chữ 11pt in đậm và căn giữa cho tableView."""
        if not hasattr(self.uic, 'tableView') or self.uic.tableView is None:
            return
        table = self.uic.tableView

        table.setStyleSheet("""
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
                background-color: #F5FFE1;
            }
            /* Hiệu ứng khi chọn dòng */
            QTableView::item:selected {
                background-color: #E9F8FF;
                color: black;
            }
        """)

        table.verticalHeader().setDefaultSectionSize(36)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.horizontalHeader().setHighlightSections(False)
        table.horizontalHeader().setStretchLastSection(True)

        self._format_table_headers()
        self._setup_column_widths()

    def _setup_column_widths(self):
        """Cấu hình độ rộng chuyên nghiệp, cân đối cho từng cột trong tableView."""
        if not hasattr(self.uic, 'tableView') or self.uic.tableView is None:
            return
        table = self.uic.tableView
        header = table.horizontalHeader()

        col_widths = {
            "Label Name": 140,
            "Enabled [✓]": 90,
            "OK [🟢]": 85,
            "NG [🔴]": 85,
            "Qty": 75,
            "Min Width": 90,
            "Max Width": 90,
            "Min Height": 90,
            "Max Height": 90,
            "Register": 105,
            "Value": 75,
            "Confidence": 95,
        }

        for i, col_name in enumerate(self.uic.model_column):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Interactive)
            w = col_widths.get(col_name, 90)
            table.setColumnWidth(i, w)

    def _setup_table_delegates(self):
        """Cài đặt các delegates: Delegate mặc định font 11 Bold căn giữa, 
        CheckboxDelegate cho cột tích chọn và RegisterDelegate cho cột Register."""
        if not hasattr(self.uic, 'tableView') or self.uic.tableView is None:
            return
        
        # 1. Delegate mặc định cho toàn bộ các ô text: font 11 Bold, căn giữa
        centered_delegate = CenteredItemDelegate(self.uic.tableView)
        self.uic.tableView.setItemDelegate(centered_delegate)

        # 2. Checkbox Delegate cho các cột Enabled, OK, NG
        checkbox_delegate = CheckboxDelegate(self.uic.tableView)
        for chk_col in [self.keys_mapping[1], self.keys_mapping[2], self.keys_mapping[3]]:
            if chk_col in self.uic.model_column:
                self.uic.tableView.setItemDelegateForColumn(self.uic.model_column.index(chk_col), checkbox_delegate)

        # 3. Register Delegate cho cột Register
        if "Register" in self.uic.model_column:
            self.uic.tableView.setItemDelegateForColumn(
                self.uic.model_column.index("Register"),
                RegisterDelegate(self.uic.tableView)
            )

    def _format_table_headers(self):
        """Định dạng font 11, in đậm và căn giữa cho tiêu đề cột (Horizontal Header)."""
        if not hasattr(self.uic, 'model') or self.uic.model is None:
            return
        font_header = QtGui.QFont("Segoe UI", 11)
        font_header.setBold(True)
        for col in range(self.uic.model.columnCount()):
            h_item = self.uic.model.horizontalHeaderItem(col)
            if h_item:
                h_item.setFont(font_header)
                h_item.setTextAlignment(Qt.AlignCenter)
                h_item.setForeground(QtGui.QBrush(QtGui.QColor("#1F4E78")))

    def format_all_table_items(self):
        """Đảm bảo tất cả các ô trong bảng và tiêu đề cột/hàng đều có font 11, in đậm và căn giữa."""
        if not hasattr(self.uic, 'model') or self.uic.model is None:
            return
        model = self.uic.model
        font_cell = QtGui.QFont("Segoe UI", 11)
        font_cell.setBold(True)

        model.blockSignals(True)
        try:
            # 1. Định dạng Horizontal Header
            for col in range(model.columnCount()):
                h_item = model.horizontalHeaderItem(col)
                if h_item:
                    h_item.setFont(font_cell)
                    h_item.setTextAlignment(Qt.AlignCenter)
                    h_item.setForeground(QtGui.QBrush(QtGui.QColor("#1F4E78")))

            # 2. Định dạng các ô dữ liệu và Vertical Header
            for row in range(model.rowCount()):
                v_item = model.verticalHeaderItem(row)
                if v_item:
                    v_item.setFont(font_cell)
                    v_item.setTextAlignment(Qt.AlignCenter)
                    v_item.setForeground(QtGui.QBrush(QtGui.QColor("#1F4E78")))

                for col in range(model.columnCount()):
                    item = model.item(row, col)
                    if item:
                        item.setFont(font_cell)
                        item.setTextAlignment(Qt.AlignCenter)
        finally:
            model.blockSignals(False)

    def create_table_row_items(self, label_name: str, custom_values: Optional[dict] = None) -> list:
        """
        Tạo danh sách QStandardItem cho 1 hàng với các giá trị mặc định chuẩn xác:
        - Font chữ 11, in đậm (Bold), căn giữa toàn bộ ô
        - Max Width, Max Height: 10000
        - Enabled [✓]: Có tích vào ô (Qt.Checked)
        - Register: Bắt đầu bằng 'DM'
        - Value: 1
        - Confidence: 30
        - Qty: 1
        - Min Width, Min Height: 1
        """
        values_dict = custom_values or {}
        row_items = []
        font_cell = QtGui.QFont("Segoe UI", 11)
        font_cell.setBold(True)

        for col_name in self.uic.model_column:
            item = QStandardItem()
            item.setFont(font_cell)
            item.setTextAlignment(Qt.AlignCenter)

            if col_name == self.keys_mapping[0]:  # "Label Name"
                item.setText(str(label_name))
            elif col_name in [self.keys_mapping[1], self.keys_mapping[2], self.keys_mapping[3]]:
                item.setCheckable(True)
                if col_name in values_dict and values_dict[col_name] is not None:
                    is_chk = bool(values_dict[col_name])
                else:
                    is_chk = bool(DEFAULT_ROW_VALUES.get(col_name, False))
                item.setCheckState(Qt.Checked if is_chk else Qt.Unchecked)
            else:
                val = values_dict.get(col_name)
                # Nếu không có giá trị từ custom_values hoặc giá trị là 0 cho các cột cần mặc định khác 0
                if val is None or str(val).strip() == "" or (str(val).strip() == "0" and col_name in (
                    "Max Width", "Max Height", "Register", "Qty", "Value", "Confidence", "Min Width", "Min Height"
                )):
                    val_str = str(DEFAULT_ROW_VALUES.get(col_name, "0"))
                else:
                    val_str = str(val).strip()

                if col_name == "Register":
                    if not val_str or val_str == "0":
                        val_str = "DM"
                    elif not val_str.upper().startswith("DM"):
                        val_str = f"DM{val_str.upper()}"
                    else:
                        val_str = val_str.upper()

                item.setText(val_str)
            row_items.append(item)
        return row_items

    def _on_table_item_changed(self, item):
        """Đảm bảo cột Register luôn có tiền tố 'DM', và toàn bộ ô nhập vào đều có font 11 Bold và căn giữa."""
        if not hasattr(self.uic, 'model_column') or item is None:
            return
        
        self.uic.model.blockSignals(True)
        try:
            font = QtGui.QFont("Segoe UI", 11)
            font.setBold(True)
            item.setFont(font)
            item.setTextAlignment(Qt.AlignCenter)

            if "Register" in self.uic.model_column:
                reg_idx = self.uic.model_column.index("Register")
                if item.column() == reg_idx:
                    txt = item.text().strip()
                    if not txt:
                        item.setText("DM")
                    elif not txt.upper().startswith("DM"):
                        item.setText(f"DM{txt.upper()}")
                    elif txt != txt.upper():
                        item.setText(txt.upper())
        finally:
            self.uic.model.blockSignals(False)

    def get_current_camera_id(self):
        """Lấy camera_id từ thuộc tính hoặc từ comboBox_camera_id."""
        if getattr(self, 'camera_id', None) is not None:
            return self.camera_id
        if hasattr(self, 'uic') and hasattr(self.uic, 'comboBox_camera_id'):
            txt = self.uic.comboBox_camera_id.currentText().strip()
            if txt.isdigit():
                self.camera_id = int(txt)
                return self.camera_id
        if self.cursor and getattr(self, 'camera_name', None):
            try:
                self.cursor.execute("SELECT id FROM NUMS_CAMERA WHERE nums_camera = %s LIMIT 1", (self.camera_name,))
                r = self.cursor.fetchone()
                if r:
                    self.camera_id = r[0]
                    return self.camera_id
            except Exception:
                pass
        return getattr(self, 'camera_id', None)

    def get_current_model_id(self):
        """Lấy model_id từ model_number, comboBox_model_id hoặc model_id của tab hiện tại."""
        if getattr(self, 'model_number', None) is not None:
            try:
                mod_str = str(self.model_number).removeprefix('model-').strip()
                if mod_str.isdigit():
                    self.model_id = int(mod_str)
                    return self.model_id
            except (ValueError, TypeError):
                pass
        if hasattr(self, 'uic') and hasattr(self.uic, 'comboBox_model_id'):
            txt = getattr(self.uic.comboBox_model_id, 'currentText', lambda: "")()
            if isinstance(txt, str) and txt.strip().isdigit():
                self.model_id = int(txt.strip())
                return self.model_id
        if getattr(self, 'model_id', None) is not None:
            return self.model_id
        return 1

    def show_table_context_menu(self, pos):
        """Hiển thị menu ngữ cảnh chuột phải khi chọn các dòng trên tableView."""
        if hasattr(self, 'slider_controller') and self.slider_controller:
            self.slider_controller.popup.hide()
        selected_indexes = self.uic.tableView.selectionModel().selectedRows()
        if not selected_indexes:
            return

        selected_labels = []
        for idx in selected_indexes:
            row = idx.row()
            item = self.uic.model.item(row, 0)
            if item:
                lbl_name = item.text().strip()
                if lbl_name and lbl_name not in selected_labels:
                    selected_labels.append(lbl_name)

        if not selected_labels:
            return

        menu = QtWidgets.QMenu(self.uic.tableView)
        menu.setStyleSheet("""
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
        """)

        action_add_task = menu.addAction(f"➕ Thêm {len(selected_labels)} nhãn đã chọn vào Task Calculator...")
        action = menu.exec_(self.uic.tableView.viewport().mapToGlobal(pos))
        if action == action_add_task:
            self.add_selected_labels_to_task(selected_labels)

    def add_selected_labels_to_task(self, selected_labels: list):
        """Mở popup chọn Task đích để nạp các nhãn đã chọn."""
        cam_id = self.get_current_camera_id()
        mod_id = self.get_current_model_id()
        if not cam_id:
            QMessageBox.warning(None, "Chưa chọn Camera", "Không tìm thấy thông tin Camera ID. Vui lòng kiểm tra lại cấu hình Camera!")
            return

        from module_3.select_task_dialog import SelectTaskForLabelsDialog
        dlg = SelectTaskForLabelsDialog(
            camera_id=cam_id,
            model_id=mod_id,
            selected_labels=selected_labels,
            cursor=self.cursor,
            connection=self.connect_db,
            parent=None
        )
        dlg.exec_()
        self.load_task_calculator_config()

    def open_task_workspace(self):
        """Mở Task Workspace Dialog quản lý các task tính toán của tab model hiện tại."""
        cam_id = self.get_current_camera_id()
        mod_id = self.get_current_model_id()
        if not cam_id:
            QMessageBox.warning(None, "Chưa chọn Camera", "Không tìm thấy thông tin Camera ID. Vui lòng kiểm tra lại cấu hình Camera!")
            return

        from module_3.task_workspace_dialog import TaskWorkspaceDialog
        dlg = TaskWorkspaceDialog(
            camera_id=cam_id,
            camera_name=self.camera_name,
            model_id=mod_id,
            item_code=self.item_code,
            cursor=self.cursor,
            connection=self.connect_db,
            parent=None
        )
        dlg.exec_()
        self.load_task_calculator_config()

    def get_key_model(self):
        """Trả về tuple key_model dạng ('camera-X', 'model-Y')."""
        cam_str = str(self.camera_name) if getattr(self, 'camera_name', None) else ""
        if not cam_str and getattr(self, 'camera_id', None):
            cam_str = str(self.camera_id)
        if not cam_str:
            cam_str = "1"
        cam_num = cam_str.removeprefix("camera-").removeprefix("built-in-")
        cam_key = f"camera-{cam_num}"

        mod_num = self.get_current_model_id()
        mod_key = f"model-{str(mod_num).removeprefix('model-')}"

        return (cam_key, mod_key)

    def load_task_calculator_config(self):
        """Tải cấu hình các task còn hiệu lực của camera và tab model này vào bộ nhớ để inference sử dụng."""
        cam_id = self.get_current_camera_id()
        mod_id = self.get_current_model_id()
        if not self.cursor or not cam_id:
            return
        try:
            from module_3.task_calculator_db import ensure_task_calculator_tables, get_tasks_by_camera, get_task_rules
            ensure_task_calculator_tables(self.cursor, self.connect_db)
            all_tasks = get_tasks_by_camera(self.cursor, cam_id, mod_id)
            
            key_model = self.get_key_model()
            tasks_list = []
            for t in all_tasks:
                if t.get('enabled'):
                    t['rules'] = get_task_rules(self.cursor, t['id'])
                    if t['rules']:
                        tasks_list.append(t)
            
            if not isinstance(self.active_tasks, dict):
                self.active_tasks = {}
            self.active_tasks[key_model] = tasks_list
            Process_Model.dict_active_tasks[key_model] = tasks_list
            _log.info("Loaded %d active geometric tasks for key_model=%s (camera_id=%s, model_id=%s)", 
                      len(tasks_list), key_model, cam_id, mod_id)
        except Exception as e:
            _log.error("Error loading task calculator config: %s", e)

    def toggle_lock(self, cursor, connect_db):
        if getattr(self, 'is_unlocked', False):
            self.lock_gui(cursor, connect_db, method=False, boolen=False)
            self.is_unlocked = False
            self.current_role = None
            self.current_user = None
            self.uic.pushButton_edit_params.setText("Edit Parameters")
        else:
            self.lock_gui(cursor, connect_db, method=True, boolen=True)

    def set_ui_enabled(self, enabled=False, role='full_control'):
        """
        Khóa hoặc mở khóa giao diện theo phân quyền:
        - read_only / enabled=False: Khóa toàn bộ các đối tượng thao tác
        - modify: Chỉ cho phép điều chỉnh bảng thông số (self.uic.tableView) và lưu bảng (pushButton_save_data)
        - full_control / __ADMIN__: Mở toàn bộ đối tượng điều khiển
        """
        widget_types = [
            QtWidgets.QPushButton, 
            QtWidgets.QLineEdit, 
            QtWidgets.QComboBox, 
            QtWidgets.QSpinBox, 
            QtWidgets.QDoubleSpinBox, 
            QtWidgets.QTableView,
            QtWidgets.QCheckBox, 
            QtWidgets.QRadioButton
        ]

        # 1. Nếu khóa toàn bộ (enabled=False) hoặc quyền read_only
        if not enabled or role == 'read_only':
            for widget_type in widget_types:
                for widget in self.uic.centralwidget.findChildren(widget_type):
                    if widget != self.uic.pushButton_edit_params:
                        widget.setEnabled(False)
            self.uic.pushButton_edit_params.setEnabled(True)
            if hasattr(self, 'slider_controller') and self.slider_controller:
                self.slider_controller.popup.hide()
            return

        # 2. Nếu quyền modify: Chỉ thao tác điều chỉnh các thông số trong tableView và lưu dữ liệu
        if role == 'modify':
            # Khóa toàn bộ widget con trước
            for widget_type in widget_types:
                for widget in self.uic.centralwidget.findChildren(widget_type):
                    if widget != self.uic.pushButton_edit_params:
                        widget.setEnabled(False)

            # Chỉ mở khóa TableView và nút Lưu dữ liệu bảng
            if hasattr(self.uic, 'tableView'):
                self.uic.tableView.setEnabled(True)
            if hasattr(self.uic, 'pushButton_save_data'):
                self.uic.pushButton_save_data.setEnabled(True)
            if hasattr(self.uic, 'pushButton_load_parameters'):
                self.uic.pushButton_load_parameters.setEnabled(True)
            self.uic.pushButton_edit_params.setEnabled(True)
            return

        # 3. Nếu quyền full_control hoặc Administrator: Mở toàn bộ các đối tượng
        if role in ('full_control', '__ADMIN__'):
            for widget_type in widget_types:
                for widget in self.uic.centralwidget.findChildren(widget_type):
                    if widget != self.uic.pushButton_edit_params:
                        widget.setEnabled(True)
            self.uic.pushButton_edit_params.setEnabled(True)
            return

    def lock_gui(self, cursor, connect_db, method=False, boolen=False):
        if not method:
            self.set_ui_enabled(enabled=False, role='read_only')
            self.is_unlocked = False
            self.current_role = None
            self.current_user = None
            if hasattr(self.uic, 'pushButton_edit_params'):
                self.uic.pushButton_edit_params.setText("Edit Parameters")
            return True

        try:
            from module_3.auth_dialog import EnterpriseAuthDialog
            dlg = EnterpriseAuthDialog(
                cursor=cursor,
                parent=getattr(self.uic, 'centralwidget', None),
                system_context="Cấu Hình Tham Số Mô Hình (Model Options)"
            )
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                is_auth, username, role = dlg.get_auth_result()
                if not is_auth:
                    return False

                self.current_user = username
                self.current_role = role

                # ─────────────────────────────────────────────────────────────
                # PHÂN QUYỀN HỆ THỐNG:
                # ─────────────────────────────────────────────────────────────
                # 1. Trường hợp read_only: Mặc dù đúng pass nhưng đối tượng vẫn bị khóa
                if role == "read_only":
                    self.set_ui_enabled(enabled=False, role="read_only")
                    self.is_unlocked = False
                    self.uic.pushButton_edit_params.setText("Edit Parameters")
                    QtWidgets.QMessageBox.warning(
                        self.uic.centralwidget,
                        "Quyền hạn bị giới hạn (Read Only)",
                        f"Tài khoản '{username}' có quyền hạn [read_only] (Chỉ xem).\n\n"
                        "Hệ thống không cho phép thực hiện thao tác hay chỉnh sửa thông số!\n"
                        "Tất cả các đối tượng tiếp tục được giữ ở trạng thái KHÓA."
                    )
                    return False

                # 2. Trường hợp modify: Chỉ cho phép điều chỉnh bảng tableView và lưu bảng
                elif role == "modify":
                    self.set_ui_enabled(enabled=True, role="modify")
                    self.is_unlocked = True
                    self.uic.pushButton_edit_params.setText("Lock Edit")
                    QtWidgets.QMessageBox.information(
                        self.uic.centralwidget,
                        "Mở khóa thành công (Quyền Modify)",
                        f"Xác thực thành công cho tài khoản '{username}' [Quyền: Modify].\n\n"
                        "Bạn chỉ được phép hiệu chỉnh các thông số trong Bảng thông số (TableView) và Lưu dữ liệu.\n"
                        "Các nhóm cấu hình khác (Weights, Camera, Thư mục lưu ảnh...) vẫn được bảo vệ khóa an toàn."
                    )
                    return True

                # 3. Trường hợp full_control hoặc Master Administrator: Mở toàn bộ
                elif role in ("full_control", "__ADMIN__"):
                    self.set_ui_enabled(enabled=True, role="full_control")
                    self.is_unlocked = True
                    self.uic.pushButton_edit_params.setText("Lock Edit")
                    QtWidgets.QMessageBox.information(
                        self.uic.centralwidget,
                        "Mở khóa thành công (Full Control)",
                        f"Xác thực thành công cho tài khoản '{username}' [Toàn quyền].\n\n"
                        "Toàn bộ các đối tượng điều khiển và cấu hình hệ thống đã được MỞ KHÓA."
                    )
                    return True
                else:
                    self.set_ui_enabled(enabled=False, role="read_only")
                    self.is_unlocked = False
                    return False
            else:
                return False
        except Exception as e:
            print("Error in lock_gui (handle_option_models):", e)
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(None, "Lỗi xác thực", str(e))
            return False

    def browse_file(self):
            options = QtWidgets.QFileDialog.Options()
            self.file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                None,
                "Chọn file",
                "",
                "PyTorch Model (*.pt);;Tất cả các file (*)",
                options=options
            )
            if self.file_path:
                self.uic.lineEdit_weight_pytorch.setText(self.file_path)

    def browse_file_detect(self):
        options = QtWidgets.QFileDialog.Options()
        self.file_path_detect, _ = QtWidgets.QFileDialog.getOpenFileName(
            None,
            "Chọn file",
            "",
            "Hình ảnh (*.jpg *.png *.bmp);;Tất cả các file (*)",
            options=options
        )
        if self.file_path_detect:
            size = self.uic.label_5.size()
            width, height = size.width(), size.height()
            self.uic.lineEdit_weight_tensorrt.setText(self.file_path_detect)

            image = cv2.imread(self.file_path_detect)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            image = cv2.resize(image, (width, height))

            qimage = QtGui.QImage(image.data, image.shape[1], image.shape[0], image.strides[0], QtGui.QImage.Format_RGB888)
            pixmap = QtGui.QPixmap.fromImage(qimage)
            self.uic.label_5.setPixmap(pixmap)

    def browse_folder_activity_history(self):
            folder = QFileDialog.getExistingDirectory(
                None,
                "Select Folder",
                "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if folder:
                self.uic.lineEdit_data_change.setText(folder)

    def browse_file_engine_tensorrt(self):
            options = QtWidgets.QFileDialog.Options()
            self.file_path_engine_tensorrt, _ = QtWidgets.QFileDialog.getOpenFileName(
                None,
                "Chọn file",
                "",
                "Engine TensorRT (*.engine);;Tất cả các file (*)",
                options=options
            )
            if self.file_path_engine_tensorrt:
                self.uic.lineEdit_weight_tensorrt.setText(self.file_path_engine_tensorrt)

    def browse_file_classes(self):
        options = QtWidgets.QFileDialog.Options()
        self.file_path_classes, _ = QtWidgets.QFileDialog.getOpenFileName(
            None,
            "Chọn file",
            "",
            "Classes (*.txt);;Tất cả các file (*)",
            options=options
        )
        if self.file_path_classes:
            self.uic.lineEdit_classes_txt.setText(self.file_path_classes)
    

    def browse_folder_ng_img_original(self):
            folder = QFileDialog.getExistingDirectory(
                None,
                "Select Folder",
                "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if folder:
                self.uic.lineEdit_NG_image_original.setText(folder)

    def browse_folder_ng_img_detected(self):
            folder = QFileDialog.getExistingDirectory(
                None,
                "Select Folder",
                "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if folder:
                self.uic.lineEdit_NG_image_detected.setText(folder)

    def browse_folder_ok_img_original(self):
            folder = QFileDialog.getExistingDirectory(
                None,
                "Select Folder",
                "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if folder:
                self.uic.lineEdit_OK_image_original.setText(folder)

    def browse_folder_ok_img_detected(self):
            folder = QFileDialog.getExistingDirectory(
                None,
                "Select Folder",
                "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if folder:
                self.uic.lineEdit_OK_image_detected.setText(folder)

    def browse_folder_image_logging(self):
            folder = QFileDialog.getExistingDirectory(
                None,
                "Select Folder",
                "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if folder:
                self.uic.lineEdit_logging_image.setText(folder)
    

    def detect_img(self):
        if not self.file_path_detect:
            QMessageBox.warning(None, "Cảnh báo4", "Vui lòng chọn file trước.")
            return
        t1 = time.time()
        size = self.uic.label_5.size()
        width_widget, height_widget = size.width(), size.height()
        image = cv2.imread(self.file_path_detect) 
        result_image_rgb,flag = self.engine(image,width_widget,height_widget)
        if flag:
            cv2.putText(result_image_rgb, 'RESULT:OK',(10, 50),cv2.FONT_HERSHEY_COMPLEX,  0.5,(0,255,0),1)
        else:
            cv2.putText(result_image_rgb, 'RESULT:NG',(10, 50),cv2.FONT_HERSHEY_COMPLEX,  0.5,(0,0,255),1)
        t2 = time.time()
        cv2.putText(result_image_rgb, f"Time: {t2-t1:.3f} s", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        qimage = QtGui.QImage(result_image_rgb.data, result_image_rgb.shape[1], result_image_rgb.shape[0], result_image_rgb.strides[0], QtGui.QImage.Format_RGB888)
        pixmap = QtGui.QPixmap.fromImage(qimage)
        self.uic.label_5.setPixmap(pixmap)

    def save_parameter_before_load_weight(self):
        model = self.uic.model
        model_column = self.uic.model_column
        label_col_index = model_column.index(self.keys_mapping[0])
        for row in range(model.rowCount()): 
            label_item = model.item(row, label_col_index)
            if label_item is None:
                continue
            label_text = label_item.text().strip()
            row_data = {}
            for col in range(model.columnCount()): 
                item = model.item(row, col)
                if item is not None:
                    if item.isCheckable():
                        value = item.checkState() == Qt.Checked
                    else:
                        value = item.text()
                    row_data[model_column[col]] = value
            row_data[self.keys_mapping[0]] = label_text
            self.list_layer.append(row_data)
        _log.info("Save parameter before load weight successfully")
        return self.list_layer

    def load_model(self):
        weight_input = self.uic.lineEdit_weight_pytorch.text().strip()
        if not weight_input:
            QMessageBox.warning(None, "Cảnh báo5", "Vui lòng chọn file trước.")
            return

        if not os.path.isabs(weight_input):
            self.file_path = os.path.join(WEIGHTS_DIR, weight_input)
        else:
            if not os.path.exists(weight_input):
                # Fallback: Nếu CSDL cũ lưu path tuyệt đối từ máy khác, ta tự sửa lại thành path chuẩn của máy mới
                basename = os.path.basename(weight_input)
                self.file_path = os.path.join(WEIGHTS_DIR, basename)
            else:
                self.file_path = weight_input
            
        source_model = self.uic.comboBox_source.currentText()
        task_model = self.uic.comboBox_source_task.currentText()

        model_runtime = self.uic.comboBox_model_runtime.currentText()
        device = self.uic.comboBox_device_gpu.currentText()

        factory_result = YoloFactory.load_model(source_model, task_model, model_runtime, self.file_path, device)

        if factory_result.get("success"):
            self.path_object = factory_result.get("path_object")
            self.model_loader = factory_result.get("model_loader")
            self.result_model = factory_result.get("result_model")
            self.model = self.model_loader

            self.use_model()
                
            self.populateTable()
            _log.info(f"Load model {source_model} successfully")
        else:
            if factory_result.get("error_msg"):
                _log.warning(factory_result.get("error_msg"))
            return
        
    def populateTable(self):
        if hasattr(self, 'slider_controller') and self.slider_controller:
            self.slider_controller.popup.hide()
        self.uic.model.removeRows(0, self.uic.model.rowCount())
        if isinstance(self.model.names, list) or isinstance(self.model.names, dict):
            self._setup_table_delegates()
            for label in (self.model.names if isinstance(self.model.names, list) else self.model.names.values()):
                row_items = self.create_table_row_items(str(label))
                self.uic.model.appendRow(row_items)
            self._setup_column_widths()
            self.format_all_table_items()
        _log.info("Populate table successfully")
        
        
    def save_values_injection_safe(self, cursor, connector):
        try:
            row_count = self.uic.model.rowCount()
            col_count = self.uic.model.columnCount()
            list_insert = []
            for row in range(row_count):
                row_data = {}
                is_empty_row = True
                for col in range(col_count):
                    header = self.uic.model_column[col] 
                    item = self.uic.model.item(row, col)
                    if item is not None:
                        if item.isCheckable():
                            value = item.checkState() == Qt.Checked
                        else:
                            value = item.text().strip()
                            if value:
                                is_empty_row = False
                        row_data[header] = value
                    else:
                        row_data[header] = None
                if not is_empty_row:
                    list_insert.append(row_data)
            cursor.execute("""
                SELECT id FROM NUMS_MODEL
                WHERE camera_id = %s AND nums_model = %s
            """, (self.uic.comboBox_camera_id.currentText(), self.uic.comboBox_model_id.currentText()))

            result = cursor.fetchone()
            if not result:
                raise ValueError("Không tìm thấy model_id tương ứng.")
            
            _log.info("Find model_id successfully")

            model_id = result[0]
            weight_path_input = self.uic.lineEdit_weight_pytorch.text().strip()
            if weight_path_input and not os.path.isabs(weight_path_input):
                full_weight_path = os.path.join(WEIGHTS_DIR, weight_path_input)
            else:
                full_weight_path = weight_path_input
            weight_filename_for_db = ""
            if full_weight_path and full_weight_path.endswith('.pt'):
                if os.path.exists(full_weight_path):
                    try:
                        hasher = hashlib.md5()
                        with open(full_weight_path, 'rb') as f:
                            for chunk in iter(lambda: f.read(8192), b""):
                                hasher.update(chunk)
                        file_hash = hasher.hexdigest()[:8]
                        
                        original_name = os.path.basename(full_weight_path)
                        if original_name.startswith(f"{file_hash}_"):
                            weight_filename_for_db = original_name
                        else:
                            weight_filename_for_db = f"{file_hash}_{original_name}"
                            
                        target_path = os.path.join(WEIGHTS_DIR, weight_filename_for_db)
                        
                        if os.path.abspath(full_weight_path) != os.path.abspath(target_path):
                            shutil.copy2(full_weight_path, target_path)
                            _log.info("Smart-copied weight to %s", target_path)
                    except Exception as e:
                        _log.error("Failed to smart-copy weight: %s", e)
                            
            conf = self.uic.spinBox_confidenc_score.value()
            size = self.uic.comboBox_imgsz.currentText()
            activity_history = self.uic.lineEdit_data_change.text().strip()
            device_load_model = self.uic.comboBox_device_gpu.currentText()
            source_model = self.uic.comboBox_source.currentText()
            task_model = self.uic.comboBox_source_task.currentText()
            model_runtime = self.uic.comboBox_model_runtime.currentText()
            weight_tensorrt_path = self.uic.lineEdit_weight_tensorrt.text().strip()
            classes_file_path = self.uic.lineEdit_classes_txt.text().strip()
            iou_value = self.uic.spinBox_iou.value()
            max_detections = self.uic.spinBox_max_detection.value()
            image_format = self.uic.Image_format.currentText().strip() if hasattr(self.uic, 'Image_format') else 'PNG'
            folder_ng_original_path = self.uic.lineEdit_NG_image_original.text().strip()
            save_ng_original = self.uic.checkBox_NG_image_original.isChecked()
            folder_ng_detected_path = self.uic.lineEdit_NG_image_detected.text().strip()
            save_ng_detected = self.uic.checkBox_NG_image_detected.isChecked()
            folder_ok_original_path = self.uic.lineEdit_OK_image_original.text().strip()
            save_ok_original = self.uic.checkBox_OK_image_original.isChecked()
            folder_ok_detected_path = self.uic.lineEdit_OK_image_detected.text().strip()
            save_ok_detected = self.uic.checkBox_OK_image_detected.isChecked()
            folder_image_logging = self.uic.lineEdit_logging_image.text().strip()
            
            try:
                cursor.execute("SHOW COLUMNS FROM WEIGHTS LIKE 'Image_format'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE WEIGHTS ADD COLUMN Image_format VARCHAR(255) DEFAULT 'PNG' AFTER Max_Detections")
            except Exception:
                pass

            cursor.execute(
                    f"DELETE FROM WEIGHTS WHERE model_id = %s",
                    (model_id,),
                )
   
            if weight_filename_for_db and weight_filename_for_db.endswith('.pt'):
                cursor.execute("""
                    INSERT IGNORE INTO WEIGHTS
                    (Weight_Path, Activity_History_Path, Conf_Value, Size_Value, Device, Source, Task, Model_Runtime, Weight_TensorRT_Path, Classes_File_Path, IOU_Value, Max_Detections, Image_format, Folder_NG_Original_Path, Save_NG_Original, Folder_NG_Detected_Path, Save_NG_Detected, Folder_OK_Original_Path, Save_OK_Original, Folder_OK_Detected_Path, Save_OK_Detected, Folder_Image_Logging, model_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (weight_filename_for_db, activity_history, conf, size, device_load_model, source_model, task_model, model_runtime, weight_tensorrt_path, classes_file_path, iou_value, max_detections, image_format, folder_ng_original_path, save_ng_original, folder_ng_detected_path, save_ng_detected, folder_ok_original_path, save_ok_original, folder_ok_detected_path, save_ok_detected, folder_image_logging, model_id))

            cursor.execute(
                    f"DELETE FROM PARAMETERSET WHERE model_id = %s",
                    (model_id,),
                )

            if list_insert:
                for row_idx, row_dict in enumerate(list_insert):
                    if "Register" in row_dict:
                        val = row_dict["Register"]
                        if val is not None and str(val).strip() != "":
                            val_str = str(val).strip().upper()
                            if not val_str.startswith("DM"):
                                val_str = f"DM{val_str}"
                            row_dict["Register"] = val_str
                    if "Value" in row_dict:
                        val = row_dict["Value"]
                        if val is not None and str(val).strip() != "":
                            if not str(val).lstrip('-').isdigit():
                                QMessageBox.warning(None, "Loi Nhap Lieu", f"Dong {row_idx + 1}: Cot 'Value' phai la so nguyen.")
                                return
                    if "Confidence" in row_dict:
                        val = row_dict["Confidence"]
                        if val is not None and str(val).strip() != "":
                            if not str(val).lstrip('-').isdigit() or not (0 <= int(val) <= 100):
                                QMessageBox.warning(None, "Loi Nhap Lieu", f"Dong {row_idx + 1}: Cot 'Confidence' phai la so nguyen tu 0 den 100.")
                                return
                    for size_col in ["Min Width", "Max Width", "Min Height", "Max Height"]:
                        if size_col in row_dict:
                            val = row_dict[size_col]
                            if val is not None and str(val).strip() != "":
                                if not str(val).lstrip('-').isdigit():
                                    QMessageBox.warning(None, "Loi Nhap Lieu", f"Dong {row_idx + 1}: Cot '{size_col}' phai la so nguyen (khong chua dau thap phan hoac chu).")
                                    return
                param_fields = list(COLUMN_MAPPING.values())
                sql = f"""
                    INSERT IGNORE INTO PARAMETERSET 
                    ({', '.join(param_fields)}, model_id)
                    VALUES ({', '.join(['%s'] * (len(param_fields) + 1))})
                """

                for row_dict in list_insert:
                    values = [row_dict.get(ui_col, None) for ui_col in COLUMN_MAPPING.keys()]
                    values.append(model_id)
                    cursor.execute(sql, values)

                connector.connection.commit()
            _log.info("Save parameter successfully")
            QMessageBox.information(None, "Thành công", "Lưu thông số thành công")

        except Error as e:
            connector.connection.rollback()
            QMessageBox.critical(None, "Lỗi", f"MySQL Error: {e}")
            _log.error("Save parameter failed: %s", e)

        except Exception as e:
            connector.connection.rollback()
            QMessageBox.critical(None, "Lỗi không xác định", str(e))
            _log.error("Save parameter failed: %s", e)

    def load_data_injection_safe(self):
        model = self.uic.model
        model_column = self.uic.model_column
        label_col_index = model_column.index(self.keys_mapping[0])

        for row in range(model.rowCount()):
            label_item = model.item(row, label_col_index)
            if label_item is None:
                continue
            label_text = label_item.text().strip()
            for param_dict in self.list_layer:
                if param_dict[self.keys_mapping[0]] == label_text:
                    row_items = self.create_table_row_items(label_text, param_dict)
                    for col, item in enumerate(row_items):
                        model.setItem(row, col, item)

        self.format_all_table_items()
        _log.info("Load parameter successfully")
            
    def assign_values(self,model,camera,code):  
        self.camera_name = str(camera)
        self.item_code = str(code)
        self.model_number = model
        self.uic.comboBox_line_code_id.clear()
        self.uic.comboBox_camera_id.clear()
        self.uic.comboBox_model_id.clear()
        self.uic.comboBox_line_code_id.addItem(str(code))
        self.uic.comboBox_camera_id.addItem(str(camera))
        self.uic.comboBox_model_id.addItem(str(model))

    def collect_device(self):
        devices = torch.cuda.device_count()
        for i in range(devices):
            self.uic.comboBox_device_gpu.addItem(f'cuda:{i}-{torch.cuda.get_device_name(i)}')

    def use_model(self):
        """Tự động bind hàm xử lý ảnh từ bất cứ phiên bản YOLO nào (V5, V8...) được load."""
        if self.result_model is not None and hasattr(self.result_model, 'run_model'):
            self.process_image_func = self.result_model.run_model
            print('activated by run_model')
        else:
            self.process_image_func = None
            _log.warning("result_model is missing or does not have a run_model method")
        
    def load_parameter_injection_safe(self, camera_id, model, cursor, connect_db, tabWidget, ui_instances):
        try:
            self.camera_id = camera_id
            self.model_number = model
            self.cursor = cursor
            self.connect_db = connect_db
            self.model_id = self.get_current_model_id()
            self.load_task_calculator_config()

            try:
                cursor.execute("SHOW COLUMNS FROM WEIGHTS LIKE 'Image_format'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE WEIGHTS ADD COLUMN Image_format VARCHAR(255) DEFAULT 'PNG' AFTER Max_Detections")
            except Exception:
                pass

            weight_path = None
            cursor.execute("""
                SELECT Weight_Path, Activity_History_Path ,Conf_Value, Size_Value, Device,Source,Task,
                Model_Runtime, Weight_TensorRT_Path, Classes_File_Path, IOU_Value, Max_Detections, Image_format, Folder_NG_Original_Path, Save_NG_Original, Folder_NG_Detected_Path, Save_NG_Detected, Folder_OK_Original_Path, Save_OK_Original, Folder_OK_Detected_Path, Save_OK_Detected, Folder_Image_Logging
                FROM WEIGHTS
                WHERE model_id = (SELECT id FROM NUMS_MODEL WHERE camera_id = %s AND nums_model = %s)
            """, (camera_id, model))
            result = cursor.fetchall()

            if result:
                weight_db_val, activity_history, conf_value, size_value, device, source, task, model_runtime, weight_tensorrt_path, classes_file_path, iou_value, max_detections, image_format, folder_ng_original_path, save_ng_original, folder_ng_detected_path, save_ng_detected, folder_ok_original_path, save_ok_original, folder_ok_detected_path, save_ok_detected, folder_image_logging = result[0]
                
                weight_path = ""
                weight_filename = ""
                if weight_db_val and weight_db_val.endswith('.pt'):
                    weight_filename = os.path.basename(weight_db_val)
                    weight_path = os.path.join(WEIGHTS_DIR, weight_filename)
                    # Tính năng migrate: Tự động copy file từ path cũ sang folder mới nếu chưa có
                    if not os.path.exists(weight_path) and os.path.exists(weight_db_val):
                        try:
                            shutil.copy2(weight_db_val, weight_path)
                            _log.info("Migrated weight to %s", weight_path)
                        except Exception:
                            pass
                self.uic.lineEdit_weight_pytorch.setText(weight_filename)
                self.uic.spinBox_confidenc_score.setValue(conf_value)
                self.uic.comboBox_imgsz.setCurrentText(str(size_value))
                self.uic.lineEdit_data_change.setText(activity_history)
                self.uic.comboBox_device_gpu.setCurrentText(device)
                self.uic.comboBox_source.setCurrentText(source)
                self.uic.comboBox_source_task.setCurrentText(task)
                self.uic.comboBox_model_runtime.setCurrentText(model_runtime)
                self.uic.lineEdit_weight_tensorrt.setText(weight_tensorrt_path)
                self.uic.lineEdit_classes_txt.setText(classes_file_path)
                self.uic.spinBox_iou.setValue(iou_value)
                self.uic.spinBox_max_detection.setValue(max_detections)
                if image_format and hasattr(self.uic, 'Image_format'):
                    self.uic.Image_format.setCurrentText(str(image_format))
                self.uic.lineEdit_NG_image_original.setText(folder_ng_original_path)
                self.uic.checkBox_NG_image_original.setChecked(save_ng_original)
                self.uic.lineEdit_NG_image_detected.setText(folder_ng_detected_path)
                self.uic.checkBox_NG_image_detected.setChecked(save_ng_detected)
                self.uic.lineEdit_OK_image_original.setText(folder_ok_original_path)
                self.uic.checkBox_OK_image_original.setChecked(save_ok_original)
                self.uic.lineEdit_OK_image_detected.setText(folder_ok_detected_path)
                self.uic.checkBox_OK_image_detected.setChecked(save_ok_detected)
                self.uic.lineEdit_logging_image.setText(folder_image_logging)

                # Gọi Factory xử lý toàn bộ logic khởi tạo Model
                factory_result = YoloFactory.load_model(source, task, model_runtime, weight_path, device)
                if factory_result.get("success"):
                    self.path_object = factory_result.get("path_object")
                    self.model_loader = factory_result.get("model_loader")
                    self.result_model = factory_result.get("result_model")
                    # Liên kết logic xử lý image inference vào self.process_image_func
                    self.use_model()
                else:
                    if factory_result.get("error_msg"):
                        _log.warning(factory_result.get("error_msg"))

        except Error as e:
            connect_db.connection.rollback()
            QMessageBox.critical(None, "Lỗi", f"MySQL Error: {e}")
            return

        try:
            reverse_column_map = {v: k for k, v in COLUMN_MAPPING.items()}

            db_columns = list(COLUMN_MAPPING.values())
            cursor.execute(f"""
                SELECT {', '.join(db_columns)}
                FROM PARAMETERSET
                WHERE model_id = (SELECT id FROM NUMS_MODEL WHERE camera_id = %s AND nums_model = %s)
            """, (camera_id, model))
            result = cursor.fetchall()
            if result:
                self.uic.model.removeRows(0, self.uic.model.rowCount())
                
                # Check an toàn tránh lỗi 'NoneType' object has no attribute 'names'
                if self.model_loader is not None and hasattr(self.model_loader, 'names'):
                    for label_name in (self.model_loader.names if isinstance(self.model_loader.names, list) else self.model_loader.names.values()):
                        for row_data in result:
                            if str(row_data[db_columns.index(list(COLUMN_MAPPING.values())[0])]) == str(label_name):
                                custom_vals = {}
                                for ui_col in self.uic.model_column:
                                    db_col = COLUMN_MAPPING[ui_col]
                                    db_value = row_data[db_columns.index(db_col)]
                                    custom_vals[ui_col] = db_value
                                row_items = self.create_table_row_items(str(label_name), custom_vals)
                                self.uic.model.appendRow(row_items)   
                    self._setup_table_delegates()
                    self._setup_column_widths()
                    self.format_all_table_items()
                else:
                    _log.warning("Not found label model data in database")  
            self.parametes_model = self.save_parameter_before_load_weight()
        except Error as e:
            connect_db.connection.rollback()
            QMessageBox.critical(None, "Lỗi", f"MySQL Error: {e}")

        except Exception as e:
            connect_db.connection.rollback()
            QMessageBox.critical(None, "Lỗi không xác định", str(e))
    # CREATE TABLE IF NOT EXISTS mode_display (
    #     id              INT AUTO_INCREMENT PRIMARY KEY,
    #     display_mode    VARCHAR(255) NOT NULL,
    #     layout_mode     VARCHAR(255) NOT NULL,
    #     FOREIGN KEY (item_code_id) REFERENCES ITEMS_CODE(id) ON DELETE CASCADE
    # """,
    def save_display_mode(self,cursor,connection,item_code_id,display_mode,layout_mode,show_layout):
        cursor.execute("""
            SELECT * FROM mode_display
            WHERE item_code_id = %s
        """,(item_code_id,))
        if result_cursor := cursor.fetchall():
            cursor.execute("""
                UPDATE mode_display
                SET display_mode = %s, layout_mode = %s,show_layout = %s
                WHERE item_code_id = %s
            """,(display_mode,layout_mode,show_layout,item_code_id))
            connection.connection.commit()
        else:
            cursor.execute("""
                INSERT INTO mode_display (item_code_id, display_mode, layout_mode,show_layout)
                VALUES (%s, %s, %s,%s)
            """,(item_code_id,display_mode,layout_mode,show_layout))
            connection.connection.commit()


    def load_display_mode(self,cursor,connection,item_code_id,ui):
        cursor.execute("""
            SELECT display_mode, layout_mode,show_layout FROM mode_display
            WHERE item_code_id = %s
        """,(item_code_id,))
        if result_cursor := cursor.fetchone():
            display_mode, layout_mode,show_layout = result_cursor
            ui.comboBox_display_mode.setCurrentText(display_mode)
            ui.comboBox_layout_mode_by.setCurrentText(layout_mode)
            ui.comboBox_show_ui.setCurrentText(show_layout)
            

            
class Process_Camera_Device:

    def __init__(self,connection,cursor,uic=None):
        self.uic = uic
        self.connection = connection
        self.cursor = cursor

    def query_camera_type(self, item_code_id, camera):
        self.cursor.execute("""
            SELECT device_type, device_serial, connection_type, ip_address
            FROM NUMS_CAMERA 
            WHERE item_code_id = %s AND nums_camera = %s
        """, (item_code_id, camera))

        row = self.cursor.fetchone()
        if row is None:
            raise ValueError(f"[query_camera_type] Không tìm thấy camera '{camera}' với item_code_id '{item_code_id}'")

        device_type, serial, conn_type, ip_address = row
        return device_type, serial, conn_type, ip_address
    
    def query_mode_id_to_user_index(self,item_code_id,device_ui):
        try:
            camera_name = self.uic.comboBox_camera.currentText()
            mode_name = self.uic.comboBox_mode_auto.currentText()
            index_user_selector = device_ui.comboBox_user_selector.currentIndex()
            user_set_selector = device_ui.comboBox_user_selector.currentText()
            self.cursor.execute("""
                        SELECT id FROM NUMS_CAMERA 
                        WHERE item_code_id = %s AND nums_camera = %s
                    """, (item_code_id, camera_name))
                
            result_camera_id = self.cursor.fetchone() 
            if (camera_id := result_camera_id[0] if result_camera_id else None):
                self.cursor.execute("""
                    SELECT id FROM MODE_AUTO 
                    WHERE mode_name = %s AND camera_id = %s 
                """, (mode_name,camera_id))
                mode_row = self.cursor.fetchone()
                if mode_row and (mode_id := mode_row[0]):
                    self.cursor.execute("""
                    SELECT * FROM USER_SET_CAMERA 
                    WHERE mode_id = %s
                """, (mode_id,))
                    result_record = self.cursor.fetchone() 
                    if not result_record:
                        self.cursor.execute("""
                            INSERT INTO USER_SET_CAMERA (index_user_selector, user_set_selector,mode_id)
                            VALUES (%s, %s, %s)
                        """, (index_user_selector,user_set_selector,mode_id))
                        
                    else:
                        self.cursor.execute("""
                            UPDATE USER_SET_CAMERA 
                            SET index_user_selector = %s, user_set_selector = %s
                            WHERE mode_id = %s
                        """, (index_user_selector,user_set_selector,mode_id))

                    self.connection.connection.commit()
                    if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                        self.uic.config_logger.set_status('userset_camera', 'success', f"Đã lưu UserSet '{user_set_selector}' cho mode '{mode_name}'")
                    QMessageBox.information(None, "Information", f"Lưu thay đổi thành công")
                else:
                    if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                        self.uic.config_logger.set_status('userset_camera', 'error', f"Chưa tồn tại Mode '{mode_name}' trong CSDL để gán UserSet")
                    QMessageBox.critical(None, "Error", f"Mode '{mode_name}' chưa tồn tại!")
            else:
                if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                    self.uic.config_logger.set_status('userset_camera', 'error', f"Không tìm thấy camera '{camera_name}'")
                QMessageBox.critical(None, "Error", f"Không tìm thấy camera '{camera_name}'!")
        except Exception as error:
            if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                self.uic.config_logger.set_status('userset_camera', 'error', f"Lỗi lưu UserSet: {str(error)}")
            QMessageBox.critical(None, "Error", f"Lỗi Insert: {str(error)}")


        
    