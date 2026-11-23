# -*- coding: utf-8 -*-
"""
AI Vision Pro - Main Application Entrypoint
===========================================
Tập tin khởi chạy chính của hệ thống kiểm tra công nghiệp AI Vision Pro.
Quản lý vòng đời khởi động:
  1. Cấu hình môi trường High DPI và Windows Per-Monitor DPI Awareness
  2. Cài đặt hệ thống ghi log và bẫy lỗi toàn cục (Global Exception Hook)
  3. Kiểm tra bản quyền khóa cứng USB Hardware Key
  4. Khởi động luồng giám sát nền CoreWorker và kết nối PLC
  5. Khởi tạo giao diện đồ họa chính (VisionMainWindow) và MainThread logic
  6. Kết nối các menu actions, phím tắt (F11/Esc, Ctrl+R, Ctrl+X) và chạy vòng lặp Qt
"""

import os
import sys
import ctypes
import datetime
import traceback


# Thiết lập đường dẫn thư mục gốc dự án
_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)
    
from module_1.root_path import _setup_external_code_override
_setup_external_code_override()

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QShortcut

from module_2.home_main import Ui_MainWindow as MainWindowUI
from module_2.main_core import core
from module_2.main_thread import main_thread
from module_2.single_instance import SingleInstanceManager
from module_2.startup_splash import StartupSplashWindow
from Administrator.hardware_key import open_hardware_key
from app_logger.app_logger import get_logger as _get_logger, open_log_window

_log = _get_logger('module_2.run')

# Đường dẫn file log crash khẩn cấp
_DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")
_CRASH_LOG_PATH = os.path.join(_DESKTOP_PATH, "VisionApp_crash.log")


def write_crash_log(msg: str) -> None:
    """Ghi thông điệp trạng thái hoặc nhật ký sự cố vào file crash log trên Desktop."""
    try:
        with open(_CRASH_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.datetime.now()}]\n{msg}\n")
            f.flush()
    except Exception:
        pass


def show_fatal_error(title: str, msg: str) -> None:
    """Hiển thị hộp thoại lỗi nghiêm trọng và ghi lại vết lỗi."""
    write_crash_log(f"FATAL [{title}]:\n{msg}")
    _log.critical("FATAL [%s]: %s", title, msg)
    try:
        QMessageBox.critical(
            None,
            f"[FATAL] {title}",
            f"{msg}\n\nXem chi tiết tại nhật ký:\n{_CRASH_LOG_PATH}"
        )
    except Exception:
        pass


def setup_global_exception_handler() -> None:
    """Cài đặt bộ chặn ngoại lệ chưa được xử lý để tránh crash ứng dụng im lặng."""
    def _handler(exc_type, exc_value, exc_traceback):
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        write_crash_log(f"UNHANDLED EXCEPTION:\n{msg}")
        _log.error("Unhandled Exception:\n%s", msg)
        try:
            QMessageBox.critical(
                None,
                "Lỗi Nghiêm Trọng",
                f"Ứng dụng gặp sự cố không mong muốn!\n\n{msg}\n\nNhật ký sự cố: {_CRASH_LOG_PATH}"
            )
        except Exception:
            pass

    sys.excepthook = _handler


def setup_environment() -> None:
    """Cấu hình nhận thức High DPI cho Windows và thuộc tính đồ họa Qt."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    try:
        QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass


class VisionMainWindow(QMainWindow):
    """Cửa sổ chính của hệ thống AI Vision Pro."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = MainWindowUI()
        self.ui.setupUi(self)
        self.main_core = None
        self.main_thread = None
        self.hardware_key_guard = None

        # Thiết lập phím tắt toàn màn hình (F11) và thoát toàn màn hình (Esc)
        self.shortcut_fullscreen = QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_F11), self)
        self.shortcut_fullscreen.activated.connect(self._toggle_fullscreen)

        self.shortcut_escape = QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Escape), self)
        self.shortcut_escape.activated.connect(self._exit_fullscreen)

    def _toggle_fullscreen(self):
        """Bật / tắt chế độ toàn màn hình (Full Screen)."""
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()

    def _exit_fullscreen(self):
        """Thoát chế độ toàn màn hình về Maximized."""
        if self.isFullScreen():
            self.showMaximized()

    def setup_app_components(self, main_core_instance, main_thread_instance):
        """Liên kết các đối tượng tầng core và tầng thread logic với giao diện."""
        self.main_core = main_core_instance
        self.main_thread = main_thread_instance
        self._connect_signals()

        # Khởi động bộ giám sát định kỳ USB Hardware Key (3 - 5 phút quét 1 lần) nếu được Administrator cho phép
        try:
            from Administrator.user_db import is_watchdog_enabled
            db_conn = getattr(self.main_core, 'cursor', None) or getattr(self.main_core, 'connection', None)
            if is_watchdog_enabled('hardware_key', conn_or_cursor=db_conn):
                from module_2.hardware_key_guard import HardwareKeyGuard
                self.hardware_key_guard = HardwareKeyGuard(
                    main_core=self.main_core,
                    parent_window=self,
                    min_interval_sec=180,  # 3 phút
                    max_interval_sec=300   # 5 phút
                )
                self.hardware_key_guard.start()
                _log.info("HardwareKeyGuard đã được khởi động.")
            else:
                _log.info("[HardwareKeyGuard] Giám sát liên tục USB Key bị TẮT theo cấu hình của Administrator.")
        except Exception as e:
            _log.error("Lỗi khi khởi chạy HardwareKeyGuard: %s", e)

    def _connect_signals(self):
        """Kết nối toàn bộ các menu actions và signals của ứng dụng."""
        ui = self.ui
        mt = self.main_thread
        core_inst = self.main_core

        # 1. Device Setup & Startup Management
        ui.actiondevice_configuration_settings.triggered.connect(lambda: mt.open_pyuic5())
        ui.actionAuto_Configuration.triggered.connect(lambda: mt.auto_mysql())

        # 2. Reset & Close actions
        ui.actionRestart.triggered.connect(lambda: mt.restart_application())
        ui.actionManageReset.triggered.connect(lambda: mt._open_manage_restart())
        ui.actionManage_2.triggered.connect(lambda: mt.close_application(None, core_inst))
        ui.actionManage_Close.triggered.connect(lambda: mt._open_manage_close())

        # 3. User & Administrator Management
        ui.actionConfigure_settings.triggered.connect(lambda: mt._open_admin_config())
        ui.actionCreate_User.triggered.connect(lambda: mt._open_create_user())
        ui.actionRemove_User.triggered.connect(lambda: mt._open_remove_user())
        ui.actionHardware_Key.triggered.connect(lambda: mt._open_hardware_key())

        # 4. Tools & Data Export/Import
        ui.actionScripts.triggered.connect(lambda: mt._open_scripts())
        ui.actionData_Export.triggered.connect(lambda: mt._open_data_export())
        ui.actionData_Import.triggered.connect(lambda: mt._open_data_import())

        # 5. Core worker background signals (PLC trigger, actions)
        if hasattr(core_inst, 'worker_thread') and core_inst.worker_thread:
            core_inst.worker_thread.system_action_triggered.connect(mt.handle_system_action)

        # 6. Help & Information dialogs
        ui.actionDocumentation.triggered.connect(self._show_documentation)
        ui.actionUser_Manual.triggered.connect(self._show_user_manual)
        ui.actionAbout.triggered.connect(self._show_about)

        # 7. Performance overview dialogs
        ui.actionOverView_of_Monitor.triggered.connect(self._show_performance_overview)
        ui.actionSystem_Sumary.triggered.connect(self._show_system_summary)

    def closeEvent(self, event):
        """Xử lý sự kiện đóng cửa sổ chính qua logic của main_thread."""
        if self.hardware_key_guard:
            try:
                self.hardware_key_guard.stop()
            except Exception:
                pass
        if self.main_thread:
            self.main_thread.closeEvent(event, self.main_core)
        else:
            event.accept()

    def _show_about(self):
        """Hiển thị hộp thoại giới thiệu phần mềm."""
        QMessageBox.about(
            self,
            "About AI Vision Pro",
            "<h2>AI Vision Pro Inspection System</h2>"
            "<p><b>Phiên bản:</b> 2.0 (Build 2026)</p>"
            "<p><b>Mô tả:</b> Hệ thống kiểm tra chất lượng sản phẩm công nghiệp ứng dụng AI Deep Learning "
            "(YOLOv5 / YOLOv8) tích hợp tự động hóa PLC Keyence / Mitsubishi / Omron.</p>"
            "<p><b>Bản quyền:</b> © 2026 AI Vision Team. Tất cả các quyền được bảo lưu.</p>"
        )

    def _show_documentation(self):
        """Hiển thị thông tin tài liệu kỹ thuật của hệ thống."""
        QMessageBox.information(
            self,
            "Tài liệu kỹ thuật",
            "<h3>Tài liệu kỹ thuật AI Vision Pro</h3>"
            "<p>Hệ thống hỗ trợ:</p>"
            "<ul>"
            "<li>Quản lý công thức sản phẩm (Recipe / Item code).</li>"
            "<li>Tích hợp Camera công nghiệp qua Basler Pylon & Hikvision MVS.</li>"
            "<li>Giao tiếp PLC qua Ethernet Socket (Keyence, Mitsubishi, Omron).</li>"
            "<li>Lập trình kịch bản tự động hóa qua Scripts Editor.</li>"
            "</ul>"
            "<p>Vui lòng tham khảo tài liệu kỹ thuật chi tiết trong thư mục cài đặt.</p>"
        )

    def _show_user_manual(self):
        """Hiển thị hướng dẫn vận hành nhanh cho người dùng."""
        QMessageBox.information(
            self,
            "Hướng dẫn sử dụng",
            "<h3>Hướng dẫn vận hành nhanh</h3>"
            "<ol>"
            "<li><b>Cấu hình kết nối:</b> Vào <i>Systems → Startup Management</i> để kiểm tra MySQL và PLC.</li>"
            "<li><b>Cài đặt Camera & Model:</b> Vào <i>Create Device → Device Setup</i> để cấu hình camera và mô hình nhận diện AI.</li>"
            "<li><b>Quản lý Reset/Close:</b> Sử dụng <i>Reset Application</i> hoặc <i>Close Application</i> trong menu Systems để cài đặt tín hiệu tự động từ PLC.</li>"
            "<li><b>Quản trị người dùng:</b> Vào <i>Users and Group</i> để tạo/xóa tài khoản và đăng ký USB License Key.</li>"
            "</ol>"
        )

    def _show_performance_overview(self):
        """Hiển thị tổng quan hiệu năng hệ thống (CPU, RAM, GPU AI)."""
        cpu_usage = "N/A"
        ram_usage = "N/A"
        try:
            import psutil
            cpu_usage = f"{psutil.cpu_percent()}%"
            ram_usage = f"{psutil.virtual_memory().percent}%"
        except Exception:
            pass

        gpu_info = "Không khả dụng / CPU mode"
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                mem_alloc = torch.cuda.memory_allocated(0) / (1024 ** 2)
                gpu_info = f"{gpu_name} (Sử dụng: {mem_alloc:.1f} MB)"
        except Exception:
            pass

        QMessageBox.information(
            self,
            "Hiệu năng hệ thống",
            f"<h3>Tổng quan hiệu năng</h3>"
            f"<p><b>CPU sử dụng:</b> {cpu_usage}</p>"
            f"<p><b>RAM sử dụng:</b> {ram_usage}</p>"
            f"<p><b>GPU AI:</b> {gpu_info}</p>"
        )

    def _show_system_summary(self):
        """Hiển thị tóm tắt trạng thái kết nối PLC, MySQL và thông số hiện tại."""
        core_inst = self.main_core
        plc_ip = getattr(core_inst, 'ip_address_plc', 'N/A')
        plc_port = getattr(core_inst, 'port_plc', 'N/A')
        item_code = getattr(core_inst, 'item_code', 'Chưa chọn')
        line_code = getattr(core_inst, 'line_code', 'Chưa chọn')
        db_status = "Đã kết nối" if (core_inst and core_inst.connection and core_inst.connection.is_connected()) else "Chưa kết nối"

        QMessageBox.information(
            self,
            "Thông tin hệ thống",
            f"<h3>Thông tin tổng quát hệ thống</h3>"
            f"<p><b>Cơ sở dữ liệu MySQL:</b> {db_status}</p>"
            f"<p><b>PLC Module:</b> {getattr(core_inst, 'plc_module', 'KEYENCE')}</p>"
            f"<p><b>Địa chỉ PLC:</b> {plc_ip}:{plc_port}</p>"
            f"<p><b>Item Code hiện tại:</b> {item_code}</p>"
            f"<p><b>Line Code hiện tại:</b> {line_code}</p>"
        )


def check_license(main_core_instance) -> bool:
    """
    Kiểm tra bản quyền khóa cứng USB (Hardware Key).
    Nếu không tìm thấy khóa, hỏi người dùng có muốn mở License Manager hay không.
    Trả về True nếu giấy phép hợp lệ để tiếp tục; False nếu người dùng từ chối hoặc không hợp lệ.
    """
    write_crash_log("STEP 4: Querying hardware key")
    enable_open_app = main_core_instance.query_hardware_key()
    write_crash_log(f"STEP 4: query_hardware_key returned: {enable_open_app}")

    if not enable_open_app:
        write_crash_log("STEP 4b: Hardware key DENIED - prompting for registration")
        reply = QMessageBox.question(
            None,
            "Yêu cầu Giấy phép (License Required)",
            "Không tìm thấy USB Khóa cứng (Hardware Key) hợp lệ!\n\n"
            "Bạn có muốn mở Trình quản lý bản quyền (License Manager) để đăng ký khóa mới?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if main_core_instance.connection and main_core_instance.connection.is_connected():
                try:
                    cursor = main_core_instance.connection.cursor()
                    open_hardware_key(cursor, main_core_instance.connection, main_core_instance.connection)
                    write_crash_log("STEP 4c: Re-checking hardware key after registration")
                    enable_open_app = main_core_instance.query_hardware_key()
                except Exception as e:
                    _log.error("Error opening hardware key manager: %s", e)
                    QMessageBox.warning(None, "Lỗi", f"Không thể mở Hardware Key Manager:\n{e}")
            else:
                QMessageBox.warning(None, "Lỗi CSDL", "Không có kết nối MySQL để quản lý bản quyền.")

    return bool(enable_open_app)


def run_application():
    """Hàm khởi động chính của ứng dụng AI Vision Pro."""
    # 0. Cài đặt bẫy lỗi toàn cục và log khởi động
    setup_global_exception_handler()
    write_crash_log("=== VisionApp startup ===")

    # 1. Cấu hình DPI nhận thức và thuộc tính High DPI cho Qt
    setup_environment()

    # 2. Khởi tạo đối tượng QApplication
    try:
        app = QtWidgets.QApplication(sys.argv)
        app.setStyle('Fusion')
        write_crash_log("STEP 1: QApplication initialized (Style: Fusion)")
    except Exception:
        show_fatal_error("QApplication Initialization", traceback.format_exc())
        return

    # 3. KIỂM TRA ĐƠN PHIÊN BẢN (SINGLE INSTANCE CHECK):
    # Tuyệt đối không cho phép chạy song song 2 phiên bản phần mềm.
    # Nếu phát hiện đã có phiên bản đang chạy (hoặc đang khởi động), hiển thị cảnh báo và thoát ngay.
    try:
        if SingleInstanceManager.is_already_running():
            write_crash_log("STEP 1b: Duplicate instance detected! Prompting operator and exiting immediately.")
            _log.warning("[SingleInstance] Phát hiện phần mềm đã đang chạy! Hiển thị cảnh báo và dừng tiến trình này.")
            SingleInstanceManager.show_already_running_warning()
            sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        write_crash_log(f"STEP 1b WARNING (SingleInstance check error): {e}")

    # 4. HIỂN THỊ MÀN HÌNH KHỞI ĐỘNG (STARTUP LOADING SPLASH SCREEN) NGAY LẬP TỨC
    # Màn hình này cảnh báo rõ ràng cho công nhân vận hành: "Đang khởi tạo - KHÔNG ĐƯỢC CLICK LẠI ICON"
    splash = None
    single_mgr = None
    window = None

    try:
        splash = StartupSplashWindow()
        splash.show()
        splash.update_status("Đang khởi tạo hệ thống kiểm tra...", "Đăng ký khóa đơn phiên bản (Single Instance)...", 5)

        # Đăng ký Named Pipe Server để nhận tín hiệu kích hoạt nếu người dùng click icon sau này
        single_mgr = SingleInstanceManager()

        def _on_remote_activate(msg="ACTIVATE"):
            _log.info("[SingleInstance] Nhận tín hiệu kích hoạt từ tiến trình thứ 2: %s", msg)
            if splash and splash.isVisible():
                splash.activate_splash()
            elif window and window.isVisible():
                window.showMaximized()
                window.raise_()
                window.activateWindow()

        single_mgr.start_server(on_activate_callback=_on_remote_activate)
    except Exception as e:
        write_crash_log(f"STEP 1c WARNING (Splash / SingleInstance server error): {e}")

    # 5. Mở cửa sổ theo dõi log ứng dụng (nếu cấu hình)
    try:
        if splash:
            splash.update_status("Đang nạp cửa sổ nhật ký ứng dụng...", "Khởi tạo hệ thống logging...", 10)
        open_log_window()
        write_crash_log("STEP 2: open_log_window OK")
    except Exception:
        write_crash_log("STEP 2 WARNING (open_log_window):\n" + traceback.format_exc())

    # 6. Khởi tạo tầng logic lõi Main Core (kèm callback cập nhật Splash trực tiếp)
    try:
        if splash:
            splash.update_status("Đang kết nối cơ sở dữ liệu MySQL...", "Hệ thống đang tự động phục hồi dịch vụ dữ liệu...", 15)
        progress_cb = splash.update_status if splash else None
        main_core = core(progress_callback=progress_cb)
        write_crash_log("STEP 3: core() initialized OK")
    except BaseException as e:
        if splash:
            splash.close()
        show_fatal_error("Core Initialization", f"Type: {type(e).__name__}\n\n{traceback.format_exc()}")
        return

    # 7. Xác thực Giấy phép (Hardware Key License) TRƯỚC KHI chạy luồng nền hoặc giao diện
    try:
        if splash:
            splash.update_status("Đang xác thực bản quyền phần mềm...", "Kiểm tra USB Hardware Key...", 75)
        license_ok = check_license(main_core)
        if not license_ok:
            write_crash_log("STEP 4d: License verification denied or cancelled - exiting cleanly")
            if splash:
                splash.close()
            sys.exit(0)
        write_crash_log("STEP 4: License verified successfully")
    except SystemExit:
        if splash:
            splash.close()
        raise
    except Exception:
        if splash:
            splash.close()
        show_fatal_error("License Verification", traceback.format_exc())
        return

    # 8. Khởi động luồng giám sát tín hiệu nền CoreWorker (CHỈ DUY NHẤT 1 LẦN)
    try:
        if splash:
            splash.update_status("Đang khởi động giám sát tín hiệu nền...", "Kích hoạt luồng CoreWorker & Watchdog...", 82)
        main_core.start_monitoring()
        write_crash_log("STEP 5: CoreWorker monitoring started")
    except Exception:
        if splash:
            splash.close()
        show_fatal_error("start_monitoring", traceback.format_exc())
        return

    # 9. Khởi tạo cửa sổ chính và giao diện
    try:
        if splash:
            splash.update_status("Đang khởi tạo giao diện điều khiển...", "Chuẩn bị màn hình chính...", 88)
        window = VisionMainWindow()
        write_crash_log("STEP 6: VisionMainWindow created")
    except Exception:
        if splash:
            splash.close()
        show_fatal_error("VisionMainWindow Creation", traceback.format_exc())
        return

    # 10. Khởi tạo MainThread xử lý logic & kết nối với giao diện
    try:
        main_thread_instance = main_thread(window.ui, main_core.connection, main_core)
        window.setup_app_components(main_core, main_thread_instance)
        write_crash_log("STEP 7: main_thread initialized and connected to UI")
    except Exception:
        if splash:
            splash.close()
        show_fatal_error("main_thread Setup", traceback.format_exc())
        return

    # 11. Khởi tạo màn hình chờ động (radar) và cấu hình Pyuic5 / module_3
    try:
        if splash:
            splash.update_status("Đang nạp cấu hình hiển thị và mô hình AI...", "Khởi tạo thiết bị đồ họa và Workspace...", 95)
        main_thread_instance.setup_home_screen(window.ui.graphicsView)
        main_thread_instance.init_Pyuic5()
        write_crash_log("STEP 8: Home screen animation and Pyuic5 initialized")
    except Exception:
        if splash:
            splash.close()
        show_fatal_error("init_Pyuic5 Setup", traceback.format_exc())
        return

    # 12. Hoàn tất khởi động: Đóng Splash và hiển thị cửa sổ chính
    try:
        write_crash_log("STEP 9: Finishing splash and displaying MainWindow")
        if splash:
            splash.finish(window)
        else:
            window.showMaximized()
        write_crash_log("STEP 9: MainWindow displayed maximized successfully")

        # Đảm bảo nếu có cảnh báo lỗi kết nối PLC hoặc Camera lúc khởi động phần mềm,
        # cửa sổ cảnh báo được hiển thị và nâng lên trên cùng sau khi MainWindow đã phóng to cực đại.
        def _raise_startup_alerts():
            try:
                # 1. Hiển thị và nâng cảnh báo kết nối PLC nếu mất kết nối lúc khởi động
                if getattr(main_core, 'startup_plc_failed', False):
                    if getattr(main_core, '_plc_alert_overlay', None) is None:
                        module = getattr(main_core, 'plc_module', 'KEYENCE')
                        ip = getattr(main_core, 'ip_address_plc', '')
                        port = getattr(main_core, 'port_plc', 0)
                        main_core._on_plc_connection_lost(module, str(ip), int(port), 1)

                    overlay = getattr(main_core, '_plc_alert_overlay', None)
                    if overlay and not getattr(overlay, 'user_dismissed', False):
                        overlay._center_on_screen_or_window()
                        if not overlay.isVisible():
                            overlay.show_alert()
                        else:
                            overlay.raise_()
                            overlay.activateWindow()

                # 2. Nâng cảnh báo kết nối Camera nếu có lỗi khởi động
                if hasattr(main_thread_instance, 'camera_manager'):
                    cam_overlay = getattr(main_thread_instance.camera_manager, '_camera_alert_overlay', None)
                    if cam_overlay and cam_overlay.isVisible():
                        cam_overlay.raise_()
                        cam_overlay.activateWindow()
            except Exception as e_overlay:
                _log.debug("Lỗi nâng vị trí alert overlay sau showMaximized: %s", e_overlay)

        QtCore.QTimer.singleShot(400, _raise_startup_alerts)
        QtCore.QTimer.singleShot(1200, _raise_startup_alerts)
    except Exception:
        if splash:
            splash.close()
        show_fatal_error("showMaximized", traceback.format_exc())
        return

    # 13. Bắt đầu vòng lặp sự kiện chính của Qt
    write_crash_log("STEP 10: Entering Qt main event loop")
    sys.exit(app.exec_())


class main_pyuic:
    """Wrapper cho phép tương thích ngược khi gọi khởi chạy qua main_pyuic()."""
    def __init__(self):
        run_application()


if __name__ == "__main__":
    run_application()
