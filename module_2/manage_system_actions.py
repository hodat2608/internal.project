# -*- coding: utf-8 -*-
"""
module_2/manage_system_actions.py
==================================
Giao diện quản lý cấu hình tín hiệu PLC điều khiển Restart & Close ứng dụng.
Bao gồm:
- ManageRestartDialog: Cấu hình thanh ghi, bit ON/OFF, đếm ngược, lưu log, bảo vệ phần cứng cho Restart.
- ManageCloseDialog: Cấu hình thanh ghi, bit ON/OFF, đếm ngược, tắt máy tính/tắt app, dọn dẹp cho Close.
- ActionCountdownDialog: Hộp thoại đếm ngược hiển thị khi nhận tín hiệu từ PLC.
- Database helper: Lưu trữ cấu hình vào DATA_IP_ADDRESS.SYSTEM_ACTION_TRIGGERS và cache JSON.
"""

import os
import sys
import json
import time
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon, QColor
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QFrame, QScrollArea, QMessageBox, QWidget, QProgressBar
)
from app_logger.app_logger import get_logger

_log = get_logger('module_2.manage_system_actions')

CONFIG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", "C:\\"), "MBC_Vision_Inspector")
CONFIG_FILE = os.path.join(CONFIG_DIR, "system_action_triggers.json")

DEFAULT_RESTART_CONFIG = {
    "action_type": "RESTART",
    "enabled": 0,
    "register": "DM100",
    "data_type": "Bit",
    "value_bit_on": 1,
    "value_bit_off": "0",
    "auto_write_off": 1,
    "delay_seconds": 3,
    "show_countdown": 1,
    "save_before_action": 1,
    "cleanup_hardware": 1,
    "post_action_mode": "Normal",
    "description": "Kích hoạt khởi động lại ứng dụng Vision từ trạm PLC chính."
}

DEFAULT_CLOSE_CONFIG = {
    "action_type": "CLOSE",
    "enabled": 0,
    "register": "DM102",
    "data_type": "Bit",
    "value_bit_on": 1,
    "value_bit_off": "0",
    "auto_write_off": 1,
    "delay_seconds": 3,
    "show_countdown": 1,
    "save_before_action": 1,
    "cleanup_hardware": 1,
    "post_action_mode": "App Only",
    "description": "Kích hoạt tắt toàn bộ ứng dụng Vision từ PLC khi hết ca hoặc dừng dây chuyền."
}


def ensure_config_dir():
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
    except Exception:
        pass


def ensure_system_action_table(connection):
    """Đảm bảo bảng SYSTEM_ACTION_TRIGGERS tồn tại trong database DATA_IP_ADDRESS."""
    if not connection:
        return
    try:
        cursor = connection.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS `DATA_IP_ADDRESS`")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `DATA_IP_ADDRESS`.`SYSTEM_ACTION_TRIGGERS` (
                action_type VARCHAR(50) PRIMARY KEY,
                enabled INT DEFAULT 0,
                register VARCHAR(255) DEFAULT '',
                data_type VARCHAR(50) DEFAULT 'Bit',
                value_bit_on INT DEFAULT 1,
                value_bit_off VARCHAR(255) DEFAULT '0',
                auto_write_off INT DEFAULT 1,
                delay_seconds INT DEFAULT 3,
                show_countdown INT DEFAULT 1,
                save_before_action INT DEFAULT 1,
                cleanup_hardware INT DEFAULT 1,
                post_action_mode VARCHAR(100) DEFAULT 'Normal',
                description TEXT
            )
        """)
        connection.commit()
        cursor.close()
    except Exception as e:
        _log.warning("Could not ensure SYSTEM_ACTION_TRIGGERS table: %s", e)


def get_system_action_config(action_type: str, connection=None) -> dict:
    """Đọc cấu hình action từ MySQL (hoặc JSON fallback)."""
    ensure_config_dir()
    action_type = str(action_type).upper().strip()
    fallback = DEFAULT_RESTART_CONFIG.copy() if action_type == "RESTART" else DEFAULT_CLOSE_CONFIG.copy()

    # 1. Thử nạp từ MySQL
    if connection:
        try:
            ensure_system_action_table(connection)
            cursor = connection.cursor()
            cursor.execute("""
                SELECT action_type, enabled, register, data_type, value_bit_on,
                       value_bit_off, auto_write_off, delay_seconds, show_countdown,
                       save_before_action, cleanup_hardware, post_action_mode, description
                FROM `DATA_IP_ADDRESS`.`SYSTEM_ACTION_TRIGGERS`
                WHERE action_type = %s
            """, (action_type,))
            row = cursor.fetchone()
            cursor.close()
            if row:
                return {
                    "action_type": str(row[0]),
                    "enabled": int(row[1] or 0),
                    "register": str(row[2] or ""),
                    "data_type": str(row[3] or "Bit"),
                    "value_bit_on": int(row[4] if row[4] is not None else 1),
                    "value_bit_off": str(row[5] if row[5] is not None else "0"),
                    "auto_write_off": int(row[6] if row[6] is not None else 1),
                    "delay_seconds": int(row[7] if row[7] is not None else 3),
                    "show_countdown": int(row[8] if row[8] is not None else 1),
                    "save_before_action": int(row[9] if row[9] is not None else 1),
                    "cleanup_hardware": int(row[10] if row[10] is not None else 1),
                    "post_action_mode": str(row[11] or ("Normal" if action_type == "RESTART" else "App Only")),
                    "description": str(row[12] or "")
                }
        except Exception as e:
            _log.warning("Could not query MySQL for action %s: %s", action_type, e)

    # 2. Thử nạp từ file JSON cache
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if action_type in data:
                    res = fallback.copy()
                    res.update(data[action_type])
                    return res
        except Exception as e:
            _log.warning("Could not read JSON config: %s", e)

    return fallback


def save_system_action_config(action_type: str, config: dict, connection=None) -> bool:
    """Lưu cấu hình action vào cả MySQL và file JSON cache."""
    ensure_config_dir()
    action_type = str(action_type).upper().strip()
    config["action_type"] = action_type

    # 1. Lưu vào MySQL
    if connection:
        try:
            ensure_system_action_table(connection)
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO `DATA_IP_ADDRESS`.`SYSTEM_ACTION_TRIGGERS`
                (action_type, enabled, register, data_type, value_bit_on, value_bit_off,
                 auto_write_off, delay_seconds, show_countdown, save_before_action,
                 cleanup_hardware, post_action_mode, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    enabled = VALUES(enabled),
                    register = VALUES(register),
                    data_type = VALUES(data_type),
                    value_bit_on = VALUES(value_bit_on),
                    value_bit_off = VALUES(value_bit_off),
                    auto_write_off = VALUES(auto_write_off),
                    delay_seconds = VALUES(delay_seconds),
                    show_countdown = VALUES(show_countdown),
                    save_before_action = VALUES(save_before_action),
                    cleanup_hardware = VALUES(cleanup_hardware),
                    post_action_mode = VALUES(post_action_mode),
                    description = VALUES(description)
            """, (
                action_type,
                int(config.get("enabled", 0)),
                str(config.get("register", "")).strip(),
                str(config.get("data_type", "Bit")),
                int(config.get("value_bit_on", 1)),
                str(config.get("value_bit_off", "0")).strip(),
                int(config.get("auto_write_off", 1)),
                int(config.get("delay_seconds", 3)),
                int(config.get("show_countdown", 1)),
                int(config.get("save_before_action", 1)),
                int(config.get("cleanup_hardware", 1)),
                str(config.get("post_action_mode", "")),
                str(config.get("description", ""))
            ))
            connection.commit()
            cursor.close()
        except Exception as e:
            _log.error("Error saving action config to MySQL: %s", e)

    # 2. Lưu vào file JSON cache
    try:
        all_data = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    all_data = json.load(f)
            except Exception:
                all_data = {}
        all_data[action_type] = config
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        _log.error("Error saving action config to JSON: %s", e)
        return False


# =============================================================================
# HỘP THOẠI ĐẾM NGƯỢC (COUNTDOWN DIALOG)
# =============================================================================
class ActionCountdownDialog(QDialog):
    """
    Hộp thoại đếm ngược lớn, hiện đại hiển thị khi nhận tín hiệu từ PLC.
    Cho phép người vận hành ấn HỦY BỎ nếu tín hiệu kích hoạt nhầm.
    """
    def __init__(self, action_type: str, total_seconds: int = 3, parent=None):
        super().__init__(parent)
        self.action_type = action_type.upper()
        self.remaining_seconds = max(1, total_seconds)
        self.total_seconds = self.remaining_seconds
        self.is_aborted = False

        is_restart = (self.action_type == "RESTART")
        title = "🔄 CẢNH BÁO: KHỞI ĐỘNG LẠI ỨNG DỤNG TỪ PLC" if is_restart else "🛑 CẢNH BÁO: ĐÓNG TOÀN BỘ ỨNG DỤNG TỪ PLC"
        self.setWindowTitle(title)
        self.setFixedSize(540, 320)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._build_ui(is_restart)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(1000)

    def _build_ui(self, is_restart: bool):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        card = QFrame()
        bg_border = "#2563EB" if is_restart else "#DC2626"
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #FFFFFF;
                border: 2px solid {bg_border};
                border-radius: 12px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header Icon + Title
        icon_text = "🔄" if is_restart else "⚠️"
        title_text = "TÍN HIỆU PLC: KHỞI ĐỘNG LẠI HỆ THỐNG" if is_restart else "TÍN HIỆU PLC: ĐÓNG TOÀN BỘ ỨNG DỤNG"
        title_color = "#1E40AF" if is_restart else "#991B1B"

        header_lbl = QLabel(f"{icon_text} {title_text}")
        header_lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        header_lbl.setStyleSheet(f"color: {title_color}; border: none;")
        header_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_lbl)

        # Thông điệp cảnh báo
        msg_lbl = QLabel(
            "Hệ thống vừa nhận được tín hiệu kích hoạt từ PLC.\n"
            "Chương trình sẽ tự động thực thi sau khoảng thời gian đếm ngược dưới đây:"
        )
        msg_lbl.setFont(QFont("Segoe UI", 10))
        msg_lbl.setStyleSheet("color: #475569; border: none;")
        msg_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(msg_lbl)

        # Label đếm ngược số to
        self.lbl_count = QLabel(f"{self.remaining_seconds} giây")
        self.lbl_count.setFont(QFont("Segoe UI", 26, QFont.Bold))
        self.lbl_count.setStyleSheet(f"color: {bg_border}; border: none;")
        self.lbl_count.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_count)

        # Thanh Progress Bar
        self.progress = QProgressBar()
        self.progress.setRange(0, self.total_seconds)
        self.progress.setValue(self.remaining_seconds)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(10)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: #F1F5F9;
                border-radius: 5px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {bg_border};
                border-radius: 5px;
            }}
        """)
        layout.addWidget(self.progress)

        # Nút Hủy Bỏ (Abort) và Nút Thực Thi Ngay
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(14)

        self.btn_abort = QPushButton("❌ HỦY BỎ THAO TÁC (ABORT)")
        self.btn_abort.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.btn_abort.setFixedHeight(40)
        self.btn_abort.setCursor(Qt.PointingHandCursor)
        self.btn_abort.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #334155;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 6px 18px;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
                color: #0F172A;
            }
        """)
        self.btn_abort.clicked.connect(self._on_abort)
        btn_layout.addWidget(self.btn_abort)

        self.btn_now = QPushButton("⚡ THỰC THI NGAY")
        self.btn_now.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.btn_now.setFixedHeight(40)
        self.btn_now.setCursor(Qt.PointingHandCursor)
        self.btn_now.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_border};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 18px;
            }}
            QPushButton:hover {{
                background-color: {'#1D4ED8' if is_restart else '#B91C1C'};
            }}
        """)
        self.btn_now.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_now)

        layout.addLayout(btn_layout)
        root.addWidget(card)

    def _on_tick(self):
        self.remaining_seconds -= 1
        self.progress.setValue(self.remaining_seconds)
        if self.remaining_seconds <= 0:
            self.timer.stop()
            self.accept()
        else:
            self.lbl_count.setText(f"{self.remaining_seconds} giây")

    def _on_abort(self):
        self.timer.stop()
        self.is_aborted = True
        self.reject()


# =============================================================================
# GIAO DIỆN CHÍNH 1: QUẢN LÝ RESTART TỪ PLC (MANAGE RESTART DIALOG)
# =============================================================================
class ManageRestartDialog(QDialog):
    """Giao diện cấu hình & quản lý tín hiệu Restart Application từ PLC."""

    def __init__(self, connection=None, main_core_ref=None, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.main_core = main_core_ref
        self.setWindowTitle("🔄 Cấu hình Tín hiệu PLC: Khởi động lại ứng dụng (Restart Application)")
        self.setMinimumSize(1000, 720)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet("QDialog { background-color: #F8FAFC; }")

        self._build_ui()
        self._load_config()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # ── Scroll Area ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollBar:vertical { width: 8px; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(16)

        # ── 1. Header Banner ──
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1E3A8A, stop:1 #2563EB);
                border-radius: 8px;
            }
        """)
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(20, 16, 20, 16)

        v_title = QVBoxLayout()
        title_lbl = QLabel("🔄 PLC RESTART APPLICATION MANAGER")
        title_lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_lbl.setStyleSheet("color: #FFFFFF;")
        sub_lbl = QLabel("Cấu hình giám sát thanh ghi PLC để tự động khởi động lại phần mềm Vision theo chu kỳ hoặc lệnh điều khiển.")
        sub_lbl.setFont(QFont("Segoe UI", 9))
        sub_lbl.setStyleSheet("color: #BFDBFE;")
        v_title.addWidget(title_lbl)
        v_title.addWidget(sub_lbl)
        b_layout.addLayout(v_title)

        # Badge trạng thái PLC
        self.lbl_plc_status = QLabel(self._get_plc_status_text())
        self.lbl_plc_status.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.lbl_plc_status.setStyleSheet("background-color: rgba(255,255,255,0.18); color: #FFFFFF; border-radius: 12px; padding: 6px 14px;")
        b_layout.addWidget(self.lbl_plc_status, alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(banner)

        # ── 2. Card: Cấu hình Thanh ghi PLC ──
        grp_reg = QGroupBox("📡 1. Cấu hình Thanh ghi & Tín hiệu PLC (Register & Signal)")
        grp_reg.setFont(QFont("Segoe UI", 11, QFont.Bold))
        grp_reg.setStyleSheet(self._group_box_qss("#2563EB"))
        grid_reg = QGridLayout(grp_reg)
        grid_reg.setContentsMargins(16, 16, 16, 16)
        grid_reg.setSpacing(12)

        # Enable checkbox
        self.chk_enabled = QCheckBox("Bật tính năng lắng nghe tín hiệu Restart từ PLC")
        self.chk_enabled.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.chk_enabled.setStyleSheet("color: #1E3A8A;")
        grid_reg.addWidget(self.chk_enabled, 0, 0, 1, 2)

        # Register Input
        lbl_reg = QLabel("Địa chỉ thanh ghi (Register):")
        lbl_reg.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.txt_register = QLineEdit()
        self.txt_register.setPlaceholderText("Ví dụ: DM100, MR100, D500, R1000...")
        self.txt_register.setFont(QFont("Consolas", 10, QFont.Bold))
        self.txt_register.setStyleSheet(self._input_qss())
        grid_reg.addWidget(lbl_reg, 1, 0)
        grid_reg.addWidget(self.txt_register, 1, 1)

        # Quick Format Buttons
        h_quick = QHBoxLayout()
        h_quick.addWidget(QLabel("Mẫu nhanh:"))
        for prefix in ["DM", "MR", "D", "W", "B", "R"]:
            btn_pf = QPushButton(prefix)
            btn_pf.setFixedHeight(24)
            btn_pf.setFixedWidth(40)
            btn_pf.setFont(QFont("Segoe UI", 8, QFont.Bold))
            btn_pf.setStyleSheet("background-color: #E2E8F0; color: #334155; border-radius: 3px;")
            btn_pf.clicked.connect(lambda _, p=prefix: self._insert_prefix(p))
            h_quick.addWidget(btn_pf)
        h_quick.addStretch()
        grid_reg.addLayout(h_quick, 2, 1)

        # Value Bit ON
        lbl_on = QLabel("Giá trị kích hoạt (Value Bit ON):")
        lbl_on.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.spin_val_on = QSpinBox()
        self.spin_val_on.setRange(-32768, 65535)
        self.spin_val_on.setValue(1)
        self.spin_val_on.setStyleSheet(self._input_qss())
        grid_reg.addWidget(lbl_on, 3, 0)
        grid_reg.addWidget(self.spin_val_on, 3, 1)

        # Value Bit OFF
        lbl_off = QLabel("Giá trị trả về (Value Bit OFF):")
        lbl_off.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.cbo_val_off = QComboBox()
        self.cbo_val_off.setEditable(True)
        self.cbo_val_off.addItems(["0", "1", "No Value"])
        self.cbo_val_off.setStyleSheet(self._input_qss())
        grid_reg.addWidget(lbl_off, 4, 0)
        grid_reg.addWidget(self.cbo_val_off, 4, 1)

        # Handshake Auto Write-back
        self.chk_auto_write_off = QCheckBox("Tự động ghi trả giá trị OFF về PLC sau khi nhận tín hiệu (Handshake Acknowledgment)")
        self.chk_auto_write_off.setChecked(True)
        self.chk_auto_write_off.setFont(QFont("Segoe UI", 9))
        grid_reg.addWidget(self.chk_auto_write_off, 5, 0, 1, 2)

        layout.addWidget(grp_reg)

        # ── 3. Card: Tùy chọn Nâng cao cho Restart ──
        grp_adv = QGroupBox("⚙️ 2. Tùy chọn Khởi động lại & An toàn dữ liệu (Safety & Options)")
        grp_adv.setFont(QFont("Segoe UI", 11, QFont.Bold))
        grp_adv.setStyleSheet(self._group_box_qss("#2563EB"))
        grid_adv = QGridLayout(grp_adv)
        grid_adv.setContentsMargins(16, 16, 16, 16)
        grid_adv.setSpacing(12)

        # Countdown Delay
        grid_adv.addWidget(QLabel("Thời gian trễ đếm ngược (giây):"), 0, 0)
        self.spin_delay = QSpinBox()
        self.spin_delay.setRange(0, 60)
        self.spin_delay.setValue(3)
        self.spin_delay.setSuffix(" giây")
        self.spin_delay.setStyleSheet(self._input_qss())
        grid_adv.addWidget(self.spin_delay, 0, 1)

        self.chk_show_countdown = QCheckBox("Hiển thị hộp thoại đếm ngược cảnh báo trên màn hình cho người vận hành")
        self.chk_show_countdown.setChecked(True)
        self.chk_show_countdown.setFont(QFont("Segoe UI", 9))
        grid_adv.addWidget(self.chk_show_countdown, 1, 0, 1, 2)

        # Data safety
        self.chk_save_before = QCheckBox("Tự động lưu lại toàn bộ cấu hình CSDL và chốt file Log trước khi khởi động lại")
        self.chk_save_before.setChecked(True)
        self.chk_save_before.setFont(QFont("Segoe UI", 9))
        grid_adv.addWidget(self.chk_save_before, 2, 0, 1, 2)

        self.chk_cleanup_hw = QCheckBox("Ngắt kết nối an toàn Camera và giải phóng bộ nhớ đồ họa trước khi khởi động lại")
        self.chk_cleanup_hw.setChecked(True)
        self.chk_cleanup_hw.setFont(QFont("Segoe UI", 9))
        grid_adv.addWidget(self.chk_cleanup_hw, 3, 0, 1, 2)

        # Description
        grid_adv.addWidget(QLabel("Ghi chú / Mục đích sử dụng:"), 4, 0)
        self.txt_desc = QLineEdit()
        self.txt_desc.setPlaceholderText("Ví dụ: Khởi động lại hàng ngày lúc giao ca...")
        self.txt_desc.setStyleSheet(self._input_qss())
        grid_adv.addWidget(self.txt_desc, 4, 1)

        layout.addWidget(grp_adv)

        # ── 4. Card: Công cụ Kiểm tra Trực tiếp (Live Diagnostic) ──
        grp_test = QGroupBox("🧪 3. Kiểm tra kết nối & Thử nghiệm trực tiếp (Live Test)")
        grp_test.setFont(QFont("Segoe UI", 11, QFont.Bold))
        grp_test.setStyleSheet(self._group_box_qss("#2563EB"))
        h_test = QHBoxLayout(grp_test)
        h_test.setContentsMargins(16, 16, 16, 16)
        h_test.setSpacing(10)

        self.btn_read_now = QPushButton("🔍 Đọc thử giá trị PLC")
        self.btn_read_now.setStyleSheet(self._btn_outline_qss("#2563EB"))
        self.btn_read_now.clicked.connect(self._test_read_plc)
        h_test.addWidget(self.btn_read_now)

        self.lbl_read_val = QLabel("Chưa đọc")
        self.lbl_read_val.setFont(QFont("Consolas", 10, QFont.Bold))
        self.lbl_read_val.setStyleSheet("background-color: #E2E8F0; color: #475569; padding: 4px 10px; border-radius: 4px;")
        h_test.addWidget(self.lbl_read_val)

        self.btn_write_on = QPushButton("✍️ Ghi thử giá trị ON")
        self.btn_write_on.setStyleSheet(self._btn_outline_qss("#059669"))
        self.btn_write_on.clicked.connect(self._test_write_on)
        h_test.addWidget(self.btn_write_on)

        self.btn_test_restart = QPushButton("⚡ Thử Restart ngay")
        self.btn_test_restart.setStyleSheet(self._btn_outline_qss("#D97706"))
        self.btn_test_restart.clicked.connect(self._test_trigger_restart)
        h_test.addWidget(self.btn_test_restart)

        h_test.addStretch()
        layout.addWidget(grp_test)

        layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # ── 5. Footer Buttons ──
        footer = QHBoxLayout()
        footer.setSpacing(12)

        btn_default = QPushButton("🔄 Khôi phục mặc định")
        btn_default.setStyleSheet(self._btn_outline_qss("#64748B"))
        btn_default.clicked.connect(self._on_defaults)
        footer.addWidget(btn_default)

        footer.addStretch()

        btn_close = QPushButton("Đóng")
        btn_close.setStyleSheet(self._btn_outline_qss("#64748B"))
        btn_close.clicked.connect(self.reject)
        footer.addWidget(btn_close)

        btn_save = QPushButton("💾 Lưu cấu hình (Save)")
        btn_save.setFont(QFont("Segoe UI", 10, QFont.Bold))
        btn_save.setFixedHeight(36)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                border-radius: 6px;
                padding: 6px 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
        """)
        btn_save.clicked.connect(self._on_save)
        footer.addWidget(btn_save)

        main_layout.addLayout(footer)

    def _get_plc_status_text(self):
        if self.main_core and getattr(self.main_core, 'mode_init_plc', 0):
            plc_name = getattr(self.main_core, 'plc_module', 'PLC')
            ip = getattr(self.main_core, 'ip_address_plc', '127.0.0.1')
            return f"🟢 Đã kết nối {plc_name} ({ip})"
        return "🟡 Chưa kết nối PLC vật lý"

    def _insert_prefix(self, p):
        cur = self.txt_register.text().strip()
        digits = ''.join(filter(str.isdigit, cur))
        self.txt_register.setText(f"{p}{digits if digits else '100'}")

    def _load_config(self):
        cfg = get_system_action_config("RESTART", self.connection)
        self.chk_enabled.setChecked(bool(cfg.get("enabled", 0)))
        self.txt_register.setText(str(cfg.get("register", "DM100")))
        self.spin_val_on.setValue(int(cfg.get("value_bit_on", 1)))
        self.cbo_val_off.setCurrentText(str(cfg.get("value_bit_off", "0")))
        self.chk_auto_write_off.setChecked(bool(cfg.get("auto_write_off", 1)))
        self.spin_delay.setValue(int(cfg.get("delay_seconds", 3)))
        self.chk_show_countdown.setChecked(bool(cfg.get("show_countdown", 1)))
        self.chk_save_before.setChecked(bool(cfg.get("save_before_action", 1)))
        self.chk_cleanup_hw.setChecked(bool(cfg.get("cleanup_hardware", 1)))
        self.txt_desc.setText(str(cfg.get("description", "")))

    def _on_defaults(self):
        reply = QMessageBox.question(
            self, "Xác nhận", "Bạn có chắc chắn muốn đặt lại các thông số mặc định?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            cfg = DEFAULT_RESTART_CONFIG
            self.chk_enabled.setChecked(bool(cfg["enabled"]))
            self.txt_register.setText(cfg["register"])
            self.spin_val_on.setValue(cfg["value_bit_on"])
            self.cbo_val_off.setCurrentText(cfg["value_bit_off"])
            self.chk_auto_write_off.setChecked(bool(cfg["auto_write_off"]))
            self.spin_delay.setValue(cfg["delay_seconds"])
            self.chk_show_countdown.setChecked(bool(cfg["show_countdown"]))
            self.chk_save_before.setChecked(bool(cfg["save_before_action"]))
            self.chk_cleanup_hw.setChecked(bool(cfg["cleanup_hardware"]))
            self.txt_desc.setText(cfg["description"])

    def _on_save(self):
        reg = self.txt_register.text().strip()
        if self.chk_enabled.isChecked() and not reg:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập địa chỉ thanh ghi PLC!")
            self.txt_register.setFocus()
            return

        cfg = {
            "action_type": "RESTART",
            "enabled": 1 if self.chk_enabled.isChecked() else 0,
            "register": reg,
            "data_type": "Bit",
            "value_bit_on": self.spin_val_on.value(),
            "value_bit_off": self.cbo_val_off.currentText().strip(),
            "auto_write_off": 1 if self.chk_auto_write_off.isChecked() else 0,
            "delay_seconds": self.spin_delay.value(),
            "show_countdown": 1 if self.chk_show_countdown.isChecked() else 0,
            "save_before_action": 1 if self.chk_save_before.isChecked() else 0,
            "cleanup_hardware": 1 if self.chk_cleanup_hw.isChecked() else 0,
            "post_action_mode": "Normal",
            "description": self.txt_desc.text().strip()
        }

        ok = save_system_action_config("RESTART", cfg, self.connection)
        if self.main_core and hasattr(self.main_core, 'reload_system_action_configs'):
            self.main_core.reload_system_action_configs()

        if ok:
            QMessageBox.information(self, "Thành công", "Đã lưu cấu hình tín hiệu Restart thành công!")
            self.accept()
        else:
            QMessageBox.warning(self, "Lỗi", "Không thể lưu cấu hình! Vui lòng kiểm tra lại log hệ thống.")

    def _test_read_plc(self):
        reg = self.txt_register.text().strip()
        if not reg:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập địa chỉ thanh ghi cần đọc!")
            return
        if not self.main_core or not getattr(self.main_core, 'driver_loader', None):
            QMessageBox.warning(self, "PLC Offline", "Hiện chưa có kết nối vật lý đến PLC!")
            return
        try:
            val = self.main_core.driver_loader.read_plc(reg)
            if val is not None:
                self.lbl_read_val.setText(f"Giá trị: {val}")
                self.lbl_read_val.setStyleSheet("background-color: #DCFCE7; color: #166534; font-weight: bold; padding: 4px 10px; border-radius: 4px;")
            else:
                self.lbl_read_val.setText("Không có phản hồi")
                self.lbl_read_val.setStyleSheet("background-color: #FEE2E2; color: #991B1B; padding: 4px 10px; border-radius: 4px;")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi đọc PLC", f"Không thể đọc thanh ghi {reg}:\n{e}")

    def _test_write_on(self):
        reg = self.txt_register.text().strip()
        if not reg:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập địa chỉ thanh ghi!")
            return
        if not self.main_core or not getattr(self.main_core, 'driver_loader', None):
            QMessageBox.warning(self, "PLC Offline", "Hiện chưa có kết nối vật lý đến PLC!")
            return
        try:
            val = self.spin_val_on.value()
            self.main_core.driver_loader.write_plc(reg, val)
            QMessageBox.information(self, "Thành công", f"Đã ghi thành công giá trị {val} vào thanh ghi {reg}!")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi ghi PLC", f"Không thể ghi vào thanh ghi {reg}:\n{e}")

    def _test_trigger_restart(self):
        reply = QMessageBox.question(
            self, "Thử nghiệm Restart",
            "Bạn có chắc muốn kích hoạt thử nghiệm quy trình Khởi động lại ứng dụng ngay bây giờ?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.accept()
            if self.main_core and hasattr(self.main_core, 'worker_thread'):
                cfg = {
                    "action_type": "RESTART",
                    "delay_seconds": self.spin_delay.value(),
                    "show_countdown": 1 if self.chk_show_countdown.isChecked() else 0,
                    "save_before_action": 1 if self.chk_save_before.isChecked() else 0,
                    "cleanup_hardware": 1 if self.chk_cleanup_hw.isChecked() else 0,
                }
                self.main_core.worker_thread.system_action_triggered.emit("RESTART", cfg)

    @staticmethod
    def _group_box_qss(color="#2563EB"):
        return f"""
            QGroupBox {{
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-left: 4px solid {color};
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #0F172A;
            }}
        """

    @staticmethod
    def _input_qss():
        return """
            QLineEdit, QSpinBox, QComboBox {
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 6px 10px;
                color: #0F172A;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid #2563EB;
                background-color: #FFFFFF;
            }
        """

    @staticmethod
    def _btn_outline_qss(color):
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {color};
                border: 1px solid {color};
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: #FFFFFF;
            }}
        """


# =============================================================================
# GIAO DIỆN CHÍNH 2: QUẢN LÝ CLOSE APPLICATION TỪ PLC (MANAGE CLOSE DIALOG)
# =============================================================================
class ManageCloseDialog(QDialog):
    """Giao diện cấu hình & quản lý tín hiệu Close Application từ PLC."""

    def __init__(self, connection=None, main_core_ref=None, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.main_core = main_core_ref
        self.setWindowTitle("🛑 Cấu hình Tín hiệu PLC: Đóng ứng dụng (Close Application)")
        self.setMinimumSize(1000, 750)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet("QDialog { background-color: #F8FAFC; }")

        self._build_ui()
        self._load_config()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollBar:vertical { width: 8px; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(16)

        # ── 1. Header Banner ──
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #991B1B, stop:1 #DC2626);
                border-radius: 8px;
            }
        """)
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(20, 16, 20, 16)

        v_title = QVBoxLayout()
        title_lbl = QLabel("🛑 PLC CLOSE APPLICATION MANAGER")
        title_lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_lbl.setStyleSheet("color: #FFFFFF;")
        sub_lbl = QLabel("Cấu hình giám sát thanh ghi PLC để tắt an toàn toàn bộ hệ thống Vision, giải phóng camera và tùy chọn tắt máy tính.")
        sub_lbl.setFont(QFont("Segoe UI", 9))
        sub_lbl.setStyleSheet("color: #FECACA;")
        v_title.addWidget(title_lbl)
        v_title.addWidget(sub_lbl)
        b_layout.addLayout(v_title)

        self.lbl_plc_status = QLabel(self._get_plc_status_text())
        self.lbl_plc_status.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.lbl_plc_status.setStyleSheet("background-color: rgba(255,255,255,0.18); color: #FFFFFF; border-radius: 12px; padding: 6px 14px;")
        b_layout.addWidget(self.lbl_plc_status, alignment=Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(banner)

        # ── 2. Card: Cấu hình Thanh ghi PLC ──
        grp_reg = QGroupBox("📡 1. Cấu hình Thanh ghi & Tín hiệu PLC (Register & Signal)")
        grp_reg.setFont(QFont("Segoe UI", 11, QFont.Bold))
        grp_reg.setStyleSheet(self._group_box_qss("#DC2626"))
        grid_reg = QGridLayout(grp_reg)
        grid_reg.setContentsMargins(16, 16, 16, 16)
        grid_reg.setSpacing(12)

        self.chk_enabled = QCheckBox("Bật tính năng lắng nghe tín hiệu Đóng ứng dụng từ PLC")
        self.chk_enabled.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.chk_enabled.setStyleSheet("color: #991B1B;")
        grid_reg.addWidget(self.chk_enabled, 0, 0, 1, 2)

        lbl_reg = QLabel("Địa chỉ thanh ghi (Register):")
        lbl_reg.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.txt_register = QLineEdit()
        self.txt_register.setPlaceholderText("Ví dụ: DM102, MR102, D502, R1002...")
        self.txt_register.setFont(QFont("Consolas", 10, QFont.Bold))
        self.txt_register.setStyleSheet(self._input_qss())
        grid_reg.addWidget(lbl_reg, 1, 0)
        grid_reg.addWidget(self.txt_register, 1, 1)

        h_quick = QHBoxLayout()
        h_quick.addWidget(QLabel("Mẫu nhanh:"))
        for prefix in ["DM", "MR", "D", "W", "B", "R"]:
            btn_pf = QPushButton(prefix)
            btn_pf.setFixedHeight(24)
            btn_pf.setFixedWidth(40)
            btn_pf.setFont(QFont("Segoe UI", 8, QFont.Bold))
            btn_pf.setStyleSheet("background-color: #E2E8F0; color: #334155; border-radius: 3px;")
            btn_pf.clicked.connect(lambda _, p=prefix: self._insert_prefix(p))
            h_quick.addWidget(btn_pf)
        h_quick.addStretch()
        grid_reg.addLayout(h_quick, 2, 1)

        lbl_on = QLabel("Giá trị kích hoạt (Value Bit ON):")
        lbl_on.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.spin_val_on = QSpinBox()
        self.spin_val_on.setRange(-32768, 65535)
        self.spin_val_on.setValue(1)
        self.spin_val_on.setStyleSheet(self._input_qss())
        grid_reg.addWidget(lbl_on, 3, 0)
        grid_reg.addWidget(self.spin_val_on, 3, 1)

        lbl_off = QLabel("Giá trị trả về (Value Bit OFF):")
        lbl_off.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.cbo_val_off = QComboBox()
        self.cbo_val_off.setEditable(True)
        self.cbo_val_off.addItems(["0", "1", "No Value"])
        self.cbo_val_off.setStyleSheet(self._input_qss())
        grid_reg.addWidget(lbl_off, 4, 0)
        grid_reg.addWidget(self.cbo_val_off, 4, 1)

        self.chk_auto_write_off = QCheckBox("Tự động ghi trả giá trị OFF về PLC xác nhận trước khi tắt")
        self.chk_auto_write_off.setChecked(True)
        self.chk_auto_write_off.setFont(QFont("Segoe UI", 9))
        grid_reg.addWidget(self.chk_auto_write_off, 5, 0, 1, 2)

        layout.addWidget(grp_reg)

        # ── 3. Card: Tùy chọn Nâng cao cho Close ──
        grp_adv = QGroupBox("⚙️ 2. Hành vi tắt & Dọn dẹp tài nguyên (Shutdown Behavior)")
        grp_adv.setFont(QFont("Segoe UI", 11, QFont.Bold))
        grp_adv.setStyleSheet(self._group_box_qss("#DC2626"))
        grid_adv = QGridLayout(grp_adv)
        grid_adv.setContentsMargins(16, 16, 16, 16)
        grid_adv.setSpacing(12)

        # Delay
        grid_adv.addWidget(QLabel("Thời gian trễ đếm ngược trước khi đóng:"), 0, 0)
        self.spin_delay = QSpinBox()
        self.spin_delay.setRange(0, 60)
        self.spin_delay.setValue(3)
        self.spin_delay.setSuffix(" giây")
        self.spin_delay.setStyleSheet(self._input_qss())
        grid_adv.addWidget(self.spin_delay, 0, 1)

        self.chk_show_countdown = QCheckBox("Hiển thị hộp thoại đếm ngược lớn (cho phép người vận hành ấn HỦY nếu ấn nhầm)")
        self.chk_show_countdown.setChecked(True)
        self.chk_show_countdown.setFont(QFont("Segoe UI", 9))
        grid_adv.addWidget(self.chk_show_countdown, 1, 0, 1, 2)

        # Post action mode
        grid_adv.addWidget(QLabel("Hành vi sau khi đóng ứng dụng:"), 2, 0)
        self.cbo_post_action = QComboBox()
        self.cbo_post_action.addItems([
            "Chỉ đóng phần mềm Vision (Close Application Only)",
            "Đóng phần mềm và Tắt máy tính (Shutdown Windows PC)",
            "Đóng phần mềm và Khởi động lại máy tính (Reboot Windows PC)"
        ])
        self.cbo_post_action.setStyleSheet(self._input_qss())
        grid_adv.addWidget(self.cbo_post_action, 2, 1)

        # Cleanup
        self.chk_cleanup_hw = QCheckBox("Tắt đèn chiếu sáng / Trigger và ngắt kết nối an toàn toàn bộ Camera")
        self.chk_cleanup_hw.setChecked(True)
        self.chk_cleanup_hw.setFont(QFont("Segoe UI", 9))
        grid_adv.addWidget(self.chk_cleanup_hw, 3, 0, 1, 2)

        self.chk_kill_zombie = QCheckBox("Diệt sạch toàn bộ tiến trình con Python chạy ngầm (Force Kill Workers)")
        self.chk_kill_zombie.setChecked(True)
        self.chk_kill_zombie.setFont(QFont("Segoe UI", 9))
        grid_adv.addWidget(self.chk_kill_zombie, 4, 0, 1, 2)

        grid_adv.addWidget(QLabel("Ghi chú / Mục đích sử dụng:"), 5, 0)
        self.txt_desc = QLineEdit()
        self.txt_desc.setPlaceholderText("Ví dụ: Tắt máy cuối ca sản xuất chiều...")
        self.txt_desc.setStyleSheet(self._input_qss())
        grid_adv.addWidget(self.txt_desc, 5, 1)

        layout.addWidget(grp_adv)

        # ── 4. Card: Live Test ──
        grp_test = QGroupBox("🧪 3. Kiểm tra kết nối & Thử nghiệm trực tiếp (Live Test)")
        grp_test.setFont(QFont("Segoe UI", 11, QFont.Bold))
        grp_test.setStyleSheet(self._group_box_qss("#DC2626"))
        h_test = QHBoxLayout(grp_test)
        h_test.setContentsMargins(16, 16, 16, 16)
        h_test.setSpacing(10)

        self.btn_read_now = QPushButton("🔍 Đọc thử giá trị PLC")
        self.btn_read_now.setStyleSheet(self._btn_outline_qss("#DC2626"))
        self.btn_read_now.clicked.connect(self._test_read_plc)
        h_test.addWidget(self.btn_read_now)

        self.lbl_read_val = QLabel("Chưa đọc")
        self.lbl_read_val.setFont(QFont("Consolas", 10, QFont.Bold))
        self.lbl_read_val.setStyleSheet("background-color: #E2E8F0; color: #475569; padding: 4px 10px; border-radius: 4px;")
        h_test.addWidget(self.lbl_read_val)

        self.btn_write_on = QPushButton("✍️ Ghi thử giá trị ON")
        self.btn_write_on.setStyleSheet(self._btn_outline_qss("#059669"))
        self.btn_write_on.clicked.connect(self._test_write_on)
        h_test.addWidget(self.btn_write_on)

        self.btn_test_close = QPushButton("⚡ Thử Đóng ngay")
        self.btn_test_close.setStyleSheet(self._btn_outline_qss("#991B1B"))
        self.btn_test_close.clicked.connect(self._test_trigger_close)
        h_test.addWidget(self.btn_test_close)

        h_test.addStretch()
        layout.addWidget(grp_test)

        layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # ── 5. Footer Buttons ──
        footer = QHBoxLayout()
        footer.setSpacing(12)

        btn_default = QPushButton("🔄 Khôi phục mặc định")
        btn_default.setStyleSheet(self._btn_outline_qss("#64748B"))
        btn_default.clicked.connect(self._on_defaults)
        footer.addWidget(btn_default)

        footer.addStretch()

        btn_close = QPushButton("Đóng")
        btn_close.setStyleSheet(self._btn_outline_qss("#64748B"))
        btn_close.clicked.connect(self.reject)
        footer.addWidget(btn_close)

        btn_save = QPushButton("💾 Lưu cấu hình (Save)")
        btn_save.setFont(QFont("Segoe UI", 10, QFont.Bold))
        btn_save.setFixedHeight(36)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                color: #FFFFFF;
                border-radius: 6px;
                padding: 6px 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #B91C1C;
            }
        """)
        btn_save.clicked.connect(self._on_save)
        footer.addWidget(btn_save)

        main_layout.addLayout(footer)

    def _get_plc_status_text(self):
        if self.main_core and getattr(self.main_core, 'mode_init_plc', 0):
            plc_name = getattr(self.main_core, 'plc_module', 'PLC')
            ip = getattr(self.main_core, 'ip_address_plc', '127.0.0.1')
            return f"🟢 Đã kết nối {plc_name} ({ip})"
        return "🟡 Chưa kết nối PLC vật lý"

    def _insert_prefix(self, p):
        cur = self.txt_register.text().strip()
        digits = ''.join(filter(str.isdigit, cur))
        self.txt_register.setText(f"{p}{digits if digits else '102'}")

    def _load_config(self):
        cfg = get_system_action_config("CLOSE", self.connection)
        self.chk_enabled.setChecked(bool(cfg.get("enabled", 0)))
        self.txt_register.setText(str(cfg.get("register", "DM102")))
        self.spin_val_on.setValue(int(cfg.get("value_bit_on", 1)))
        self.cbo_val_off.setCurrentText(str(cfg.get("value_bit_off", "0")))
        self.chk_auto_write_off.setChecked(bool(cfg.get("auto_write_off", 1)))
        self.spin_delay.setValue(int(cfg.get("delay_seconds", 3)))
        self.chk_show_countdown.setChecked(bool(cfg.get("show_countdown", 1)))
        self.chk_cleanup_hw.setChecked(bool(cfg.get("cleanup_hardware", 1)))
        self.chk_kill_zombie.setChecked(bool(cfg.get("save_before_action", 1)))
        self.txt_desc.setText(str(cfg.get("description", "")))

        post_mode = str(cfg.get("post_action_mode", "App Only"))
        if "Shutdown" in post_mode:
            self.cbo_post_action.setCurrentIndex(1)
        elif "Reboot" in post_mode:
            self.cbo_post_action.setCurrentIndex(2)
        else:
            self.cbo_post_action.setCurrentIndex(0)

    def _on_defaults(self):
        reply = QMessageBox.question(
            self, "Xác nhận", "Bạn có chắc chắn muốn đặt lại các thông số mặc định?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            cfg = DEFAULT_CLOSE_CONFIG
            self.chk_enabled.setChecked(bool(cfg["enabled"]))
            self.txt_register.setText(cfg["register"])
            self.spin_val_on.setValue(cfg["value_bit_on"])
            self.cbo_val_off.setCurrentText(cfg["value_bit_off"])
            self.chk_auto_write_off.setChecked(bool(cfg["auto_write_off"]))
            self.spin_delay.setValue(cfg["delay_seconds"])
            self.chk_show_countdown.setChecked(bool(cfg["show_countdown"]))
            self.cbo_post_action.setCurrentIndex(0)
            self.chk_cleanup_hw.setChecked(bool(cfg["cleanup_hardware"]))
            self.chk_kill_zombie.setChecked(True)
            self.txt_desc.setText(cfg["description"])

    def _on_save(self):
        reg = self.txt_register.text().strip()
        if self.chk_enabled.isChecked() and not reg:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập địa chỉ thanh ghi PLC!")
            self.txt_register.setFocus()
            return

        post_idx = self.cbo_post_action.currentIndex()
        post_mode = "App Only" if post_idx == 0 else ("Shutdown PC" if post_idx == 1 else "Reboot PC")

        cfg = {
            "action_type": "CLOSE",
            "enabled": 1 if self.chk_enabled.isChecked() else 0,
            "register": reg,
            "data_type": "Bit",
            "value_bit_on": self.spin_val_on.value(),
            "value_bit_off": self.cbo_val_off.currentText().strip(),
            "auto_write_off": 1 if self.chk_auto_write_off.isChecked() else 0,
            "delay_seconds": self.spin_delay.value(),
            "show_countdown": 1 if self.chk_show_countdown.isChecked() else 0,
            "save_before_action": 1 if self.chk_kill_zombie.isChecked() else 0,
            "cleanup_hardware": 1 if self.chk_cleanup_hw.isChecked() else 0,
            "post_action_mode": post_mode,
            "description": self.txt_desc.text().strip()
        }

        ok = save_system_action_config("CLOSE", cfg, self.connection)
        if self.main_core and hasattr(self.main_core, 'reload_system_action_configs'):
            self.main_core.reload_system_action_configs()

        if ok:
            QMessageBox.information(self, "Thành công", "Đã lưu cấu hình tín hiệu Close thành công!")
            self.accept()
        else:
            QMessageBox.warning(self, "Lỗi", "Không thể lưu cấu hình! Vui lòng kiểm tra lại log hệ thống.")

    def _test_read_plc(self):
        reg = self.txt_register.text().strip()
        if not reg:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập địa chỉ thanh ghi cần đọc!")
            return
        if not self.main_core or not getattr(self.main_core, 'driver_loader', None):
            QMessageBox.warning(self, "PLC Offline", "Hiện chưa có kết nối vật lý đến PLC!")
            return
        try:
            val = self.main_core.driver_loader.read_plc(reg)
            if val is not None:
                self.lbl_read_val.setText(f"Giá trị: {val}")
                self.lbl_read_val.setStyleSheet("background-color: #DCFCE7; color: #166534; font-weight: bold; padding: 4px 10px; border-radius: 4px;")
            else:
                self.lbl_read_val.setText("Không có phản hồi")
                self.lbl_read_val.setStyleSheet("background-color: #FEE2E2; color: #991B1B; padding: 4px 10px; border-radius: 4px;")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi đọc PLC", f"Không thể đọc thanh ghi {reg}:\n{e}")

    def _test_write_on(self):
        reg = self.txt_register.text().strip()
        if not reg:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập địa chỉ thanh ghi!")
            return
        if not self.main_core or not getattr(self.main_core, 'driver_loader', None):
            QMessageBox.warning(self, "PLC Offline", "Hiện chưa có kết nối vật lý đến PLC!")
            return
        try:
            val = self.spin_val_on.value()
            self.main_core.driver_loader.write_plc(reg, val)
            QMessageBox.information(self, "Thành công", f"Đã ghi thành công giá trị {val} vào thanh ghi {reg}!")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi ghi PLC", f"Không thể ghi vào thanh ghi {reg}:\n{e}")

    def _test_trigger_close(self):
        reply = QMessageBox.question(
            self, "Thử nghiệm Đóng ứng dụng",
            "Bạn có chắc muốn kích hoạt thử nghiệm quy trình Đóng toàn bộ ứng dụng ngay bây giờ?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.accept()
            if self.main_core and hasattr(self.main_core, 'worker_thread'):
                post_idx = self.cbo_post_action.currentIndex()
                post_mode = "App Only" if post_idx == 0 else ("Shutdown PC" if post_idx == 1 else "Reboot PC")
                cfg = {
                    "action_type": "CLOSE",
                    "delay_seconds": self.spin_delay.value(),
                    "show_countdown": 1 if self.chk_show_countdown.isChecked() else 0,
                    "cleanup_hardware": 1 if self.chk_cleanup_hw.isChecked() else 0,
                    "post_action_mode": post_mode
                }
                self.main_core.worker_thread.system_action_triggered.emit("CLOSE", cfg)

    @staticmethod
    def _group_box_qss(color="#DC2626"):
        return f"""
            QGroupBox {{
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-left: 4px solid {color};
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #0F172A;
            }}
        """

    @staticmethod
    def _input_qss():
        return """
            QLineEdit, QSpinBox, QComboBox {
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 6px 10px;
                color: #0F172A;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid #DC2626;
                background-color: #FFFFFF;
            }
        """

    @staticmethod
    def _btn_outline_qss(color):
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {color};
                border: 1px solid {color};
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: #FFFFFF;
            }}
        """


# =============================================================================
# CÁC HÀM TIỆN ÍCH MỞ DIALOG TỪ MENU
# =============================================================================
def open_manage_restart_dialog(cursor, connection, main_core_ref=None, parent=None):
    """Mở dialog Manage Restart từ Menu."""
    dlg = ManageRestartDialog(connection, main_core_ref, parent)
    return dlg.exec_()


def open_manage_close_dialog(cursor, connection, main_core_ref=None, parent=None):
    """Mở dialog Manage Close từ Menu."""
    dlg = ManageCloseDialog(connection, main_core_ref, parent)
    return dlg.exec_()

