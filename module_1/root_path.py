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


def get_app_data_dir():
    """
    Trả về thư mục AppData bền vững cho ứng dụng (không cần quyền Administrator,
    không bị xóa khi đóng file exe hay khi cập nhật ứng dụng).
    """
    app_data = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or os.path.expanduser('~')
    base_dir = os.path.join(app_data, 'MBC_Vision_Inspector')
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def get_mysql_config_path(for_writing=False):
    """
    Lấy đường dẫn file mysql_config.log trong AppData của người dùng:
    - for_writing=True: Trả về đường dẫn trong AppData để ghi dữ liệu vĩnh viễn.
    - for_writing=False: Nếu file trong AppData chưa có, tự động copy file mẫu từ bundle sang.
    """
    config_dir = get_app_data_dir()
    config_file = os.path.join(config_dir, 'mysql_config.log')

    if for_writing:
        return config_file

    if os.path.exists(config_file):
        return config_file

    # Nếu chưa tồn tại trong AppData, copy từ file mẫu trong bundle
    bundled_file = resource_path("module_2/mysql_config.log")
    if os.path.exists(bundled_file):
        try:
            import shutil
            shutil.copy2(bundled_file, config_file)
            return config_file
        except Exception:
            return bundled_file

    return config_file


_TRIGGER_SYNCED = False


def get_trigger_simulation_dir():
    r"""
    Trả về thư mục lưu trữ file mô phỏng PLC trigger_{register}.txt bền vững
    trong AppData/Local/MBC_Vision_Inspector/module_3/
    (Không bị Access Denied khi cài trong C:\Program Files, không cần quyền Administrator).
    Tự động sao chép các file trigger mẫu có sẵn từ bundle sang nếu chưa có.
    """
    global _TRIGGER_SYNCED
    base_dir = get_app_data_dir()
    sim_dir = os.path.join(base_dir, 'module_3')
    os.makedirs(sim_dir, exist_ok=True)
    if not _TRIGGER_SYNCED:
        _TRIGGER_SYNCED = True
        sync_all_bundled_trigger_files()
    return sim_dir


def sync_all_bundled_trigger_files():
    """
    Tự động đồng bộ toàn bộ các file trigger_*.txt và trigger.txt mẫu từ bundle
    sang AppData/Local/MBC_Vision_Inspector/module_3/ nếu bên AppData chưa có.
    """
    try:
        base_dir = get_app_data_dir()
        sim_dir = os.path.join(base_dir, 'module_3')
        os.makedirs(sim_dir, exist_ok=True)
        bundled_dir = resource_path("module_3")
        if os.path.exists(bundled_dir) and os.path.isdir(bundled_dir):
            import shutil
            for fname in os.listdir(bundled_dir):
                if fname.lower().startswith("trigger") and fname.lower().endswith(".txt"):
                    dest_file = os.path.join(sim_dir, fname)
                    if not os.path.exists(dest_file):
                        src_file = os.path.join(bundled_dir, fname)
                        try:
                            shutil.copy2(src_file, dest_file)
                        except Exception:
                            pass
    except Exception:
        pass


def get_trigger_file_path(register: str = "", for_writing: bool = False, auto_create: bool = True) -> str:
    """
    Lấy đường dẫn file trigger_{register}.txt trong AppData:
    - for_writing=True: Trả về đường dẫn trong AppData để ghi dữ liệu.
    - for_writing=False: Nếu file trong AppData chưa có:
        1. Tìm file mẫu từ bundle để copy sang AppData.
        2. Nếu cả AppData và bundle đều chưa có và auto_create=True, tự động tạo file mới
           với giá trị mặc định là 0 (ví dụ: 'DM1999 = 0').
    """
    reg_clean = str(register).strip().replace(" ", "") if register else ""
    if reg_clean.lower().startswith("trigger_"):
        reg_clean = reg_clean[8:]
    if reg_clean.lower().endswith(".txt"):
        reg_clean = reg_clean[:-4]

    file_name = f"trigger_{reg_clean}.txt" if reg_clean else "trigger.txt"
    sim_dir = get_trigger_simulation_dir()
    target_file = os.path.join(sim_dir, file_name)

    if for_writing:
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        return target_file

    if os.path.exists(target_file):
        return target_file

    # 1. Nếu chưa có trong AppData, kiểm tra xem có file mẫu trong bundle không
    bundled_file = resource_path(os.path.join("module_3", file_name))
    if os.path.exists(bundled_file):
        try:
            import shutil
            shutil.copy2(bundled_file, target_file)
            return target_file
        except Exception:
            return bundled_file

    # 2. Nếu cả AppData và bundle đều chưa có, tự động tạo file mới để tránh lỗi không tìm thấy
    if auto_create:
        try:
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            with open(target_file, 'w', encoding='utf-8') as f:
                if reg_clean:
                    f.write(f"{reg_clean} = 0\n")
                else:
                    f.write("0\n")
            return target_file
        except Exception:
            pass

    return target_file
