# Administrator/autostart_manager.py
# Quản lý cơ cấu tự động khởi động cùng Windows (Auto-Start on System Boot)
# Hỗ trợ Windows Registry (HKCU Run) và đồng bộ/dọn dẹp thư mục shell:startup

import os
import sys
import winreg
from app_logger.app_logger import get_logger as _get_logger

_log = _get_logger('Administrator.autostart_manager')

REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "VisionProInspector"


def get_app_executable_path() -> str:
    """
    Xác định đường dẫn file thực thi chính của ứng dụng.
    - Khi đóng gói PyInstaller: sys.executable (ví dụ VisionProInspector.exe).
    - Khi chạy môi trường Python dev: sys.executable hoặc script chính.
    """
    if getattr(sys, 'frozen', False):
        return os.path.abspath(sys.executable)
    else:
        candidate_run = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'module_2', 'run.py'))
        if os.path.exists(candidate_run):
            return candidate_run
        return os.path.abspath(sys.argv[0])


def get_app_launch_command() -> str:
    """
    Tạo chuỗi câu lệnh để Windows Startup kích hoạt ứng dụng.
    Bao bọc trong dấu ngoặc kép để hỗ trợ đường dẫn có khoảng trắng.
    """
    if getattr(sys, 'frozen', False):
        exe_path = os.path.abspath(sys.executable)
        return f'"{exe_path}"'
    else:
        python_exe = os.path.abspath(sys.executable)
        # Entrypoint chính của ứng dụng là module_2/run.py
        candidate_run = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'module_2', 'run.py'))
        if os.path.exists(candidate_run):
            script = candidate_run
        else:
            script = os.path.abspath(sys.argv[0])
        return f'"{python_exe}" "{script}"'


def get_startup_folder_path() -> str:
    """Trả về đường dẫn thư mục shell:startup của người dùng hiện tại"""
    app_data = os.environ.get('APPDATA') or os.path.expanduser('~')
    return os.path.join(app_data, r'Microsoft\Windows\Start Menu\Programs\Startup')


def is_registry_autostart_enabled() -> tuple[bool, str]:
    """
    Kiểm tra xem ứng dụng đã được đăng ký trong Windows Registry (HKCU Run) chưa.
    Returns: (is_enabled, registered_command_or_error)
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_REG_NAME)
            return True, str(val)
    except FileNotFoundError:
        return False, ""
    except Exception as e:
        _log.warning("Lỗi đọc Windows Registry: %s", e)
        return False, str(e)


def cleanup_startup_folder_shortcuts() -> list[str]:
    """
    Dọn dẹp các shortcut hoặc file thực thi cũ trong thư mục shell:startup
    liên quan đến ứng dụng để tránh Windows khởi động 2 lần.
    """
    cleaned = []
    startup_dir = get_startup_folder_path()
    if not os.path.exists(startup_dir):
        return cleaned

    target_keywords = [
        'visionproinspector', 'visionapp', 'mbc_vision', 'project_vision', 'internal'
    ]

    try:
        for fname in os.listdir(startup_dir):
            lower = fname.lower()
            if any(kw in lower for kw in target_keywords):
                if lower.endswith('.lnk') or lower.endswith('.exe') or lower.endswith('.bat'):
                    full_path = os.path.join(startup_dir, fname)
                    try:
                        os.remove(full_path)
                        cleaned.append(fname)
                        _log.info("Dọn dẹp file startup cũ: %s", full_path)
                    except Exception as err:
                        _log.warning("Không thể xóa file startup cũ %s: %s", full_path, err)
    except Exception as e:
        _log.warning("Lỗi quét thư mục shell:startup: %s", e)

    return cleaned


def set_auto_start_registry(enable: bool) -> tuple[bool, str]:
    """
    Kích hoạt hoặc Hủy kích hoạt tự khởi động trong Windows Registry (HKCU Run).
    Cơ chế này:
    - Không cần quyền Administrator (chạy được trên mọi tài khoản Windows thường).
    - Tự động hiển thị và quản lý trong Windows Task Manager -> Startup apps.
    - Tự dọn dẹp thư mục shell:startup nếu trước đây user từng copy file thủ công vào đó.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_ALL_ACCESS) as key:
            if enable:
                cmd = get_app_launch_command()
                winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, cmd)
                cleaned = cleanup_startup_folder_shortcuts()
                msg = f"Đã kích hoạt tự khởi động cùng Windows (Registry HKCU: Run).\n\nLệnh thực thi: {cmd}"
                if cleaned:
                    msg += f"\n\nĐã tự động dọn dẹp các mục cũ trong shell:startup ({', '.join(cleaned)}) để tránh khởi động trùng lặp."
                _log.info("Set auto start SUCCESS: %s", cmd)
                return True, msg
            else:
                try:
                    winreg.DeleteValue(key, APP_REG_NAME)
                except FileNotFoundError:
                    pass
                cleaned = cleanup_startup_folder_shortcuts()
                msg = "Đã hủy cấu hình tự khởi động cùng Windows."
                if cleaned:
                    msg += f"\n\nĐã dọn dẹp các mục trong shell:startup ({', '.join(cleaned)})."
                _log.info("Disabled auto start SUCCESS")
                return True, msg
    except Exception as e:
        err_msg = f"Lỗi thao tác Windows Registry: {str(e)}"
        _log.error("Set auto start failed: %s", err_msg)
        return False, err_msg
