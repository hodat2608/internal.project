# -*- coding: utf-8 -*-
"""
module_2/plc_alert_ui.py
========================
Giao diện UI cảnh báo mất kết nối PLC và thông báo khôi phục kết nối thành công:
1. PLCAlertOverlay:
   - Giao diện cảnh báo mất kết nối nổi bật, rõ ràng, đẹp và chuyên nghiệp.
   - Nền tối hiện đại (Dark Slate #0F172A), viền đỏ cảnh báo (#EF4444) với hiệu ứng phát sáng (Glow Drop Shadow).
   - Hiển thị đầy đủ thông tin: Thiết bị PLC, IP, Port, nguyên nhân có thể xảy ra.
   - Trạng thái tự động kết nối lại (Auto-reconnecting status with pulsing progress bar & attempt counter).
   - Draggable: người dùng có thể nhấp chuột kéo thả di chuyển vị trí nếu cần quan sát bên dưới.
   - Non-blocking: Không khóa giao diện hay các luồng xử lý khác.
2. PLCSuccessBanner:
   - Giao diện thông báo kết nối lại thành công màu xanh lục ngọc (#10B981).
   - Tự động hiển thị và đóng sau 5 giây (với bộ đếm lùi thời gian).
3. PLCWatchdogSignals:
   - Các Qt Signals đảm bảo giao tiếp an toàn đa luồng giữa Watchdog Thread và giao diện chính.
"""

import socket
import select
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QProgressBar, QGraphicsDropShadowEffect, QFrame, QApplication
)
from app_logger.app_logger import get_logger as _get_logger

_log = _get_logger('module_2.plc_alert_ui')


# ---------------------------------------------------------------------------
# Qt Signals cho PLC Watchdog (Thread-safe)
# ---------------------------------------------------------------------------
class PLCWatchdogSignals(QObject):
    connection_lost = pyqtSignal(str, str, int, int)       # module, ip, port, attempts
    reconnect_attempt = pyqtSignal(int)                    # attempts
    connection_restored = pyqtSignal(str, str, int)        # module, ip, port


# ---------------------------------------------------------------------------
# Giao diện Cảnh báo Mất kết nối PLC (Warning UI)
# ---------------------------------------------------------------------------
class PLCAlertOverlay(QDialog):
    retry_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(720, 520)
        self.resize(740, 540)
        self._drag_pos = None
        self.user_dismissed = False

        self._setup_ui()

    def _setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(15, 15, 15, 15)

        # Card chứa nội dung chính
        self.card = QFrame(self)
        self.card.setObjectName("alertCard")
        self.card.setStyleSheet("""
            QFrame#alertCard {
                background-color: #A7A7A7;
                border: 2.5px solid #EF4444;
                border-radius: 14px;
            }
        """)

        # Hiệu ứng đổ bóng đỏ phát sáng
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(35)
        shadow.setColor(QtGui.QColor(239, 68, 68, 140))
        shadow.setOffset(0, 0)
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(14)

        # 1. Header: Icon cảnh báo nhấp nháy + Tiêu đề
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        self.icon_badge = QLabel("⚠️", self.card)
        self.icon_badge.setStyleSheet("""
            QLabel {
                font-size: 32px;
                background-color: #371B1B;
                border: 1.5px solid #7F1D1D;
                border-radius: 26px;
                padding: 6px;
                min-width: 52px;
                max-width: 52px;
                min-height: 52px;
                max-height: 52px;
                qproperty-alignment: AlignCenter;
            }
        """)
        header_layout.addWidget(self.icon_badge)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(3)

        self.label_title = QLabel("CẢNH BÁO: MẤT KẾT NỐI TỚI PLC", self.card)
        self.label_title.setStyleSheet("""
            color: #FF0000;
            font-size: 17px;
            font-weight: 800;
            font-family: 'Segoe UI', Arial, sans-serif;
            letter-spacing: 0.5px;
        """)
        title_layout.addWidget(self.label_title)

        self.label_subtitle = QLabel("PLC COMMUNICATION LINK INTERRUPTED", self.card)
        self.label_subtitle.setStyleSheet("""
            color: #FFD70B;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 1px;
        """)
        title_layout.addWidget(self.label_subtitle)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        # Nút đóng nhanh (✕) ở góc phải tiêu đề
        self.btn_close = QPushButton("✕", self.card)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setFixedSize(32, 32)
        self.btn_close.setToolTip("Đóng cảnh báo để kiểm tra cài đặt (Hệ thống vẫn tự động kết nối lại ngầm)")
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: #94A3B8;
                border: 1px solid #334155;
                border-radius: 16px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #EF4444;
                color: #FFFFFF;
                border: 1px solid #DC2626;
            }
            QPushButton:pressed {
                background-color: #B91C1C;
            }
        """)
        self.btn_close.clicked.connect(self.dismiss)
        header_layout.addWidget(self.btn_close)

        card_layout.addLayout(header_layout)

        # 2. Hộp thông tin chi tiết (Details Box)
        self.info_box = QFrame(self.card)
        self.info_box.setStyleSheet("""
            QFrame {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 4px;
            }
            QLabel {
                font-family: 'Segoe UI', Arial;
            }
        """)
        info_layout = QtWidgets.QGridLayout(self.info_box)
        info_layout.setContentsMargins(14, 10, 14, 10)
        info_layout.setHorizontalSpacing(16)
        info_layout.setVerticalSpacing(6)

        lbl_dev_k = QLabel("Thiết bị PLC:", self.info_box)
        lbl_dev_k.setStyleSheet("color: #94A3B8; font-weight: 600; font-size: 12px;")
        self.lbl_dev_v = QLabel("KEYENCE (Socket Client)", self.info_box)
        self.lbl_dev_v.setStyleSheet("color: #F1F5F9; font-weight: bold; font-size: 12px;")

        lbl_addr_k = QLabel("Địa chỉ & Cổng:", self.info_box)
        lbl_addr_k.setStyleSheet("color: #94A3B8; font-weight: 600; font-size: 12px;")
        self.lbl_addr_v = QLabel("192.168.0.10 : 5000", self.info_box)
        self.lbl_addr_v.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 12px;")

        lbl_cause_k = QLabel("Nguyên nhân:", self.info_box)
        lbl_cause_k.setStyleSheet("color: #94A3B8; font-weight: 600; font-size: 12px;")
        self.lbl_cause_v = QLabel("Lỏng cáp mạng Ethernet, switch mất nguồn hoặc PLC tắt.", self.info_box)
        self.lbl_cause_v.setStyleSheet("color: #FBBF24; font-weight: 500; font-size: 12px;")

        info_layout.addWidget(lbl_dev_k, 0, 0)
        info_layout.addWidget(self.lbl_dev_v, 0, 1)
        info_layout.addWidget(lbl_addr_k, 1, 0)
        info_layout.addWidget(self.lbl_addr_v, 1, 1)
        info_layout.addWidget(lbl_cause_k, 2, 0)
        info_layout.addWidget(self.lbl_cause_v, 2, 1)

        card_layout.addWidget(self.info_box)

        # 3. Trạng thái tự động kết nối lại + Thanh tiến trình nhấp nháy
        reconnect_box = QVBoxLayout()
        reconnect_box.setSpacing(6)

        status_row = QHBoxLayout()
        self.lbl_status = QLabel("🔄 Đang tự động kiểm tra và kết nối lại... (Lần thử: 1)", self.card)
        self.lbl_status.setStyleSheet("""
            color: #FFD600;
            font-size: 12px;
            font-weight: bold;
            font-family: 'Segoe UI', Arial;
        """)
        status_row.addWidget(self.lbl_status)
        status_row.addStretch()
        reconnect_box.addLayout(status_row)

        self.progress_bar = QProgressBar(self.card)
        self.progress_bar.setRange(0, 0)  # Indeterminate animation
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #EF4444, stop:0.5 #F59E0B, stop:1 #EF4444);
                border-radius: 3px;
            }
        """)
        reconnect_box.addWidget(self.progress_bar)
        card_layout.addLayout(reconnect_box)

        # 4. Ghi chú hướng dẫn cho người vận hành
        lbl_hint = QLabel(
            "💡 Giao diện chính và thông số được giữ nguyên. Hệ thống sẽ tự động khôi phục ngay khi cắm lại dây hoặc khởi động lại PLC.",
            self.card
        )
        lbl_hint.setWordWrap(True)
        lbl_hint.setStyleSheet("""
            color: #3F3F3F;
            font-size: 11px;
            font-style: italic;
            font-family: 'Segoe UI', Arial;
        """)
        card_layout.addWidget(lbl_hint)

        # 5. Thanh nút thao tác bên dưới (Thử kết nối lại & Đóng cảnh báo)
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 4, 0, 0)
        bottom_bar.addStretch()

        self.btn_retry = QPushButton("🔄  Thử kết nối lại ngay (Retry Now)", self.card)
        self.btn_retry.setCursor(Qt.PointingHandCursor)
        self.btn_retry.setFixedHeight(38)
        self.btn_retry.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                border: 1.5px solid #3B82F6;
                border-radius: 8px;
                padding: 6px 20px;
                font-size: 13px;
                font-weight: 700;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
                border: 1.5px solid #60A5FA;
            }
            QPushButton:pressed {
                background-color: #1E40AF;
            }
        """)
        self.btn_retry.clicked.connect(self.retry_requested.emit)
        bottom_bar.addWidget(self.btn_retry)
        bottom_bar.addSpacing(12)

        self.btn_dismiss = QPushButton("✕  Đóng cảnh báo (Tiếp tục kiểm tra cài đặt)", self.card)
        self.btn_dismiss.setCursor(Qt.PointingHandCursor)
        self.btn_dismiss.setFixedHeight(38)
        self.btn_dismiss.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: #E2E8F0;
                border: 1.5px solid #475569;
                border-radius: 8px;
                padding: 6px 22px;
                font-size: 13px;
                font-weight: 700;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #FFFFFF;
                border: 1.5px solid #94A3B8;
            }
            QPushButton:pressed {
                background-color: #0F172A;
            }
        """)
        self.btn_dismiss.clicked.connect(self.dismiss)
        bottom_bar.addWidget(self.btn_dismiss)
        bottom_bar.addStretch()
        card_layout.addLayout(bottom_bar)

        outer_layout.addWidget(self.card)

    def dismiss(self):
        """Người dùng chủ động đóng cảnh báo để kiểm tra cài đặt. Watchdog PLC vẫn tiếp tục chạy ngầm."""
        self.user_dismissed = True
        self.hide()

    def set_plc_info(self, plc_module: str, ip: str, port: int, attempts: int = 1):
        """Cập nhật thông tin PLC và số lần thử kết nối lại."""
        self.lbl_dev_v.setText(f"{plc_module} (Socket Client)")
        self.lbl_addr_v.setText(f"{ip} : {port}")
        self.update_attempts(attempts)

    def update_attempts(self, attempts: int):
        """Cập nhật số lần thử kết nối lại."""
        self.lbl_status.setText(f"🔄 Đang tự động kiểm tra và kết nối lại liên tục... (Lần thử: {attempts})")
        if not self.isVisible() and not getattr(self, 'user_dismissed', False):
            self.show_alert()
        elif self.isVisible():
            self.raise_()
            self.activateWindow()

    def show_alert(self):
        """Hiển thị cảnh báo ở vị trí trung tâm cửa sổ đang hoạt động."""
        self.user_dismissed = False
        self._center_on_screen_or_window()
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_alert(self):
        """Ẩn cảnh báo khi đã kết nối lại thành công."""
        self.user_dismissed = False
        self.hide()

    def _center_on_screen_or_window(self):
        active_win = QApplication.activeWindow()
        if active_win and active_win != self and active_win.isVisible():
            geo = active_win.geometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(max(10, x), max(10, y))
        else:
            screen = QApplication.primaryScreen().geometry()
            x = (screen.width() - self.width()) // 2
            y = (screen.height() - self.height()) // 2
            self.move(max(10, x), max(10, y))

    # Hỗ trợ kéo thả di chuyển vị trí dialog
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()


# ---------------------------------------------------------------------------
# Giao diện Thông báo Khôi phục Kết nối Thành công (Success UI - Tự tắt sau 5s)
# ---------------------------------------------------------------------------
class PLCSuccessBanner(QDialog):
    """
    Thông báo kết nối lại thành công màu xanh lục ngọc (#10B981),
    tự động hiển thị và đóng sau 5 giây.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(700, 500)
        self.resize(720, 520)
        self._drag_pos = None

        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._on_tick)
        self._remaining_seconds = 5

        self._setup_ui()

    def _setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(15, 15, 15, 15)

        self.card = QFrame(self)
        self.card.setObjectName("successCard")
        self.card.setStyleSheet("""
            QFrame#successCard {
                background-color: #064E3B;
                border: 2.5px solid #10B981;
                border-radius: 14px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(35)
        shadow.setColor(QtGui.QColor(16, 185, 129, 150))
        shadow.setOffset(0, 0)
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(22, 18, 22, 18)
        card_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        icon_badge = QLabel("✅", self.card)
        icon_badge.setStyleSheet("""
            QLabel {
                font-size: 28px;
                background-color: #065F46;
                border: 1.5px solid #047857;
                border-radius: 24px;
                padding: 4px;
                min-width: 48px;
                max-width: 48px;
                min-height: 48px;
                max-height: 48px;
                qproperty-alignment: AlignCenter;
            }
        """)
        header_layout.addWidget(icon_badge)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(3)

        label_title = QLabel("KHÔI PHỤC KẾT NỐI PLC THÀNH CÔNG", self.card)
        label_title.setStyleSheet("""
            color: #34D399;
            font-size: 16px;
            font-weight: 800;
            font-family: 'Segoe UI', Arial, sans-serif;
            letter-spacing: 0.5px;
        """)
        title_layout.addWidget(label_title)

        label_subtitle = QLabel("PLC COMMUNICATION LINK RESTORED & READY", self.card)
        label_subtitle.setStyleSheet("""
            color: #A7F3D0;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.8px;
        """)
        title_layout.addWidget(label_subtitle)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        card_layout.addLayout(header_layout)

        self.lbl_msg = QLabel(
            "Đã kết nối lại thành công với PLC. Các tín hiệu _safe_read_plc và _safe_write_plc đã sẵn sàng!",
            self.card
        )
        self.lbl_msg.setWordWrap(True)
        self.lbl_msg.setStyleSheet("""
            color: #ECFDF5;
            font-size: 12px;
            font-weight: 500;
            font-family: 'Segoe UI', Arial;
        """)
        card_layout.addWidget(self.lbl_msg)

        # Footer countdown
        footer_layout = QHBoxLayout()
        self.lbl_countdown = QLabel("⏱️ Tự động đóng thông báo sau 5 giây...", self.card)
        self.lbl_countdown.setStyleSheet("""
            color: #6EE7B7;
            font-size: 11px;
            font-style: italic;
            font-family: 'Segoe UI', Arial;
        """)
        footer_layout.addWidget(self.lbl_countdown)
        footer_layout.addStretch()
        card_layout.addLayout(footer_layout)

        outer_layout.addWidget(self.card)

    def show_success(self, plc_module: str, ip: str, port: int, duration_ms: int = 5000):
        """Hiển thị thông báo thành công và bắt đầu đếm lùi 5 giây để đóng."""
        self.lbl_msg.setText(
            f"Đã kết nối lại thành công tới thiết bị PLC {plc_module} ({ip}:{port}).\n"
            f"Các kênh đọc/ghi _safe_read_plc & _safe_write_plc đã được khôi phục hoàn toàn!"
        )
        self._remaining_seconds = int(duration_ms / 1000)
        self.lbl_countdown.setText(f"⏱️ Tự động đóng thông báo sau {self._remaining_seconds} giây...")

        self._center_on_screen_or_window()
        self.show()
        self.raise_()
        self.activateWindow()

        self._countdown_timer.start()

    def _on_tick(self):
        self._remaining_seconds -= 1
        if self._remaining_seconds > 0:
            self.lbl_countdown.setText(f"⏱️ Tự động đóng thông báo sau {self._remaining_seconds} giây...")
        else:
            self._countdown_timer.stop()
            self.close()

    def _center_on_screen_or_window(self):
        active_win = QApplication.activeWindow()
        if active_win and active_win != self and active_win.isVisible():
            geo = active_win.geometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(max(10, x), max(10, y))
        else:
            screen = QApplication.primaryScreen().geometry()
            x = (screen.width() - self.width()) // 2
            y = (screen.height() - self.height()) // 2
            self.move(max(10, x), max(10, y))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

