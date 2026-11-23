# -*- coding: utf-8 -*-
"""
Module: startup_splash.py
Chức năng: Màn hình khởi động (Startup Loading UI / Splash Screen) chuyên nghiệp cho môi trường công nghiệp.
- Hiển thị ngay lập tức khi máy tính khởi động và phần mềm tự động chạy (hoặc khi mở thủ công).
- Cảnh báo trực quan nổi bật cho công nhân vận hành: "ĐANG KHỞI TẠO - KHÔNG ĐƯỢC CLICK ICON TRÊN DESKTOP".
- Cập nhật tiến trình thời gian thực (kết nối MySQL, PLC, License, nạp Task, UI...).
- Tự động gọi QApplication.processEvents() để UI luôn mượt mà ngay cả khi chạy các bước đồng bộ.
"""

import os
import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from app_logger.app_logger import get_logger

_log = get_logger('module_2.startup_splash')


class StartupSplashWindow(QtWidgets.QWidget):
    """
    Cửa sổ Splash thông báo tiến trình khởi động phần mềm.
    Thiết kế hiện đại, độ nổi bật cao, cố định trên cùng màn hình (Always on Top).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_progress = 0
        self.init_ui()

    def init_ui(self):
        # Thiết lập thuộc tính cửa sổ: Không viền, luôn nổi trên cùng, không chiếm taskbar phụ
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        self.setFixedSize(680, 420)

        # Layout chính của widget gốc
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Card chứa nội dung (có viền bo góc và bóng đổ)
        self.card = QtWidgets.QFrame(self)
        self.card.setObjectName("splashCard")
        self.card.setStyleSheet("""
            QFrame#splashCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #090d16, stop:0.5 #0f172a, stop:1 #1e293b);
                border: 2px solid #3b82f6;
                border-radius: 16px;
            }
        """)

        # Hiệu ứng đổ bóng cho khung nhìn sang trọng
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QtGui.QColor(0, 0, 0, 180))
        shadow.setOffset(0, 6)
        self.card.setGraphicsEffect(shadow)

        card_layout = QtWidgets.QVBoxLayout(self.card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(14)

        # 1. Header: Logo + Tên ứng dụng + Phiên bản
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(14)

        icon_label = QtWidgets.QLabel()
        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "module_3", "assert", "icon", "artificial-intelligence.ico"
        )
        if os.path.exists(icon_path):
            pixmap = QtGui.QPixmap(icon_path).scaled(54, 54, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            icon_label.setPixmap(pixmap)
        else:
            icon_label.setText("👁️")
            icon_label.setStyleSheet("font-size: 38px; color: #60a5fa;")
        header_layout.addWidget(icon_label)

        title_vbox = QtWidgets.QVBoxLayout()
        title_vbox.setSpacing(2)

        lbl_app_name = QtWidgets.QLabel("AI VISION PRO INSPECTOR")
        lbl_app_name.setStyleSheet("""
            font-size: 21px;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: 1px;
            font-family: 'Segoe UI', Arial, sans-serif;
        """)

        lbl_sub_title = QtWidgets.QLabel("HỆ THỐNG KIỂM TRA CHẤT LƯỢNG THỊ GIÁC MÁY CÔNG NGHIỆP • V2.0")
        lbl_sub_title.setStyleSheet("""
            font-size: 11px;
            font-weight: 600;
            color: #94a3b8;
            letter-spacing: 0.5px;
        """)

        title_vbox.addWidget(lbl_app_name)
        title_vbox.addWidget(lbl_sub_title)
        header_layout.addLayout(title_vbox)
        header_layout.addStretch()

        card_layout.addLayout(header_layout)

        # Đường kẻ phân cách tinh tế
        sep_line = QtWidgets.QFrame()
        sep_line.setFrameShape(QtWidgets.QFrame.HLine)
        sep_line.setFrameShadow(QtWidgets.QFrame.Sunken)
        sep_line.setStyleSheet("background-color: #334155; max-height: 1px;")
        card_layout.addWidget(sep_line)

        # 2. KHUNG CẢNH BÁO NỔI BẬT DÀNH CHO CÔNG NHÂN VẬN HÀNH (OPERATOR NOTICE)
        self.alert_frame = QtWidgets.QFrame()
        self.alert_frame.setObjectName("alertFrame")
        self.alert_frame.setStyleSheet("""
            QFrame#alertFrame {
                background-color: #451a03;
                border: 2px solid #f59e0b;
                border-radius: 10px;
                padding: 10px 14px;
            }
        """)
        alert_vbox = QtWidgets.QVBoxLayout(self.alert_frame)
        alert_vbox.setContentsMargins(12, 10, 12, 10)
        alert_vbox.setSpacing(6)

        alert_title = QtWidgets.QLabel("⚡ ĐANG TỰ ĐỘNG KHỞI TẠO HỆ THỐNG KIỂM TRA")
        alert_title.setStyleSheet("""
            color: #fbbf24;
            font-size: 14px;
            font-weight: bold;
            font-family: 'Segoe UI', Arial, sans-serif;
        """)
        alert_vbox.addWidget(alert_title)

        alert_desc = QtWidgets.QLabel(
            "Hệ thống đang tự động kết nối PLC, Camera công nghiệp và cơ sở dữ liệu.\n"
            "⚠️ VUI LÒNG CHỜ TRONG GIÂY LÁT — TUYỆT ĐỐI KHÔNG CLICK LẠI ICON TRÊN MÀN HÌNH!"
        )
        alert_desc.setWordWrap(True)
        alert_desc.setStyleSheet("""
            color: #fef08a;
            font-size: 12px;
            font-weight: 600;
            line-height: 140%;
        """)
        alert_vbox.addWidget(alert_desc)

        card_layout.addWidget(self.alert_frame)

        # 3. Thông tin trạng thái chi tiết đang thực hiện
        status_box = QtWidgets.QVBoxLayout()
        status_box.setSpacing(4)

        self.lbl_status = QtWidgets.QLabel("Đang nạp các mô-đun cốt lõi...")
        self.lbl_status.setStyleSheet("""
            color: #38bdf8;
            font-size: 13px;
            font-weight: 600;
            font-family: 'Segoe UI', Arial, sans-serif;
        """)

        self.lbl_detail = QtWidgets.QLabel("Vui lòng đợi hệ thống hoàn tất các tiến trình kết nối nền...")
        self.lbl_detail.setStyleSheet("""
            color: #94a3b8;
            font-size: 11px;
            font-style: italic;
        """)

        status_box.addWidget(self.lbl_status)
        status_box.addWidget(self.lbl_detail)
        card_layout.addLayout(status_box)

        # 4. Thanh tiến trình (ProgressBar) + Nhãn phần trăm
        progress_hbox = QtWidgets.QHBoxLayout()
        progress_hbox.setSpacing(10)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(5)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: 1px solid #475569;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563eb, stop:0.7 #38bdf8, stop:1 #67e8f9);
                border-radius: 5px;
            }
        """)

        self.lbl_percent = QtWidgets.QLabel("5%")
        self.lbl_percent.setFixedWidth(45)
        self.lbl_percent.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.lbl_percent.setStyleSheet("""
            color: #38bdf8;
            font-size: 12px;
            font-weight: bold;
            font-family: 'Consolas', monospace;
        """)

        progress_hbox.addWidget(self.progress_bar)
        progress_hbox.addWidget(self.lbl_percent)
        card_layout.addLayout(progress_hbox)

        main_layout.addWidget(self.card)

        # Căn giữa màn hình hiển thị
        self.center_on_screen()

    def center_on_screen(self):
        """Căn giữa cửa sổ Splash trên màn hình chính."""
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            x = (screen_geo.width() - self.width()) // 2
            y = (screen_geo.height() - self.height()) // 2
            self.move(x, y)

    def update_status(self, message: str, detail: str = "", progress: int = -1):
        """
        Cập nhật trạng thái tiến trình khởi động.
        Đồng thời kích hoạt xử lý sự kiện Qt để giao diện vẽ lại tức thì mà không bị đơ.
        """
        try:
            if message:
                self.lbl_status.setText(message)
            if detail is not None and detail != "":
                self.lbl_detail.setText(detail)

            if progress is not None and progress >= 0:
                self._current_progress = min(100, max(0, int(progress)))
                self.progress_bar.setValue(self._current_progress)
                self.lbl_percent.setText(f"{self._current_progress}%")

            _log.info("[SplashProgress %s%%] %s | %s", self._current_progress, message, detail)

            # Cưỡng chế Qt Event Loop xử lý vẽ lại khung nhìn ngay lập tức
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 50)
        except Exception as e:
            _log.debug("Lỗi cập nhật UI splash: %s", e)

    def activate_splash(self):
        """Đưa cửa sổ Splash lên trên cùng và kích hoạt tiêu điểm."""
        try:
            self.show()
            self.raise_()
            self.activateWindow()
            QtWidgets.QApplication.processEvents()
        except Exception as e:
            _log.debug("Lỗi activate splash: %s", e)

    def finish(self, target_window=None):
        """
        Kết thúc hiển thị màn hình khởi động.
        Đưa thanh tiến trình về 100%, tạm dừng 300ms rồi ẩn splash và đưa cửa sổ chính lên.
        """
        try:
            self.update_status("Khởi tạo hệ thống thành công!", "Đang mở giao diện chính...", 100)
            QtWidgets.QApplication.processEvents()
            QtCore.QThread.msleep(300)

            if target_window:
                target_window.showMaximized()
                target_window.raise_()
                target_window.activateWindow()

            self.close()
            QtWidgets.QApplication.processEvents()
        except Exception as e:
            _log.error("Lỗi khi kết thúc splash: %s", e)
            self.close()

