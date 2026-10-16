# Administrator/user_db.py
# Database operations cho quản lý User và Hardware Key

import hashlib
from datetime import datetime
from PyQt5.QtWidgets import QMessageBox


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
    """
]


def ensure_admin_tables(connection):
    """
    Tạo bảng ADMIN_USERS và HARDWARE_KEY_CONFIG nếu chưa tồn tại.
    Gọi hàm này khi app khởi động hoặc khi nhấn Configure Settings.
    
    Args:
        connection: MySQL connection object (không phải cursor)
    """
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
    print("connect_db",connect_db)
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
    try:
        cursor.execute("DELETE FROM ADMINISTRATOR.ADMIN_USERS WHERE id = %s", (user_id,))
        connect_db.commit()
        return True, "Xóa user thành công!"
    except Exception as e:
        connect_db.rollback()
        return False, f"Lỗi: {e}"


def get_all_users(cursor):
    """Lấy danh sách tất cả users"""
    try:
        cursor.execute(
            "SELECT id, username, role, is_active, created_at, last_login FROM ADMINISTRATOR.ADMIN_USERS ORDER BY id"
        )
        return cursor.fetchall()
    except Exception:
        return []


def update_user_role(cursor, connect_db, user_id: int, new_role: str):
    """Cập nhật quyền của user"""
    try:
        cursor.execute("UPDATE ADMINISTRATOR.ADMIN_USERS SET role = %s WHERE id = %s", (new_role, user_id))
        connect_db.commit()
        return True
    except Exception:
        connect_db.rollback()
        return False


def toggle_user_active(cursor, connect_db, user_id: int, is_active: bool):
    """Vô hiệu hóa / kích hoạt user"""
    try:
        cursor.execute("UPDATE ADMINISTRATOR.ADMIN_USERS SET is_active = %s WHERE id = %s", (int(is_active), user_id))
        connect_db.commit()
        return True
    except Exception:
        connect_db.rollback()
        return False


def get_user_count(cursor) -> int:
    """Đếm số lượng user hiện tại"""
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
    try:
        cursor.execute("DELETE FROM ADMINISTRATOR.HARDWARE_KEY_CONFIG WHERE id = %s", (key_id,))
        connect_db.commit()
        return True
    except Exception:
        connect_db.rollback()
        return False


def get_all_hardware_keys(cursor):
    """Lấy danh sách tất cả USB keys đã đăng ký"""
    try:
        cursor.execute("SELECT id, serial_number, hash_code, description, is_enabled, registered_at FROM ADMINISTRATOR.HARDWARE_KEY_CONFIG ORDER BY id")
        return cursor.fetchall()
    except Exception:
        return []


def toggle_hardware_key(cursor, connect_db, key_id: int, is_enabled: bool):
    """Bật / tắt USB key"""
    try:
        cursor.execute("UPDATE ADMINISTRATOR.HARDWARE_KEY_CONFIG SET is_enabled = %s WHERE id = %s", (int(is_enabled), key_id))
        connect_db.commit()
        return True
    except Exception:
        connect_db.rollback()
        return False


def is_usb_serial_authorized(cursor, hash_code: str) -> bool:
    """Kiểm tra xem serial USB có được phép sử dụng app không"""
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM ADMINISTRATOR.HARDWARE_KEY_CONFIG WHERE hash_code = %s AND is_enabled = 1",
            (hash_code,)
        )
        return cursor.fetchone()[0] > 0
    except Exception:
        return False
