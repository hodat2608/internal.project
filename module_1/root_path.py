import sys
import os

def resource_path(relative_path):
    """ Lấy đường dẫn tuyệt đối cho tài nguyên, hoạt động cả trên VS Code và PyInstaller """
    try:
        # Khi chạy bằng file exe (PyInstaller)
        base_path = sys._MEIPASS
    except Exception:
        # Khi chạy trên VS Code
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)
