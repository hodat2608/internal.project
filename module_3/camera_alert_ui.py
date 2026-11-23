# -*- coding: utf-8 -*-
"""
module_3/camera_alert_ui.py
===========================
Giao diện UI cảnh báo mất kết nối Camera và thông báo khôi phục kết nối thành công:
1. CameraAlertOverlay:
   - Giao diện cảnh báo mất kết nối Camera nổi bật, rõ ràng, đẹp và chuyên nghiệp (tương tự PLCAlertOverlay).
   - Nền tối hiện đại (Dark Slate #0F172A), viền đỏ cảnh báo (#EF4444) với hiệu ứng phát sáng (Glow Drop Shadow).
   - Hiển thị cụ thể: Tên/Kênh Camera bị mất kết nối (ví dụ Camera 1, Camera 2...), Loại thiết bị (HIK, Basler), Cổng & Định danh (IP/Serial), nguyên nhân và trạng thái an toàn PLC.
   - Hỗ trợ đa camera: Theo dõi chính xác nếu một hoặc nhiều camera cùng lúc bị sự cố.
   - Trạng thái tự động kết nối lại (Auto-reconnecting status with pulsing progress bar & attempt counter).
   - Draggable: người dùng có thể nhấp chuột kéo thả di chuyển vị trí.
   - Non-blocking: Không khóa giao diện hay các luồng xử lý AI / PLC khác.
2. CameraSuccessBanner:
   - Giao diện thông báo kết nối lại camera thành công màu xanh lục ngọc (#10B981).
   - Tự động hiển thị và đóng sau 5 giây (với bộ đếm lùi thời gian).
3. CameraWatchdogSignals:
   - Các Qt Signals đảm bảo giao tiếp an toàn đa luồng giữa CameraWatchdogThread và giao diện chính.
"""

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QProgressBar, QGraphicsDropShadowEffect, QFrame, QApplication
)
from app_logger.app_logger import get_logger as _get_logger

_log = _get_logger('module_3.camera_alert_ui')


# ---------------------------------------------------------------------------
# Qt Signals cho Camera Watchdog (Thread-safe)
# ---------------------------------------------------------------------------
class CameraWatchdogSignals(QObject):
    camera_lost = pyqtSignal(str, str, str, str, int)      # camera_name, device_type, identifier, conn_mode, attempts
    reconnect_attempt = pyqtSignal(str, int)               # camera_name, attempts
    camera_restored = pyqtSignal(str, str, str, str)       # camera_name, device_type, identifier, conn_mode

    # Aliases tương thích ngược
    camera_disconnected = pyqtSignal(str)
    camera_reconnecting = pyqtSignal(str, int)
    camera_reconnected = pyqtSignal(str, object)


# ---------------------------------------------------------------------------
# Giao diện Cảnh báo Mất kết nối Camera (Warning UI)
# ---------------------------------------------------------------------------
class CameraAlertOverlay(QDialog):
    """
    Cửa sổ cảnh báo mất kết nối Camera nổi bật trên màn hình,
    không chặn luồng (non-blocking, non-modal), hiển thị rõ camera nào đang bị ngắt kết nối.
    """
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

        # Lưu trữ danh sách các camera đang bị mất kết nối:
        # {cam_name: {'device_type': ..., 'identifier': ..., 'conn_mode': ..., 'attempts': ...}}
        self.disconnected_cameras = {}

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

        # 1. Header: Icon cảnh báo Camera nhấp nháy + Tiêu đề
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        self.icon_badge = QLabel("📷", self.card)
        self.icon_badge.setStyleSheet("""
            QLabel {
                font-size: 26px;
                background-color: #371B1B;
                border: 1.5px solid #7F1D1D;
                border-radius: 26px;
                padding: 4px;
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

        self.label_title = QLabel("CẢNH BÁO: MẤT KẾT NỐI TỚI CAMERA", self.card)
        self.label_title.setStyleSheet("""
            color: #FF0000;
            font-size: 17px;
            font-weight: 800;
            font-family: 'Segoe UI', Arial, sans-serif;
            letter-spacing: 0.5px;
        """)
        title_layout.addWidget(self.label_title)

        self.label_subtitle = QLabel("CAMERA HARDWARE COMMUNICATION LINK INTERRUPTED ⚠️", self.card)
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
        self.btn_close.setToolTip("Đóng cảnh báo để kiểm tra cài đặt (Hệ thống vẫn tự động kết nối lại Camera ngầm)")
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
        info_layout.setContentsMargins(14, 12, 14, 12)
        info_layout.setHorizontalSpacing(16)
        info_layout.setVerticalSpacing(8)

        # Hàng 1: Camera bị ngắt kết nối (HIỂN THỊ NỔI BẬT NHẤT)
        lbl_cam_k = QLabel("Camera bị ngắt kết nối:", self.info_box)
        lbl_cam_k.setStyleSheet("color: #94A3B8; font-weight: 600; font-size: 13px;")
        self.lbl_cam_v = QLabel("Camera 1", self.info_box)
        self.lbl_cam_v.setStyleSheet("""
            color: #EF4444; 
            font-weight: 900; 
            font-size: 15px;
            background-color: #451A1A;
            border: 1px solid #7F1D1D;
            border-radius: 4px;
            padding: 2px 8px;
        """)

        # Hàng 2: Loại thiết bị
        lbl_dev_k = QLabel("Loại thiết bị / Driver:", self.info_box)
        lbl_dev_k.setStyleSheet("color: #94A3B8; font-weight: 600; font-size: 12px;")
        self.lbl_dev_v = QLabel("HIK - MVS", self.info_box)
        self.lbl_dev_v.setStyleSheet("color: #F1F5F9; font-weight: bold; font-size: 12px;")

        # Hàng 3: Cổng kết nối & Địa chỉ
        lbl_addr_k = QLabel("Cổng & Định danh:", self.info_box)
        lbl_addr_k.setStyleSheet("color: #94A3B8; font-weight: 600; font-size: 12px;")
        self.lbl_addr_v = QLabel("GigE - IP: 192.168.1.100", self.info_box)
        self.lbl_addr_v.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 12px;")

        # Hàng 4: Nguyên nhân
        lbl_cause_k = QLabel("Nguyên nhân có thể:", self.info_box)
        lbl_cause_k.setStyleSheet("color: #94A3B8; font-weight: 600; font-size: 12px;")
        self.lbl_cause_v = QLabel("Lỏng cáp Ethernet/USB, switch mạng mất nguồn hoặc camera bị ngắt điện.", self.info_box)
        self.lbl_cause_v.setWordWrap(True)
        self.lbl_cause_v.setStyleSheet("color: #FBBF24; font-weight: 500; font-size: 12px;")

        # Hàng 5: Trạng thái an toàn PLC
        lbl_plc_k = QLabel("Tín hiệu an toàn PLC:", self.info_box)
        lbl_plc_k.setStyleSheet("color: #94A3B8; font-weight: 600; font-size: 12px;")
        self.lbl_plc_v = QLabel("🔒 Đã gửi tín hiệu OFF tới PLC để tạm dừng chu trình chụp ảnh.", self.info_box)
        self.lbl_plc_v.setStyleSheet("color: #F43F5E; font-weight: bold; font-size: 12px;")

        info_layout.addWidget(lbl_cam_k, 0, 0)
        info_layout.addWidget(self.lbl_cam_v, 0, 1)
        info_layout.addWidget(lbl_dev_k, 1, 0)
        info_layout.addWidget(self.lbl_dev_v, 1, 1)
        info_layout.addWidget(lbl_addr_k, 2, 0)
        info_layout.addWidget(self.lbl_addr_v, 2, 1)
        info_layout.addWidget(lbl_cause_k, 3, 0)
        info_layout.addWidget(self.lbl_cause_v, 3, 1)
        info_layout.addWidget(lbl_plc_k, 4, 0)
        info_layout.addWidget(self.lbl_plc_v, 4, 1)

        card_layout.addWidget(self.info_box)

        # 3. Trạng thái tự động kết nối lại + Thanh tiến trình nhấp nháy
        reconnect_box = QVBoxLayout()
        reconnect_box.setSpacing(6)

        status_row = QHBoxLayout()
        self.lbl_status = QLabel("🔄 Đang tự động kiểm tra và kết nối lại Camera... (Lần thử: 1)", self.card)
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
            "💡 Giao diện chính và các tham số kiểm tra được giữ nguyên an toàn. Hệ thống sẽ tự động khôi phục luồng lấy ảnh ngay khi cắm lại cáp hoặc bật nguồn lại cho camera.",
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

        # 5. Nút đóng cảnh báo để thao tác trên giao diện chính
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 4, 0, 0)
        bottom_bar.addStretch()

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
        """Người dùng chủ động đóng cảnh báo để kiểm tra cài đặt. Watchdog camera vẫn chạy ngầm."""
        self.user_dismissed = True
        self.hide()

    def set_camera_info(self, camera_name: str, device_type: str, identifier: str, conn_mode: str, attempts: int = 1):
        """Thêm hoặc cập nhật camera bị mất kết nối và hiển thị lên giao diện."""
        cam_clean = str(camera_name).replace('built-in-camera-', '').replace('built-in-', '').replace('camera-', '')
        self.disconnected_cameras[cam_clean] = {
            'device_type': str(device_type),
            'identifier': str(identifier),
            'conn_mode': str(conn_mode),
            'attempts': int(attempts)
        }
        self._refresh_display()

    def update_attempts(self, camera_name: str, attempts: int, device_type: str = None, identifier: str = None, conn_mode: str = None):
        """Cập nhật số lần thử kết nối lại cho camera."""
        cam_clean = str(camera_name).replace('built-in-camera-', '').replace('built-in-', '').replace('camera-', '')
        if cam_clean in self.disconnected_cameras:
            self.disconnected_cameras[cam_clean]['attempts'] = int(attempts)
        else:
            self.disconnected_cameras[cam_clean] = {
                'device_type': str(device_type or 'Camera'),
                'identifier': str(identifier or 'N/A'),
                'conn_mode': str(conn_mode or 'N/A'),
                'attempts': int(attempts)
            }
        self._refresh_display()
        if not self.isVisible() and not getattr(self, 'user_dismissed', False):
            self.show_alert()
        elif self.isVisible():
            self.raise_()

    def remove_camera(self, camera_name: str) -> bool:
        """
        Xóa camera đã khôi phục kết nối.
        Trả về True nếu vẫn còn camera khác bị mất kết nối, False nếu đã kết nối lại hết.
        """
        cam_clean = str(camera_name).replace('built-in-camera-', '').replace('built-in-', '').replace('camera-', '')
        self.disconnected_cameras.pop(cam_clean, None)
        if self.disconnected_cameras:
            self._refresh_display()
            return True
        return False

    def _refresh_display(self):
        """Cập nhật toàn bộ nhãn hiển thị theo danh sách camera bị ngắt kết nối."""
        if not self.disconnected_cameras:
            return

        cams = list(self.disconnected_cameras.keys())
        max_attempts = max((c['attempts'] for c in self.disconnected_cameras.values()), default=1)

        if len(cams) == 1:
            cam = cams[0]
            info = self.disconnected_cameras[cam]
            self.lbl_cam_v.setText(f"Camera {cam}")
            self.lbl_dev_v.setText(f"{info['device_type']}")
            self.lbl_addr_v.setText(f"{info['conn_mode']} - {info['identifier']}")
            self.lbl_status.setText(f"🔄 Đang tự động kiểm tra và kết nối lại Camera {cam}... (Lần thử: {info['attempts']})")
        else:
            cam_list_str = ", ".join([f"Camera {c}" for c in cams])
            self.lbl_cam_v.setText(cam_list_str)
            dev_types = ", ".join(sorted(set(info['device_type'] for info in self.disconnected_cameras.values())))
            self.lbl_dev_v.setText(dev_types)
            addrs = " | ".join([f"Cam {c}: {info['identifier']}" for c, info in self.disconnected_cameras.items()])
            self.lbl_addr_v.setText(addrs)
            self.lbl_status.setText(f"🔄 Đang tự động kiểm tra và kết nối lại các camera ({cam_list_str})... (Lần thử cao nhất: {max_attempts})")

    def show_alert(self):
        """Hiển thị cảnh báo ở vị trí trung tâm cửa sổ đang hoạt động."""
        self.user_dismissed = False
        self._center_on_screen_or_window()
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_alert(self):
        """Ẩn cảnh báo khi tất cả camera đã kết nối lại thành công."""
        self.user_dismissed = False
        self.disconnected_cameras.clear()
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
# Giao diện Thông báo Khôi phục Camera Thành công (Success UI - Tự tắt sau 5s)
# ---------------------------------------------------------------------------
class CameraSuccessBanner(QDialog):
    """
    Thông báo kết nối lại camera thành công màu xanh lục ngọc (#10B981),
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
        self.setMinimumSize(720, 480)
        self.resize(740, 500)
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

        icon_badge = QLabel("📷✅", self.card)
        icon_badge.setStyleSheet("""
            QLabel {
                font-size: 26px;
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

        label_title = QLabel("KHÔI PHỤC KẾT NỐI CAMERA THÀNH CÔNG", self.card)
        label_title.setStyleSheet("""
            color: #34D399;
            font-size: 16px;
            font-weight: 800;
            font-family: 'Segoe UI', Arial, sans-serif;
            letter-spacing: 0.5px;
        """)
        title_layout.addWidget(label_title)

        label_subtitle = QLabel("CAMERA HARDWARE LINK RESTORED & READY", self.card)
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
            "Đã kết nối lại thành công với Camera. Luồng lấy ảnh tự động và tín hiệu sẵn sàng tới PLC đã được khôi phục hoàn toàn!",
            self.card
        )
        self.lbl_msg.setWordWrap(True)
        self.lbl_msg.setStyleSheet("""
            color: #ECFDF5;
            font-size: 13px;
            font-weight: 500;
            font-family: 'Segoe UI', Arial;
            padding: 8px 0px;
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

    def show_success(self, camera_name: str, device_type: str, identifier: str, conn_mode: str, duration_ms: int = 5000):
        """Hiển thị thông báo thành công và bắt đầu đếm lùi 5 giây để đóng."""
        cam_clean = str(camera_name).replace('built-in-camera-', '').replace('built-in-', '').replace('camera-', '')
        self.lbl_msg.setText(
            f"Đã khôi phục kết nối thành công tới Camera {cam_clean} ({device_type} - {conn_mode} {identifier}).\n"
            f"Kênh lấy ảnh tự động và các tín hiệu Ready / Run tới PLC đã sẵn sàng hoạt động bình thường!"
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

