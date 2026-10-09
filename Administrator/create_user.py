# Administrator/create_user.py
# Giao diện tạo User mới

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from Administrator.user_db import create_user, get_user_count


class CreateUserDialog(QDialog):
    """Dialog cho phép người dùng tạo tài khoản mới"""
    def __init__(self, cursor, connect_db, max_users=10, parent=None):
        super().__init__(parent)
        self.cursor = cursor
        self.connect_db = connect_db
        self.max_users = max_users
        self.setWindowTitle("👤 Tạo tài khoản User mới")
        self.setFixedSize(460, 340)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(28, 24, 28, 24)

        # ── Header ──
        header = QLabel("👤 TẠO TÀI KHOẢN MỚI")
        header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("color: #1E3A5F; padding-bottom: 8px; border-bottom: 2px solid #22C55E;")
        layout.addWidget(header)

        desc = QLabel("Nhập thông tin để tạo tài khoản user mới.\nSau khi tạo, Administrator có thể quản lý quyền hạn.")
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #64748B; font-size: 11px;")
        layout.addWidget(desc)

        # ── Form ──
        form = QGridLayout()
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(12)

        form.addWidget(QLabel("Username:"), 0, 0)
        self.txt_username = QLineEdit()
        self.txt_username.setPlaceholderText("Nhập tên đăng nhập...")
        form.addWidget(self.txt_username, 0, 1)

        form.addWidget(QLabel("Mật khẩu:"), 1, 0)
        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.Password)
        self.txt_password.setPlaceholderText("Nhập mật khẩu...")
        form.addWidget(self.txt_password, 1, 1)

        form.addWidget(QLabel("Xác nhận MK:"), 2, 0)
        self.txt_confirm = QLineEdit()
        self.txt_confirm.setEchoMode(QLineEdit.Password)
        self.txt_confirm.setPlaceholderText("Nhập lại mật khẩu...")
        form.addWidget(self.txt_confirm, 2, 1)

        form.addWidget(QLabel("Quyền hạn:"), 3, 0)
        self.cmb_role = QComboBox()
        self.cmb_role.addItems(["read_only", "modify", "full_control"])
        self.cmb_role.setCurrentText("read_only")
        form.addWidget(self.cmb_role, 3, 1)

        layout.addLayout(form)

        # ── Buttons ──
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Hủy")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_layout.addStretch()

        btn_save = QPushButton("✅ Tạo tài khoản")
        btn_save.setStyleSheet("QPushButton { background-color: #22C55E; color: white; padding: 8px 24px; font-weight: bold; }")
        btn_save.clicked.connect(self._on_create)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def _on_create(self):
        username = self.txt_username.text().strip()
        password = self.txt_password.text().strip()
        confirm = self.txt_confirm.text().strip()
        role = self.cmb_role.currentText()

        # Validation
        if not username:
            QMessageBox.warning(self, "Cảnh báo", "Username không được để trống!")
            return
        if len(username) < 3:
            QMessageBox.warning(self, "Cảnh báo", "Username phải có ít nhất 3 ký tự!")
            return
        if not password:
            QMessageBox.warning(self, "Cảnh báo", "Mật khẩu không được để trống!")
            return
        if len(password) < 4:
            QMessageBox.warning(self, "Cảnh báo", "Mật khẩu phải có ít nhất 4 ký tự!")
            return
        if password != confirm:
            QMessageBox.critical(self, "Lỗi", "Mật khẩu và xác nhận không khớp!")
            return

        # Kiểm tra giới hạn user
        current_count = get_user_count(self.cursor)
        if current_count >= self.max_users:
            QMessageBox.critical(
                self, "Giới hạn",
                f"Đã đạt giới hạn tối đa {self.max_users} user!\n"
                "Liên hệ Administrator để tăng giới hạn hoặc xóa user cũ."
            )
            return

        # Tạo user
        ok, msg = create_user(self.cursor, self.connect_db, username, password, role)
        if ok:
            QMessageBox.information(self, "Thành công", f"Đã tạo tài khoản '{username}' thành công!")
            self.accept()
        else:
            QMessageBox.critical(self, "Lỗi", msg)


def open_create_user(cursor, connect_db, connection, parent=None):
    """Entry point: Tạo bảng nếu chưa có → Mở dialog tạo user"""
    from Administrator.user_db import ensure_admin_tables
    ensure_admin_tables(connection)
    dialog = CreateUserDialog(cursor, connect_db, parent=parent)
    dialog.exec_()
