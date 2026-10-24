# -*- coding: utf-8 -*-
"""
Module: auth_dialog.py
Chức năng: Hộp thoại xác thực phân quyền người dùng chuyên nghiệp (Enterprise Security Authentication Dialog).
Hỗ trợ kiểm tra quyền hạn (Role-Based Access Control):
- Administrator (Master System)
- full_control: Toàn quyền cấu hình & chỉnh sửa
- modify: Chỉ hiệu chỉnh thông số bảng (TableView)
- read_only: Chỉ xem, khóa toàn bộ chức năng
"""

from PyQt5 import QtCore, QtGui, QtWidgets
from typing import Optional, Tuple


class EnterpriseAuthDialog(QtWidgets.QDialog):
    """
    Hộp thoại xác thực người dùng giao diện doanh nghiệp cao cấp.
    Hỗ trợ hiển thị vai trò người dùng theo thời gian thực (Live Role Preview)
    và kiểm tra mật khẩu qua CSDL hoặc Master Admin.
    """

    ROLE_DETAILS = {
        "__ADMIN__": {
            "title": "QUẢN TRỊ VIÊN TỐI CAO (MASTER ADMIN)",
            "desc": "Toàn quyền quản trị, cấu hình và can thiệp toàn bộ hệ thống.",
            "color": "#1D4ED8",
            "bg": "#EFF6FF",
            "border": "#93C5FD",
            "icon": "👑"
        },
        "full_control": {
            "title": "FULL CONTROL (TOÀN QUYỀN ĐIỀU KHIỂN)",
            "desc": "Toàn quyền hiệu chỉnh thông số mô hình, camera và tín hiệu PLC.",
            "color": "#15803D",
            "bg": "#F0FDF4",
            "border": "#86EFAC",
            "icon": "⚡"
        },
        "modify": {
            "title": "MODIFY (HIỆU CHỈNH THÔNG SỐ)",
            "desc": "Được phép điều chỉnh và lưu Bảng thông số Model (TableView).",
            "color": "#B45309",
            "bg": "#FFFBEB",
            "border": "#FDE68A",
            "icon": "✏️"
        },
        "read_only": {
            "title": "READ ONLY (CHỈ XEM)",
            "desc": "Tài khoản chỉ xem. Hệ thống tiếp tục KHÓA toàn bộ chức năng.",
            "color": "#B91C1C",
            "bg": "#FEF2F2",
            "border": "#FECACA",
            "icon": "🔒"
        }
    }

    def __init__(self, cursor, parent=None, system_context: str = "Hệ Thống Quản Lý Vision"):
        super().__init__(parent)
        self.cursor = cursor
        self.system_context = system_context
        
        # Kết quả xác thực
        self.auth_success = False
        self.selected_user = ""
        self.user_role = ""

        self._setup_window_properties()
        self._setup_ui()
        self._load_users_from_db()
        self._update_role_preview()

    def _setup_window_properties(self):
        self.setWindowTitle("Xác Thực Người Dùng | MBC Vision Inspector")
        self.setFixedSize(450, 480)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #F8FAFC;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Roboto', sans-serif;
            }
        """)

    def _setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ─────────────────────────────────────────────
        # 1. HEADER BANNER (Gradient Dark Slate)
        # ─────────────────────────────────────────────
        header_widget = QtWidgets.QWidget()
        header_widget.setFixedHeight(85)
        header_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #0F172A, stop:0.5 #1E293B, stop:1 #0F172A);
                border-bottom: 2px solid #334155;
            }
        """)
        h_layout = QtWidgets.QHBoxLayout(header_widget)
        h_layout.setContentsMargins(20, 10, 20, 10)
        h_layout.setSpacing(14)

        # Shield Icon Box
        lbl_icon = QtWidgets.QLabel("🛡️")
        lbl_icon.setFixedSize(48, 48)
        lbl_icon.setAlignment(QtCore.Qt.AlignCenter)
        lbl_icon.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 24px;
                font-size: 24px;
            }
        """)
        h_layout.addWidget(lbl_icon)

        # Header Titles
        title_vbox = QtWidgets.QVBoxLayout()
        title_vbox.setSpacing(3)
        title_vbox.setAlignment(QtCore.Qt.AlignVCenter)

        lbl_title = QtWidgets.QLabel("XÁC THỰC NGƯỜI DÙNG")
        lbl_title.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-size: 15px;
                font-weight: bold;
                letter-spacing: 0.5px;
                background: transparent;
            }
        """)
        lbl_subtitle = QtWidgets.QLabel(f"{self.system_context} • Phân quyền thao tác")
        lbl_subtitle.setStyleSheet("""
            QLabel {
                color: #94A3B8;
                font-size: 11px;
                background: transparent;
            }
        """)
        title_vbox.addWidget(lbl_title)
        title_vbox.addWidget(lbl_subtitle)
        h_layout.addLayout(title_vbox)
        h_layout.addStretch()

        main_layout.addWidget(header_widget)

        # ─────────────────────────────────────────────
        # 2. BODY CONTAINER
        # ─────────────────────────────────────────────
        body_widget = QtWidgets.QWidget()
        body_layout = QtWidgets.QVBoxLayout(body_widget)
        body_layout.setContentsMargins(24, 18, 24, 18)
        body_layout.setSpacing(12)

        # A. Chọn Tài khoản
        lbl_user = QtWidgets.QLabel("👤 TÀI KHOẢN NGƯỜI DÙNG:")
        lbl_user.setStyleSheet("font-size: 11px; font-weight: bold; color: #475569;")
        body_layout.addWidget(lbl_user)

        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setFixedHeight(38)
        self.user_combo.setStyleSheet("""
            QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
                color: #1E293B;
                font-weight: 500;
            }
            QComboBox:hover {
                border-color: #94A3B8;
            }
            QComboBox:focus {
                border: 2px solid #2563EB;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border-left: 1px solid #E2E8F0;
                background-color: #F8FAFC;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                selection-background-color: #EFF6FF;
                selection-color: #1D4ED8;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                min-height: 28px;
                padding: 4px 8px;
            }
        """)
        self.user_combo.currentIndexChanged.connect(self._update_role_preview)
        body_layout.addWidget(self.user_combo)

        # B. Thẻ hiển thị vai trò (Dynamic Role Preview Card)
        self.card_role = QtWidgets.QFrame()
        self.card_role.setFixedHeight(68)
        card_role_layout = QtWidgets.QHBoxLayout(self.card_role)
        card_role_layout.setContentsMargins(12, 8, 12, 8)
        card_role_layout.setSpacing(10)

        self.lbl_role_icon = QtWidgets.QLabel("⚡")
        self.lbl_role_icon.setFixedSize(32, 32)
        self.lbl_role_icon.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_role_icon.setStyleSheet("font-size: 18px; background: transparent;")
        card_role_layout.addWidget(self.lbl_role_icon)

        role_info_vbox = QtWidgets.QVBoxLayout()
        role_info_vbox.setSpacing(2)
        role_info_vbox.setAlignment(QtCore.Qt.AlignVCenter)

        self.lbl_role_title = QtWidgets.QLabel("VAI TRÒ NGƯỜI DÙNG")
        self.lbl_role_title.setStyleSheet("font-size: 11px; font-weight: bold; background: transparent;")
        self.lbl_role_desc = QtWidgets.QLabel("Mô tả quyền hạn thao tác...")
        self.lbl_role_desc.setWordWrap(True)
        self.lbl_role_desc.setStyleSheet("font-size: 10px; color: #475569; background: transparent;")

        role_info_vbox.addWidget(self.lbl_role_title)
        role_info_vbox.addWidget(self.lbl_role_desc)
        card_role_layout.addLayout(role_info_vbox)

        body_layout.addWidget(self.card_role)

        # C. Nhập Mật khẩu
        lbl_pass = QtWidgets.QLabel("🔑 MẬT KHẨU BẢO VỆ:")
        lbl_pass.setStyleSheet("font-size: 11px; font-weight: bold; color: #475569; margin-top: 4px;")
        body_layout.addWidget(lbl_pass)

        pass_container = QtWidgets.QWidget()
        pass_layout = QtWidgets.QHBoxLayout(pass_container)
        pass_layout.setContentsMargins(0, 0, 0, 0)
        pass_layout.setSpacing(6)

        self.password_input = QtWidgets.QLineEdit()
        self.password_input.setFixedHeight(38)
        self.password_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.password_input.setPlaceholderText("Nhập mật khẩu xác thực tài khoản...")
        self.password_input.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
                color: #1E293B;
            }
            QLineEdit:hover {
                border-color: #94A3B8;
            }
            QLineEdit:focus {
                border: 2px solid #2563EB;
            }
        """)
        self.password_input.returnPressed.connect(self._handle_auth)
        pass_layout.addWidget(self.password_input)

        # Nút ẩn/hiện mật khẩu
        self.btn_toggle_eye = QtWidgets.QPushButton("👁️")
        self.btn_toggle_eye.setFixedSize(38, 38)
        self.btn_toggle_eye.setCheckable(True)
        self.btn_toggle_eye.setToolTip("Hiện / Ẩn mật khẩu")
        self.btn_toggle_eye.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #F1F5F9;
                border-color: #94A3B8;
            }
            QPushButton:checked {
                background-color: #EFF6FF;
                border-color: #2563EB;
            }
        """)
        self.btn_toggle_eye.toggled.connect(self._toggle_password_visibility)
        pass_layout.addWidget(self.btn_toggle_eye)

        body_layout.addWidget(pass_container)

        # Thông báo lỗi nội bộ
        self.lbl_error = QtWidgets.QLabel("")
        self.lbl_error.setFixedHeight(20)
        self.lbl_error.setStyleSheet("color: #DC2626; font-size: 11px; font-weight: 500;")
        self.lbl_error.setVisible(False)
        body_layout.addWidget(self.lbl_error)

        main_layout.addWidget(body_widget)
        main_layout.addStretch()

        # ─────────────────────────────────────────────
        # 3. FOOTER BUTTONS
        # ─────────────────────────────────────────────
        footer_widget = QtWidgets.QWidget()
        footer_widget.setFixedHeight(64)
        footer_widget.setStyleSheet("""
            QWidget {
                background-color: #F1F5F9;
                border-top: 1px solid #E2E8F0;
            }
        """)
        footer_layout = QtWidgets.QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(24, 12, 24, 12)
        footer_layout.setSpacing(12)

        self.btn_cancel = QtWidgets.QPushButton("Hủy Bỏ")
        self.btn_cancel.setFixedHeight(38)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 0 18px;
                color: #475569;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
                color: #1E293B;
            }
            QPushButton:pressed {
                background-color: #CBD5E1;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        footer_layout.addWidget(self.btn_cancel)

        self.btn_unlock = QtWidgets.QPushButton("🔓 Xác Thực & Mở Khóa")
        self.btn_unlock.setFixedHeight(38)
        self.btn_unlock.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #1D4ED8);
                border: none;
                border-radius: 6px;
                padding: 0 22px;
                color: #FFFFFF;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #2563EB);
            }
            QPushButton:pressed {
                background-color: #1E40AF;
            }
        """)
        self.btn_unlock.clicked.connect(self._handle_auth)
        footer_layout.addWidget(self.btn_unlock)

        main_layout.addWidget(footer_widget)

    def _toggle_password_visibility(self, checked: bool):
        if checked:
            self.password_input.setEchoMode(QtWidgets.QLineEdit.Normal)
            self.btn_toggle_eye.setText("🙈")
        else:
            self.password_input.setEchoMode(QtWidgets.QLineEdit.Password)
            self.btn_toggle_eye.setText("👁️")

    def _load_users_from_db(self):
        self.user_combo.clear()
        
        # 1. Administrator mặc định
        self.user_combo.addItem("👑 Administrator (Master System)", userData=("__ADMIN__", "full_control"))

        # 2. Các user từ CSDL
        if self.cursor:
            try:
                from Administrator.user_db import get_all_users
                users = get_all_users(self.cursor)
                if users:
                    for u in users:
                        user_id, username, role, is_active, *_ = u
                        if is_active:
                            role_str = str(role or "read_only").strip().lower()
                            display_text = f"👤 {username}   [{role_str.upper()}]"
                            self.user_combo.addItem(display_text, userData=(username, role_str))
            except Exception as e:
                print(f"[EnterpriseAuthDialog] Không thể tải danh sách người dùng từ DB: {e}")

    def _update_role_preview(self):
        user_data = self.user_combo.currentData()
        if not user_data:
            return

        username, role = user_data
        role_key = "__ADMIN__" if username == "__ADMIN__" else role
        details = self.ROLE_DETAILS.get(role_key, self.ROLE_DETAILS.get("read_only"))

        self.card_role.setStyleSheet(f"""
            QFrame {{
                background-color: {details['bg']};
                border: 1px solid {details['border']};
                border-radius: 8px;
            }}
        """)
        self.lbl_role_icon.setText(details["icon"])
        self.lbl_role_title.setText(details["title"])
        self.lbl_role_title.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {details['color']}; background: transparent;")
        self.lbl_role_desc.setText(details["desc"])

        # Reset thông báo lỗi khi đổi user
        self.lbl_error.setVisible(False)
        self.password_input.clear()
        self.password_input.setFocus()

    def _handle_auth(self):
        user_data = self.user_combo.currentData()
        if not user_data:
            return

        selected_user, role = user_data
        input_pass = self.password_input.text()

        if not input_pass:
            self.lbl_error.setText("⚠️ Vui lòng nhập mật khẩu xác thực!")
            self.lbl_error.setVisible(True)
            self.password_input.setFocus()
            return

        # 1. Master Administrator
        if selected_user == "__ADMIN__":
            from Administrator.user_db import verify_admin_password
            if verify_admin_password(input_pass):
                self.auth_success = True
                self.selected_user = "__ADMIN__"
                self.user_role = "full_control"
                self.accept()
            else:
                self.lbl_error.setText("❌ Mật khẩu Administrator không chính xác!")
                self.lbl_error.setVisible(True)
                QtWidgets.QMessageBox.warning(self, "Sai mật khẩu", "Mật khẩu Admin Master không chính xác!")
                self.password_input.selectAll()
                self.password_input.setFocus()
            return

        # 2. Người dùng CSDL
        if not self.cursor:
            self.lbl_error.setText("❌ Không có kết nối Cơ sở dữ liệu!")
            self.lbl_error.setVisible(True)
            return

        try:
            self.cursor.execute(
                "SELECT password_hash, role FROM ADMINISTRATOR.ADMIN_USERS WHERE username = %s AND is_active = 1",
                (selected_user,)
            )
            result = self.cursor.fetchone()
            if result:
                saved_hash, db_role = result
                from Administrator.user_db import verify_password
                if verify_password(input_pass, saved_hash):
                    self.auth_success = True
                    self.selected_user = selected_user
                    self.user_role = str(db_role).strip().lower()
                    self.accept()
                else:
                    self.lbl_error.setText("❌ Mật khẩu không chính xác!")
                    self.lbl_error.setVisible(True)
                    QtWidgets.QMessageBox.warning(self, "Sai mật khẩu", "Mật khẩu người dùng không chính xác!")
                    self.password_input.selectAll()
                    self.password_input.setFocus()
            else:
                self.lbl_error.setText("❌ Tài khoản không tồn tại hoặc đã bị khóa!")
                self.lbl_error.setVisible(True)
                QtWidgets.QMessageBox.warning(self, "Lỗi tài khoản", "Tài khoản không tồn tại hoặc đã bị vô hiệu hóa!")
        except Exception as e:
            self.lbl_error.setText(f"❌ Lỗi CSDL: {str(e)[:40]}")
            self.lbl_error.setVisible(True)
            QtWidgets.QMessageBox.critical(self, "Lỗi Cơ Sở Dữ Liệu", str(e))

    def get_auth_result(self) -> Tuple[bool, str, str]:
        """
        Trả về kết quả xác thực:
        (is_authenticated, selected_user, role)
        role: '__ADMIN__', 'full_control', 'modify', 'read_only'
        """
        return self.auth_success, self.selected_user, self.user_role
