"""
Module: change_reason_dialog.py
Mục đích: Hộp thoại bắt buộc người dùng nhập lý do khi lưu thay đổi cấu hình.
Nếu không nhập lý do (hoặc nhập dưới 3 ký tự), hệ thống sẽ không cho phép lưu.
Hỗ trợ đánh dấu Bản Chuẩn (Golden Config) đối với tài khoản Full Control.
"""

from typing import Tuple, Optional
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt


class ChangeReasonDialog(QtWidgets.QDialog):
    """
    Hộp thoại yêu cầu Kỹ sư nhập lý do thay đổi thông số trước khi ghi đè CSDL.
    """
    def __init__(
        self,
        username: str = "Unknown",
        user_role: str = "modify",
        scope_title: str = "Cấu Hình Hệ Thống",
        current_user: Optional[str] = None,
        current_role: Optional[str] = None,
        context_info: Optional[str] = None,
        parent=None
    ):
        super().__init__(parent)
        self.username = str(current_user or username or 'Unknown').strip()
        self.user_role = str(current_role or user_role or 'modify').strip()
        self.scope_title = str(context_info or scope_title or 'Cấu Hình Hệ Thống').strip()
        self.is_confirmed = False
        self.change_reason = ""
        self.is_golden = False

        self.setWindowTitle("Xác Nhận Lưu & Ghi Nhận Thay Đổi Cấu Hình")
        self.setFixedSize(540, 360)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()

    def _init_ui(self):
        # Phong cách Slate Industrial hiện đại, tone sáng trầm
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QFrame#headerFrame {
                background-color: #ffffff;
                border-bottom: 1px solid #cbd5e1;
                padding: 12px;
            }
            QLabel#lblTitle {
                color: #0f172a;
                font-size: 15px;
                font-weight: bold;
            }
            QLabel#lblSub {
                color: #64748b;
                font-size: 12px;
            }
            QFrame#badgeFrame {
                background-color: #f1f5f9;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QTextEdit {
                background-color: #ffffff;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
                color: #0f172a;
            }
            QTextEdit:focus {
                border-color: #2563eb;
                background-color: #ffffff;
            }
            QCheckBox {
                font-size: 13px;
                font-weight: 600;
                color: #1e293b;
            }
            QPushButton#btnSave {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #1d4ed8;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton#btnSave:hover {
                background-color: #1d4ed8;
            }
            QPushButton#btnSave:disabled {
                background-color: #94a3b8;
                border-color: #cbd5e1;
                color: #f1f5f9;
            }
            QPushButton#btnCancel {
                background-color: #ffffff;
                color: #475569;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 18px;
            }
            QPushButton#btnCancel:hover {
                background-color: #f1f5f9;
                color: #1e293b;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 14)
        layout.setSpacing(12)

        # Header
        header = QtWidgets.QFrame()
        header.setObjectName("headerFrame")
        h_layout = QtWidgets.QHBoxLayout(header)
        h_layout.setContentsMargins(16, 10, 16, 10)

        icon_lbl = QtWidgets.QLabel("📝")
        icon_lbl.setStyleSheet("font-size: 28px;")
        h_layout.addWidget(icon_lbl)

        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QtWidgets.QLabel("Ghi Nhận Lý Do Thay Đổi Cấu Hình")
        lbl_title.setObjectName("lblTitle")
        title_box.addWidget(lbl_title)
        lbl_sub = QtWidgets.QLabel("Mọi thay đổi thông số đều được lưu trữ vào lịch sử để phục vụ truy vết.")
        lbl_sub.setObjectName("lblSub")
        title_box.addWidget(lbl_sub)
        h_layout.addLayout(title_box)
        h_layout.addStretch()
        layout.addWidget(header)

        # Body container
        body = QtWidgets.QWidget()
        b_layout = QtWidgets.QVBoxLayout(body)
        b_layout.setContentsMargins(18, 0, 18, 0)
        b_layout.setSpacing(10)

        # User & Scope Badge
        badge = QtWidgets.QFrame()
        badge.setObjectName("badgeFrame")
        badge_layout = QtWidgets.QHBoxLayout(badge)
        badge_layout.setContentsMargins(10, 6, 10, 6)

        user_color = "#16a34a" if self.user_role in ('full_control', '__ADMIN__') else "#2563eb"
        user_info = QtWidgets.QLabel(f"👤 Kỹ sư: <b>{self.username}</b> <span style='color:{user_color};'>[{self.user_role}]</span>")
        user_info.setTextFormat(Qt.RichText)
        badge_layout.addWidget(user_info)

        badge_layout.addSpacing(20)
        scope_info = QtWidgets.QLabel(f"🎯 Phạm vi: <b>{self.scope_title}</b>")
        scope_info.setTextFormat(Qt.RichText)
        badge_layout.addWidget(scope_info)
        badge_layout.addStretch()
        b_layout.addWidget(badge)

        # Reason Input Area
        lbl_prompt = QtWidgets.QLabel("Lý do thay đổi thông số <span style='color:#dc2626;'>* (Bắt buộc)</span>:")
        lbl_prompt.setTextFormat(Qt.RichText)
        lbl_prompt.setStyleSheet("font-weight: bold; font-size: 13px; color: #1e293b;")
        b_layout.addWidget(lbl_prompt)

        self.txt_reason = QtWidgets.QTextEdit()
        self.txt_reason.setPlaceholderText("")
        self.txt_reason.textChanged.connect(self._on_text_changed)
        b_layout.addWidget(self.txt_reason)

        # Validation message
        self.lbl_warning = QtWidgets.QLabel("⚠️ Vui lòng nhập ít nhất 3 ký tự lý do để hệ thống ghi nhận.")
        self.lbl_warning.setStyleSheet("color: #dc2626; font-size: 12px; font-weight: 500;")
        b_layout.addWidget(self.lbl_warning)

        # Golden Config Checkbox
        can_set_golden = self.user_role in ('full_control', '__ADMIN__')
        self.chk_golden = QtWidgets.QCheckBox("⭐ Bản Chuẩn Kiểm Thử")
        self.chk_golden.setEnabled(can_set_golden)
        if not can_set_golden:
            self.chk_golden.setToolTip("Chỉ tài khoản Full Control / Administrator mới được phép đánh dấu Bản Chuẩn.")
        b_layout.addWidget(self.chk_golden)

        layout.addWidget(body)

        # Footer Actions
        footer = QtWidgets.QHBoxLayout()
        footer.setContentsMargins(18, 0, 18, 0)
        footer.setSpacing(10)

        self.btn_cancel = QtWidgets.QPushButton("Hủy Bỏ")
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.btn_cancel.clicked.connect(self.reject)
        footer.addWidget(self.btn_cancel)

        footer.addStretch()

        self.btn_save = QtWidgets.QPushButton("💾 Xác Nhận & Lưu")
        self.btn_save.setObjectName("btnSave")
        self.btn_save.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.btn_save.setEnabled(False)  # Mặc định khóa khi chưa nhập
        self.btn_save.clicked.connect(self._on_save_clicked)
        footer.addWidget(self.btn_save)

        layout.addLayout(footer)

    def _on_text_changed(self):
        text = self.txt_reason.toPlainText().strip()
        valid = len(text) >= 3
        self.btn_save.setEnabled(valid)
        self.lbl_warning.setVisible(not valid)

    def _on_save_clicked(self):
        text = self.txt_reason.toPlainText().strip()
        if len(text) < 3:
            QtWidgets.QMessageBox.warning(self, "Thiếu Lý Do", "Vui lòng nhập lý do thay đổi cụ thể (tối thiểu 3 ký tự) để tiếp tục lưu!")
            self.txt_reason.setFocus()
            return

        self.change_reason = text
        self.is_golden = self.chk_golden.isChecked()
        self.is_confirmed = True
        self.accept()

    def get_result(self) -> Tuple[bool, str, bool]:
        """Trả về: (đã xác nhận, lý do, là bản chuẩn hay không)"""
        return self.is_confirmed, self.change_reason, self.is_golden

    def get_reason_and_golden(self) -> Tuple[str, bool]:
        """Trả về: (lý do, là bản chuẩn hay không)"""
        reason = self.change_reason or (self.txt_reason.toPlainText().strip() if hasattr(self, 'txt_reason') else "")
        golden = self.is_golden or (self.chk_golden.isChecked() if hasattr(self, 'chk_golden') and self.chk_golden.isEnabled() else False)
        return reason, golden


class RollbackPasswordDialog(QtWidgets.QDialog):
    """
    Hộp thoại yêu cầu Kỹ sư xác thực mật khẩu Full Control trước khi thực hiện Rollback.
    """
    def __init__(self, username: str = "", snapshot_desc: str = "", cursor = None, parent=None):
        super().__init__(parent)
        self.username = str(username or '').strip()
        self.snapshot_desc = snapshot_desc
        self.cursor = cursor
        self.is_authorized = False

        self.setWindowTitle("Xác Thực Mật Khẩu Khôi Phục")
        self.setFixedSize(500, 310)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QFrame#headerFrame {
                background-color: #ffffff;
                border-bottom: 1px solid #cbd5e1;
                padding: 10px;
            }
            QLabel#lblTitle {
                color: #b91c1c;
                font-size: 15px;
                font-weight: bold;
            }
            QLabel#lblSub {
                color: #64748b;
                font-size: 12px;
            }
            QFrame#warnBox {
                background-color: #fef2f2;
                border: 1px solid #fecaca;
                border-radius: 6px;
                padding: 8px;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 14px;
                color: #0f172a;
            }
            QLineEdit:focus {
                border-color: #dc2626;
            }
            QPushButton#btnConfirm {
                background-color: #dc2626;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #b91c1c;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton#btnConfirm:hover {
                background-color: #b91c1c;
            }
            QPushButton#btnCancel {
                background-color: #ffffff;
                color: #475569;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 18px;
            }
            QPushButton#btnCancel:hover {
                background-color: #f1f5f9;
                color: #1e293b;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 14)
        layout.setSpacing(12)

        # Header
        header = QtWidgets.QFrame()
        header.setObjectName("headerFrame")
        h_layout = QtWidgets.QHBoxLayout(header)
        h_layout.setContentsMargins(16, 8, 16, 8)

        icon_lbl = QtWidgets.QLabel("🔒")
        icon_lbl.setStyleSheet("font-size: 26px;")
        h_layout.addWidget(icon_lbl)

        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QtWidgets.QLabel("Xác Thực Quyền Hạn Khôi Phục")
        lbl_title.setObjectName("lblTitle")
        title_box.addWidget(lbl_title)
        lbl_sub = QtWidgets.QLabel("Yêu cầu nhập mật khẩu tài khoản Full Control để tiếp tục.")
        lbl_sub.setObjectName("lblSub")
        title_box.addWidget(lbl_sub)
        h_layout.addLayout(title_box)
        h_layout.addStretch()
        layout.addWidget(header)

        # Body
        body = QtWidgets.QWidget()
        b_layout = QtWidgets.QVBoxLayout(body)
        b_layout.setContentsMargins(18, 0, 18, 0)
        b_layout.setSpacing(10)

        # Warning target description box
        warn_box = QtWidgets.QFrame()
        warn_box.setObjectName("warnBox")
        w_layout = QtWidgets.QVBoxLayout(warn_box)
        w_layout.setContentsMargins(8, 8, 8, 8)
        w_layout.setSpacing(4)

        lbl_target = QtWidgets.QLabel(f"<b>Mục tiêu khôi phục:</b> {self.snapshot_desc}")
        lbl_target.setTextFormat(Qt.RichText)
        lbl_target.setStyleSheet("color: #991b1b; font-size: 12px;")
        lbl_target.setWordWrap(True)
        w_layout.addWidget(lbl_target)

        lbl_notice = QtWidgets.QLabel("⚠️ <i>Hành động này sẽ ghi đè toàn bộ CSDL về phiên bản đã chọn!</i>")
        lbl_notice.setTextFormat(Qt.RichText)
        lbl_notice.setStyleSheet("color: #b91c1c; font-size: 11px;")
        w_layout.addWidget(lbl_notice)
        b_layout.addWidget(warn_box)

        # User prompt & Password Input
        lbl_pass = QtWidgets.QLabel(f"Mật khẩu của tài khoản <b>{self.username}</b>:")
        lbl_pass.setTextFormat(Qt.RichText)
        lbl_pass.setStyleSheet("font-size: 13px; color: #1e293b;")
        b_layout.addWidget(lbl_pass)

        self.txt_pass = QtWidgets.QLineEdit()
        self.txt_pass.setEchoMode(QtWidgets.QLineEdit.Password)
        self.txt_pass.setPlaceholderText("Nhập mật khẩu xác nhận...")
        self.txt_pass.returnPressed.connect(self._on_confirm_clicked)
        b_layout.addWidget(self.txt_pass)

        self.lbl_err = QtWidgets.QLabel("")
        self.lbl_err.setStyleSheet("color: #dc2626; font-size: 12px; font-weight: bold;")
        self.lbl_err.setVisible(False)
        b_layout.addWidget(self.lbl_err)

        layout.addWidget(body)

        # Footer Actions
        footer = QtWidgets.QHBoxLayout()
        footer.setContentsMargins(18, 0, 18, 0)
        footer.setSpacing(10)

        self.btn_cancel = QtWidgets.QPushButton("Hủy Bỏ")
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.btn_cancel.clicked.connect(self.reject)
        footer.addWidget(self.btn_cancel)

        footer.addStretch()

        self.btn_confirm = QtWidgets.QPushButton("↺ Xác Nhận Khôi Phục")
        self.btn_confirm.setObjectName("btnConfirm")
        self.btn_confirm.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.btn_confirm.setEnabled(False)
        self.btn_confirm.clicked.connect(self._on_confirm_clicked)
        self.txt_pass.textChanged.connect(lambda txt: self.btn_confirm.setEnabled(bool(txt.strip())))
        footer.addWidget(self.btn_confirm)

        layout.addLayout(footer)

    def _on_confirm_clicked(self):
        raw_pass = self.txt_pass.text()
        if not raw_pass:
            self.lbl_err.setText("Vui lòng nhập mật khẩu!")
            self.lbl_err.setVisible(True)
            self.txt_pass.setFocus()
            return

        from module_3.config_version_manager import verify_user_can_rollback
        ok, msg = verify_user_can_rollback(self.cursor, self.username, raw_pass)
        if ok:
            self.is_authorized = True
            self.accept()
        else:
            self.lbl_err.setText(f"❌ {msg}")
            self.lbl_err.setVisible(True)
            QtWidgets.QMessageBox.warning(self, "Xác Thực Thất Bại", msg)
            self.txt_pass.selectAll()
            self.txt_pass.setFocus()

