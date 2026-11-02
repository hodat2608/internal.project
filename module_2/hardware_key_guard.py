# -*- coding: utf-8 -*-
"""
AI Vision Pro - Runtime USB Hardware Key Guard
===============================================
Module bảo vệ và giám sát định kỳ USB Hardware Key trong suốt quá trình vận hành ứng dụng.
- Tần số quét định kỳ ngẫu nhiên từ 3 - 5 phút (180s - 300s).
- Quét chạy trong luồng nền (Worker Thread) không gây lag hoặc giật khung hình camera.
- Khi USB Key bị rút giữa chừng:
    1. Kích hoạt hộp thoại cảnh báo Modal khẩn cấp.
    2. Đếm ngược (120 giây) trước khi tự động đóng ứng dụng an toàn.
    3. Cho phép người dùng cắm lại USB Key và bấm "Thử lại" để khôi phục vận hành mà không phải khởi động lại phần mềm.
"""

import random
import os
import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame

from app_logger.app_logger import get_logger as _get_logger

_log = _get_logger('module_2.hardware_key_guard')


class HardwareKeyCheckWorker(QThread):
    """Luồng phụ thực hiện quét thiết bị USB nhằm tránh làm đứng giao diện chính."""
    check_finished = pyqtSignal(bool)

    def __init__(self, main_core, parent=None):
        super().__init__(parent)
        self.main_core = main_core

    def run(self):
        try:
            # Kiểm tra âm thầm không pop-up dialog
            is_valid = self.main_core.query_hardware_key(show_dialog=False)
        except Exception as e:
            _log.error("Lỗi khi quét USB Key trong luồng phụ: %s", e)
            is_valid = False
        self.check_finished.emit(bool(is_valid))


class HardwareKeyAlertModal(QDialog):
    """
    Hộp thoại cảnh báo Modal nổi bật khi USB Hardware Key bị rút giữa chừng.
    Bao gồm bộ đếm ngược tự động thoát và nút kiểm tra lại khóa.
    """

    def __init__(self, main_core, parent=None, countdown_seconds=120):
        super().__init__(parent)
        self.main_core = main_core
        self.remaining_seconds = countdown_seconds
        self.is_checking = False

        self.setWindowTitle("CẢNH BÁO: MẤT KHÓA BẢN QUYỀN (LICENSE KEY DISCONNECTED)")
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setWindowModality(Qt.ApplicationModal)
        self.setMinimumWidth(560)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                border: 2px solid #e74c3c;
                border-radius: 8px;
            }
            QLabel {
                color: #cdd6f4;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
            }
            QPushButton#btnRetry {
                background-color: #27ae60;
                color: #ffffff;
                border: none;
            }
            QPushButton#btnRetry:hover {
                background-color: #2ecc71;
            }
            QPushButton#btnRetry:disabled {
                background-color: #7f8c8d;
                color: #bdc3c7;
            }
            QPushButton#btnExit {
                background-color: #c0392b;
                color: #ffffff;
                border: none;
            }
            QPushButton#btnExit:hover {
                background-color: #e74c3c;
            }
        """)

        self._build_ui()

        # Bộ đếm ngược 1 giây
        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(1000)
        self.countdown_timer.timeout.connect(self._on_tick)
        self.countdown_timer.start()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header cảnh báo
        header_layout = QHBoxLayout()
        icon_label = QLabel("⚠️")
        icon_label.setStyleSheet("font-size: 38px; color: #f39c12;")
        header_layout.addWidget(icon_label)

        title_label = QLabel("KHÓA BẢN QUYỀN USB ĐÃ BỊ RÚT RA!")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #e74c3c;")
        header_layout.addWidget(title_label, stretch=1)
        layout.addLayout(header_layout)

        # Đường kẻ phân cách
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #45475a;")
        layout.addWidget(line)

        # Nội dung thông báo
        desc_label = QLabel(
            "Hệ thống phát hiện <b>USB Hardware Key đã bị ngắt kết nối</b> trong khi phần mềm đang vận hành.<br><br>"
            "• Các tác vụ kiểm tra tự động tạm thời bị <b>đình chỉ</b> để đảm bảo bản quyền.<br>"
            "• Vui lòng <b>cắm lại USB License Key</b> vào máy tính và bấm nút <b>'Thử lại'</b>.<br>"
            "• Nếu không cắm lại khóa, phần mềm sẽ tự động đóng để bảo vệ an toàn."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 13px; line-height: 1.5; color: #bac2de;")
        layout.addWidget(desc_label)

        # Nhãn đếm ngược
        self.lbl_countdown = QLabel(f"⏱️ Thời gian chờ còn lại: <b style='color: #e74c3c; font-size: 15px;'>{self.remaining_seconds} giây</b>")
        self.lbl_countdown.setAlignment(Qt.AlignCenter)
        self.lbl_countdown.setStyleSheet("background-color: #313244; padding: 10px; border-radius: 6px; font-size: 13px;")
        layout.addWidget(self.lbl_countdown)

        # Nhãn trạng thái kiểm tra lại
        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("font-size: 12px; font-weight: bold;")
        layout.addWidget(self.lbl_status)

        # Nút thao tác
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self.btn_retry = QPushButton("🔄 Thử lại (Kiểm tra USB)")
        self.btn_retry.setObjectName("btnRetry")
        self.btn_retry.setCursor(Qt.PointingHandCursor)
        self.btn_retry.clicked.connect(self._on_retry_clicked)
        button_layout.addWidget(self.btn_retry)

        self.btn_exit = QPushButton("🚪 Thoát ứng dụng")
        self.btn_exit.setObjectName("btnExit")
        self.btn_exit.setCursor(Qt.PointingHandCursor)
        self.btn_exit.clicked.connect(self._on_exit_clicked)
        button_layout.addWidget(self.btn_exit)

        layout.addLayout(button_layout)

    def _on_tick(self):
        """Mỗi giây giảm thời gian đếm ngược."""
        self.remaining_seconds -= 1
        if self.remaining_seconds > 0:
            self.lbl_countdown.setText(f"⏱️ Thời gian chờ còn lại: <b style='color: #e74c3c; font-size: 15px;'>{self.remaining_seconds} giây</b>")
        else:
            self.countdown_timer.stop()
            self.lbl_countdown.setText("<b style='color: #e74c3c; font-size: 14px;'>Hết thời gian chờ! Đang đóng ứng dụng...</b>")
            _log.warning("Hết thời gian chờ cắm lại USB Key. Tự động thoát ứng dụng!")
            QtCore.QTimer.singleShot(1500, self._force_exit)

    def _on_retry_clicked(self):
        """Xử lý khi người dùng ấn nút Thử lại."""
        if self.is_checking:
            return
        self.is_checking = True
        self.btn_retry.setEnabled(False)
        self.lbl_status.setStyleSheet("color: #f1c40f; font-size: 12px; font-weight: bold;")
        self.lbl_status.setText("⏳ Đang quét thiết bị USB...")
        QtWidgets.QApplication.processEvents()

        # Quét kiểm tra USB
        self._retry_worker = HardwareKeyCheckWorker(self.main_core, self)
        self._retry_worker.check_finished.connect(self._on_retry_completed)
        self._retry_worker.start()

    def _on_retry_completed(self, is_valid: bool):
        self.is_checking = False
        self.btn_retry.setEnabled(True)

        if is_valid:
            self.countdown_timer.stop()
            self.lbl_status.setStyleSheet("color: #2ecc71; font-size: 13px; font-weight: bold;")
            self.lbl_status.setText("✅ Khóa bản quyền hợp lệ! Đang khôi phục vận hành...")
            QtWidgets.QApplication.processEvents()
            _log.info("Người dùng đã cắm lại USB Key hợp lệ. Khôi phục vận hành!")
            QtCore.QTimer.singleShot(800, self.accept)
        else:
            self.lbl_status.setStyleSheet("color: #e74c3c; font-size: 12px; font-weight: bold;")
            self.lbl_status.setText("❌ Vẫn chưa phát hiện USB Key hợp lệ! Vui lòng cắm đúng cổng USB.")

    def _on_exit_clicked(self):
        """Người dùng chọn đóng phần mềm chủ động."""
        self.countdown_timer.stop()
        self._force_exit()

    def _force_exit(self):
        """Thoát chương trình an toàn."""
        _log.info("Đóng ứng dụng do không có USB Hardware Key.")
        parent_window = self.parent()
        if parent_window and hasattr(parent_window, 'main_thread') and parent_window.main_thread:
            try:
                parent_window.main_thread.close_application(None, self.main_core)
                return
            except Exception:
                pass
        sys.exit(0)

    def reject(self):
        """Ngăn chặn đóng dialog qua phím Esc hoặc nút X khi chưa xác thực thành công."""
        pass


class HardwareKeyGuard(QtCore.QObject):
    """
    Bộ giám sát định kỳ USB Hardware Key.
    - Quản lý lịch quét ngẫu nhiên trong khoảng 3 - 5 phút (180s - 300s).
    - Tự động kích hoạt Alert Modal khi USB bị rút.
    """

    key_status_changed = pyqtSignal(bool)

    def __init__(self, main_core, parent_window=None, min_interval_sec=180, max_interval_sec=300):
        super().__init__(parent_window)
        self.main_core = main_core
        self.parent_window = parent_window
        self.min_interval_sec = min_interval_sec
        self.max_interval_sec = max_interval_sec
        self.is_active = False
        self._is_checking = False
        self._alert_dialog = None

        self._schedule_timer = QTimer(self)
        self._schedule_timer.setSingleShot(True)
        self._schedule_timer.timeout.connect(self._trigger_check)

    def start(self):
        """Bắt đầu chu trình giám sát định kỳ."""
        self.is_active = True
        self._schedule_next()
        _log.info(
            "HardwareKeyGuard đã khởi động. Tần số quét định kỳ: %d - %d giây (3-5 phút).",
            self.min_interval_sec, self.max_interval_sec
        )

    def stop(self):
        """Dừng chu trình giám sát."""
        self.is_active = False
        self._schedule_timer.stop()
        if self._alert_dialog and self._alert_dialog.isVisible():
            self._alert_dialog.close()
        _log.info("HardwareKeyGuard đã dừng.")

    def _schedule_next(self):
        """Lên lịch cho lần quét tiếp theo với độ trễ ngẫu nhiên từ min_interval_sec đến max_interval_sec."""
        if not self.is_active:
            return
        delay_sec = random.randint(self.min_interval_sec, self.max_interval_sec)
        # _log.info("[HardwareKeyGuard] Lần quét USB Key kế tiếp sau: %d giây (%.1f phút).", delay_sec, delay_sec / 60.0)
        self._schedule_timer.start(delay_sec * 1000)

    def _trigger_check(self):
        """Kích hoạt quét kiểm tra USB trong luồng phụ."""
        if not self.is_active or self._is_checking:
            return

        # Nếu đang hiển thị modal cảnh báo thì không quét đè
        if self._alert_dialog and self._alert_dialog.isVisible():
            return

        self._is_checking = True
        self._worker = HardwareKeyCheckWorker(self.main_core, self)
        self._worker.check_finished.connect(self._on_check_completed)
        self._worker.start()

    def _on_check_completed(self, is_valid: bool):
        """Nhận kết quả kiểm tra từ luồng phụ."""
        self._is_checking = False

        if not self.is_active:
            return

        if is_valid:
            # _log.info("[HardwareKeyGuard] Quét định kỳ: USB Key HỢP LỆ.")
            self.key_status_changed.emit(True)
            self._schedule_next()
        else:
            _log.warning("[HardwareKeyGuard] CẢNH BÁO: USB Key ĐÃ BỊ RÚT RA hoặc không hợp lệ!")
            self.key_status_changed.emit(False)
            self._handle_key_disconnected()

    def _handle_key_disconnected(self):
        """Xử lý sự kiện khóa USB bị rút giữa chừng."""
        if self._alert_dialog and self._alert_dialog.isVisible():
            return

        _log.critical("[HardwareKeyGuard] Đang hiển thị hộp thoại cảnh báo mất khóa bản quyền.")

        # Tạm dừng giám sát tín hiệu nền trong lúc chờ cắm lại khóa
        had_monitoring = False
        try:
            if hasattr(self.main_core, 'worker_thread') and self.main_core.worker_thread:
                had_monitoring = getattr(self.main_core.worker_thread, 'running', False)
                if had_monitoring:
                    self.main_core.stop_monitoring()
                    _log.info("[HardwareKeyGuard] Đã tạm dừng CoreWorker monitoring để bảo vệ bản quyền.")
        except Exception as e:
            _log.warning("Không thể tạm dừng giám sát: %s", e)

        self._alert_dialog = HardwareKeyAlertModal(self.main_core, self.parent_window, countdown_seconds=120)
        result = self._alert_dialog.exec_()

        if result == QDialog.Accepted:
            _log.info("[HardwareKeyGuard] Khóa USB đã được khôi phục. Tiếp tục chu trình định kỳ.")
            self._alert_dialog = None

            # Khôi phục lại giám sát tín hiệu nền
            if had_monitoring:
                try:
                    self.main_core.start_monitoring()
                    _log.info("[HardwareKeyGuard] Đã khôi phục CoreWorker monitoring.")
                except Exception as e:
                    _log.error("Lỗi khôi phục giám sát: %s", e)

            self.key_status_changed.emit(True)
            self._schedule_next()
        else:
            _log.warning("[HardwareKeyGuard] Hộp thoại bị đóng không thành công. Đóng ứng dụng.")
            sys.exit(0)
