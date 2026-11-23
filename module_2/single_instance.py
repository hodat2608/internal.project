# -*- coding: utf-8 -*-
"""
Module: single_instance.py
Chức năng: Đảm bảo chỉ có DUY NHẤT MỘT phiên bản của phần mềm VisionProInspector chạy trên hệ thống.
- Phát hiện phiên bản đang chạy qua Named Pipe (QLocalServer / QLocalSocket) và Windows Named Mutex.
- Nếu phát hiện phần mềm đã mở (hoặc đang trong tiến trình khởi động), lập tức gửi thông điệp
  kích hoạt đưa cửa sổ / splash đang chạy lên Foreground, đồng thời hiển thị hộp thoại cảnh báo
  rõ ràng cho người vận hành trước khi thoát phiên bản thứ hai ngay lập tức.
"""

import sys
import ctypes
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from app_logger.app_logger import get_logger

_log = get_logger('module_2.single_instance')

SERVER_NAME = "VisionProInspector_SingleInstance_Pipe_v2"
MUTEX_NAME = "Local\\VisionProInspector_SingleInstance_Mutex_v2"


class SingleInstanceManager(QtCore.QObject):
    """Quản lý khóa đơn phiên bản (Single Instance Lock) cho toàn bộ ứng dụng."""
    message_received = QtCore.pyqtSignal(str)
    _primary_mutex_handle = None

    def __init__(self, server_name=SERVER_NAME, parent=None):
        super().__init__(parent)
        self.server_name = server_name
        self.server = None

    @classmethod
    def is_already_running(cls, server_name=SERVER_NAME, timeout_ms=600) -> bool:
        """
        Kiểm tra xem đã có phiên bản nào của ứng dụng đang chạy hay chưa.
        1. Thử kết nối tới QLocalServer.
        2. Nếu kết nối thành công -> Đã có app đang chạy. Gửi thông điệp 'ACTIVATE' và return True.
        3. Kiểm tra bổ sung qua Windows Named Mutex để đảm bảo an toàn tuyệt đối.
        """
        # 1. Kiểm tra qua QLocalSocket
        try:
            socket = QLocalSocket()
            socket.connectToServer(server_name)
            if socket.waitForConnected(timeout_ms):
                _log.warning("[SingleInstance] Phát hiện phiên bản phần mềm đang chạy qua QLocalServer (%s)!", server_name)
                try:
                    socket.write(b"ACTIVATE\n")
                    socket.waitForBytesWritten(300)
                except Exception:
                    pass
                socket.disconnectFromServer()
                return True
        except Exception as e:
            _log.debug("Lỗi socket kiểm tra single instance: %s", e)

        # 2. Kiểm tra qua Windows Named Mutex
        try:
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
            last_err = kernel32.GetLastError()
            ERROR_ALREADY_EXISTS = 183
            if last_err == ERROR_ALREADY_EXISTS:
                _log.warning("[SingleInstance] Phát hiện phiên bản phần mềm đang chạy qua Windows Mutex (%s)!", MUTEX_NAME)
                if handle:
                    kernel32.CloseHandle(handle)
                return True
            # Giữ handle của phiên bản đầu tiên để mutex tồn tại suốt vòng đời tiến trình
            cls._primary_mutex_handle = handle
        except Exception as e:
            _log.debug("Lỗi mutex kiểm tra single instance: %s", e)

        return False

    @classmethod
    def show_already_running_warning(cls, parent=None):
        """Hiển thị hộp thoại cảnh báo người vận hành rằng phần mềm đã mở hoặc đang khởi động."""
        msg_box = QtWidgets.QMessageBox(parent)
        msg_box.setWindowTitle("⚠️ Cảnh Báo: Phần Mềm Đang Chạy")
        msg_box.setIcon(QtWidgets.QMessageBox.Warning)
        msg_box.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Dialog)

        msg_box.setText(
            "<h2 style='color: #b45309;'>PHẦN MỀM ĐANG HOẠT ĐỘNG HOẶC ĐANG TRONG TIẾN TRÌNH KHỞI ĐỘNG!</h2>"
            "<p style='font-size: 13px;'>Hệ thống nhận diện phần mềm <b>AI Vision Pro Inspector</b> đã được mở trên máy tính này.</p>"
            "<hr>"
            "<p style='color: #dc2626; font-size: 13px; font-weight: bold;'>⚠️ LƯU Ý QUAN TRỌNG CHO NGƯỜI VẬN HÀNH:</p>"
            "<ul style='font-size: 12px; line-height: 150%;'>"
            "<li><b>TUYỆT ĐỐI KHÔNG CLICK ICON KHỞI ĐỘNG NHIỀU LẦN</b> để tránh gây xung đột cổng truyền thông PLC và Camera công nghiệp!</li>"
            "<li>Nếu vừa bật nguồn máy tính, phần mềm đang tự động nạp cấu hình và kết nối nền.</li>"
            "<li>Vui lòng kiểm tra trên thanh tác vụ (Taskbar) hoặc chờ màn hình khởi động hoàn tất.</li>"
            "<li>Cửa sổ phần mềm đang chạy đã được tự động kích hoạt đưa lên màn hình chính.</li>"
            "</ul>"
        )
        btn = msg_box.addButton("Đã Hiểu (Đóng Thông Báo Này)", QtWidgets.QMessageBox.AcceptRole)
        btn.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: white; font-weight: bold; padding: 8px 18px; border-radius: 6px; } "
            "QPushButton:hover { background-color: #1d4ed8; }"
        )
        msg_box.exec_()

    def start_server(self, on_activate_callback=None) -> bool:
        """
        Bắt đầu lắng nghe kết nối từ các lần click sau của người dùng.
        Khi có bản copy khác click mở, gọi on_activate_callback để đưa cửa sổ / splash lên màn hình.
        """
        try:
            QLocalServer.removeServer(self.server_name)
        except Exception:
            pass

        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._handle_new_connection)
        if on_activate_callback:
            self.message_received.connect(lambda msg: on_activate_callback())

        if not self.server.listen(self.server_name):
            _log.warning("[SingleInstance] Không thể lắng nghe QLocalServer trên %s: %s", self.server_name, self.server.errorString())
            return False

        _log.info("[SingleInstance] Đã khởi động SingleInstance Server lắng nghe tại: %s", self.server_name)
        return True

    def _handle_new_connection(self):
        client = self.server.nextPendingConnection()
        if not client:
            return

        def _read():
            try:
                data = client.readAll().data().decode('utf-8', errors='ignore').strip()
                if "ACTIVATE" in data:
                    _log.info("[SingleInstance] Nhận được tín hiệu ACTIVATE từ phiên bản thứ hai! Kích hoạt giao diện lên màn hình.")
                    self.message_received.emit("ACTIVATE")
            except Exception:
                pass
            finally:
                client.deleteLater()

        client.readyRead.connect(_read)

    def close(self):
        """Đóng server và giải phóng tài nguyên pipe/mutex."""
        try:
            if self.server:
                self.server.close()
                self.server = None
            QLocalServer.removeServer(self.server_name)
        except Exception:
            pass

        try:
            if SingleInstanceManager._primary_mutex_handle:
                ctypes.windll.kernel32.CloseHandle(SingleInstanceManager._primary_mutex_handle)
                SingleInstanceManager._primary_mutex_handle = None
        except Exception:
            pass
