# -*- coding: utf-8 -*-
"""
Module quản lý toàn bộ giao diện UI động và cơ chế lưu/tải các tín hiệu khởi đầu (Program Signal Ready)
khi khởi tạo thành công PLC và Camera.

Bao gồm các lựa chọn:
- Tên tín hiệu PLC (Signal Name)
- Giá trị ON (khi kết nối thành công)
- Giá trị OFF (khi mất kết nối / lỗi)
- Kích hoạt (is_enabled: tham gia xử lý)
- Gửi liên tục (is_continuous: có gửi liên tục heartbeat không)
- Nút xóa hàng
"""

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMessageBox
from module_1.root_path import resource_path
from app_logger.app_logger import get_logger as _get_logger

_log = _get_logger('module_3.program_signal_ready')


def _parse_bool(val, default=True):
    """Chuyển đổi an toàn giá trị từ MySQL (int, str, bytes, bool) thành True/False."""
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, (bytes, bytearray)):
        if val in (b'\x00', b'0'):
            return False
        if val in (b'\x01', b'1'):
            return True
        try:
            val = val.decode('utf-8', errors='ignore')
        except Exception:
            return default
    s = str(val).strip('\x00 \t\n').lower()
    if s in ('1', 'true', 'yes', 'on'):
        return True
    if s in ('0', 'false', 'no', 'off', ''):
        return False
    return default


def _ensure_program_signal_ready_table(cursor, connect_db=None):
    """Đảm bảo bảng program_signal_ready luôn tồn tại và có đầy đủ cột is_continuous."""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS program_signal_ready (
                id                  INT AUTO_INCREMENT PRIMARY KEY,
                camera_id           INT NOT NULL,
                signal_name         VARCHAR(100) NOT NULL,
                val_on              VARCHAR(50) NOT NULL DEFAULT '1',
                val_off             VARCHAR(50) NOT NULL DEFAULT '0',
                is_enabled          TINYINT(1) NOT NULL DEFAULT 1,
                is_continuous       TINYINT(1) NOT NULL DEFAULT 1,
                order_index         INT NOT NULL DEFAULT 0,
                INDEX idx_camera_ready (camera_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        if connect_db and hasattr(connect_db, 'connection') and connect_db.connection:
            connect_db.connection.commit()
    except Exception as e:
        _log.warning("Lỗi kiểm tra/tạo bảng program_signal_ready: %s", e)

    # Đảm bảo migration cột is_continuous nếu bảng đã tạo từ trước
    try:
        cursor.execute("SHOW COLUMNS FROM program_signal_ready LIKE 'is_continuous'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE program_signal_ready ADD COLUMN is_continuous TINYINT(1) NOT NULL DEFAULT 1 AFTER is_enabled")
            if connect_db and hasattr(connect_db, 'connection') and connect_db.connection:
                connect_db.connection.commit()
    except Exception as e:
        _log.warning("Lỗi migration cột is_continuous trong program_signal_ready: %s", e)


class SignalReadyRowWidget(QtWidgets.QFrame):
    """Widget đại diện cho 1 hàng cấu hình tín hiệu khởi đầu."""

    def __init__(self, index: int, available_signals: list, signal_name=None,
                 val_on="1", val_off="0", is_enabled=True, is_continuous=True,
                 parent_manager=None, parent=None):
        super().__init__(parent)
        self.parent_manager = parent_manager
        self.setObjectName("signal_ready_row_card")

        font_10 = QtGui.QFont("Segoe UI", 10)
        font_10_bold = QtGui.QFont("Segoe UI", 10)
        font_10_bold.setBold(True)

        self.setStyleSheet("""
            QFrame#signal_ready_row_card {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
            }
            QFrame#signal_ready_row_card:hover {
                border: 1px solid #0284C7;
                background-color: #F8FAFC;
            }
        """)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(10)

        # 1. Số thứ tự (Index)
        self.label_index = QtWidgets.QLabel(f"#{index}")
        self.label_index.setFont(font_10_bold)
        self.label_index.setAlignment(QtCore.Qt.AlignCenter)
        self.label_index.setFixedWidth(35)
        self.label_index.setStyleSheet("color: #64748B;")
        layout.addWidget(self.label_index)

        # 2. ComboBox Tên tín hiệu
        self.combo_signal = QtWidgets.QComboBox()
        self.combo_signal.setFont(font_10_bold)
        self.combo_signal.setMinimumHeight(30)
        self.combo_signal.setStyleSheet("""
            QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #94A3B8;
                border-radius: 4px;
                padding: 2px 8px;
                color: #0F172A;
                font-family: 'Segoe UI';
                font-size: 10pt;
                font-weight: bold;
            }
            QComboBox:hover {
                border-color: #0284C7;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
        """)
        self.update_available_signals(available_signals, signal_name)
        self.combo_signal.currentTextChanged.connect(self._on_signal_changed)
        layout.addWidget(self.combo_signal, stretch=3)

        # 3. SpinBox Giá trị ON (Khi kết nối OK)
        self.spin_on = QtWidgets.QSpinBox()
        self.spin_on.setFont(font_10_bold)
        self.spin_on.setRange(-999999, 999999)
        self.spin_on.setAlignment(QtCore.Qt.AlignCenter)
        self.spin_on.setMinimumHeight(30)
        self.spin_on.setToolTip("Giá trị gửi tới PLC khi Camera và PLC kết nối THÀNH CÔNG (ON)")
        self.spin_on.setStyleSheet("""
            QSpinBox {
                background-color: #F0FDF4;
                border: 1px solid #86EFAC;
                border-radius: 4px;
                padding: 2px 4px;
                color: #166534;
                font-family: 'Segoe UI';
                font-size: 10pt;
                font-weight: bold;
            }
            QSpinBox:hover, QSpinBox:focus {
                border-color: #22C55E;
                background-color: #DCFCE7;
            }
        """)
        try:
            self.spin_on.setValue(int(val_on))
        except Exception:
            self.spin_on.setValue(1)
        layout.addWidget(self.spin_on, stretch=2)

        # 4. SpinBox Giá trị OFF (Khi mất kết nối / Lỗi)
        self.spin_off = QtWidgets.QSpinBox()
        self.spin_off.setFont(font_10_bold)
        self.spin_off.setRange(-999999, 999999)
        self.spin_off.setAlignment(QtCore.Qt.AlignCenter)
        self.spin_off.setMinimumHeight(30)
        self.spin_off.setToolTip("Giá trị gửi tới PLC khi Camera hoặc PLC THẤT BẠI / MẤT KẾT NỐI (OFF)")
        self.spin_off.setStyleSheet("""
            QSpinBox {
                background-color: #FEF2F2;
                border: 1px solid #FECACA;
                border-radius: 4px;
                padding: 2px 4px;
                color: #991B1B;
                font-family: 'Segoe UI';
                font-size: 10pt;
                font-weight: bold;
            }
            QSpinBox:hover, QSpinBox:focus {
                border-color: #EF4444;
                background-color: #FEE2E2;
            }
        """)
        try:
            self.spin_off.setValue(int(val_off))
        except Exception:
            self.spin_off.setValue(0)
        layout.addWidget(self.spin_off, stretch=2)

        # 5. CheckBox Kích hoạt (Enable)
        self.check_enabled = QtWidgets.QCheckBox("")
        self.check_enabled.setFont(font_10_bold)
        self.check_enabled.setChecked(bool(is_enabled))
        self.check_enabled.setFixedWidth(80)
        self.check_enabled.setToolTip("Tích chọn để tín hiệu này tham gia xử lý")
        self.check_enabled.setStyleSheet("""
            QCheckBox {
                font-family: 'Segoe UI';
                font-size: 10pt;
                font-weight: bold;
                color: #1E293B;
            }
        """)
        self.check_enabled.toggled.connect(self._on_enable_toggled)
        layout.addWidget(self.check_enabled)

        # 6. CheckBox Gửi liên tục (Continuous)
        self.check_continuous = QtWidgets.QCheckBox("")
        self.check_continuous.setFont(font_10_bold)
        self.check_continuous.setChecked(bool(is_continuous))
        self.check_continuous.setFixedWidth(85)
        self.check_continuous.setToolTip("Tích chọn: gửi liên tục qua luồng heartbeat; Bỏ tích: chỉ gửi 1 lần khi khởi động")
        self.check_continuous.setStyleSheet("""
            QCheckBox {
                font-family: 'Segoe UI';
                font-size: 10pt;
                font-weight: bold;
                color: #0284C7;
            }
        """)
        self.check_continuous.toggled.connect(self._on_continuous_toggled)
        layout.addWidget(self.check_continuous)

        # 7. Nút Xóa hàng
        self.btn_delete = QtWidgets.QPushButton(" ✕ ")
        self.btn_delete.setFont(font_10_bold)
        self.btn_delete.setFixedWidth(75)
        self.btn_delete.setMinimumHeight(30)
        self.btn_delete.setToolTip("Xóa hàng tín hiệu này")
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #FFF1F2;
                color: #DC2626;
                border: 1px solid #FECDD3;
                border-radius: 4px;
                padding: 2px 8px;
                font-family: 'Segoe UI';
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FEE2E2;
                border-color: #F87171;
                color: #B91C1C;
            }
            QPushButton:pressed {
                background-color: #FECDD3;
            }
        """)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self.btn_delete)

        self._apply_enable_style(self.check_enabled.isChecked())

    def update_available_signals(self, available_signals: list, select_signal=None):
        """Cập nhật danh sách tín hiệu khả dụng trong ComboBox."""
        current = select_signal or self.combo_signal.currentText()
        self.combo_signal.blockSignals(True)
        self.combo_signal.clear()
        for sig in available_signals:
            self.combo_signal.addItem(str(sig))
        if current:
            idx = self.combo_signal.findText(current)
            if idx >= 0:
                self.combo_signal.setCurrentIndex(idx)
            else:
                self.combo_signal.addItem(current)
                self.combo_signal.setCurrentText(current)
        self.combo_signal.blockSignals(False)

    def _on_signal_changed(self, new_sig: str):
        """Tự động gợi ý ON/OFF phù hợp khi đổi tên tín hiệu (vd: busy ON=0/OFF=1)."""
        sig_lower = str(new_sig).strip().lower()
        if sig_lower == 'busy':
            self.spin_on.setValue(0)
            self.spin_off.setValue(1)
        elif sig_lower in ('run', 'ready', 'gate', 'complete'):
            self.spin_on.setValue(1)
            self.spin_off.setValue(0)

    def _on_enable_toggled(self, checked: bool):
        self._apply_enable_style(checked)
        if self.parent_manager:
            self.parent_manager.update_status_info()

    def _on_continuous_toggled(self, checked: bool):
        if self.parent_manager:
            self.parent_manager.update_status_info()

    def _apply_enable_style(self, checked: bool):
        self.combo_signal.setEnabled(checked)
        self.spin_on.setEnabled(checked)
        self.spin_off.setEnabled(checked)
        self.check_continuous.setEnabled(checked)

    def _on_delete_clicked(self):
        if self.parent_manager:
            self.parent_manager.remove_row(self)

    def get_data(self) -> dict:
        return {
            'signal_name': self.combo_signal.currentText().strip(),
            'val_on': str(self.spin_on.value()),
            'val_off': str(self.spin_off.value()),
            'is_enabled': int(self.check_enabled.isChecked()),
            'is_continuous': int(self.check_continuous.isChecked())
        }


class ProgramSignalReadyManager:
    """
    Trình quản lý giao diện danh sách tín hiệu khởi đầu (Program Signal Ready).
    Toàn bộ layout và nút bấm được sinh tự động bằng code Python, tương thích hoàn toàn
    với cấu trúc UI được sinh từ Qt Designer.
    """

    DEFAULT_PRESETS = [
        {'signal_name': 'ready', 'val_on': '1', 'val_off': '0', 'is_enabled': 1, 'is_continuous': 1},
        {'signal_name': 'run',   'val_on': '1', 'val_off': '0', 'is_enabled': 1, 'is_continuous': 1},
        {'signal_name': 'busy',  'val_on': '0', 'val_off': '1', 'is_enabled': 1, 'is_continuous': 1},
    ]

    def __init__(self, uic, signal_table_helper=None, parent_process=None):
        self.uic = uic
        self.signal_table_helper = signal_table_helper
        self.parent_process = parent_process
        self.rows = []

        self._setup_action_bar()
        self._setup_container()

    def _setup_action_bar(self):
        """Khởi tạo và gắn động các nút điều khiển bên dưới ScrollArea vào gridLayout_29."""
        grid = getattr(self.uic, 'gridLayout_29', None)
        if not grid:
            return

        btn_load = getattr(self.uic, 'pushButton_load_setting_ProgramSignalReady', None)
        btn_apply = getattr(self.uic, 'pushButton_apply_setting_ProgramSignalReady', None)
        lbl_sep = getattr(self.uic, 'label_45', None)
        group_box = getattr(self.uic, 'groupProgramSignalReady', None)

        # Tháo các phần tử hiện tại khỏi gridLayout_29 để sắp xếp lại
        while grid.count():
            item = grid.takeAt(0)
            w = item.widget()
            if w and w not in (btn_load, btn_apply, lbl_sep):
                w.hide()

        grid.setSpacing(6)

        font_bold = QtGui.QFont("Segoe UI", 10)
        font_bold.setBold(True)
        font_normal = QtGui.QFont("Segoe UI", 10)

        # 1. Nút Thêm tín hiệu (Add Signal)
        self.pushButton_add = QtWidgets.QPushButton(group_box)
        self.pushButton_add.setObjectName("pushButton_add_ProgramSignalReady")
        self.pushButton_add.setMinimumSize(QtCore.QSize(130, 32))
        self.pushButton_add.setFont(font_bold)
        self.pushButton_add.setText(" + Thêm tín hiệu")
        self.pushButton_add.setToolTip("Thêm một hàng tín hiệu mới vào danh sách gửi PLC")
        try:
            icon_add = QtGui.QIcon()
            icon_add.addPixmap(QtGui.QPixmap(resource_path("module_3/assert/icon/add_row.png")), QtGui.QIcon.Normal, QtGui.QIcon.Off)
            self.pushButton_add.setIcon(icon_add)
            self.pushButton_add.setIconSize(QtCore.QSize(18, 18))
        except Exception:
            pass

        self.pushButton_add.setStyleSheet("""
            QPushButton {
                background-color: #0284C7;
                color: #FFFFFF;
                border: 1px solid #0369A1;
                border-radius: 5px;
                padding: 4px 12px;
                font-family: 'Segoe UI';
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0369A1;
            }
            QPushButton:pressed {
                background-color: #075985;
            }
        """)
        self.pushButton_add.clicked.connect(lambda: self.add_row())
        grid.addWidget(self.pushButton_add, 0, 0, 1, 1)

        # 2. Nút Mặc định (Reset to default: ready, run, busy)
        self.pushButton_default = QtWidgets.QPushButton(group_box)
        self.pushButton_default.setObjectName("pushButton_default_ProgramSignalReady")
        self.pushButton_default.setMinimumSize(QtCore.QSize(100, 32))
        self.pushButton_default.setFont(font_bold)
        self.pushButton_default.setText(" Default")
        self.pushButton_default.setToolTip("Restore standard : ready, run, busy")
        try:
            icon_refresh = QtGui.QIcon()
            icon_refresh.addPixmap(QtGui.QPixmap(resource_path("module_3/assert/icon/circular-arrows.png")), QtGui.QIcon.Normal, QtGui.QIcon.Off)
            self.pushButton_default.setIcon(icon_refresh)
            self.pushButton_default.setIconSize(QtCore.QSize(16, 16))
        except Exception:
            pass

        self.pushButton_default.setStyleSheet("""
            QPushButton {
                background-color: #F8FAFC;
                color: #334155;
                border: 1px solid #CBD5E1;
                border-radius: 5px;
                padding: 4px 10px;
                font-family: 'Segoe UI';
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
                color: #0F172A;
            }
            QPushButton:pressed {
                background-color: #CBD5E1;
            }
        """)
        self.pushButton_default.clicked.connect(self.reset_to_default)
        grid.addWidget(self.pushButton_default, 0, 1, 1, 1)

        # 3. Nút Xóa hết (Clear all)
        self.pushButton_clear = QtWidgets.QPushButton(group_box)
        self.pushButton_clear.setObjectName("pushButton_clear_all_ProgramSignalReady")
        self.pushButton_clear.setMinimumSize(QtCore.QSize(90, 32))
        self.pushButton_clear.setFont(font_bold)
        self.pushButton_clear.setText(" Delete All")
        self.pushButton_clear.setToolTip("Xóa toàn bộ các hàng tín hiệu hiện có trong bảng")
        try:
            icon_broom = QtGui.QIcon()
            icon_broom.addPixmap(QtGui.QPixmap(resource_path("module_3/assert/icon/broom.png")), QtGui.QIcon.Normal, QtGui.QIcon.Off)
            self.pushButton_clear.setIcon(icon_broom)
            self.pushButton_clear.setIconSize(QtCore.QSize(16, 16))
        except Exception:
            pass

        self.pushButton_clear.setStyleSheet("""
            QPushButton {
                background-color: #FFF1F2;
                color: #BE123C;
                border: 1px solid #FECDD3;
                border-radius: 5px;
                padding: 4px 10px;
                font-family: 'Segoe UI';
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FFE4E6;
                color: #9F1239;
            }
            QPushButton:pressed {
                background-color: #FECDD3;
            }
        """)
        self.pushButton_clear.clicked.connect(self.clear_all_rows)
        grid.addWidget(self.pushButton_clear, 0, 2, 1, 1)

        # 4. Label hiển thị thông tin số lượng
        self.label_info = QtWidgets.QLabel(group_box)
        self.label_info.setObjectName("label_info_ProgramSignalReady")
        self.label_info.setFont(font_normal)
        self.label_info.setText("Choosing: 0 signal")
        self.label_info.setStyleSheet("color: #475569; font-style: italic; padding-left: 8px;")
        grid.addWidget(self.label_info, 0, 3, 1, 1)

        # 5. Expanding Spacer đẩy các nút Load/Apply sang phải
        spacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        grid.addItem(spacer, 0, 4, 1, 1)

        # 6. Gán lại nút Load
        if btn_load:
            btn_load.setToolTip("Tải cấu hình tín hiệu khởi đầu từ CSDL")
            btn_load.setMinimumSize(QtCore.QSize(32, 32))
            btn_load.setMaximumSize(QtCore.QSize(32, 32))
            grid.addWidget(btn_load, 0, 5, 1, 1)

        # 7. Separator label giữa Load và Apply
        if lbl_sep:
            lbl_sep.setMinimumSize(QtCore.QSize(10, 0))
            grid.addWidget(lbl_sep, 0, 6, 1, 1)

        # 8. Gán lại nút Apply
        if btn_apply:
            btn_apply.setToolTip("Lưu cấu hình tín hiệu khởi đầu vào CSDL")
            btn_apply.setMinimumSize(QtCore.QSize(32, 32))
            btn_apply.setMaximumSize(QtCore.QSize(32, 32))
            grid.addWidget(btn_apply, 0, 7, 1, 1)

        # Gán thuộc tính vào uic để đảm bảo tính trong suốt
        self.uic.pushButton_add_ProgramSignalReady = self.pushButton_add
        self.uic.pushButton_default_ProgramSignalReady = self.pushButton_default
        self.uic.pushButton_clear_all_ProgramSignalReady = self.pushButton_clear
        self.uic.label_info_ProgramSignalReady = self.label_info

    def _setup_container(self):
        """Khởi tạo cấu trúc giao diện bảng bên trong scrollAreaWidgetContents_2."""
        container = getattr(self.uic, 'scrollAreaWidgetContents_2', None)
        if not container:
            return

        scroll_area = getattr(self.uic, 'scrollArea_ProgramSignalReady', None)
        if scroll_area:
            scroll_area.setWidgetResizable(True)

        old_layout = container.layout()
        if old_layout:
            while old_layout.count():
                child = old_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            QtWidgets.QWidget().setLayout(old_layout)

        main_layout = QtWidgets.QVBoxLayout(container)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(4)

        # 1. Tạo Header Bar (tiêu đề các cột)
        header_frame = QtWidgets.QFrame()
        header_frame.setObjectName("header_program_signal_ready")
        header_frame.setMinimumHeight(34)
        header_frame.setMaximumHeight(34)
        header_frame.setStyleSheet("""
            QFrame#header_program_signal_ready {
                background-color: #E0F2FE;
                border: 1px solid #BAE6FD;
                border-radius: 5px;
            }
            QLabel {
                color: #0369A1;
                font-family: 'Segoe UI';
                font-size: 10pt;
                font-weight: bold;
            }
        """)

        h_layout = QtWidgets.QHBoxLayout(header_frame)
        h_layout.setContentsMargins(6, 2, 6, 2)
        h_layout.setSpacing(10)

        lbl_no = QtWidgets.QLabel("#No")
        lbl_no.setFixedWidth(35)
        lbl_no.setAlignment(QtCore.Qt.AlignCenter)
        h_layout.addWidget(lbl_no)

        lbl_sig = QtWidgets.QLabel("Signal Name")
        h_layout.addWidget(lbl_sig, stretch=3)

        lbl_on = QtWidgets.QLabel("Value ON")
        lbl_on.setAlignment(QtCore.Qt.AlignCenter)
        h_layout.addWidget(lbl_on, stretch=2)

        lbl_off = QtWidgets.QLabel("Value OFF")
        lbl_off.setAlignment(QtCore.Qt.AlignCenter)
        h_layout.addWidget(lbl_off, stretch=2)

        lbl_enable = QtWidgets.QLabel("Enable")
        lbl_enable.setFixedWidth(80)
        lbl_enable.setAlignment(QtCore.Qt.AlignCenter)
        h_layout.addWidget(lbl_enable)

        lbl_continuous = QtWidgets.QLabel("Continuous")
        lbl_continuous.setFixedWidth(85)
        lbl_continuous.setAlignment(QtCore.Qt.AlignCenter)
        h_layout.addWidget(lbl_continuous)

        lbl_action = QtWidgets.QLabel("Delete")
        lbl_action.setFixedWidth(75)
        lbl_action.setAlignment(QtCore.Qt.AlignCenter)
        h_layout.addWidget(lbl_action)

        main_layout.addWidget(header_frame)

        # 2. Layout chứa các hàng động
        self.rows_layout = QtWidgets.QVBoxLayout()
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(4)
        main_layout.addLayout(self.rows_layout)

        # 3. Expanding vertical spacer bên dưới cùng
        self.vertical_spacer = QtWidgets.QSpacerItem(20, 20, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        main_layout.addItem(self.vertical_spacer)

        self.update_status_info()

    def get_available_signals(self) -> list:
        """Lấy toàn bộ tên thanh ghi / tín hiệu từ bảng tableWidget."""
        signals = []
        table = getattr(self.uic, 'tableWidget', None)
        if table:
            for row in range(table.rowCount()):
                item = table.verticalHeaderItem(row)
                if item and item.text().strip():
                    sig_name = item.text().strip()
                    if sig_name not in signals:
                        signals.append(sig_name)

        if not signals:
            signals = ['ready', 'run', 'trigger', 'busy', 'gate', 'complete', 'reset_ok', 'reset_counter', 'counter_plc']
        return signals

    def refresh_available_signals(self):
        """Cập nhật lại danh sách tín hiệu khả dụng cho tất cả combobox các hàng hiện hữu."""
        signals = self.get_available_signals()
        for row in self.rows:
            row.update_available_signals(signals)

    def add_row(self, signal_name=None, val_on=None, val_off=None, is_enabled=True, is_continuous=True) -> SignalReadyRowWidget:
        """Thêm 1 hàng cấu hình tín hiệu mới."""
        available = self.get_available_signals()

        if not signal_name:
            chosen = [r.combo_signal.currentText().strip() for r in self.rows]
            for sig in available:
                if sig not in chosen:
                    signal_name = sig
                    break
            if not signal_name and available:
                signal_name = available[0]

        sig_lower = str(signal_name).strip().lower() if signal_name else ""
        if val_on is None:
            val_on = "0" if sig_lower == 'busy' else "1"
        if val_off is None:
            val_off = "1" if sig_lower == 'busy' else "0"

        index = len(self.rows) + 1
        row_widget = SignalReadyRowWidget(
            index=index,
            available_signals=available,
            signal_name=signal_name,
            val_on=val_on,
            val_off=val_off,
            is_enabled=is_enabled,
            is_continuous=is_continuous,
            parent_manager=self
        )

        self.rows.append(row_widget)
        self.rows_layout.addWidget(row_widget)
        self._reindex_rows()
        self.update_status_info()
        return row_widget

    def remove_row(self, row_widget: SignalReadyRowWidget):
        """Xóa 1 hàng tín hiệu khỏi danh sách."""
        if row_widget in self.rows:
            self.rows.remove(row_widget)
            self.rows_layout.removeWidget(row_widget)
            row_widget.setParent(None)
            row_widget.deleteLater()
            self._reindex_rows()
            self.update_status_info()

    def _reindex_rows(self):
        """Cập nhật lại số thứ tự #1, #2... sau khi thêm hoặc xóa."""
        for i, row in enumerate(self.rows, 1):
            row.label_index.setText(f"#{i}")

    def update_status_info(self):
        """Cập nhật label thống kê số lượng tín hiệu."""
        lbl = getattr(self, 'label_info', None)
        if lbl:
            total = len(self.rows)
            active = sum(1 for r in self.rows if r.check_enabled.isChecked())
            continuous = sum(1 for r in self.rows if r.check_enabled.isChecked() and r.check_continuous.isChecked())
            lbl.setText(f"Choosing: {total} signal ({active} activated, {continuous} send continuously)")

    def reset_to_default(self):
        """Khôi phục về danh sách tín hiệu chuẩn: ready, run, busy."""
        self.clear_all_rows(show_confirm=False)
        for item in self.DEFAULT_PRESETS:
            self.add_row(
                signal_name=item['signal_name'],
                val_on=item['val_on'],
                val_off=item['val_off'],
                is_enabled=item['is_enabled'],
                is_continuous=item.get('is_continuous', 1)
            )

    def clear_all_rows(self, show_confirm=True):
        """Xóa toàn bộ các hàng tín hiệu hiện có."""
        if show_confirm and self.rows:
            reply = QMessageBox.question(
                None, "Xác nhận xóa hết",
                "Bạn có chắc chắn muốn xóa toàn bộ các hàng tín hiệu trong danh sách?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        for row in list(self.rows):
            self.rows_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        self.rows.clear()
        self.update_status_info()

    def get_all_rows_data(self) -> list:
        """Lấy toàn bộ dữ liệu hiện tại trên giao diện."""
        data = []
        for i, row in enumerate(self.rows):
            item = row.get_data()
            item['order_index'] = i
            data.append(item)
        return data

    def save_to_db(self, cursor, connect_db, camera_id):
        """Lưu cấu hình tín hiệu khởi đầu vào CSDL MySQL."""
        if self.parent_process and hasattr(self.parent_process, 'check_permission_full_control'):
            if not self.parent_process.check_permission_full_control():
                return False

        try:
            _ensure_program_signal_ready_table(cursor, connect_db)
            cursor.execute("DELETE FROM program_signal_ready WHERE camera_id = %s", (camera_id,))

            rows_data = self.get_all_rows_data()
            sql_insert = """
                INSERT INTO program_signal_ready
                    (camera_id, signal_name, val_on, val_off, is_enabled, is_continuous, order_index)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            for r in rows_data:
                cursor.execute(sql_insert, (
                    camera_id,
                    r['signal_name'],
                    r['val_on'],
                    r['val_off'],
                    r['is_enabled'],
                    r.get('is_continuous', 1),
                    r['order_index']
                ))

            if connect_db and hasattr(connect_db, 'connection') and connect_db.connection:
                connect_db.connection.commit()

            if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                self.uic.config_logger.set_status(
                    'program_signal_ready', 'success',
                    f"Đã lưu thành công {len(rows_data)} tín hiệu khởi đầu Ready"
                )

            QMessageBox.information(
                None, "Thành công",
                f"Đã lưu thành công {len(rows_data)} tín hiệu khởi đầu (Program Signal Ready)!"
            )
            return True

        except Exception as e:
            if connect_db and hasattr(connect_db, 'connection') and connect_db.connection:
                connect_db.connection.rollback()
            _log.error("Lỗi khi lưu program_signal_ready: %s", e)
            if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                self.uic.config_logger.set_status('program_signal_ready', 'error', f"Lỗi lưu: {str(e)}")
            QMessageBox.critical(None, "Lỗi khi lưu tín hiệu Ready", str(e))
            return False

    def load_from_db(self, cursor, camera_id):
        """Tải cấu hình tín hiệu khởi đầu từ CSDL MySQL lên giao diện."""
        try:
            _ensure_program_signal_ready_table(cursor)
            cursor.execute("""
                SELECT signal_name, val_on, val_off, is_enabled, is_continuous
                FROM program_signal_ready
                WHERE camera_id = %s
                ORDER BY order_index ASC, id ASC
            """, (camera_id,))
            records = cursor.fetchall()

            self.clear_all_rows(show_confirm=False)

            if records:
                for row in records:
                    is_en = _parse_bool(row[3], default=True) if len(row) > 3 else True
                    is_cont = _parse_bool(row[4], default=True) if len(row) > 4 else True
                    self.add_row(
                        signal_name=row[0],
                        val_on=row[1],
                        val_off=row[2],
                        is_enabled=is_en,
                        is_continuous=is_cont
                    )
            else:
                self.reset_to_default()

            self.update_status_info()
            return True

        except Exception as e:
            _log.error("Lỗi khi tải program_signal_ready: %s", e)
            self.reset_to_default()
            return False
