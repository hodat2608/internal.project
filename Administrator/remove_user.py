# Administrator/remove_user.py
# Giao diện xóa User - Yêu cầu mật khẩu Administrator

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from Administrator.admin_config import AdminPasswordDialog
from Administrator.user_db import get_all_users, delete_user


class RemoveUserWindow(QDialog):
    """Cửa sổ cho phép Administrator xóa user"""
    def __init__(self, cursor, connect_db, parent=None):
        super().__init__(parent)
        self.cursor = cursor
        self.connect_db = connect_db
        self.setWindowTitle("🗑️ Remove User - Administrator")
        self.setMinimumSize(700, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._build_ui()
        self._load_users()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # ── Header ──
        header = QLabel("🗑️ QUẢN LÝ XÓA TÀI KHOẢN USER")
        header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("color: #DC2626; padding-bottom: 8px; border-bottom: 2px solid #EF4444;")
        layout.addWidget(header)

        desc = QLabel("Chọn user cần xóa. Hành động này không thể hoàn tác!\nChỉ Administrator mới có quyền thực hiện.")
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #64748B; font-size: 11px; padding: 4px;")
        layout.addWidget(desc)

        # ── User Table ──
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(6)
        self.user_table.setHorizontalHeaderLabels(["", "ID", "Username", "Quyền", "Trạng thái", "Ngày tạo"])
        self.user_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.user_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.user_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.user_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.user_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.user_table.setAlternatingRowColors(True)
        layout.addWidget(self.user_table)

        # ── Buttons ──
        btn_layout = QHBoxLayout()

        btn_refresh = QPushButton("🔄 Làm mới")
        btn_refresh.clicked.connect(self._load_users)
        btn_layout.addWidget(btn_refresh)

        btn_layout.addStretch()

        self.lbl_selected = QLabel("Đã chọn: 0 user")
        self.lbl_selected.setStyleSheet("color: #64748B; font-weight: bold;")
        btn_layout.addWidget(self.lbl_selected)

        btn_delete = QPushButton("🗑️ Xóa các user đã chọn")
        btn_delete.setStyleSheet("QPushButton { background-color: #DC2626; color: white; padding: 8px 20px; font-weight: bold; }")
        btn_delete.clicked.connect(self._on_delete_selected)
        btn_layout.addWidget(btn_delete)

        layout.addLayout(btn_layout)

    def _load_users(self):
        self.checkboxes = []
        users = get_all_users(self.cursor)
        self.user_table.setRowCount(len(users))

        for row, user in enumerate(users):
            uid, username, role, is_active, created_at, last_login = user

            # Checkbox chọn
            chk = QCheckBox()
            chk.stateChanged.connect(self._update_selected_count)
            chk.setProperty("user_id", uid)
            chk.setProperty("username", username)
            self.checkboxes.append(chk)
            self.user_table.setCellWidget(row, 0, chk)

            self.user_table.setItem(row, 1, QTableWidgetItem(str(uid)))
            self.user_table.setItem(row, 2, QTableWidgetItem(username))
            self.user_table.setItem(row, 3, QTableWidgetItem(role))

            status_text = "✅ Kích hoạt" if is_active else "❌ Vô hiệu hóa"
            item_status = QTableWidgetItem(status_text)
            item_status.setForeground(Qt.darkGreen if is_active else Qt.red)
            self.user_table.setItem(row, 4, item_status)

            date_str = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "N/A"
            self.user_table.setItem(row, 5, QTableWidgetItem(date_str))

        self._update_selected_count()

    def _update_selected_count(self):
        count = sum(1 for chk in self.checkboxes if chk.isChecked())
        self.lbl_selected.setText(f"Đã chọn: {count} user")

    def _on_delete_selected(self):
        selected = [(chk.property("user_id"), chk.property("username"))
                     for chk in self.checkboxes if chk.isChecked()]

        if not selected:
            QMessageBox.warning(self, "Cảnh báo", "Chưa chọn user nào để xóa!")
            return

        names = ", ".join([s[1] for s in selected])
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa {len(selected)} user sau?\n\n"
            f"👤 {names}\n\n"
            "⚠️ Hành động này KHÔNG THỂ hoàn tác!",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        success_count = 0
        for uid, uname in selected:
            ok, msg = delete_user(self.cursor, self.connect_db, uid)
            if ok:
                success_count += 1

        QMessageBox.information(
            self, "Kết quả",
            f"Đã xóa thành công {success_count}/{len(selected)} user."
        )
        self._load_users()


def open_remove_user(cursor, connect_db,connection,parent=None):
    """Entry point: Kiểm tra admin password rồi mở Remove User"""
    from Administrator.user_db import ensure_admin_tables
    ensure_admin_tables(connection)
    auth = AdminPasswordDialog(parent)
    if auth.exec_() == QDialog.Accepted and auth.authenticated:
        dialog = RemoveUserWindow(cursor, connect_db, parent)
        dialog.exec_()
