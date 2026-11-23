# Administrator/user_db.py
# Database operations cho quản lý User và Hardware Key

import os
import json
import hashlib
import threading
from datetime import datetime
from PyQt5.QtWidgets import QMessageBox

# Đồng bộ khóa đa luồng cơ sở dữ liệu với toàn bộ hệ thống
try:
    from module_3.task_calculator_db import _db_lock
except Exception:
    _db_lock = threading.RLock()


# ─────────────────────────────────────────────
#  TẠO BẢNG ADMIN (gọi khi khởi động hoặc khi mở Configure Settings)
# ─────────────────────────────────────────────
_ADMIN_TABLES_SQL = [
    """
    CREATE DATABASE IF NOT EXISTS ADMINISTRATOR;
    """,
    """
    CREATE TABLE IF NOT EXISTS ADMINISTRATOR.ADMIN_USERS (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        username        VARCHAR(255) NOT NULL UNIQUE,
        password_hash   VARCHAR(255) NOT NULL,
        role            ENUM('read_only','modify','full_control') NOT NULL DEFAULT 'read_only',
        is_active       TINYINT(1) NOT NULL DEFAULT 1,
        created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_login      DATETIME DEFAULT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS ADMINISTRATOR.HARDWARE_KEY_CONFIG (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        serial_number   VARCHAR(255) NOT NULL UNIQUE,
        hash_code       VARCHAR(255) NOT NULL UNIQUE,
        description     VARCHAR(255) DEFAULT '',
        is_enabled      TINYINT(1) NOT NULL DEFAULT 1,
        registered_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS ADMINISTRATOR.SYSTEM_CONFIG (
        config_key      VARCHAR(100) PRIMARY KEY,
        config_value    TEXT,
        description     VARCHAR(255) DEFAULT '',
        updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
]


def ensure_admin_tables(connection):
    """
    Tạo bảng ADMIN_USERS và HARDWARE_KEY_CONFIG nếu chưa tồn tại.
    Gọi hàm này khi app khởi động hoặc khi nhấn Configure Settings.
    
    Args:
        connection: MySQL connection object (không phải cursor)
    """
    with _db_lock:
        try:
            cursor = connection.cursor()
            for sql in _ADMIN_TABLES_SQL:
                cursor.execute(sql)
            connection.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"[Administrator] Lỗi tạo bảng admin: {e}")
            return False


def hash_password(password: str) -> str:
    """Hash password bằng SHA-256"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """So sánh password nhập vào với hash đã lưu"""
    return hash_password(password) == password_hash


# ─────────────────────────────────────────────
#  ADMIN PASSWORD (hard-coded default & AppData writable path)
# ─────────────────────────────────────────────
import os
import sys
import json

if getattr(sys, 'frozen', False):
    app_data = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or os.path.expanduser('~')
    _ADMIN_DIR = os.path.join(app_data, 'MBC_Vision_Inspector', 'Administrator')
else:
    _ADMIN_DIR = os.path.dirname(__file__)

_ADMIN_FILE = os.path.join(_ADMIN_DIR, "admin_secret.json")
_DEFAULT_ADMIN_PASS = "admin@2026"


def get_admin_password_hash() -> str:
    """Đọc admin password hash từ file, nếu chưa có thì tạo mặc định"""
    # 1. Kiểm tra file cấu hình người dùng (trong AppData khi đóng gói)
    if os.path.exists(_ADMIN_FILE):
        try:
            with open(_ADMIN_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("password_hash", hash_password(_DEFAULT_ADMIN_PASS))
        except Exception:
            pass

    # 2. Kiểm tra file gốc đi kèm ứng dụng (_internal/Administrator/admin_secret.json)
    bundled_file = os.path.join(os.path.dirname(__file__), "admin_secret.json")
    if os.path.exists(bundled_file):
        try:
            with open(bundled_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("password_hash", hash_password(_DEFAULT_ADMIN_PASS))
        except Exception:
            pass

    return hash_password(_DEFAULT_ADMIN_PASS)


def save_admin_password_hash(new_hash: str):
    """Lưu admin password hash mới vào file trong thư mục có quyền ghi (AppData)"""
    os.makedirs(_ADMIN_DIR, exist_ok=True)
    with open(_ADMIN_FILE, 'w', encoding='utf-8') as f:
        json.dump({"password_hash": new_hash}, f, indent=4)


def verify_admin_password(password: str) -> bool:
    """Kiểm tra mật khẩu admin"""
    return verify_password(password, get_admin_password_hash())


# ─────────────────────────────────────────────
#  USER CRUD OPERATIONS
# ─────────────────────────────────────────────
def create_user(cursor, connect_db, username: str, password: str, role: str = "read_only"):
    """Tạo user mới"""
    with _db_lock:
        try:
            cursor.execute(
                """INSERT INTO ADMINISTRATOR.ADMIN_USERS (username, password_hash, role, is_active, created_at)
                   VALUES (%s, %s, %s, 1, %s)""",
                (username, hash_password(password), role, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            connect_db.commit()
            return True, "Tạo user thành công!"
        except Exception as e:
            connect_db.rollback()
            if "Duplicate entry" in str(e):
                return False, f"Username '{username}' đã tồn tại!"
            return False, f"Lỗi: {e}"


def delete_user(cursor, connect_db, user_id: int):
    """Xóa user theo ID"""
    with _db_lock:
        try:
            cursor.execute("DELETE FROM ADMINISTRATOR.ADMIN_USERS WHERE id = %s", (user_id,))
            connect_db.commit()
            return True, "Xóa user thành công!"
        except Exception as e:
            connect_db.rollback()
            return False, f"Lỗi: {e}"


def get_all_users(cursor):
    """Lấy danh sách tất cả users"""
    with _db_lock:
        try:
            cursor.execute(
                "SELECT id, username, role, is_active, created_at, last_login FROM ADMINISTRATOR.ADMIN_USERS ORDER BY id"
            )
            return cursor.fetchall()
        except Exception:
            return []


def update_user_role(cursor, connect_db, user_id: int, new_role: str):
    """Cập nhật quyền của user"""
    with _db_lock:
        try:
            cursor.execute("UPDATE ADMINISTRATOR.ADMIN_USERS SET role = %s WHERE id = %s", (new_role, user_id))
            connect_db.commit()
            return True
        except Exception:
            connect_db.rollback()
            return False


def toggle_user_active(cursor, connect_db, user_id: int, is_active: bool):
    """Vô hiệu hóa / kích hoạt user"""
    with _db_lock:
        try:
            cursor.execute("UPDATE ADMINISTRATOR.ADMIN_USERS SET is_active = %s WHERE id = %s", (int(is_active), user_id))
            connect_db.commit()
            return True
        except Exception:
            connect_db.rollback()
            return False


def get_user_count(cursor) -> int:
    """Đếm số lượng user hiện tại"""
    with _db_lock:
        try:
            cursor.execute("SELECT COUNT(*) FROM ADMINISTRATOR.ADMIN_USERS")
            return cursor.fetchone()[0]
        except Exception:
            return 0


# ─────────────────────────────────────────────
#  HARDWARE KEY CRUD
# ─────────────────────────────────────────────
def add_hardware_key(cursor, connect_db, serial: str, hash_code: str, description: str = ""):
    """Thêm USB serial number được phép sử dụng"""
    with _db_lock:
        try:
            cursor.execute(
                """INSERT INTO ADMINISTRATOR.HARDWARE_KEY_CONFIG (serial_number, hash_code, description, is_enabled, registered_at)
                   VALUES (%s, %s, %s, 1, %s)""",
                (serial, hash_code, description, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            connect_db.commit()
            return True, "Đăng ký USB Key thành công!"
        except Exception as e:
            connect_db.rollback()
            if "Duplicate entry" in str(e):
                return False, f"Serial '{serial}' đã được đăng ký!"
            return False, f"Lỗi: {e}"


def remove_hardware_key(cursor, connect_db, key_id: int):
    """Xóa USB key"""
    with _db_lock:
        try:
            cursor.execute("DELETE FROM ADMINISTRATOR.HARDWARE_KEY_CONFIG WHERE id = %s", (key_id,))
            connect_db.commit()
            return True
        except Exception:
            connect_db.rollback()
            return False


def get_all_hardware_keys(cursor):
    """Lấy danh sách tất cả USB keys đã đăng ký"""
    with _db_lock:
        try:
            cursor.execute("SELECT id, serial_number, hash_code, description, is_enabled, registered_at FROM ADMINISTRATOR.HARDWARE_KEY_CONFIG ORDER BY id")
            return cursor.fetchall()
        except Exception:
            return []


def toggle_hardware_key(cursor, connect_db, key_id: int, is_enabled: bool):
    """Bật / tắt USB key"""
    with _db_lock:
        try:
            cursor.execute("UPDATE ADMINISTRATOR.HARDWARE_KEY_CONFIG SET is_enabled = %s WHERE id = %s", (int(is_enabled), key_id))
            connect_db.commit()
            return True
        except Exception:
            connect_db.rollback()
            return False


def is_usb_serial_authorized(cursor, hash_code: str) -> bool:
    """Kiểm tra xem serial USB có được phép sử dụng app không"""
    with _db_lock:
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM ADMINISTRATOR.HARDWARE_KEY_CONFIG WHERE hash_code = %s AND is_enabled = 1",
                (hash_code,)
            )
            return cursor.fetchone()[0] > 0
        except Exception:
            return False


# ─────────────────────────────────────────────
#  SAFE CURSOR EXTRACTION & CONNECTION HEALTH HELPER
# ─────────────────────────────────────────────
def _extract_active_cursor(conn_or_cursor):
    """
    Kiểm tra và chuẩn hóa đối tượng kết nối/cursor:
    - Nhận vào:
        + MySQLConnection (gốc)
        + Cursor (MySQLCursor, CMySQLCursor, ...)
        + Đối tượng bọc (CoreLogic/main_core, DatabaseManager, Connect2Mysql) chứa .connection hoặc .cursor
        + None hoặc object bất kỳ.
    - Kiểm tra tính sống của socket qua is_connected(), tự khôi phục nếu cần.
    - Kiểm tra cursor._closed, tự tạo cursor mới nếu cursor cũ đã bị đóng.
    - Xả sạch unread_result để tránh xung đột 'Unread result found'.
    - Trả về tuple: (active_cursor, should_close: bool)
    """
    if conn_or_cursor is None:
        return None, False

    with _db_lock:
        try:
            obj = conn_or_cursor

            # Bước 0: Nếu đối tượng truyền vào là wrapper (như CoreLogic/main_core) chứa .connection hoặc .cursor
            # Ưu tiên bóc tách .connection thật sự nếu có
            if not (hasattr(obj, 'execute') and callable(getattr(obj, 'execute', None))):
                inner_conn = getattr(obj, 'connection', None)
                if inner_conn is not None and hasattr(inner_conn, 'cursor') and callable(getattr(inner_conn, 'cursor', None)):
                    obj = inner_conn
                elif hasattr(obj, 'cursor'):
                    inner_cur = getattr(obj, 'cursor', None)
                    if inner_cur is not None and hasattr(inner_cur, 'execute') and callable(getattr(inner_cur, 'execute', None)):
                        obj = inner_cur

            # Bước 1: obj là Cursor object (có method execute callable)
            if hasattr(obj, 'execute') and callable(getattr(obj, 'execute', None)):
                cur = obj
                is_closed = getattr(cur, '_closed', False) or getattr(cur, 'closed', False)
                conn = getattr(cur, '_connection', None) or getattr(cur, 'connection', None)

                # Nếu cursor đã bị đóng nhưng connection còn sống -> tạo cursor mới
                if is_closed:
                    if conn and hasattr(conn, 'is_connected'):
                        try:
                            if not conn.is_connected():
                                conn.reconnect(attempts=1, delay=0)
                            if conn.is_connected():
                                new_cur = conn.cursor(buffered=True)
                                return new_cur, True
                        except Exception:
                            return None, False
                    return None, False

                # Cursor chưa đóng: kiểm tra connection bên dưới
                if conn and hasattr(conn, 'is_connected'):
                    try:
                        if not conn.is_connected():
                            conn.reconnect(attempts=1, delay=0)
                    except Exception:
                        return None, False

                # Xả sạch kết quả chưa đọc nếu có
                if getattr(cur, 'unread_result', False) or getattr(cur, '_have_unread_result', False):
                    try:
                        cur.fetchall()
                    except Exception:
                        pass

                return cur, False

            # Bước 2: obj là Connection object (có method cursor callable)
            cursor_method = getattr(obj, 'cursor', None)
            if cursor_method is not None and callable(cursor_method):
                conn = obj
                if hasattr(conn, 'is_connected'):
                    try:
                        if not conn.is_connected():
                            conn.reconnect(attempts=1, delay=0)
                    except Exception:
                        return None, False
                cur = conn.cursor(buffered=True)
                return cur, True

        except Exception as e:
            print(f"[_extract_active_cursor] Lỗi trích xuất cursor: {e}")
            return None, False

    return None, False


# ─────────────────────────────────────────────
#  SYSTEM CONFIG CRUD (Auto-start & System Settings)
# ─────────────────────────────────────────────
def get_system_config(cursor=None, config_key: str = "", default: str = None, conn_or_cursor=None) -> str:
    """Lấy giá trị cấu hình từ bảng ADMINISTRATOR.SYSTEM_CONFIG (an toàn với connection hoặc cursor)"""
    with _db_lock:
        target = conn_or_cursor if conn_or_cursor is not None else cursor
        if target is None:
            return default
        cur, should_close = _extract_active_cursor(target)
        if cur is None:
            return default
        try:
            cur.execute(
                "SELECT config_value FROM ADMINISTRATOR.SYSTEM_CONFIG WHERE config_key = %s",
                (config_key,)
            )
            row = cur.fetchone()
            if row is not None and len(row) > 0:
                return row[0]
            return default
        except Exception as e:
            print(f"[get_system_config] Lỗi: {e}")
            return default
        finally:
            if should_close:
                try:
                    cur.close()
                except Exception:
                    pass


def set_system_config(cursor=None, connect_db=None, config_key: str = "", config_value: str = "", description: str = "") -> bool:
    """Lưu giá trị cấu hình vào bảng ADMINISTRATOR.SYSTEM_CONFIG (Upsert)"""
    with _db_lock:
        target = cursor or connect_db
        cur, should_close = _extract_active_cursor(target)
        if cur is None:
            return False
        conn = getattr(connect_db, 'connection', None) or connect_db or getattr(cur, '_connection', None) or getattr(cur, 'connection', None)
        try:
            cur.execute(
                """
                INSERT INTO ADMINISTRATOR.SYSTEM_CONFIG (config_key, config_value, description)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    config_value = VALUES(config_value),
                    description = VALUES(description),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (config_key, config_value, description)
            )
            if conn and hasattr(conn, 'commit'):
                conn.commit()
            return True
        except Exception as e:
            if conn and hasattr(conn, 'rollback'):
                try:
                    conn.rollback()
                except Exception:
                    pass
            print(f"[set_system_config] Lỗi: {e}")
            return False
        finally:
            if should_close:
                try:
                    cur.close()
                except Exception:
                    pass


def get_auto_start_setting(cursor) -> bool:
    """Đọc cấu hình tự khởi động từ database (True nếu bật, False nếu tắt)"""
    with _db_lock:
        val = get_system_config(cursor, 'auto_start_on_boot', default='0')
        return str(val).strip() in ('1', 'true', 'True')


def set_auto_start_setting(cursor, connect_db, enabled: bool) -> bool:
    """Lưu trạng thái tự khởi động vào database"""
    with _db_lock:
        val = '1' if enabled else '0'
        desc = 'Automatic application launch on Windows system startup'
        return set_system_config(cursor, connect_db, 'auto_start_on_boot', val, desc)


# ─────────────────────────────────────────────
#  WATCHDOG & CONTINUOUS CONNECTION SETTINGS
# ─────────────────────────────────────────────
WATCHDOG_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchdog_config.json")


def get_watchdog_settings(cursor=None, conn_or_cursor=None) -> dict:
    """
    Đọc cấu hình 3 tính năng giám sát kết nối liên tục toàn thời gian (Watchdog):
    - 'hardware_key': Giám sát liên tục USB Hardware Key (mặc định True)
    - 'plc': Giám sát liên tục kết nối PLC (mặc định True)
    - 'camera': Giám sát liên tục kết nối Camera (mặc định True)
    """
    target = conn_or_cursor if conn_or_cursor is not None else cursor
    settings = {
        'hardware_key': True,
        'plc': True,
        'camera': True
    }

    # 1. Thử đọc từ local json file trước
    if os.path.exists(WATCHDOG_CONFIG_FILE):
        try:
            with open(WATCHDOG_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for k in settings:
                        if k in data:
                            settings[k] = bool(data[k])
        except Exception as e:
            print(f"[get_watchdog_settings] Lỗi đọc json: {e}")

    # 2. Nếu có connection / cursor database, ưu tiên đọc từ ADMINISTRATOR.SYSTEM_CONFIG
    if target is not None:
        with _db_lock:
            cur, should_close = _extract_active_cursor(target)
            if cur is not None:
                try:
                    cur.execute(
                        "SELECT config_key, config_value FROM ADMINISTRATOR.SYSTEM_CONFIG "
                        "WHERE config_key IN ('watchdog_hardware_key', 'watchdog_plc', 'watchdog_camera')"
                    )
                    rows = cur.fetchall()
                    for r in rows:
                        k, v = r[0], r[1]
                        b_val = str(v).strip() in ('1', 'true', 'True')
                        if k == 'watchdog_hardware_key':
                            settings['hardware_key'] = b_val
                        elif k == 'watchdog_plc':
                            settings['plc'] = b_val
                        elif k == 'watchdog_camera':
                            settings['camera'] = b_val
                except Exception as e:
                    print(f"[get_watchdog_settings] Lỗi đọc database: {e}")
                finally:
                    if should_close:
                        try:
                            cur.close()
                        except Exception:
                            pass

    return settings


def set_watchdog_settings(cursor=None, connect_db=None, hardware_key: bool = True, plc: bool = True, camera: bool = True, conn_or_cursor=None) -> bool:
    """
    Lưu cấu hình 3 tính năng giám sát kết nối liên tục vào local json và MySQL database.
    """
    target = conn_or_cursor if conn_or_cursor is not None else cursor
    settings = {
        'hardware_key': bool(hardware_key),
        'plc': bool(plc),
        'camera': bool(camera)
    }

    # 1. Lưu vào file json
    try:
        with open(WATCHDOG_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[set_watchdog_settings] Lỗi ghi file json: {e}")

    # 2. Lưu vào database nếu có connection hoặc cursor
    ok = True
    with _db_lock:
        cur, should_close = _extract_active_cursor(target or connect_db)
        if cur is not None:
            conn = getattr(connect_db, 'connection', None) or connect_db or getattr(cur, '_connection', None) or getattr(cur, 'connection', None)
            try:
                set_system_config(cur, conn, 'watchdog_hardware_key', '1' if hardware_key else '0', 'Continuous USB Hardware Key Watchdog')
                set_system_config(cur, conn, 'watchdog_plc', '1' if plc else '0', 'Continuous PLC Connection Watchdog')
                set_system_config(cur, conn, 'watchdog_camera', '1' if camera else '0', 'Continuous Camera Connection Watchdog')
                if conn and hasattr(conn, 'commit'):
                    conn.commit()
            except Exception as e:
                print(f"[set_watchdog_settings] Lỗi lưu database: {e}")
                ok = False
            finally:
                if should_close:
                    try:
                        cur.close()
                    except Exception:
                        pass

    return ok


def is_watchdog_enabled(watchdog_type: str, cursor=None, conn_or_cursor=None) -> bool:
    """
    Kiểm tra nhanh xem 1 tính năng watchdog cụ thể có đang được bật hay không.
    watchdog_type: 'hardware_key', 'plc', 'camera'
    """
    with _db_lock:
        target = conn_or_cursor if conn_or_cursor is not None else cursor
        settings = get_watchdog_settings(conn_or_cursor=target)
        return settings.get(watchdog_type, True)


