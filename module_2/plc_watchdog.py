# -*- coding: utf-8 -*-
"""
module_2/plc_watchdog.py
========================
Tiến trình giám sát và khôi phục kết nối PLC tự động (Watchdog & Auto-Reconnect):
- Liên tục kiểm tra tính toàn vẹn của kết nối PLC (cả ở chế độ chạy và trạng thái ngắt kết nối).
- Phát hiện kịp thời sự cố mất kết nối (lỏng cáp Ethernet, switch mất nguồn, PLC tắt nguồn).
- Tự động phát tín hiệu mở giao diện cảnh báo rõ ràng, đẹp mắt cho người dùng.
- Tự động thăm dò kết nối lại (thử lại mỗi 1.5 giây mà không làm treo UI).
- Khi kết nối thành công: tự động khôi phục client, cập nhật driver_loader, tắt cảnh báo,
  hiển thị thông báo thành công trong 5 giây và cho phép các tác vụ _safe_read_plc, _safe_write_plc
  hoạt động lại bình thường mà không cần khởi động lại phần mềm!
"""

import time
import socket
import select
from PyQt5 import QtCore
from app_logger.app_logger import get_logger as _get_logger
from module_6.mitsubishi.initial import SocketClient as Mitsubishi_Socket_Client
from module_6.keyence.initial import KeyenceClient as Keyence_Socket_Client
from module_6.omron.initial import OmronClient as Omron_Socket_Client

_log = _get_logger('module_2.plc_watchdog')

PLC_COLLECT = {
    'KEYENCE'     : Keyence_Socket_Client,
    'OMRON'       : Omron_Socket_Client,
    'MITSHUBISHI' : Mitsubishi_Socket_Client,
}


def test_tcp_connection(ip: str, port: int, timeout: float = 1.0) -> bool:
    """Kiểm tra nhanh kết nối TCP tới IP:Port của PLC với timeout ngắn (1.0s)."""
    if not ip or not port:
        return False
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((str(ip).strip(), int(port)))
        try:
            s.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        return True
    except Exception:
        return False
    finally:
        if s is not None:
            try:
                s.close()
            except Exception:
                pass


class PLCWatchdogThread(QtCore.QThread):
    """
    Luồng giám sát kết nối PLC liên tục và tự động kết nối lại khi có sự cố.
    """
    def __init__(self, core_instance):
        super().__init__()
        self.core = core_instance
        self.running = True
        self.is_connected = False
        self.consecutive_errors = 0
        self.reconnect_attempts = 0
        self.check_interval_ms = 1500

    def run(self):
        _log.info("[PLCWatchdog] Bắt đầu tiến trình giám sát kết nối PLC...")

        while self.running:
            try:
                # 1. Bỏ qua kiểm tra nếu đang ở chế độ mô phỏng qua LOG hoặc chế độ Manual
                if self.core.is_indirect_log_mode() or getattr(self.core, 'manual', 0) == 1:
                    self.msleep(1500)
                    continue

                ip = getattr(self.core, 'ip_address_plc', '')
                port = getattr(self.core, 'port_plc', 0)
                module = getattr(self.core, 'plc_module', 'KEYENCE')

                if not ip or not port:
                    self.msleep(1500)
                    continue

                # 2. Xử lý theo trạng thái kết nối hiện tại
                if self.is_connected:
                    # Đang ở trạng thái KẾT NỐI: Kiểm tra xem socket còn sống không
                    alive = self._check_socket_alive()
                    if not alive:
                        self.consecutive_errors += 1
                    else:
                        self.consecutive_errors = 0

                    # Nếu phát hiện lỗi liên tiếp >= 2 lần -> Kích hoạt trạng thái MẤT KẾT NỐI
                    if self.consecutive_errors >= 2:
                        self.is_connected = False
                        self.core.is_plc_connected = False
                        self.core.mode_init_plc = 0
                        self.reconnect_attempts = 1
                        _log.warning("[PLCWatchdog] Phát hiện MẤT KẾT NỐI tới PLC %s (%s:%s)!", module, ip, port)
                        
                        # Dọn dẹp driver cũ
                        self._cleanup_old_driver()
                        
                        # Phát tín hiệu hiển thị giao diện cảnh báo (UI thread)
                        if hasattr(self.core, 'plc_signals'):
                            self.core.plc_signals.connection_lost.emit(module, str(ip), int(port), self.reconnect_attempts)

                else:
                    # Đang ở trạng thái MẤT KẾT NỐI: Tự động thăm dò và thử kết nối lại
                    self.reconnect_attempts += 1
                    if hasattr(self.core, 'plc_signals'):
                        self.core.plc_signals.reconnect_attempt.emit(self.reconnect_attempts)

                    # Thử kết nối TCP trước (timeout 1.0s)
                    can_connect_tcp = test_tcp_connection(ip, port, timeout=1.0)
                    if can_connect_tcp:
                        _log.info("[PLCWatchdog] Đã kết nối TCP tới %s:%s! Đang khởi tạo lại client PLC...", ip, port)
                        plc_cls = PLC_COLLECT.get(module, Keyence_Socket_Client)
                        new_client = plc_cls(ip, port)
                        connected = False
                        try:
                            connected = bool(new_client.connect())
                        except Exception as e_conn:
                            _log.debug("[PLCWatchdog] Lỗi new_client.connect(): %s", e_conn)

                        if connected:
                            # Khôi phục kết nối thành công!
                            self.core.driver_loader = new_client
                            self.core.is_plc_connected = True
                            self.core.mode_init_plc = 1
                            self.is_connected = True
                            self.consecutive_errors = 0
                            _log.info("[PLCWatchdog] ✅ Khôi phục kết nối thành công tới PLC %s (%s:%s) sau %d lần thử!", 
                                      module, ip, port, self.reconnect_attempts)
                            
                            # Phát tín hiệu khôi phục kết nối (tắt cảnh báo, hiện thông báo 5s)
                            if hasattr(self.core, 'plc_signals'):
                                self.core.plc_signals.connection_restored.emit(module, str(ip), int(port))

            except Exception as e:
                _log.debug("[PLCWatchdog] Ngoại lệ trong vòng lặp watchdog: %s", e)

            self.msleep(self.check_interval_ms)

        _log.info("[PLCWatchdog] Dừng tiến trình giám sát kết nối PLC.")

    def _check_socket_alive(self) -> bool:
        """Kiểm tra xem socket kết nối hiện tại có còn hoạt động không."""
        driver = getattr(self.core, 'driver_loader', None)
        if driver is None:
            return False

        sock = getattr(driver, 'sock', None)
        if sock is None:
            # Đối với client không dùng trực tiếp self.sock (như Type3E hoặc Omron)
            ip = getattr(self.core, 'ip_address_plc', '')
            port = getattr(self.core, 'port_plc', 0)
            return test_tcp_connection(ip, port, timeout=0.8)

        # Tránh xung đột với các lệnh đọc/ghi đang diễn ra
        driver_lock = getattr(driver, 'locked', None)
        have_lock = False
        if driver_lock:
            have_lock = driver_lock.acquire(timeout=0.05)
            if not have_lock:
                # Driver đang bận truyền thông dữ liệu -> Socket đang hoạt động
                return True

        try:
            if sock.fileno() == -1:
                return False
            # Kiểm tra xem có lỗi socket từ hệ điều hành không
            r, _, x = select.select([sock], [], [sock], 0)
            if x:
                return False
            if r:
                data = sock.recv(1, socket.MSG_PEEK)
                if len(data) == 0:
                    # Đầu bên kia đã đóng kết nối (EOF/FIN)
                    return False
            return True
        except Exception:
            return False
        finally:
            if have_lock and driver_lock:
                driver_lock.release()

    def _cleanup_old_driver(self):
        """Đóng và giải phóng socket cũ để tránh rò rỉ tài nguyên."""
        driver = getattr(self.core, 'driver_loader', None)
        if driver is not None:
            try:
                if hasattr(driver, 'close'):
                    driver.close()
                elif hasattr(driver, 'sock') and driver.sock:
                    try:
                        driver.sock.close()
                    except Exception:
                        pass
            except Exception:
                pass
            self.core.driver_loader = None

    def stop(self):
        """Dừng tiến trình giám sát an toàn."""
        self.running = False
        self.quit()
        self.wait(2000)
