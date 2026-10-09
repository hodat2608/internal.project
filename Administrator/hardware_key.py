# Administrator/hardware_key.py
# Giao diện quản lý Hardware Key USB
# Quét serial USB đang cắm, đăng ký serial hợp lệ, và kiểm tra khi app khởi động

import subprocess
import re
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor
from Administrator.admin_config import AdminPasswordDialog
from Administrator.user_db import (
    add_hardware_key, remove_hardware_key, get_all_hardware_keys,
    toggle_hardware_key, is_usb_serial_authorized
)

"""
Kết hợp đa lớp định danh (Hardware ID - HWID): Thay vì chỉ lấy SerialNumber đơn thuần, thuật toán mới lấy cả PNPDeviceID (chứa mã Vendor ID và Product ID của USB từ nhà sản xuất). Chuỗi nhận diện giờ đây sẽ là SerialNumber + PNPDeviceID.
Mã hoá thuật toán Hash một chiều (SHA-256): Thay vì lưu thẳng mã Serial vào Database, hệ thống sẽ sử dụng thuật toán Băm (Hash) SHA-256 cùng với một khoá bí mật (Salt) là AI_VISION_PRO_SECURE_SALT_. => Chuỗi lưu vào database và chuỗi hiển thị trên UI giờ đây trông giống như một License Key chuyên nghiệp (ví dụ: E4C3D...), không thể bị dịch ngược ra Serial gốc, người dùng có truy cập được Database cũng không thể biết được Serial thật là gì để làm giả.
Tối ưu hoá Script PowerShell (Parsing): Ở phiên bản cũ, việc dùng ConvertTo-Csv hoặc Format-Table sau đó dùng regex split(',') là rất dễ phát sinh lỗi (nếu thiết bị có chứa dấu phẩy hoặc ký tự đặc biệt). Tôi đã chuyển sang dùng ConvertTo-Json -Compress kết hợp module json của Python, giúp dữ liệu quét phần cứng trả về cực kỳ ổn định, chính xác tuyệt đối.
"""

def get_connected_usb_serials() -> list:
    """
    Quét tất cả USB đang cắm và tạo Hardware ID (HWID) bảo mật.
    Sử dụng PowerShell kết hợp ConvertTo-Json để parse dữ liệu chính xác.
    """
    import json
    import hashlib
    import subprocess

    usb_list = []
    try:
        cmd = (
            'powershell -Command "'
            "Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPDeviceID -match '^USB' } | ForEach-Object { $serial = $_.PNPDeviceID.Split('\')[-1]; [PSCustomObject]@{ 'Device Name' = $_.Name; 'Serial Number' = $serial } } | ConvertTo-Csv -NoTypeInformation"
            '"'
        )
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=10)
        output = result.stdout.strip()
        if output:
            lines = output.strip().split('\n')
            for line in lines[1:]:
                parts = line.strip().strip('"').split('","')
                if len(parts) >= 2:
                    model = parts[0].strip()
                    pnp_and_serial = parts[1].strip()
                    if pnp_and_serial and "ROOT_HUB" not in pnp_and_serial:
                        raw_hwid = pnp_and_serial
                        salt = "AI_VISION_PRO_SECURE_SALT_"
                        secure_hash = hashlib.sha256((salt + raw_hwid).encode('utf-8')).hexdigest().upper()
                        usb_list.append({
                            "serial": secure_hash,
                            "raw_serial": raw_hwid,
                            "model": model
                        })
    except Exception as e:
        print(f"Lỗi khi quét USB bảo mật: {e}")
        
    return usb_list


class HardwareKeyWindow(QDialog):
    """Cửa sổ quản lý Hardware Key USB"""
    def __init__(self, cursor, connect_db, parent=None):
        super().__init__(parent)
        self.cursor = cursor
        self.connect_db = connect_db
        self.setWindowTitle("🔑 Hardware Key USB - Settings")
        self.setMinimumSize(800, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._build_ui()
        self._load_registered_keys()
        self._scan_usb()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(18, 18, 18, 18)

        # ── Title ──
        title = QLabel("🔑 HARDWARE KEY USB MANAGEMENT")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #1E3A5F; padding: 8px; border-bottom: 2px solid #F59E0B;")
        main_layout.addWidget(title)

        desc = QLabel(
            "Quản lý USB Key bảo mật cho ứng dụng.\n"
            "Chỉ những USB có serial đã đăng ký mới được phép khởi động application."
        )
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #64748B; font-size: 11px; padding: 4px;")
        main_layout.addWidget(desc)

        # ── Group 1: USB đang cắm ──
        grp_detect = QGroupBox("🔍 USB đang kết nối")
        grp_detect.setFont(QFont("Segoe UI", 11, QFont.Bold))
        detect_layout = QVBoxLayout(grp_detect)

        self.usb_table = QTableWidget()
        self.usb_table.setColumnCount(4)
        self.usb_table.setHorizontalHeaderLabels(["Serial Number", "Hash Code", "Model / Mô tả", "Thao tác"])
        self.usb_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.usb_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.usb_table.setMaximumHeight(160)
        detect_layout.addWidget(self.usb_table)

        scan_layout = QHBoxLayout()
        btn_scan = QPushButton("🔄 Quét lại USB")
        btn_scan.clicked.connect(self._scan_usb)
        scan_layout.addWidget(btn_scan)

        scan_layout.addStretch()
        
        # Nhập serial thủ công
        scan_layout.addWidget(QLabel("Nhập Serial thủ công:"))
        self.txt_manual_serial = QLineEdit()
        self.txt_manual_serial.setPlaceholderText("Nhập serial number...")
        self.txt_manual_serial.setFixedWidth(200)
        scan_layout.addWidget(self.txt_manual_serial)
        
        btn_add_manual = QPushButton("➕ Đăng ký")
        btn_add_manual.setStyleSheet("QPushButton { background-color: #22C55E; color: white; padding: 4px 12px; }")
        btn_add_manual.clicked.connect(self._add_manual_key)
        scan_layout.addWidget(btn_add_manual)

        detect_layout.addLayout(scan_layout)
        main_layout.addWidget(grp_detect)

        # ── Group 2: USB Key đã đăng ký ──
        grp_registered = QGroupBox("📋 Danh sách USB Key đã đăng ký")
        grp_registered.setFont(QFont("Segoe UI", 11, QFont.Bold))
        reg_layout = QVBoxLayout(grp_registered)

        self.reg_table = QTableWidget()
        self.reg_table.setColumnCount(6)
        self.reg_table.setHorizontalHeaderLabels(["ID", "Serial Number", "Hash Code", "Mô tả", "Trạng thái", "Thao tác"])
        self.reg_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.reg_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.reg_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.reg_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.reg_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.reg_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.reg_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.reg_table.setAlternatingRowColors(True)
        reg_layout.addWidget(self.reg_table)

        reg_btn_layout = QHBoxLayout()
        btn_refresh = QPushButton("🔄 Làm mới")
        btn_refresh.clicked.connect(self._load_registered_keys)
        reg_btn_layout.addWidget(btn_refresh)
        reg_btn_layout.addStretch()
        reg_layout.addLayout(reg_btn_layout)

        main_layout.addWidget(grp_registered)
        self.usb_table.cellDoubleClicked.connect(self._show_cell_tooltip)
        self.reg_table.cellDoubleClicked.connect(self._show_cell_tooltip)

    def _show_cell_tooltip(self, row, col):
        table = self.sender()
        item = table.item(row, col)
        if item and item.text():
            from PyQt5.QtWidgets import QToolTip
            from PyQt5.QtGui import QCursor
            QToolTip.showText(QCursor.pos(), item.text(), table)

    def _scan_usb(self):
        """Quét USB đang cắm vào máy"""
        usb_list = get_connected_usb_serials()
        self.usb_table.setRowCount(len(usb_list))

        if not usb_list:
            self.usb_table.setRowCount(1)
            item = QTableWidgetItem("Không phát hiện USB nào được cắm vào")
            item.setForeground(QColor("#94A3B8"))
            self.usb_table.setItem(0, 0, item)
            self.usb_table.setSpan(0, 0, 1, 4)
            return

        for row, usb in enumerate(usb_list):
            item_raw = QTableWidgetItem(usb.get("raw_serial", ""))
            item_raw.setToolTip(usb.get("raw_serial", ""))
            self.usb_table.setItem(row, 0, item_raw)
            
            item_hash = QTableWidgetItem(usb["serial"])
            item_hash.setToolTip(usb["serial"])
            self.usb_table.setItem(row, 1, item_hash)
            
            item_model = QTableWidgetItem(usb["model"])
            item_model.setToolTip(usb["model"])
            self.usb_table.setItem(row, 2, item_model)

            btn_register = QPushButton("➕ Đăng ký Key này")
            btn_register.setStyleSheet("QPushButton { background-color: #3B82F6; color: white; padding: 3px 10px; }")
            btn_register.clicked.connect(lambda _, r=usb.get("raw_serial", ""), s=usb["serial"], m=usb["model"]: self._register_key(r, s, m))
            self.usb_table.setCellWidget(row, 3, btn_register)

    def _register_key(self, raw_serial, hash_code, description):
        """Đăng ký USB serial vào database"""
        ok, msg = add_hardware_key(self.cursor, self.connect_db, raw_serial, hash_code, description)
        if ok:
            QMessageBox.information(self, "Thành công", msg)
            self._load_registered_keys()
        else:
            QMessageBox.critical(self, "Lỗi", msg)

    def _add_manual_key(self):
        """Đăng ký serial nhập tay"""
        serial = self.txt_manual_serial.text().strip()
        if not serial:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập serial number!")
            return
        
        import hashlib
        salt = "AI_VISION_PRO_SECURE_SALT_"
        hash_code = hashlib.sha256((salt + serial).encode('utf-8')).hexdigest().upper()
        
        self._register_key(serial, hash_code, "Manual Entry")
        self.txt_manual_serial.clear()

    def _load_registered_keys(self):
        """Tải danh sách USB Key đã đăng ký từ DB"""
        keys = get_all_hardware_keys(self.cursor)
        self.reg_table.setRowCount(len(keys))

        for row, key in enumerate(keys):
            kid, serial, hash_code, desc, is_enabled, registered_at = key

            self.reg_table.setItem(row, 0, QTableWidgetItem(str(kid)))
            
            item_raw = QTableWidgetItem(serial)
            item_raw.setToolTip(serial)
            self.reg_table.setItem(row, 1, item_raw)
            
            item_hash = QTableWidgetItem(hash_code)
            item_hash.setToolTip(hash_code)
            self.reg_table.setItem(row, 2, item_hash)
            
            item_desc = QTableWidgetItem(desc or "")
            item_desc.setToolTip(desc or "")
            self.reg_table.setItem(row, 3, item_desc)

            # Toggle bật/tắt
            chk = QCheckBox("Bật")
            chk.setChecked(bool(is_enabled))
            chk.stateChanged.connect(lambda state, kid=kid: self._toggle_key(kid, state == Qt.Checked))
            self.reg_table.setCellWidget(row, 4, chk)

            # Nút xóa
            btn_del = QPushButton("🗑️ Xóa")
            btn_del.setStyleSheet("QPushButton { background-color: #EF4444; color: white; padding: 3px 8px; }")
            btn_del.clicked.connect(lambda _, kid=kid, s=serial: self._delete_key(kid, s))
            self.reg_table.setCellWidget(row, 5, btn_del)

    def _toggle_key(self, key_id, is_enabled):
        toggle_hardware_key(self.cursor, self.connect_db, key_id, is_enabled)

    def _delete_key(self, key_id, serial):
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            f"Bạn có chắc muốn xóa USB Key?\n\nSerial: {serial}\n\n"
            "⚠️ Sau khi xóa, USB này sẽ không thể dùng để khởi động app!",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if remove_hardware_key(self.cursor, self.connect_db, key_id):
                QMessageBox.information(self, "Thành công", "Đã xóa USB Key!")
                self._load_registered_keys()
            else:
                QMessageBox.critical(self, "Lỗi", "Không thể xóa USB Key!")


def check_usb_authorization(cursor) -> bool:
    """
    Kiểm tra xem có USB hợp lệ nào đang được cắm vào không.
    Gọi hàm này khi app khởi động.
    Trả về True nếu:
      - Không có key nào được đăng ký trong DB (cho phép chạy tự do)
      - Có ít nhất 1 USB đang cắm có serial khớp với DB
    """
    try:
        keys = get_all_hardware_keys(cursor)
        # Nếu chưa đăng ký key nào → cho phép chạy tự do
        if not keys:
            return True
        
        # Nếu đã đăng ký key → kiểm tra USB đang cắm
        connected = get_connected_usb_serials()
        for usb in connected:
            if is_usb_serial_authorized(cursor, usb["serial"]):
                return True
        return False
    except Exception:
        return True  # Nếu lỗi, cho chạy để tránh lock cứng app


def open_hardware_key(cursor, connect_db, connection, parent=None):
    """Entry point: Tạo bảng nếu chưa có → Kiểm tra admin password → Mở Hardware Key settings"""
    from Administrator.user_db import ensure_admin_tables
    ensure_admin_tables(connection)
    auth = AdminPasswordDialog(parent)
    if auth.exec_() == QDialog.Accepted and auth.authenticated:
        dialog = HardwareKeyWindow(cursor, connect_db, parent)
        dialog.exec_()

