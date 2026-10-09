"""
ipv4_settings_ui.py
--------------------
Giao diện PyQt5 mô phỏng phong cách "Windows Settings" (Fluent Design)
để xem và chỉnh IPv4 tĩnh cho các network adapter, thay thế thao tác thủ
công trong Settings -> Network & internet -> Advanced network settings.

Yêu cầu: pip install PyQt5
Chạy:    python ipv4_settings_ui.py   (sẽ tự xin quyền admin qua UAC)
"""

import sys
import ctypes
import subprocess
import re
import argparse

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon, QColor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFormLayout, QFrame, QScrollArea,
    QGridLayout, QDialog, QRadioButton, QButtonGroup, QMessageBox,
    QSizePolicy, QGraphicsDropShadowEffect
)


# ============================================================
#  Quyền Admin (UAC) — bắt buộc để đổi IP, giống Windows Settings
# ============================================================

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def relaunch_as_admin(extra_args=None):
    """
    Mở lại chính script này với quyền admin (kích hoạt UAC).
    extra_args: list các tham số bổ sung, ví dụ ["--edit", "Ethernet 7"]
    để sau khi elevate xong, app tự mở luôn dialog Edit của adapter đó.
    Trả về True nếu Windows đã khởi động được tiến trình admin
    (không có nghĩa là người dùng đã nhập đúng mật khẩu — chỉ biết
    được điều đó nếu tiến trình mới chạy thành công).
    """
    script = sys.argv[0]
    args = list(sys.argv[1:])
    if extra_args:
        args += extra_args
    params = " ".join(f'"{a}"' for a in args)

    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{script}" {params}', None, 1
    )
    # ShellExecuteW trả về giá trị > 32 nếu thành công khởi chạy tiến trình
    return result > 32


# ============================================================
#  Backend: netsh + WMI-lite qua PowerShell (đọc thông tin adapter)
# ============================================================

def run(cmd: str):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           encoding="utf-8", errors="ignore")


def get_adapters():
    """Lấy danh sách adapter kèm trạng thái, tốc độ, mô tả qua PowerShell."""
    ps = (
        "Get-NetAdapter | Select-Object Name, InterfaceDescription, Status, "
        "LinkSpeed, MacAddress | ConvertTo-Json"
    )
    result = run(f'powershell -NoProfile -Command "{ps}"')
    import json
    try:
        data = json.loads(result.stdout)
        if isinstance(data, dict):
            data = [data]
        return data
    except Exception:
        return []


def get_adapter_stats(name: str):
    ps = f"Get-NetAdapterStatistics -Name '{name}' | ConvertTo-Json"
    result = run(f'powershell -NoProfile -Command "{ps}"')
    import json
    try:
        return json.loads(result.stdout)
    except Exception:
        return {}


def set_static_ip(adapter, ip, mask, gateway):
    return run(f'netsh interface ip set address name="{adapter}" static {ip} {mask} {gateway} 1')


def set_dhcp(adapter):
    return run(f'netsh interface ip set address name="{adapter}" dhcp')


def set_dns(adapter, dns1, dns2=""):
    outs = [run(f'netsh interface ip set dns name="{adapter}" static {dns1} primary')]
    if dns2:
        outs.append(run(f'netsh interface ip add dns name="{adapter}" {dns2} index=2'))
    return outs


def set_dns_auto(adapter):
    return run(f'netsh interface ip set dns name="{adapter}" dhcp')


IP_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")


def valid_ip(s: str) -> bool:
    if not IP_RE.match(s):
        return False
    return all(0 <= int(p) <= 255 for p in s.split("."))


# ============================================================
#  Style — mô phỏng bảng màu / font Fluent Design (Windows 11 Settings)
# ============================================================

QSS = """
QWidget {
    font-family: "Segoe UI", "Segoe UI Variable", sans-serif;
    font-size: 13px;
    color: #1b1b1b;
}
#MainBg {
    background-color: #f3f3f3;
}
#Breadcrumb {
    color: #6b6b6b;
    font-size: 22px;
    font-weight: 400;
}
#BreadcrumbActive {
    color: #1b1b1b;
    font-size: 22px;
    font-weight: 600;
}
#SectionLabel {
    color: #1b1b1b;
    font-size: 12px;
    font-weight: 600;
    padding-left: 4px;
}
QFrame#Card {
    background-color: #fbfbfb;
    border: 1px solid #e5e5e5;
    border-radius: 8px;
}
QFrame#CardHeader {
    background-color: transparent;
}
QLabel#AdapterName {
    font-size: 14px;
    font-weight: 500;
    color: #1b1b1b;
}
QLabel#AdapterDesc {
    font-size: 12px;
    color: #6b6b6b;
}
QLabel#DetailKey {
    color: #6b6b6b;
    font-size: 12px;
}
QLabel#DetailVal {
    color: #1b1b1b;
    font-size: 12px;
}
QPushButton#PillButton {
    background-color: #fbfbfb;
    border: 1px solid #c6c6c6;
    border-radius: 4px;
    padding: 6px 16px;
}
QPushButton#PillButton:hover {
    background-color: #f0f0f0;
    border: 1px solid #b0b0b0;
}
QPushButton#AccentButton {
    background-color: #0067c0;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 7px 20px;
    font-weight: 500;
}
QPushButton#AccentButton:hover {
    background-color: #005ba1;
}
QPushButton#Chevron {
    border: none;
    background: transparent;
    color: #6b6b6b;
    font-size: 14px;
}
QDialog {
    background-color: #f3f3f3;
}
QLineEdit {
    border: 1px solid #c6c6c6;
    border-radius: 4px;
    padding: 5px 8px;
    background: white;
}
QLineEdit:focus {
    border: 1px solid #0067c0;
}
QLineEdit:disabled {
    background: #ececec;
    color: #9a9a9a;
}
QRadioButton {
    font-size: 13px;
    padding: 3px;
}
"""


def card_shadow():
    eff = QGraphicsDropShadowEffect()
    eff.setBlurRadius(10)
    eff.setOffset(0, 1)
    eff.setColor(QColor(0, 0, 0, 25))
    return eff


# ============================================================
#  Dialog: chỉnh IPv4 — mô phỏng "Internet Protocol Version 4 (TCP/IPv4) Properties"
# ============================================================

class IPv4Dialog(QDialog):
    def __init__(self, adapter_name, parent=None):
        super().__init__(parent)
        self.adapter_name = adapter_name
        self.setWindowTitle(f"Chỉnh sửa IPv4 — {adapter_name}")
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = QLabel(f"Internet Protocol Version 4 (TCP/IPv4) — {self.adapter_name}")
        title.setStyleSheet("font-weight:600; font-size:14px;")
        title.setWordWrap(True)
        layout.addWidget(title)

        self.group = QButtonGroup(self)
        self.rb_auto = QRadioButton("Obtain an IP address automatically (DHCP)")
        self.rb_manual = QRadioButton("Use the following IP address:")
        self.rb_manual.setChecked(True)
        self.group.addButton(self.rb_auto)
        self.group.addButton(self.rb_manual)
        layout.addWidget(self.rb_auto)
        layout.addWidget(self.rb_manual)

        form = QFormLayout()
        form.setSpacing(8)
        self.ip_edit = QLineEdit()
        self.mask_edit = QLineEdit("255.255.255.0")
        self.gw_edit = QLineEdit()
        form.addRow("IP address:", self.ip_edit)
        form.addRow("Subnet mask:", self.mask_edit)
        form.addRow("Default gateway:", self.gw_edit)
        layout.addLayout(form)

        self.dns_group = QButtonGroup(self)
        self.rb_dns_auto = QRadioButton("Obtain DNS server address automatically")
        self.rb_dns_manual = QRadioButton("Use the following DNS server addresses:")
        self.rb_dns_manual.setChecked(True)
        self.dns_group.addButton(self.rb_dns_auto)
        self.dns_group.addButton(self.rb_dns_manual)
        layout.addWidget(self.rb_dns_auto)
        layout.addWidget(self.rb_dns_manual)

        dns_form = QFormLayout()
        dns_form.setSpacing(8)
        self.dns1_edit = QLineEdit("8.8.8.8")
        self.dns2_edit = QLineEdit("8.8.4.4")
        dns_form.addRow("Preferred DNS:", self.dns1_edit)
        dns_form.addRow("Alternate DNS:", self.dns2_edit)
        layout.addLayout(dns_form)

        self.rb_auto.toggled.connect(self._toggle_manual_fields)
        self.rb_dns_auto.toggled.connect(self._toggle_dns_fields)
        self._toggle_manual_fields()
        self._toggle_dns_fields()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("AccentButton")
        ok_btn.clicked.connect(self.apply)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("PillButton")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _toggle_manual_fields(self):
        enabled = self.rb_manual.isChecked()
        for w in (self.ip_edit, self.mask_edit, self.gw_edit):
            w.setEnabled(enabled)

    def _toggle_dns_fields(self):
        enabled = self.rb_dns_manual.isChecked()
        for w in (self.dns1_edit, self.dns2_edit):
            w.setEnabled(enabled)

    def apply(self):
        if self.rb_manual.isChecked():
            ip, mask, gw = self.ip_edit.text().strip(), self.mask_edit.text().strip(), self.gw_edit.text().strip()
            if not (valid_ip(ip) and valid_ip(mask) and valid_ip(gw)):
                QMessageBox.warning(self, "Sai định dạng", "IP / Subnet mask / Gateway không hợp lệ.")
                return
            r = set_static_ip(self.adapter_name, ip, mask, gw)
            if r.returncode != 0:
                QMessageBox.critical(self, "Lỗi", r.stderr or r.stdout)
                return
        else:
            set_dhcp(self.adapter_name)

        if self.rb_dns_manual.isChecked():
            dns1, dns2 = self.dns1_edit.text().strip(), self.dns2_edit.text().strip()
            if dns1 and not valid_ip(dns1):
                QMessageBox.warning(self, "Sai định dạng", "DNS ưu tiên không hợp lệ.")
                return
            if dns1:
                set_dns(self.adapter_name, dns1, dns2)
        else:
            set_dns_auto(self.adapter_name)

        QMessageBox.information(self, "Thành công", "Đã áp dụng cấu hình mạng.")
        self.accept()


# ============================================================
#  Card cho từng adapter — mô phỏng khối trong ảnh Windows Settings
# ============================================================

class AdapterCard(QFrame):
    def __init__(self, info: dict):
        super().__init__()
        self.info = info
        self.expanded = False
        self.setObjectName("Card")
        self.setGraphicsEffect(card_shadow())
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(0)

        header = QHBoxLayout()
        icon = QLabel("🖧")
        icon.setFixedWidth(28)
        icon.setStyleSheet("font-size:18px;")
        header.addWidget(icon)

        name_box = QVBoxLayout()
        name_box.setSpacing(2)
        name_lbl = QLabel(self.info.get("Name", "Unknown"))
        name_lbl.setObjectName("AdapterName")
        desc_lbl = QLabel(self.info.get("InterfaceDescription", ""))
        desc_lbl.setObjectName("AdapterDesc")
        name_box.addWidget(name_lbl)
        name_box.addWidget(desc_lbl)
        header.addLayout(name_box)
        header.addStretch()

        status = str(self.info.get("Status", "")).lower()
        self.toggle_btn = QPushButton("Disable" if status == "up" else "Enable")
        self.toggle_btn.setObjectName("PillButton")
        self.toggle_btn.setFixedWidth(90)
        header.addWidget(self.toggle_btn)

        self.chevron_btn = QPushButton("▾")
        self.chevron_btn.setObjectName("Chevron")
        self.chevron_btn.setFixedWidth(24)
        self.chevron_btn.clicked.connect(self.toggle_expand)
        header.addWidget(self.chevron_btn)

        outer.addLayout(header)

        # Vùng chi tiết (ẩn mặc định)
        self.detail_frame = QFrame()
        detail_layout = QVBoxLayout(self.detail_frame)
        detail_layout.setContentsMargins(36, 10, 8, 4)

        stats = get_adapter_stats(self.info.get("Name", ""))
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(4)
        rows = [
            ("Media state:", "Enabled" if status == "up" else "Disabled"),
            ("MAC address:", self.info.get("MacAddress", "-")),
            ("Link speed:", self.info.get("LinkSpeed", "-")),
            ("Bytes sent:", f'{stats.get("SentBytes", "-"):,}' if isinstance(stats.get("SentBytes"), int) else "-"),
            ("Bytes received:", f'{stats.get("ReceivedBytes", "-"):,}' if isinstance(stats.get("ReceivedBytes"), int) else "-"),
        ]
        for r, (k, v) in enumerate(rows):
            kl = QLabel(k); kl.setObjectName("DetailKey")
            vl = QLabel(str(v)); vl.setObjectName("DetailVal")
            grid.addWidget(kl, r, 0)
            grid.addWidget(vl, r, 1)
        detail_layout.addLayout(grid)

        edit_row = QHBoxLayout()
        edit_row.addStretch()
        edit_btn = QPushButton("Edit IPv4 settings")
        edit_btn.setObjectName("AccentButton")
        edit_btn.clicked.connect(self.open_edit_dialog)
        edit_row.addWidget(edit_btn)
        detail_layout.addLayout(edit_row)

        self.detail_frame.setVisible(False)
        outer.addWidget(self.detail_frame)

    def toggle_expand(self):
        self.expanded = not self.expanded
        self.detail_frame.setVisible(self.expanded)
        self.chevron_btn.setText("▴" if self.expanded else "▾")

    def open_edit_dialog(self):
        adapter_name = self.info.get("Name", "")

        if not is_admin():
            # Giống Windows: bấm Edit -> bật UAC xin mật khẩu admin.
            # Sau khi elevate thành công, relaunch app với cờ --edit để
            # tự động mở lại đúng dialog này ở phiên bản đã có quyền admin.
            ok = relaunch_as_admin(extra_args=["--edit", adapter_name])
            if ok:
                # Đóng phiên không có quyền admin hiện tại, để tránh
                # có 2 cửa sổ (1 admin, 1 thường) cùng lúc.
                QApplication.quit()
            else:
                QMessageBox.warning(
                    self, "Bị từ chối",
                    "Bạn cần cấp quyền admin để chỉnh sửa cài đặt mạng."
                )
            return

        dlg = IPv4Dialog(adapter_name, self)
        dlg.exec_()


# ============================================================
#  Cửa sổ chính — breadcrumb + danh sách card, giống ảnh mẫu
# ============================================================

class MainWindow(QMainWindow):
    def __init__(self, auto_open_edit_for: str = None, progress_callback=None):
        super().__init__()
        self.setWindowTitle("Advanced network settings")
        self.resize(760, 620)
        self.auto_open_edit_for = auto_open_edit_for
        self.progress_callback = progress_callback
        self._build_ui()

        if self.auto_open_edit_for:
            # App vừa được elevate xong do người dùng bấm Edit trước đó ->
            # tự động mở lại dialog Edit đúng adapter, không cần bấm lại.
            for card in self.findChildren(AdapterCard):
                if card.info.get("Name") == self.auto_open_edit_for:
                    card.expanded = True
                    card.detail_frame.setVisible(True)
                    card.chevron_btn.setText("▴")
                    # Mở dialog sau khi UI đã dựng xong
                    from PyQt5.QtCore import QTimer
                    QTimer.singleShot(150, card.open_edit_dialog)
                    break

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("MainBg")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(16)

        crumb = QHBoxLayout()
        l1 = QLabel("Network & internet")
        l1.setObjectName("Breadcrumb")
        arrow = QLabel("  >  ")
        arrow.setObjectName("Breadcrumb")
        l2 = QLabel("Advanced network settings")
        l2.setObjectName("BreadcrumbActive")
        crumb.addWidget(l1); crumb.addWidget(arrow); crumb.addWidget(l2)
        crumb.addStretch()
        root.addLayout(crumb)

        section = QLabel("NETWORK ADAPTERS")
        section.setObjectName("SectionLabel")
        root.addWidget(section)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        self.list_layout = QVBoxLayout(container)
        self.list_layout.setSpacing(10)
        self.list_layout.setContentsMargins(0, 0, 0, 0)

        if self.progress_callback:
            self.progress_callback(10, "Đang lấy danh sách card mạng...")

        adapters = get_adapters()
        total = len(adapters)

        for i, info in enumerate(adapters):
            if self.progress_callback:
                self.progress_callback(10 + int(90 * (i / total)) if total > 0 else 100, f"Đang tải thông tin: {info.get('Name', 'Unknown')}...")
            self.list_layout.addWidget(AdapterCard(info))
            
        if self.progress_callback:
            self.progress_callback(100, "Hoàn tất!")
            
        self.list_layout.addStretch()

        scroll.setWidget(container)
        root.addWidget(scroll)


def main():
    if sys.platform != "win32":
        print("Chương trình này chỉ chạy trên Windows.")
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("--edit", default=None,
                         help="Tên adapter cần tự mở dialog Edit ngay sau khi elevate")
    args, _ = parser.parse_known_args()

    # KHÔNG elevate ngay khi mở app. App mở ở quyền thường,
    # chỉ xin quyền admin (UAC) khi người dùng bấm "Edit".
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    app.setFont(QFont("Segoe UI", 10))
    win = MainWindow(auto_open_edit_for=args.edit)
    win.show()
    sys.exit(app.exec_())


# if __name__ == "__main__":
#     main()