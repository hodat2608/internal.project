# Administrator/admin_config.py
# Giao diện Configure Settings - Dành cho Administrator
# Quản lý User, mật khẩu Admin, cấu hình Auto-Start on System Boot và cài đặt hệ thống

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QComboBox, QSpinBox, QCheckBox, QHeaderView, QMessageBox, QInputDialog,
    QScrollArea, QFrame, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon
from Administrator.user_db import (
    verify_admin_password, get_admin_password_hash, save_admin_password_hash,
    hash_password, get_all_users, update_user_role, toggle_user_active,
    delete_user, get_user_count,
    get_system_config, set_system_config,
    get_auto_start_setting, set_auto_start_setting
)
from Administrator.autostart_manager import (
    get_app_executable_path,
    get_app_launch_command,
    is_registry_autostart_enabled,
    set_auto_start_registry,
    cleanup_startup_folder_shortcuts
)


class AdminPasswordDialog(QDialog):
    """Dialog nhập password admin trước khi vào Configure Settings"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔒 Administrator Authentication")
        self.setFixedSize(420, 220)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._build_ui()
        self.authenticated = False

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header
        header = QLabel("🔐 Nhập mật khẩu Administrator")
        header.setFont(QFont("Segoe UI", 14, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("color: #1E3A5F; padding: 8px;")
        layout.addWidget(header)

        desc = QLabel("Chức năng này chỉ dành cho Administrator.\nVui lòng nhập mật khẩu để tiếp tục.")
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #64748B; font-size: 11px;")
        layout.addWidget(desc)

        # Password field
        pw_layout = QHBoxLayout()
        pw_label = QLabel("Mật khẩu:")
        pw_label.setFixedWidth(80)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Nhập mật khẩu admin...")
        self.password_input.returnPressed.connect(self._on_login)
        pw_layout.addWidget(pw_label)
        pw_layout.addWidget(self.password_input)
        layout.addLayout(pw_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Hủy")
        btn_cancel.clicked.connect(self.reject)
        btn_login = QPushButton("Xác nhận")
        btn_login.setStyleSheet("QPushButton { background-color: #2563EB; color: white; padding: 6px 20px; font-weight: bold; }")
        btn_login.clicked.connect(self._on_login)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_login)
        layout.addLayout(btn_layout)

    def _on_login(self):
        password = self.password_input.text().strip()
        if not password:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập mật khẩu!")
            return
        if verify_admin_password(password):
            self.authenticated = True
            self.accept()
        else:
            QMessageBox.critical(self, "Sai mật khẩu", "Mật khẩu không chính xác!\nVui lòng thử lại.")
            self.password_input.clear()
            self.password_input.setFocus()


class AdminConfigWindow(QDialog):
    """Cửa sổ Configure Settings chính cho Administrator"""
    def __init__(self, cursor, connect_db, parent=None):
        super().__init__(parent)
        self.cursor = cursor
        self.connect_db = connect_db
        self.setWindowTitle("⚙️ Administrator - Configure Settings")
        self.setMinimumSize(860, 680)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._build_ui()
        self._load_users()
        self._load_startup_config()
        self._load_general_settings()

    def _build_ui(self):
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(12, 12, 12, 12)
        dialog_layout.setSpacing(10)

        # ── Scroll Area bọc ngoài để giao diện hiển thị hoàn hảo trên mọi độ phân giải ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # ── Title ──
        title = QLabel("⚙️ ADMINISTRATOR CONTROL PANEL")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #1E3A5F; padding: 8px; border-bottom: 2px solid #3B82F6;")
        main_layout.addWidget(title)

        # ── Group 1: Đổi mật khẩu Admin ──
        grp_password = QGroupBox("🔑 Đổi mật khẩu Administrator")
        grp_password.setFont(QFont("Segoe UI", 11, QFont.Bold))
        pw_layout = QGridLayout(grp_password)
        pw_layout.setSpacing(8)

        pw_layout.addWidget(QLabel("Mật khẩu hiện tại:"), 0, 0)
        self.current_pw = QLineEdit()
        self.current_pw.setEchoMode(QLineEdit.Password)
        pw_layout.addWidget(self.current_pw, 0, 1)

        pw_layout.addWidget(QLabel("Mật khẩu mới:"), 1, 0)
        self.new_pw = QLineEdit()
        self.new_pw.setEchoMode(QLineEdit.Password)
        pw_layout.addWidget(self.new_pw, 1, 1)

        pw_layout.addWidget(QLabel("Xác nhận mật khẩu:"), 2, 0)
        self.confirm_pw = QLineEdit()
        self.confirm_pw.setEchoMode(QLineEdit.Password)
        pw_layout.addWidget(self.confirm_pw, 2, 1)

        btn_change_pw = QPushButton("Đổi mật khẩu")
        btn_change_pw.setStyleSheet("QPushButton { background-color: #DC2626; color: white; padding: 6px 16px; font-weight: bold; border-radius: 4px; }")
        btn_change_pw.clicked.connect(self._change_admin_password)
        pw_layout.addWidget(btn_change_pw, 3, 1, alignment=Qt.AlignRight)
        main_layout.addWidget(grp_password)

        # ── Group 2: Quản lý User ──
        grp_users = QGroupBox("👥 Quản lý tài khoản User")
        grp_users.setFont(QFont("Segoe UI", 11, QFont.Bold))
        user_layout = QVBoxLayout(grp_users)
        user_layout.setSpacing(8)

        # User count info
        info_layout = QHBoxLayout()
        self.lbl_user_count = QLabel("Tổng số user: 0")
        self.lbl_user_count.setStyleSheet("font-weight: bold; color: #2563EB;")
        info_layout.addWidget(self.lbl_user_count)
        info_layout.addStretch()

        lbl_max = QLabel("Giới hạn user tối đa:")
        self.spn_max_users = QSpinBox()
        self.spn_max_users.setRange(1, 100)
        self.spn_max_users.setValue(10)
        info_layout.addWidget(lbl_max)
        info_layout.addWidget(self.spn_max_users)
        user_layout.addLayout(info_layout)

        # User table
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(6)
        self.user_table.setHorizontalHeaderLabels(["ID", "Username", "Quyền", "Trạng thái", "Ngày tạo", "Thao tác"])
        self.user_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.user_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.user_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.user_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.user_table.setAlternatingRowColors(True)
        self.user_table.setMinimumHeight(180)
        user_layout.addWidget(self.user_table)

        # Action buttons
        act_layout = QHBoxLayout()
        btn_refresh = QPushButton("🔄 Làm mới danh sách")
        btn_refresh.clicked.connect(self._load_users)
        act_layout.addWidget(btn_refresh)
        act_layout.addStretch()
        user_layout.addLayout(act_layout)

        main_layout.addWidget(grp_users)

        # ── Group 3: Cấu hình tự động khởi động (System Startup & Boot Management) ──
        grp_startup = QGroupBox("🚀 Cấu hình khởi động hệ thống (System Startup & Boot Management)")
        grp_startup.setFont(QFont("Segoe UI", 11, QFont.Bold))
        startup_layout = QVBoxLayout(grp_startup)
        startup_layout.setSpacing(10)

        # Checkbox Auto-Start
        self.chk_auto_start = QCheckBox("Tự động khởi động phần mềm khi bật máy tính (Auto-Start on System Boot)")
        self.chk_auto_start.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.chk_auto_start.setStyleSheet("QCheckBox { color: #1E3A5F; spacing: 8px; } QCheckBox::indicator { width: 18px; height: 18px; }")
        startup_layout.addWidget(self.chk_auto_start)

        # Explanation / Tech Note
        lbl_startup_desc = QLabel(
            "ℹ️ Tự động đăng ký vào Windows Startup Registry (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run).\n"
            "Chạy tự động khi Windows khởi động mà không cần quyền Administrator và không cần copy app vào shell:startup."
        )
        lbl_startup_desc.setStyleSheet("color: #475569; font-size: 11px; padding-left: 26px;")
        startup_layout.addWidget(lbl_startup_desc)

        # Status & Details Box
        status_frame = QFrame()
        status_frame.setStyleSheet("QFrame { background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 6px; padding: 6px; }")
        status_layout = QGridLayout(status_frame)
        status_layout.setHorizontalSpacing(14)
        status_layout.setVerticalSpacing(6)

        status_layout.addWidget(QLabel("Trạng thái Windows Registry:"), 0, 0)
        self.lbl_reg_status = QLabel("Đang kiểm tra...")
        self.lbl_reg_status.setStyleSheet("font-weight: bold; color: #64748B;")
        status_layout.addWidget(self.lbl_reg_status, 0, 1)

        status_layout.addWidget(QLabel("Trạng thái Database (MySQL):"), 1, 0)
        self.lbl_db_status = QLabel("Đang kiểm tra...")
        self.lbl_db_status.setStyleSheet("font-weight: bold; color: #64748B;")
        status_layout.addWidget(self.lbl_db_status, 1, 1)

        status_layout.addWidget(QLabel("Lệnh thực thi (Launch Command):"), 2, 0)
        self.txt_exe_command = QLineEdit()
        self.txt_exe_command.setReadOnly(True)
        self.txt_exe_command.setStyleSheet("background-color: #EDE9FE; color: #4338CA; font-family: Consolas; font-size: 11px; padding: 4px;")
        status_layout.addWidget(self.txt_exe_command, 2, 1)

        startup_layout.addWidget(status_frame)

        # Action Buttons for Startup
        startup_btn_layout = QHBoxLayout()
        btn_apply_startup = QPushButton("💾 Áp dụng & Lưu cấu hình Startup (Apply & Save)")
        btn_apply_startup.setStyleSheet("QPushButton { background-color: #2563EB; color: white; font-weight: bold; padding: 7px 18px; border-radius: 4px; } QPushButton:hover { background-color: #1D4ED8; }")
        btn_apply_startup.clicked.connect(self._apply_startup_config)
        startup_btn_layout.addWidget(btn_apply_startup)

        btn_verify_startup = QPushButton("🔄 Kiểm tra trạng thái Windows")
        btn_verify_startup.setStyleSheet("QPushButton { background-color: #0D9488; color: white; font-weight: bold; padding: 7px 14px; border-radius: 4px; } QPushButton:hover { background-color: #0F766E; }")
        btn_verify_startup.clicked.connect(self._verify_startup_status)
        startup_btn_layout.addWidget(btn_verify_startup)

        startup_btn_layout.addStretch()
        startup_layout.addLayout(startup_btn_layout)

        main_layout.addWidget(grp_startup)

        # ── Group 4: Cấu hình hệ thống chung (General System Settings) ──
        grp_system = QGroupBox("🖥️ Cấu hình hệ thống chung (General System Settings)")
        grp_system.setFont(QFont("Segoe UI", 11, QFont.Bold))
        sys_layout = QGridLayout(grp_system)
        sys_layout.setSpacing(8)

        sys_layout.addWidget(QLabel("Ngôn ngữ hiển thị:"), 0, 0)
        self.cmb_language = QComboBox()
        self.cmb_language.addItems(["Tiếng Việt", "English"])
        sys_layout.addWidget(self.cmb_language, 0, 1)

        sys_layout.addWidget(QLabel("Chế độ bảo mật:"), 1, 0)
        self.chk_require_login = QCheckBox("Yêu cầu đăng nhập khi khởi động app")
        self.chk_require_login.setChecked(True)
        sys_layout.addWidget(self.chk_require_login, 1, 1)

        sys_layout.addWidget(QLabel("Auto-lock (phút):"), 2, 0)
        self.spn_auto_lock = QSpinBox()
        self.spn_auto_lock.setRange(0, 120)
        self.spn_auto_lock.setValue(0)
        self.spn_auto_lock.setSpecialValueText("Tắt")
        sys_layout.addWidget(self.spn_auto_lock, 2, 1)

        btn_save_general = QPushButton("💾 Lưu cấu hình hệ thống chung")
        btn_save_general.setStyleSheet("QPushButton { background-color: #4F46E5; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px; }")
        btn_save_general.clicked.connect(self._save_general_settings)
        sys_layout.addWidget(btn_save_general, 3, 1, alignment=Qt.AlignRight)

        main_layout.addWidget(grp_system)

        # Thêm container vào scroll area
        scroll.setWidget(container)
        dialog_layout.addWidget(scroll)

        # ── Bottom Close Button ──
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        btn_close = QPushButton("Đóng (Close)")
        btn_close.setStyleSheet("QPushButton { padding: 6px 22px; font-weight: bold; background-color: #64748B; color: white; border-radius: 4px; }")
        btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(btn_close)
        dialog_layout.addLayout(bottom_layout)

    def _change_admin_password(self):
        current = self.current_pw.text().strip()
        new_pw = self.new_pw.text().strip()
        confirm = self.confirm_pw.text().strip()

        if not current or not new_pw or not confirm:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng điền đầy đủ các trường!")
            return
        if not verify_admin_password(current):
            QMessageBox.critical(self, "Lỗi", "Mật khẩu hiện tại không chính xác!")
            return
        if new_pw != confirm:
            QMessageBox.critical(self, "Lỗi", "Mật khẩu mới và xác nhận không khớp!")
            return
        if len(new_pw) < 6:
            QMessageBox.warning(self, "Cảnh báo", "Mật khẩu mới phải có ít nhất 6 ký tự!")
            return

        save_admin_password_hash(hash_password(new_pw))
        QMessageBox.information(self, "Thành công", "Đổi mật khẩu Administrator thành công!")
        self.current_pw.clear()
        self.new_pw.clear()
        self.confirm_pw.clear()

    def _load_users(self):
        users = get_all_users(self.cursor)
        count = get_user_count(self.cursor)
        self.lbl_user_count.setText(f"Tổng số user: {count}")
        self.user_table.setRowCount(len(users))

        for row, user in enumerate(users):
            uid, username, role, is_active, created_at, last_login = user

            self.user_table.setItem(row, 0, QTableWidgetItem(str(uid)))
            self.user_table.setItem(row, 1, QTableWidgetItem(username))

            # Quyền - ComboBox
            cmb_role = QComboBox()
            cmb_role.addItems(["read_only", "modify", "full_control"])
            cmb_role.setCurrentText(role)
            cmb_role.currentTextChanged.connect(lambda new_role, uid=uid: self._on_role_changed(uid, new_role))
            self.user_table.setCellWidget(row, 2, cmb_role)

            # Trạng thái - CheckBox
            chk_active = QCheckBox("Kích hoạt")
            chk_active.setChecked(bool(is_active))
            chk_active.stateChanged.connect(lambda state, uid=uid: self._on_active_changed(uid, state))
            self.user_table.setCellWidget(row, 3, chk_active)

            # Ngày tạo
            date_str = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "N/A"
            self.user_table.setItem(row, 4, QTableWidgetItem(date_str))

            # Nút xóa
            btn_del = QPushButton("🗑️ Xóa")
            btn_del.setStyleSheet("QPushButton { background-color: #EF4444; color: white; padding: 3px 8px; }")
            btn_del.clicked.connect(lambda _, uid=uid, uname=username: self._on_delete_user(uid, uname))
            self.user_table.setCellWidget(row, 5, btn_del)

    def _on_role_changed(self, user_id, new_role):
        if update_user_role(self.cursor, self.connect_db, user_id, new_role):
            pass  # silent success
        else:
            QMessageBox.critical(self, "Lỗi", "Không thể cập nhật quyền!")
            self._load_users()

    def _on_active_changed(self, user_id, state):
        is_active = state == Qt.Checked
        if not toggle_user_active(self.cursor, self.connect_db, user_id, is_active):
            QMessageBox.critical(self, "Lỗi", "Không thể cập nhật trạng thái!")
            self._load_users()

    def _on_delete_user(self, user_id, username):
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa user '{username}'?\nHành động này không thể hoàn tác!",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok, msg = delete_user(self.cursor, self.connect_db, user_id)
            if ok:
                QMessageBox.information(self, "Thành công", msg)
                self._load_users()
            else:
                QMessageBox.critical(self, "Lỗi", msg)

    # ─────────────────────────────────────────────
    #  AUTO-START ON SYSTEM BOOT METHODS
    # ─────────────────────────────────────────────
    def _load_startup_config(self):
        """Đọc và hiển thị trạng thái Auto-Start từ Windows Registry và Database"""
        is_reg, reg_cmd = is_registry_autostart_enabled()
        is_db = get_auto_start_setting(self.cursor)

        # Checkbox phản ánh trạng thái thực tế trong Registry
        self.chk_auto_start.setChecked(is_reg)

        # Badge Registry
        if is_reg:
            self.lbl_reg_status.setText("🟢 Đã đăng ký (Active in Windows Registry)")
            self.lbl_reg_status.setStyleSheet("color: #059669; font-weight: bold;")
        else:
            self.lbl_reg_status.setText("⚪ Chưa kích hoạt (Disabled in Windows Registry)")
            self.lbl_reg_status.setStyleSheet("color: #64748B; font-weight: bold;")

        # Badge Database
        if is_db:
            self.lbl_db_status.setText("🟢 Bật (Enabled in Database)")
            self.lbl_db_status.setStyleSheet("color: #059669; font-weight: bold;")
        else:
            self.lbl_db_status.setText("⚪ Tắt (Disabled in Database)")
            self.lbl_db_status.setStyleSheet("color: #64748B; font-weight: bold;")

        # Lệnh khởi chạy
        self.txt_exe_command.setText(get_app_launch_command())

    def _apply_startup_config(self):
        """Áp dụng thiết lập Auto-Start vào Windows Registry và lưu vào MySQL Database"""
        enable = self.chk_auto_start.isChecked()
        ok_reg, msg_reg = set_auto_start_registry(enable)
        if not ok_reg:
            QMessageBox.critical(self, "Lỗi Windows Registry", f"Không thể thay đổi cấu hình khởi động Windows:\n{msg_reg}")
            self._load_startup_config()
            return

        # Lưu vào Database
        ok_db = set_auto_start_setting(self.cursor, self.connect_db, enable)
        self._load_startup_config()

        status_text = "ĐÃ BẬT (Enabled)" if enable else "ĐÃ TẮT (Disabled)"
        detail_msg = (
            f"Đã cập nhật cấu hình tự khởi động thành công!\n\n"
            f"• Trạng thái: {status_text}\n"
            f"• Windows Registry: Đã đồng bộ vào HKCU Run\n"
            f"• Cơ sở dữ liệu MySQL: Đã lưu vào ADMINISTRATOR.SYSTEM_CONFIG\n\n"
        )
        if enable:
            detail_msg += "Từ bây giờ, phần mềm sẽ tự động khởi động ngay khi Windows bật máy mà không cần thao tác shell:startup thủ công."
        else:
            detail_msg += "Phần mềm sẽ không tự khởi động khi bật máy."

        if not ok_db:
            detail_msg += "\n\n⚠️ Lưu ý: Windows Registry đã được thiết lập thành công nhưng lưu vào Database có cảnh báo."

        QMessageBox.information(self, "Thành công (Auto-Start Config)", detail_msg)

    def _verify_startup_status(self):
        """Kiểm tra lại trạng thái thực tế từ Registry và Database"""
        self._load_startup_config()
        is_reg, cmd = is_registry_autostart_enabled()
        status_text = "ĐANG BẬT (Active)" if is_reg else "ĐANG TẮT (Disabled)"
        msg = f"Trạng thái Windows Startup Registry hiện tại: {status_text}"
        if is_reg and cmd:
            msg += f"\nLệnh đăng ký: {cmd}"
        QMessageBox.information(self, "Kiểm tra trạng thái", msg)

    # ─────────────────────────────────────────────
    #  GENERAL SYSTEM SETTINGS METHODS
    # ─────────────────────────────────────────────
    def _load_general_settings(self):
        """Tải các thiết lập hệ thống từ Database"""
        try:
            lang = get_system_config(self.cursor, 'system_language', default='Tiếng Việt')
            self.cmb_language.setCurrentText(lang)

            req_login = get_system_config(self.cursor, 'require_login', default='1')
            self.chk_require_login.setChecked(req_login == '1')

            auto_lock = get_system_config(self.cursor, 'auto_lock_minutes', default='0')
            self.spn_auto_lock.setValue(int(auto_lock) if auto_lock.isdigit() else 0)
        except Exception:
            pass

    def _save_general_settings(self):
        """Lưu các thiết lập hệ thống vào Database"""
        try:
            set_system_config(self.cursor, self.connect_db, 'system_language', self.cmb_language.currentText(), 'Display language')
            set_system_config(self.cursor, self.connect_db, 'require_login', '1' if self.chk_require_login.isChecked() else '0', 'Require login at app startup')
            set_system_config(self.cursor, self.connect_db, 'auto_lock_minutes', str(self.spn_auto_lock.value()), 'Auto lock timeout in minutes')
            QMessageBox.information(self, "Thành công", "Lưu cấu hình hệ thống chung vào Database thành công!")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu cấu hình hệ thống: {e}")


def open_admin_config(cursor, connect_db, connection, parent=None):
    """Entry point: Tạo bảng nếu chưa có → Kiểm tra mật khẩu admin → Mở Configure Settings"""
    from Administrator.user_db import ensure_admin_tables
    ensure_admin_tables(connection)
    auth = AdminPasswordDialog(parent)
    if auth.exec_() == QDialog.Accepted and auth.authenticated:
        dialog = AdminConfigWindow(cursor, connect_db, parent)
        dialog.exec_()
