
import mysql.connector
from module_3.main_thread import intermediate_layer
import sys,os
import threading
import time
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread, Qt
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QLineEdit, 
                             QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, 
                             QFrame, QComboBox, QScrollArea, QMessageBox, QSpinBox,
                             QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
                             QGroupBox)
from module_6.mitsubishi.initial import SocketClient as Mitsubishi_Socket_Client
from module_6.keyence.initial import KeyenceClient as Keyence_Socket_Client
from module_6.omron.initial import OmronClient as Omron_Socket_Client
from datetime import datetime
from app_logger.app_logger import get_logger as _get_logger, open_log_window
import subprocess,re
from module_1.root_path import resource_path, get_mysql_config_path, get_trigger_file_path
from module_1.table_db import _ADMIN_TABLES_SQL,TABLES_SQL_ITEM_CODE_SAVE,TABLES_SQL_DATA_IP_ADDRESS,TABLES_SQL_DATA_AUTO_LOGIN
from module_2.plc_alert_ui import PLCWatchdogSignals, PLCAlertOverlay, PLCSuccessBanner
from module_2.plc_watchdog import PLCWatchdogThread
_log = _get_logger('module_2.main_core')

try:
    from module_3.task_calculator_db import _db_lock
except Exception:
    _db_lock = threading.RLock()

PLC_COLLECT = {
    'KEYENCE'     : Keyence_Socket_Client,
    'OMRON'       : Omron_Socket_Client,
    'MITSHUBISHI' : Mitsubishi_Socket_Client,
}


class CoreWorker(QThread):
    trigger_detected = pyqtSignal(str, str)
    system_action_triggered = pyqtSignal(str, dict)

    def __init__(self, core_instance):
        super().__init__()
        self.core_instance = core_instance
        self.running = True

    def run(self):
        _log.info("[CoreWorker] Running in thread: %s", threading.current_thread().name)
        self.core_instance.startup() 
        while self.running:
            self.core_instance.wait_for_signal()
            time.sleep(0.1)


class core:
    def __init__(self, progress_callback=None):
        _log.info("[core.__init__] START")
        self.progress_callback = progress_callback
        self.dict_list_line   = {}
        self.mode_init        = 0
        self.mode_init_plc    = 0
        self.is_first_startup = True

        self.item_code    = None
        self.line_code    = None
        self.date_time    = None

        self._last_item_code_plc_val: dict[tuple, Any] = {}

        self.connection    = None
        self.driver_loader = None

        self.is_plc_connected = False
        self.startup_plc_failed = False
        self.plc_watchdog_thread = None
        self.plc_signals = PLCWatchdogSignals()
        self._plc_alert_overlay = None
        self._plc_success_banner = None

        self.plc_signals.connection_lost.connect(self._on_plc_connection_lost)
        self.plc_signals.reconnect_attempt.connect(self._on_plc_reconnect_attempt)
        self.plc_signals.connection_restored.connect(self._on_plc_connection_restored)

        self.plc_module                  = "KEYENCE"
        self.connection_port             = "Enthernet"
        self.ip_address_plc              = "192.168.0.10"
        self.port_plc                    = 5000
        self.manual                      = 1
        self.automatic                   = 0
        self.local_ip                    = ""
        self.retry_attempts              = 0
        self.auto_reconnect_on_disconnect = False
        self.direct_to_plc               = True
        self.indirect_from_log           = False

        _log.info("[core.__init__] Creating CoreWorker...")
        self.worker_thread = CoreWorker(self)
        _log.info("[core.__init__] CoreWorker created. Connecting to MySQL...")
        if self.progress_callback:
            self.progress_callback("Đang kết nối cơ sở dữ liệu MySQL...", "Đang tự động phục hồi dịch vụ dữ liệu...", 15)

        connect_result, mode_init = self.connect_to_mysql(progress_callback=self.progress_callback)
        _log.info("[core.__init__] connect_to_mysql done. connect_result=%s", connect_result)
        self.connection = connect_result
        self.mode_init  = mode_init
        if self.connection is not None:
            self.cursor = self.connection.cursor()
            _log.info('Success to initialize connections')
        else:
            _log.warning('Failed to initialize connections')

        if self.progress_callback:
            self.progress_callback("Đang nạp cấu hình giao tiếp PLC...", "Kiểm tra thông số Keyence Ethernet...", 50)
        _log.info("[core.__init__] init_plc_data...")
        self.init_plc_data()
        _log.info("[core.__init__] Connecting trigger signal...")
        self.worker_thread.trigger_detected.connect(self.open_pyuic6)

        self.count = 0
        if self.progress_callback:
            self.progress_callback("Đang nạp danh mục sản phẩm và Item Code...", "Đồng bộ danh sách sản phẩm...", 60)
        _log.info("[core.__init__] collect_dict_item...")
        self.collect_dict_item()

        if self.progress_callback:
            self.progress_callback("Đang cấu hình kịch bản tự động hóa...", "Nạp System Action Configs...", 70)
        _log.info("[core.__init__] reload_system_action_configs...")
        self.system_action_configs = {}
        self._action_cooldowns = {}
        self.reload_system_action_configs()
        _log.info("[core.__init__] DONE")

    def _on_plc_connection_lost(self, module: str, ip: str, port: int, attempts: int):
        """Slot xử lý khi mất kết nối PLC: hiển thị UI cảnh báo đẹp mắt, không khóa giao diện."""
        try:
            if self._plc_success_banner and self._plc_success_banner.isVisible():
                self._plc_success_banner.close()
            if self._plc_alert_overlay is None:
                self._plc_alert_overlay = PLCAlertOverlay()
                if hasattr(self._plc_alert_overlay, 'retry_requested'):
                    self._plc_alert_overlay.retry_requested.connect(self._manual_reconnect_plc)

            self._plc_alert_overlay.set_plc_info(module, ip, port, attempts)

            # Cập nhật thông báo nếu Watchdog đang TẮT theo cấu hình Admin
            try:
                from Administrator.user_db import is_watchdog_enabled
                db_conn = getattr(self, 'cursor', None) or getattr(self, 'connection', None)
                if not is_watchdog_enabled('plc', conn_or_cursor=db_conn):
                    self._plc_alert_overlay.lbl_status.setText(
                        "⚠️ Kết nối PLC thất bại! (Chế độ tự động quét ngầm đang TẮT theo cấu hình Admin)"
                    )
                    if hasattr(self._plc_alert_overlay, 'progress_bar'):
                        self._plc_alert_overlay.progress_bar.setVisible(False)
                else:
                    if hasattr(self._plc_alert_overlay, 'progress_bar'):
                        self._plc_alert_overlay.progress_bar.setVisible(True)
            except Exception:
                pass

            self._plc_alert_overlay.show_alert()
        except Exception as e:
            _log.error("Error in _on_plc_connection_lost: %s", e)

    def _manual_reconnect_plc(self):
        """Thử kết nối lại PLC theo yêu cầu thủ công của người dùng từ giao diện cảnh báo."""
        ip = getattr(self, 'ip_address_plc', '')
        port = getattr(self, 'port_plc', 0)
        module = getattr(self, 'plc_module', 'KEYENCE')
        if not ip or not port:
            return

        if self._plc_alert_overlay:
            self._plc_alert_overlay.lbl_status.setText(f"🔄 Đang thử kết nối lại tới PLC {ip}:{port}...")

        from module_2.plc_watchdog import test_tcp_connection
        if test_tcp_connection(ip, port, timeout=1.5):
            plc_cls = PLC_COLLECT.get(module, Keyence_Socket_Client)
            new_client = plc_cls(ip, port)
            connected = False
            try:
                connected = bool(new_client.connect())
            except Exception as e:
                _log.warning("Manual reconnect PLC exception: %s", e)

            if connected:
                self.driver_loader = new_client
                self.is_plc_connected = True
                self.mode_init_plc = 1
                self.startup_plc_failed = False
                _log.info("[PLC] ✅ Người dùng thử kết nối lại thành công tới %s (%s:%s)!", module, ip, port)
                self._on_plc_connection_restored(module, ip, port)
                return

        _log.warning("[PLC] ❌ Người dùng thử kết nối lại thất bại tới %s (%s:%s)!", module, ip, port)
        if self._plc_alert_overlay:
            self._plc_alert_overlay.lbl_status.setText(f"❌ Không thể kết nối tới PLC tại {ip}:{port}! Vui lòng kiểm tra lại thiết bị.")

    def _on_plc_reconnect_attempt(self, attempts: int):
        """Slot cập nhật số lần thử kết nối lại trên UI cảnh báo."""
        try:
            if self._plc_alert_overlay is None:
                self._plc_alert_overlay = PLCAlertOverlay()
                if hasattr(self._plc_alert_overlay, 'retry_requested'):
                    self._plc_alert_overlay.retry_requested.connect(self._manual_reconnect_plc)

            user_dismissed = getattr(self._plc_alert_overlay, 'user_dismissed', False)
            if not self._plc_alert_overlay.isVisible() and not user_dismissed:
                module = getattr(self, 'plc_module', 'KEYENCE')
                ip = getattr(self, 'ip_address_plc', '')
                port = getattr(self, 'port_plc', 0)
                self._plc_alert_overlay.set_plc_info(module, str(ip), int(port), attempts)
                self._plc_alert_overlay.show_alert()
            else:
                self._plc_alert_overlay.update_attempts(attempts)
        except Exception as e:
            _log.debug("Error in _on_plc_reconnect_attempt: %s", e)

    def _on_plc_connection_restored(self, module: str, ip: str, port: int):
        """Slot xử lý khi khôi phục kết nối thành công: tắt cảnh báo, hiển thị banner thành công 5s."""
        try:
            self.startup_plc_failed = False
            if self._plc_alert_overlay:
                self._plc_alert_overlay.hide_alert()
            if self._plc_success_banner is None:
                self._plc_success_banner = PLCSuccessBanner()
            self._plc_success_banner.show_success(module, ip, port, duration_ms=5000)
        except Exception as e:
            _log.error("Error in _on_plc_connection_restored: %s", e)

    def start_plc_watchdog(self):
        """Khởi động luồng giám sát kết nối PLC liên tục nếu đang ở chế độ kết nối PLC thật và được Administrator cho phép."""
        if self.is_indirect_log_mode() or getattr(self, 'manual', 0) == 1:
            return

        try:
            from Administrator.user_db import is_watchdog_enabled
            db_conn = getattr(self, 'cursor', None) or getattr(self, 'connection', None)
            if not is_watchdog_enabled('plc', conn_or_cursor=db_conn):
                _log.info("[PLC Watchdog] Bị TẮT theo cấu hình của Administrator.")
                return
        except Exception as e:
            _log.debug("Lỗi kiểm tra is_watchdog_enabled('plc'): %s", e)

        if self.plc_watchdog_thread is None or not self.plc_watchdog_thread.isRunning():
            self.plc_watchdog_thread = PLCWatchdogThread(self)
            self.plc_watchdog_thread.is_connected = self.is_plc_connected
            self.plc_watchdog_thread.start()
            _log.info("PLC Watchdog Thread started successfully.")

    def stop_plc_watchdog(self):
        """Dừng luồng giám sát kết nối PLC."""
        if self.plc_watchdog_thread is not None and self.plc_watchdog_thread.isRunning():
            self.plc_watchdog_thread.stop()
            self.plc_watchdog_thread = None
            _log.info("PLC Watchdog Thread stopped.")

    def notify_plc_communication_error(self):
        """
        Được gọi khi _safe_read_plc hoặc _safe_write_plc gặp lỗi socket với PLC thật trong khi đang hoạt động.
        Nếu chế độ giám sát liên tục PLC đang TẮT theo cấu hình Admin, bỏ qua không hiển thị cảnh báo gián đoạn giữa chừng.
        """
        if self.is_indirect_log_mode() or getattr(self, 'manual', 0) == 1:
            return

        try:
            from Administrator.user_db import is_watchdog_enabled
            db_conn = getattr(self, 'cursor', None) or getattr(self, 'connection', None)
            if not is_watchdog_enabled('plc', conn_or_cursor=db_conn):
                return
        except Exception:
            pass

        if self.plc_watchdog_thread is not None:
            if not getattr(self, 'is_plc_connected', False):
                return
            self.plc_watchdog_thread.consecutive_errors += 1
            if self.plc_watchdog_thread.consecutive_errors >= 2:
                self.is_plc_connected = False
                self.mode_init_plc = 0
                self.plc_watchdog_thread.is_connected = False
                self.plc_watchdog_thread.reconnect_attempts = 1
                self.plc_watchdog_thread._cleanup_old_driver()
                if hasattr(self, 'plc_signals'):
                    module = getattr(self, 'plc_module', 'KEYENCE')
                    ip = getattr(self, 'ip_address_plc', '')
                    port = getattr(self, 'port_plc', 0)
                    self.plc_signals.connection_lost.emit(module, str(ip), int(port), 1)
        else:
            self.is_plc_connected = False
            self.mode_init_plc = 0
            self.start_plc_watchdog()
            try:
                from Administrator.user_db import is_watchdog_enabled
                db_conn = getattr(self, 'cursor', None) or getattr(self, 'connection', None)
                if is_watchdog_enabled('plc', conn_or_cursor=db_conn):
                    if hasattr(self, 'plc_signals'):
                        module = getattr(self, 'plc_module', 'KEYENCE')
                        ip = getattr(self, 'ip_address_plc', '')
                        port = getattr(self, 'port_plc', 0)
                        self.plc_signals.connection_lost.emit(module, str(ip), int(port), 1)
            except Exception:
                pass

    def start_monitoring(self):
        self.worker_thread.start()
        _log.info('Success to start monitoring')

    def stop_monitoring(self):
        _log.info('Stopping CoreWorker...')
        self.worker_thread.running = False
        self.worker_thread.quit()
        self.worker_thread.wait()
        self.stop_plc_watchdog()
        if hasattr(self, '_plc_alert_overlay') and self._plc_alert_overlay:
            try:
                self._plc_alert_overlay.close()
            except Exception:
                pass
        if hasattr(self, '_plc_success_banner') and self._plc_success_banner:
            try:
                self._plc_success_banner.close()
            except Exception:
                pass
        if hasattr(self, 'pyuic6_instance') and self.pyuic6_instance:
            _log.info("Reloading program: Closing existing instance for item code: %s", self.item_code)
            self.pyuic6_instance.Close_window()
        else:
            _log.info("No instance of pyuic6_instance found to close")
        _log.info('Success to stop monitoring')

    def read_mysql_config(self, filepath=None):
        if filepath is None:
            filepath = get_mysql_config_path()

        def _parse_file(path):
            if not os.path.exists(path) or os.path.getsize(path) == 0:
                return None
            for enc in ('utf-8', 'utf-8-sig', 'cp1252', 'latin-1'):
                try:
                    cfg = {}
                    with open(path, 'r', encoding=enc) as f:
                        for line in f:
                            if '=' in line:
                                key, value = line.strip().split('=', 1)
                                cfg[key.strip()] = value.strip()
                    if 'host' in cfg and 'user' in cfg:
                        return cfg
                except Exception:
                    continue
            return None

        try:
            config = _parse_file(filepath)
            if config is not None:
                return config

            bak_path = filepath + '.bak'
            if os.path.exists(bak_path):
                _log.warning("File cấu hình %s không hợp lệ. Đang tự động khôi phục từ backup %s", filepath, bak_path)
                config_bak = _parse_file(bak_path)
                if config_bak is not None:
                    try:
                        import shutil
                        shutil.copy2(bak_path, filepath)
                        _log.info("Khôi phục thành công file %s từ %s", filepath, bak_path)
                    except Exception as copy_err:
                        _log.debug("Lỗi copy file .bak sang .log: %s", copy_err)
                    return config_bak

        except FileNotFoundError:
            _log.warning("Config file not found: %s", filepath)
            return None
        except Exception as e:
            _log.error("Error reading config file: %s", e)
            return None
        return None

    def connect_mysql_from_log(self, filepath=None, retries=40, delay=1.5, progress_callback=None):
        if filepath is None:
            filepath = get_mysql_config_path()
        _log.info("[connect_mysql_from_log] Reading config from %s", filepath)
        config = self.read_mysql_config(filepath)
        if not config:
            fallback_path = resource_path("module_2/mysql_config.log")
            if fallback_path != filepath:
                _log.info("[connect_mysql_from_log] Trying fallback config from %s", fallback_path)
                config = self.read_mysql_config(fallback_path)
            if not config:
                _log.warning("[connect_mysql_from_log] No config found, using safe local defaults")
                config = {'host': '127.0.0.1', 'user': 'root', 'password': '', 'port': 3306}

        host     = config.get('host', '127.0.0.1')
        user     = config.get('user', 'root')
        password = config.get('password', '')
        port     = int(config.get('port', 3306))

        candidate_hosts = [host]
        if host in ('127.0.0.1', 'localhost'):
            alt = 'localhost' if host == '127.0.0.1' else '127.0.0.1'
            if alt not in candidate_hosts:
                candidate_hosts.append(alt)

        progress_dialog = None
        cb = progress_callback or getattr(self, 'progress_callback', None)

        for attempt in range(1, retries + 1):

            if attempt in (2, 5) and any(h in ('127.0.0.1', 'localhost') for h in candidate_hosts):
                try:
                    import subprocess
                    check_svc = subprocess.run(['sc.exe', 'query', 'MySQL80'], capture_output=True, text=True, timeout=3)
                    if 'STOPPED' in check_svc.stdout:
                        _log.info("[connect_mysql_from_log] Dịch vụ MySQL80 đang bị STOPPED! Đang gửi lệnh start...")
                        subprocess.run(['sc.exe', 'start', 'MySQL80'], capture_output=True, text=True, timeout=5)
                        subprocess.run(['net', 'start', 'MySQL80'], capture_output=True, text=True, timeout=5)
                except Exception as svc_err:
                    _log.debug("Lỗi kiểm tra service MySQL80: %s", svc_err)

            if cb:
                calc_pct = min(45, 15 + int(attempt * 0.75))
                cb(
                    f"Đang chờ dịch vụ MySQL Server sẵn sàng... ({attempt}/{retries})",
                    "Hệ thống đang tự động phục hồi kết nối dữ liệu sau khi bật nguồn...",
                    calc_pct
                )
            else:
                if attempt == 2:
                    try:
                        from PyQt5.QtWidgets import QApplication, QProgressDialog
                        app = QApplication.instance()
                        if app:
                            progress_dialog = QProgressDialog(
                                "Đang chờ khởi tạo dịch vụ MySQL Server (Đang phục hồi sau khi khởi động PC)...",
                                None, 0, retries
                            )
                            progress_dialog.setWindowTitle("Khởi tạo MySQL Database")
                            progress_dialog.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
                            progress_dialog.setMinimumWidth(500)
                            progress_dialog.setCancelButton(None)
                            progress_dialog.setValue(attempt)
                            progress_dialog.show()
                            app.processEvents()
                    except Exception:
                        progress_dialog = None

                if progress_dialog is not None:
                    try:
                        progress_dialog.setValue(attempt)
                        progress_dialog.setLabelText(
                            f"Đang chờ dịch vụ MySQL Server sẵn sàng... (Lần thử {attempt}/{retries})\n"
                            f"Hệ thống đang tự động phục hồi dữ liệu sau khi cấp lại nguồn điện."
                        )
                        from PyQt5.QtWidgets import QApplication
                        QApplication.instance().processEvents()
                    except Exception:
                        pass

            last_err = None
            for h in candidate_hosts:
                for ssl_opt in (True, False):
                    try:
                        conn_params = {
                            'host': h,
                            'user': user,
                            'password': password,
                            'port': port,
                            'use_pure': True,
                            'connection_timeout': 3
                        }
                        if ssl_opt:
                            conn_params['ssl_disabled'] = True
                        connection = mysql.connector.connect(**conn_params)
                        if connection and connection.is_connected():
                            _log.info('[connect_mysql_from_log] Success to connect mysql on attempt %d (host=%s, ssl_disabled=%s)', attempt, h, ssl_opt)
                            if cb:
                                cb("Kết nối cơ sở dữ liệu MySQL thành công!", "Dịch vụ MySQL Server đã sẵn sàng hoạt động.", 45)
                            if progress_dialog is not None:
                                try:
                                    progress_dialog.close()
                                except Exception:
                                    pass
                            return connection
                    except Exception as err:
                        last_err = err
                        continue

            _log.warning('[connect_mysql_from_log] Attempt %d/%d failed: %s', attempt, retries, last_err)

            if attempt in (2, 4, 10):
                _log.info("[connect_mysql_from_log] Kích hoạt tự động đăng nhập cứu hộ (fallback pass 123456789)...")
                fallback_conn = self.auto_login_fallback()
                if fallback_conn and fallback_conn.is_connected():
                    if progress_dialog is not None:
                        try:
                            progress_dialog.close()
                        except Exception:
                            pass
                    return fallback_conn

            if attempt < retries:
                time.sleep(delay)
            else:
                _log.error('[connect_mysql_from_log] All %d attempts failed to connect to MySQL. Last error: %s', retries, last_err)
                if progress_dialog is not None:
                    try:
                        progress_dialog.close()
                    except Exception:
                        pass

                return self.auto_login_fallback()

        if progress_dialog is not None:
            try:
                progress_dialog.close()
            except Exception:
                pass
        return self.auto_login_fallback()

    def auto_login_fallback(self):
        """
        Cơ chế tự động đăng nhập khẩn cấp tương tự module_5/mysql.py:
        Tự động thử các tổ hợp kết nối chuẩn (127.0.0.1, localhost, pass 123456789, rỗng).
        Khi kết nối thành công, tự động cập nhật DATA_AUTO_LOGIN.INFOR (chế độ Auto)
        và ghi lại file mysql_config.log để các lần sau vào thẳng phần mềm mà không cần thao tác tay.
        """
        hosts = ['127.0.0.1', 'localhost']
        passwords = ['123456789', '', 'root']
        ports = [3306]

        _log.info("[auto_login_fallback] Bắt đầu tự động quét kết nối MySQL cứu hộ (hardcode pass 123456789)...")

        for h in hosts:
            for p in passwords:
                for port in ports:
                    for ssl_disabled in (True, False):
                        try:
                            conn_params = {
                                'host': h,
                                'user': 'root',
                                'password': p,
                                'port': port,
                                'use_pure': True,
                                'connection_timeout': 2
                            }
                            if ssl_disabled:
                                conn_params['ssl_disabled'] = True

                            conn = mysql.connector.connect(**conn_params)
                            if conn and conn.is_connected():
                                _log.info("[auto_login_fallback] Tự động đăng nhập THÀNH CÔNG (host=%s, user=root, port=%d)!", h, port)
                                
                                try:
                                    cur = conn.cursor()
                                    cur.execute("CREATE DATABASE IF NOT EXISTS `DATA_AUTO_LOGIN`")
                                    cur.execute("""
                                        CREATE TABLE IF NOT EXISTS `DATA_AUTO_LOGIN`.`INFOR` (
                                            id INT AUTO_INCREMENT PRIMARY KEY,
                                            hostname VARCHAR(255),
                                            username VARCHAR(255),
                                            password VARCHAR(255),
                                            port VARCHAR(255),
                                            manual BOOLEAN DEFAULT FALSE,
                                            automatic BOOLEAN DEFAULT FALSE,
                                            credential BOOLEAN DEFAULT FALSE,
                                            retry_attemps INT NOT NULL DEFAULT 0
                                        )
                                    """)
                                    cur.execute("DELETE FROM `DATA_AUTO_LOGIN`.`INFOR`")
                                    cur.execute("""
                                        INSERT INTO `DATA_AUTO_LOGIN`.`INFOR` (
                                            hostname, username, password, port, manual, automatic, retry_attemps
                                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    """, (h, 'root', p, str(port), False, True, 0))
                                    conn.commit()
                                    cur.close()
                                    _log.info("[auto_login_fallback] Đã tự động cập nhật CSDL DATA_AUTO_LOGIN sang chế độ Auto!")
                                except Exception as db_err:
                                    _log.warning("[auto_login_fallback] Lỗi ghi DB INFOR: %s", db_err)

                                try:
                                    self.write_mysql_config(host=h, user='root', password=p, port=port, database='DATA_AUTO_LOGIN')
                                    _log.info("[auto_login_fallback] Đã tự động ghi lại file cấu hình mysql_config.log!")
                                except Exception as cfg_err:
                                    _log.warning("[auto_login_fallback] Lỗi ghi file config: %s", cfg_err)

                                return conn
                        except Exception:
                            continue

        _log.warning("[auto_login_fallback] Không thể tự động kết nối qua các tổ hợp dự phòng.")
        return None

    def write_mysql_config(self, host, user, password, port, database, filepath=None):
        if filepath is None:
            filepath = get_mysql_config_path(for_writing=True)
        try:
            tmp_path = filepath + '.tmp'
            bak_path = filepath + '.bak'

            with open(tmp_path, 'w', encoding='utf-8') as f:
                f.write(f"host={host}\n")
                f.write(f"user={user}\n")
                f.write(f"password={password}\n")
                f.write(f"port={port}\n")
                f.write(f"database={database}\n")
                f.flush()
                os.fsync(f.fileno())

            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                try:
                    import shutil
                    shutil.copy2(filepath, bak_path)
                except Exception:
                    pass

            os.replace(tmp_path, filepath)

            try:
                import shutil
                shutil.copy2(filepath, bak_path)
            except Exception:
                pass

            _log.info('Success to write mysql config to %s and backup %s', filepath, bak_path)
            return True
        except Exception as e:
            _log.warning('Failed to write mysql config: %s', e)
            return False

    def create_table_data_save_default(self, connection):
        cursor = connection.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS `ITEM_CODE_SAVE`")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `ITEM_CODE_SAVE`.`DATA_SAVE_DEFAULT` (
                id               INT AUTO_INCREMENT PRIMARY KEY,
                name_item_code   VARCHAR(255),
                name_line        VARCHAR(255),
                mode_name        VARCHAR(255),
                date_time        DATETIME NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `ITEM_CODE_SAVE`.`CAMERA_MODE_SAVE_DEFAULT` (
                id               INT AUTO_INCREMENT PRIMARY KEY,
                camera_key       VARCHAR(255) NOT NULL,
                mode_key         VARCHAR(255) NOT NULL,
                item_code        VARCHAR(255) DEFAULT '',
                date_time        DATETIME NOT NULL,
                UNIQUE KEY uq_camera_key (camera_key)
            )
        """)
        connection.commit()
        cursor.close()

    def connect_to_mysql(self, progress_callback=None):
        cb = progress_callback or getattr(self, 'progress_callback', None)
        connection = None
        while connection is None:
            _log.info("[connect_to_mysql] Calling connect_mysql_from_log...")
            connection = self.connect_mysql_from_log(retries=40, delay=1.5, progress_callback=cb)
            _log.info("[connect_to_mysql] connect_mysql_from_log returned: %s", connection)
            if connection is not None:
                break

            _log.info("[connect_to_mysql] connect_mysql_from_log thất bại, kích hoạt auto_login_fallback...")
            connection = self.auto_login_fallback()
            if connection is not None:
                _log.info("[connect_to_mysql] auto_login_fallback thành công, bỏ qua hộp thoại chờ!")
                break

            _log.info("[connect_to_mysql] Showing retry question...")
            reply = QMessageBox.question(
                None,
                "Không thể kết nối đến MySQL",
                "Dịch vụ MySQL Server chưa phản hồi sau 60 giây chờ đợi.\n"
                "(Có thể máy tính vừa bị ngắt điện đột ngột và dịch vụ MySQL vẫn đang phục hồi dữ liệu InnoDB).\n\n"
                "Bạn có muốn tiếp tục chờ và thử kết nối lại không?",
                QMessageBox.Retry | QMessageBox.Cancel,
                QMessageBox.Retry
            )
            if reply != QMessageBox.Retry:
                _log.warning("[connect_to_mysql] User cancelled connection retry.")
                return None, 0
    
        _log.info("[connect_to_mysql] Creating default table...")
        try:
            cursor = connection.cursor()
            for sql in _ADMIN_TABLES_SQL:
                cursor.execute(sql)
            for sql in TABLES_SQL_ITEM_CODE_SAVE:
                cursor.execute(sql)
            for sql in TABLES_SQL_DATA_IP_ADDRESS:
                cursor.execute(sql)
            for sql in TABLES_SQL_DATA_AUTO_LOGIN:
                cursor.execute(sql)
            connection.commit()
            cursor.close()
        except Exception as e:
            _log.warning('Failed to create default table: %s', e)

        try:
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM `DATA_AUTO_LOGIN`.`INFOR`")
            result = cursor.fetchall()

            if not result:
                cursor.execute("""
                    INSERT IGNORE INTO `DATA_AUTO_LOGIN`.`INFOR` (
                        hostname, username, password, port, manual, automatic, retry_attemps
                    ) VALUES (%s, %s, %s, %s, 0, 1, 0)
                """, ('127.0.0.1', 'root', '', '3306'))
                connection.commit()
                cursor.close()
                _log.info("[connect_to_mysql] Tự động khởi tạo cấu hình Auto-login mặc định")
                return connection, 1

            manual    = bool(result[0][5])
            automatic = bool(result[0][6])
            cursor.close()

            if manual and not automatic:
                _log.info("[connect_to_mysql] Kết nối MySQL thành công (Chế độ Manual theo thiết lập người dùng)")
                return connection, 0
            else:
                _log.info("[connect_to_mysql] Kết nối MySQL thành công (Tự động kích hoạt chế độ Auto-login)")
                return connection, 1

        except Exception as e:
            _log.error("Error in connect_to_mysql: %s", e)
            return connection, 1

        return connection, 0

    def init_plc_data(self):
        if not self.connection:
            _log.info("No connection to MySQL in init_plc_data")
            return
        try:
            cursor = self.connection.cursor()

            # Đảm bảo các cột mới tồn tại trong CSDL MySQL
            columns_to_check = [
                ("connection_port", "VARCHAR(255) DEFAULT 'Enthernet' AFTER plc_module"),
                ("local_ip", "VARCHAR(255) DEFAULT '' AFTER automatic"),
                ("retry_attempts", "INT NOT NULL DEFAULT 0 AFTER local_ip"),
                ("auto_reconnect_on_disconnect", "BOOLEAN DEFAULT FALSE AFTER retry_attempts"),
                ("direct_to_plc", "BOOLEAN DEFAULT TRUE AFTER auto_reconnect_on_disconnect"),
                ("indirect_from_log", "BOOLEAN DEFAULT FALSE AFTER direct_to_plc"),
            ]
            for col_name, col_def in columns_to_check:
                try:
                    cursor.execute(f"SHOW COLUMNS FROM `DATA_IP_ADDRESS`.`INFOR_ADDRESS` LIKE '{col_name}'")
                    if not cursor.fetchone():
                        cursor.execute(f"ALTER TABLE `DATA_IP_ADDRESS`.`INFOR_ADDRESS` ADD COLUMN {col_name} {col_def}")
                except Exception as col_err:
                    _log.debug("Column check error for %s: %s", col_name, col_err)
            self.connection.commit()

            cursor.execute("""
                SELECT plc_module, connection_port, ip_address_plc, port_plc,
                       manual, automatic, local_ip, retry_attempts,
                       auto_reconnect_on_disconnect, direct_to_plc, indirect_from_log
                FROM `DATA_IP_ADDRESS`.`INFOR_ADDRESS`
            """)
            result = cursor.fetchall()
            cursor.close()

            if not result:
                _log.warning("No PLC info found in DATA_IP_ADDRESS.INFOR_ADDRESS")
                return

            row = result[0]
            plc_module       = str(row[0] or "KEYENCE")
            connection_port  = str(row[1] or "Enthernet")
            ip_address_plc   = str(row[2] or "192.168.0.10")
            port_plc         = int(row[3] or 5000)
            manual           = bool(row[4])
            automatic        = bool(row[5])
            local_ip         = str(row[6] or "")
            retry_attempts   = int(row[7] or 0)
            auto_reconnect   = bool(row[8])
            direct_to_plc    = bool(row[9])
            indirect_from_log = bool(row[10])

            self.plc_module                  = plc_module
            self.connection_port             = connection_port
            self.ip_address_plc              = ip_address_plc
            self.port_plc                    = port_plc
            self.manual                      = manual
            self.automatic                   = automatic
            self.local_ip                    = local_ip
            self.retry_attempts              = retry_attempts
            self.auto_reconnect_on_disconnect = auto_reconnect
            self.direct_to_plc               = direct_to_plc
            self.indirect_from_log           = indirect_from_log

            # -------------------------------------------------------------
            # Lựa chọn giữa kết nối trực tiếp PLC thật hoặc mô phỏng qua LOG
            # -------------------------------------------------------------
            plc_cls = PLC_COLLECT.get(plc_module, Keyence_Socket_Client)

            if indirect_from_log:
                # Chế độ mô phỏng qua file log (không cần thiết bị PLC vật lý)
                plc_instance = plc_cls(ip_address_plc, port_plc)
                self.driver_loader = plc_instance
                self.mode_init_plc = 1
                self.is_plc_connected = True
                _log.info('PLC Simulation via Log Mode ACTIVE [indirect_from_log=True] for %s (%s:%s)', plc_module, ip_address_plc, port_plc)
            elif not manual and automatic:
                # Chế độ kết nối trực tiếp đến PLC thật
                plc_instance = plc_cls(ip_address_plc, port_plc)
                connected = False
                try:
                    connected = bool(plc_instance.connect())
                except Exception as e_conn:
                    _log.warning("Exception connecting real PLC: %s", e_conn)
                    connected = False

                if connected:
                    self.driver_loader = plc_instance
                    self.mode_init_plc = 1
                    self.is_plc_connected = True
                    self.startup_plc_failed = False
                    _log.info('Success to connect real PLC %s at %s:%s', plc_module, ip_address_plc, port_plc)
                else:
                    self.driver_loader = None
                    self.mode_init_plc = 0
                    self.is_plc_connected = False
                    self.startup_plc_failed = True
                    _log.warning('Failed to connect real PLC %s at %s:%s on startup. Triggering alert overlay.', plc_module, ip_address_plc, port_plc)
                    if hasattr(self, 'plc_signals'):
                        self.plc_signals.connection_lost.emit(plc_module, str(ip_address_plc), int(port_plc), 1)

                # Bắt đầu Watchdog theo dõi liên tục và tự động kết nối lại ngầm (nếu được Admin cho phép)
                self.start_plc_watchdog()
            else:
                self.is_plc_connected = False
                _log.warning('PLC connection disabled in settings (Manual mode active)')

        except Exception as e:
            _log.error("Error in init_plc_data: %s", e)

    def collect_dict_item(self):
        if self.connection and self.mode_init:
            _log.info('Mode Automatic Login in MySQL (Optimized)')
            with _db_lock:
                try:
                    query_find_dbs = "SELECT TABLE_SCHEMA FROM information_schema.TABLES WHERE TABLE_NAME = 'ITEMS_CODE'"
                    self.cursor.execute(query_find_dbs)
                    databases = [row[0] for row in self.cursor.fetchall()]

                    for name_line in databases:
                        query_get_items = f"SELECT name_line_code, assign_register, value_bit_on, value_bit_off FROM {name_line}.ITEMS_CODE"
                        self.cursor.execute(query_get_items)
                        item_codes = self.cursor.fetchall()

                        self.dict_list_line[name_line] = [
                            {'item_code': row[0], 'register': row[1], 'value_bit_on': row[2], 'value_bit_off': row[3]} for row in item_codes
                        ]

                    self.reset_item_code_plc_latch()
                    _log.info("Successfully loaded items from %d databases", len(databases))
                except Exception as e:
                    _log.error("Error in collect_dict_item: %s", e)
        else:
            _log.warning('Mode Manual Login or No Connection')

    def open_pyuic6(self, item_code, name_line):
        if self.connection:
            from app_utils.progress_bar import AppProgressBar
            
            progress = AppProgressBar(message="Đang khởi tạo giao diện...")

            if hasattr(self, 'pyuic6_instance') and self.pyuic6_instance:
                _log.info("Reloading program: Closing existing instance for item code: %s", self.item_code)
                self.pyuic6_instance.Close_window()
            self.pyuic6_instance = intermediate_layer(item_code, name_line, self, self.mode_init, progress_callback=progress.update_progress)
            
            progress.close()

    def is_indirect_log_mode(self) -> bool:
        """
        Kiểm tra chế độ giao tiếp PLC được cấu hình:
        - True: Chế độ mô phỏng qua LOG (indirect_from_log = True hoặc direct_to_plc = False)
        - False: Chế độ kết nối trực tiếp thiết bị PLC (direct_to_plc = True)
        """
        if bool(getattr(self, 'direct_to_plc', False)) is True and not bool(getattr(self, 'indirect_from_log', False)):
            return False
        if bool(getattr(self, 'indirect_from_log', False)) is True:
            return True
        if hasattr(self, 'direct_to_plc') and bool(getattr(self, 'direct_to_plc')) is False:
            return True

        try:
            with _db_lock:
                if self.connection and hasattr(self.connection, 'cursor'):
                    cursor = self.connection.cursor()
                    cursor.execute("SELECT direct_to_plc, indirect_from_log FROM `DATA_IP_ADDRESS`.`INFOR_ADDRESS` LIMIT 1")
                    row = cursor.fetchone()
                    cursor.close()
                    if row:
                        direct_to_plc, indirect_from_log = bool(row[0]), bool(row[1])
                        return indirect_from_log or (not direct_to_plc)
        except Exception:
            pass

        return False

    def _safe_read_plc(self, register: str):
        """
        Đọc PLC an toàn:
        - Nếu user chọn indirect_from_log: Sử dụng _safe_read_plc_log để đọc từ log mô phỏng.
        - Nếu user chọn direct_to_plc: Sử dụng đọc trực tiếp từ thiết bị PLC.
        """
        if not register or str(register).strip() == "":
            return None

        if self.is_indirect_log_mode():
            return self._safe_read_plc_log(register)

        if not getattr(self, 'is_plc_connected', True) or self.driver_loader is None:
            return None
        try:
            val = self.driver_loader.read_plc(register)
            if val is None:
                self.notify_plc_communication_error()
            else:
                if self.plc_watchdog_thread is not None:
                    self.plc_watchdog_thread.consecutive_errors = 0
            return val
        except Exception as e:
            _log.debug("_safe_read_plc exception on %s: %s", register, e)
            self.notify_plc_communication_error()
            return None

    def _safe_write_plc(self, register: str, value):
        """
        Ghi PLC an toàn:
        - Nếu value là None, rỗng ("") hoặc "No Value": bỏ qua không ghi.
        - Nếu user chọn indirect_from_log: Sử dụng _safe_write_plc_log để ghi vào log mô phỏng.
        - Nếu user chọn direct_to_plc: Sử dụng ghi trực tiếp xuống thiết bị PLC.
        """
        if value is None:
            return None
        val_str = str(value).strip()
        if val_str == "" or val_str.lower() in ("none", "no value"):
            return None

        if self.is_indirect_log_mode():
            return self._safe_write_plc_log(register, value)

        if not getattr(self, 'is_plc_connected', True) or self.driver_loader is None:
            return None
        try:
            val_to_write = int(val_str) if val_str.lstrip('-').isdigit() else val_str
            res = self.driver_loader.write_plc(register, val_to_write)
            if self.plc_watchdog_thread is not None:
                self.plc_watchdog_thread.consecutive_errors = 0
            return res
        except Exception as e:
            _log.debug("_safe_write_plc exception on %s: %s", register, e)
            self.notify_plc_communication_error()
            return None

    def _safe_read_plc_log(self, register: str):
        """Đọc PLC từ file log mô phỏng (trigger_{register}.txt)."""
        if self.driver_loader is not None and hasattr(self.driver_loader, 'read_plc_log'):
            try:
                return self.driver_loader.read_plc_log(register)
            except Exception:
                pass

        try:
            file_path = get_trigger_file_path(register, for_writing=False)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    line = f.readline().strip()
                    if '=' in line:
                        reg, val = line.split('=')
                        if reg.strip().upper() == register.strip().upper():
                            return int(val.strip())
            return 0
        except Exception:
            return 0

    def _safe_write_plc_log(self, register: str, value):
        """Ghi PLC vào file log mô phỏng (trigger_{register}.txt)."""
        if value is None:
            return False
        val_str = str(value).strip()
        if val_str == "" or val_str.lower() in ("none", "no value"):
            return False

        if self.driver_loader is not None and hasattr(self.driver_loader, 'write_plc_log'):
            try:
                return self.driver_loader.write_plc_log(register, value)
            except Exception:
                pass

        try:
            file_path = get_trigger_file_path(register, for_writing=True)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"{register} = {value}\n")
            return True
        except Exception as e:
            _log.debug("_safe_write_plc_log fallback failed on %s: %s", register, e)
            return False

    def reload_system_action_configs(self):
        try:
            from module_2.manage_system_actions import get_system_action_config
            self.system_action_configs = {
                "RESTART": get_system_action_config("RESTART", self.connection),
                "CLOSE": get_system_action_config("CLOSE", self.connection)
            }
            _log.info("System action configs reloaded successfully: %s", list(self.system_action_configs.keys()))
        except Exception as e:
            _log.warning("Could not reload system action configs: %s", e)

    def check_system_action_triggers(self):
        if not self.is_indirect_log_mode() and (not hasattr(self, 'driver_loader') or self.driver_loader is None):
            return
        if not hasattr(self, 'system_action_configs') or not self.system_action_configs:
            return

        now = time.time()
        if not hasattr(self, '_action_cooldowns'):
            self._action_cooldowns = {}

        for action_type, cfg in self.system_action_configs.items():
            if not cfg.get("enabled"):
                continue
            register = str(cfg.get("register", "")).strip()
            if not register:
                continue

            last_trig = self._action_cooldowns.get(action_type, 0)
            if now - last_trig < 15:
                continue

            try:
                current_value = self._safe_read_plc(register)
                val_on = int(cfg.get("value_bit_on", 1))
                if current_value is not None and int(current_value) == val_on:
                    self._action_cooldowns[action_type] = now
                    _log.info("PLC System Action Trigger detected: %s on register %s = %s", action_type, register, current_value)

                    if cfg.get("auto_write_off"):
                        val_off_str = str(cfg.get("value_bit_off", "0")).strip()
                        if val_off_str.lower() not in ('none', 'no value', ''):
                            self._safe_write_plc(register, val_off_str)
                            _log.info("Handshake OFF written to %s = %s", register, val_off_str)

                    if hasattr(self, 'worker_thread') and self.worker_thread:
                        self.worker_thread.system_action_triggered.emit(action_type, cfg)
            except Exception as e:
                _log.debug("Error checking system action %s on %s: %s", action_type, register, e)

    def reset_item_code_plc_latch(self):
        """Reset latch đọc thanh ghi mã hàng PLC để cho phép đọc lại giá trị kích hoạt."""
        if hasattr(self, '_last_item_code_plc_val') and isinstance(self._last_item_code_plc_val, dict):
            self._last_item_code_plc_val.clear()

    def wait_for_signal(self):
        # Kiểm tra lệnh Restart / Close từ PLC
        self.check_system_action_triggers()

        if not self.is_indirect_log_mode() and (not self.dict_list_line or self.driver_loader is None):
            return
        if self.is_indirect_log_mode() and not self.dict_list_line:
            return

        if not hasattr(self, '_last_item_code_plc_val') or not isinstance(self._last_item_code_plc_val, dict):
            self._last_item_code_plc_val = {}

        # Cache đọc PLC trong một lượt quét: tránh đọc lặp lại khi nhiều mã hàng dùng chung 1 thanh ghi
        plc_read_cache: dict[str, Any] = {}

        for name_line, values in list(self.dict_list_line.items()):
            for entry in values:
                item_code = entry.get('item_code')
                register  = entry.get('register')
                value_bit_on = entry.get('value_bit_on')
                value_bit_off = entry.get('value_bit_off')

                if not register or str(register).strip() == "" or str(register).strip().lower() in ('none', 'no value'):
                    continue

                if value_bit_on is None or str(value_bit_on).strip() == "" or str(value_bit_on).strip().lower() in ('none', 'no value'):
                    continue

                try:
                    target_on = int(value_bit_on)
                except (ValueError, TypeError):
                    continue

                reg_str = str(register).strip()

                try:
                    # Đọc có đệm trong lượt quét hiện tại
                    if reg_str in plc_read_cache:
                        current_value = plc_read_cache[reg_str]
                    else:
                        current_value = self._safe_read_plc(register)
                        plc_read_cache[reg_str] = current_value

                    if current_value is None or str(current_value).strip() == "":
                        continue

                    try:
                        plc_val = int(current_value)
                    except (ValueError, TypeError):
                        continue

                    # Cơ chế single-read latch: chỉ xử lý khi giá trị thay đổi (rising edge / edge-triggered)
                    # Định danh theo (name_line, item_code, reg_str) để hỗ trợ nhiều mã hàng dùng chung 1 thanh ghi
                    latch_key = (name_line, item_code, reg_str)
                    last_val = self._last_item_code_plc_val.get(latch_key)
                    if last_val is not None and last_val == plc_val:
                        continue

                    # Cập nhật latch giá trị vừa đọc từ PLC
                    self._last_item_code_plc_val[latch_key] = plc_val

                    # Chỉ kích hoạt mã hàng khi giá trị chuyển sang đúng value_bit_on
                    if plc_val != target_on:
                        continue

                    _log.info("PLC Trigger detected: %s = %d (Line: %s, Item: %s)", reg_str, target_on, name_line, item_code)

                    # Tắt bit kích hoạt (handshake với PLC nếu có value_bit_off)
                    if value_bit_off is not None and str(value_bit_off).strip() != "" and str(value_bit_off).strip().lower() not in ('none', 'no value'):
                        try:
                            self._safe_write_plc(register, value_bit_off)
                            if reg_str in plc_read_cache:
                                del plc_read_cache[reg_str]
                        except Exception as e:
                            _log.error("Error writing handshake OFF to %s: %s", register, e)

                    date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.item_code = item_code
                    self.line_code = name_line
                    self.write_data_save_default(date_time, item_code, name_line)

                    self.worker_thread.trigger_detected.emit(item_code, name_line)
                except Exception as e:
                    _log.error("Error while reading trigger %s for item %s: %s", register, item_code, e)

    def startup(self):
        if self.connection and self.mode_init:
            if self.is_first_startup:
                self.is_first_startup = False
                result = self.read_data_save_default()
                if result:
                    _log.info(
                        "Auto-restoring from last saved state: %s, %s (saved at %s)",
                        result[0][0], result[0][1], result[0][2]
                    )
                    restored_item = result[0][0]
                    restored_line = result[0][1]
                    self.item_code = restored_item
                    self.line_code = restored_line

                    # Đồng bộ latch để tránh reload lặp lại nếu PLC vẫn giữ nguyên thanh ghi của mã hàng này
                    if hasattr(self, '_last_item_code_plc_val') and isinstance(self._last_item_code_plc_val, dict):
                        for n_line, entries in self.dict_list_line.items():
                            if n_line == restored_line:
                                for entry in entries:
                                    if entry.get('item_code') == restored_item:
                                        reg = entry.get('register')
                                        val_on = entry.get('value_bit_on')
                                        if reg and val_on is not None:
                                            try:
                                                self._last_item_code_plc_val[(n_line, restored_item, str(reg).strip())] = int(val_on)
                                            except (ValueError, TypeError):
                                                pass

                    self.worker_thread.trigger_detected.emit(restored_item, restored_line)
                else:
                    _log.warning('No data save default')

    def write_data_save_default(self, date_time, item_code, name_line):
        if not self.connection:
            _log.info("No connection to MySQL in write_data_save_default")
            return
        with _db_lock:
            try:
                cursor = self.connection.cursor()
                cursor.execute("DELETE FROM `ITEM_CODE_SAVE`.`DATA_SAVE_DEFAULT`")
                self.connection.commit()
                cursor.execute(
                    "INSERT INTO `ITEM_CODE_SAVE`.`DATA_SAVE_DEFAULT` (date_time, name_item_code, name_line) VALUES (%s, %s, %s)",
                    (date_time, item_code, name_line)
                )
                self.connection.commit()
                cursor.close()
                _log.info('Success to write data save default: %s, %s', item_code, name_line)
            except Exception as e:
                _log.error("Error writing data save default: %s", e)

    def read_data_save_default(self):
        if not self.connection:
            _log.info("No connection to MySQL in read_data_save_default")
            return None
        with _db_lock:
            try:
                cursor = self.connection.cursor()
                cursor.execute("SELECT name_item_code, name_line, date_time FROM `ITEM_CODE_SAVE`.`DATA_SAVE_DEFAULT`")
                result = cursor.fetchall()
                cursor.close()
                return result
            except Exception as e:
                _log.error("Error reading data save default: %s", e)
                return None

        
    def query_hardware_key(self, show_dialog=True):
        if not self.connection and not getattr(self, '_hardware_key_cache', None):
            _log.warning("No database connection. Bypassing hardware key check to allow GUI configuration.")
            return True
        serial_hardware_key = self.get_serial_hardware_key()
        if not serial_hardware_key:
            if show_dialog:
                QMessageBox.warning(
                    None,
                    "No License found!",
                    "No License found! \nPlease insert USB Hardware Key to continue!\n\n"
                )
            return False
        else:
            usb_list = self.get_connected_usb_serials()
            registered_hashes = set()
            for row in serial_hardware_key:
                if row and row[0]:
                    registered_hashes.add(str(row[0]).strip().upper())

            for usb in usb_list:
                s_exact = str(usb.get('serial', '')).strip().upper()
                s_upper = str(usb.get('serial_upper', '')).strip().upper()
                if s_exact in registered_hashes or s_upper in registered_hashes:
                    _log.debug('Success to check hardware key: %s (%s)', usb.get('model'), usb.get('raw_serial'))
                    return True

            if show_dialog:
                QMessageBox.warning(
                    None,
                    "No License found!",
                    "No License found! \n Please insert USB Hardware Key to continue!\n\n"
                )
            return False

    def is_hardware_key_valid(self) -> bool:
        """Kiểm tra USB Hardware Key âm thầm, không hiển thị hộp thoại cảnh báo."""
        return self.query_hardware_key(show_dialog=False)

    def get_serial_hardware_key(self):
        """
        Lấy danh sách mã băm hash_code của các USB Key hợp lệ đã đăng ký.
        Có cơ chế Thread-safe (kết hợp cache lock và _db_lock toàn cục) và Cache trên RAM
        để tránh xung đột kết nối MySQL giữa các luồng.
        """
        if not hasattr(self, '_hardware_key_cache'):
            self._hardware_key_cache = None
            self._hardware_key_cache_lock = threading.RLock()

        with self._hardware_key_cache_lock:
            if not self.connection:
                if self._hardware_key_cache is not None:
                    return self._hardware_key_cache
                return None
            with _db_lock:
                try:
                    cursor = self.connection.cursor(buffered=True)
                    cursor.execute("SELECT hash_code FROM ADMINISTRATOR.HARDWARE_KEY_CONFIG WHERE is_enabled = 1")
                    result = cursor.fetchall()
                    cursor.close()
                    if result:
                        self._hardware_key_cache = result
                    return result
                except Exception as e:
                    _log.warning("Lỗi truy vấn hardware key từ CSDL (dùng RAM cache nếu có): %s", e)
                    if self._hardware_key_cache is not None:
                        return self._hardware_key_cache
                    return None

    def get_connected_usb_serials(self) -> list:
        """
        Quét tất cả USB đang cắm và tạo Hardware ID (HWID) bảo mật.
        Sử dụng Windows Native API (cfgmgr32.dll) siêu nhanh (2ms), 
        fallback sang PowerShell nếu cần.
        """
        import hashlib
        import ctypes
        import subprocess

        usb_list = []
        salt = "AI_VISION_PRO_SECURE_SALT_"

        # 1. Quét bằng Windows Native API (cfgmgr32.dll) - Cực nhanh (~2ms), không tốn CPU, không timeout
        try:
            cfgmgr32 = ctypes.windll.cfgmgr32
            CM_GETIDLIST_FILTER_PRESENT = 0x00000100
            CM_GETIDLIST_FILTER_ENUMERATOR = 0x00000001
            CM_DRP_DEVICEDESC = 0x00000001
            CM_DRP_FRIENDLYNAME = 0x0000000D
            filter_flag = CM_GETIDLIST_FILTER_PRESENT | CM_GETIDLIST_FILTER_ENUMERATOR

            for enumerator in ('USB', 'USBSTOR'):
                buf_size = ctypes.c_ulong(0)
                if cfgmgr32.CM_Get_Device_ID_List_SizeW(ctypes.byref(buf_size), enumerator, filter_flag) == 0:
                    if buf_size.value > 0:
                        buf = ctypes.create_unicode_buffer(buf_size.value)
                        if cfgmgr32.CM_Get_Device_ID_ListW(enumerator, buf, buf_size.value, filter_flag) == 0:
                            raw = ''.join(buf[:])
                            for dev_id in raw.split('\x00'):
                                dev_str = dev_id.strip()
                                if not dev_str or 'ROOT_HUB' in dev_str.upper():
                                    continue

                                # Lấy tên thiết bị (Friendly Name hoặc Device Description)
                                model = "USB Device"
                                devnode = ctypes.c_ulong(0)
                                if cfgmgr32.CM_Locate_DevNodeW(ctypes.byref(devnode), dev_str, 0) == 0:
                                    p_buf = ctypes.create_unicode_buffer(512)
                                    p_len = ctypes.c_ulong(ctypes.sizeof(p_buf))
                                    for prop in (CM_DRP_FRIENDLYNAME, CM_DRP_DEVICEDESC):
                                        p_len.value = ctypes.sizeof(p_buf)
                                        if cfgmgr32.CM_Get_DevNode_Registry_PropertyW(devnode, prop, None, ctypes.byref(p_buf), ctypes.byref(p_len), 0) == 0:
                                            if p_buf.value:
                                                model = p_buf.value
                                                break

                                # Tạo mã băm HWID chuẩn
                                secure_hash = hashlib.sha256((salt + dev_str).encode('utf-8')).hexdigest().upper()
                                secure_hash_upper = hashlib.sha256((salt + dev_str.upper()).encode('utf-8')).hexdigest().upper()
                                usb_list.append({
                                    "serial": secure_hash,
                                    "serial_upper": secure_hash_upper,
                                    "raw_serial": dev_str,
                                    "model": model
                                })
        except Exception as e_native:
            _log.debug("Quét USB qua native API gặp ngoại lệ: %s", e_native)

        # 2. Nếu native API đã tìm thấy thiết bị thì trả về ngay
        if usb_list:
            return usb_list

        # 3. Fallback sang PowerShell (nếu native không trả về kết quả)
        try:
            cmd = (
                'powershell -Command "'
                "Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPDeviceID -match '^USB' } | ForEach-Object { $serial = $_.PNPDeviceID.Split('\\')[-1]; [PSCustomObject]@{ 'Device Name' = $_.Name; 'Serial Number' = $serial } } | ConvertTo-Csv -NoTypeInformation"
                '"'
            )
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=10)
            output = result.stdout.strip()
            if output:
                lines = output.strip().split('\n')
                for line in lines[1:]:
                    parts = line.strip().strip('"').split('","')
                    if len(parts) >= 2:
                        model = parts[0].strip()
                        pnp_and_serial = parts[1].strip()
                        if pnp_and_serial and "ROOT_HUB" not in pnp_and_serial:
                            raw_hwid = pnp_and_serial
                            secure_hash = hashlib.sha256((salt + raw_hwid).encode('utf-8')).hexdigest().upper()
                            secure_hash_upper = hashlib.sha256((salt + raw_hwid.upper()).encode('utf-8')).hexdigest().upper()
                            usb_list.append({
                                "serial": secure_hash,
                                "serial_upper": secure_hash_upper,
                                "raw_serial": raw_hwid,
                                "model": model
                            })
        except Exception as e:
            _log.error("Lỗi khi quét USB bảo mật (PowerShell fallback): %s", e)

        return usb_list
        

    