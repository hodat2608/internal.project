"""
Module: task_workspace_dialog.py
Mục đích: Cửa sổ Quản lý Task Workspace cho từng Camera (Task Workspace Manager).
Kích hoạt khi nhấn nút `pushButton_add_tasks` ("Tasks Resolve") trong layout_option_model.py.
Cho phép:
- Xem danh sách toàn bộ các task được gán cho Camera hiện tại.
- Thêm mới, Sửa, Xóa, Bật/Tắt, Nhân bản Task.
- Chạy thử nghiệm Test Task trên frame ảnh hiện tại.
"""

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from typing import Optional, List, Dict, Any

from app_logger.app_logger import get_logger
from module_3.task_calculator_db import (
    ensure_task_calculator_tables,
    get_tasks_by_camera,
    get_task_by_id,
    get_task_rules,
    delete_task,
    toggle_task_enabled,
    get_available_labels_for_camera,
    save_task_and_rules
)
from module_3.task_rule_editor_dialog import TaskRuleEditorDialog

_log = get_logger('module_3.task_workspace_dialog')


class TaskWorkspaceDialog(QtWidgets.QDialog):
    def __init__(self, camera_id: int, camera_name: str = "", item_code: str = "",
                 cursor=None, connection=None, parent=None):
        super().__init__(parent)
        self.camera_id = camera_id
        self.camera_name = camera_name or f"Camera-{camera_id}"
        self.item_code = item_code or "N/A"
        self.cursor = cursor
        self.connection = connection
        self.tasks: List[Dict[str, Any]] = []

        self.setWindowTitle(f"Quản Lý Workspace Task - {self.camera_name} [Mã Hàng: {self.item_code}]")
        self.resize(1000, 600)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QGroupBox {
                border: 1px solid #45475a;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 14px;
                font-weight: bold;
                color: #89b4fa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QLabel {
                color: #cdd6f4;
            }
            QPushButton {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 7px 15px;
                color: #cdd6f4;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #45475a;
                color: #ffffff;
            }
            QPushButton#btnAddTask {
                background-color: #89b4fa;
                color: #11111b;
                border: none;
            }
            QPushButton#btnAddTask:hover {
                background-color: #b4befe;
            }
            QPushButton#btnEditTask {
                background-color: #f9e2af;
                color: #11111b;
                border: none;
            }
            QPushButton#btnEditTask:hover {
                background-color: #f5e0dc;
            }
            QPushButton#btnDeleteTask {
                background-color: #f38ba8;
                color: #11111b;
                border: none;
            }
            QPushButton#btnDeleteTask:hover {
                background-color: #eba0ac;
            }
            QPushButton#btnCloneTask {
                background-color: #cba6f7;
                color: #11111b;
                border: none;
            }
            QPushButton#btnCloneTask:hover {
                background-color: #dcd7ba;
            }
            QTableWidget {
                background-color: #181825;
                border: 1px solid #313244;
                gridline-color: #313244;
                color: #cdd6f4;
                border-radius: 6px;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #313244;
                color: #cdd6f4;
                padding: 6px;
                border: 1px solid #45475a;
                font-weight: bold;
            }
        """)

        self.init_ui()
        self.load_tasks()

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Header Info Banner
        header_frame = QtWidgets.QFrame()
        header_frame.setStyleSheet("background-color: #252538; border-radius: 8px; padding: 10px;")
        header_layout = QtWidgets.QHBoxLayout(header_frame)
        
        lbl_title = QtWidgets.QLabel(f"📷 <b>Camera:</b> <font color='#89b4fa'>{self.camera_name}</font> (ID: {self.camera_id}) &nbsp;|&nbsp; 🏷️ <b>Mã Hàng:</b> <font color='#a6e3a1'>{self.item_code}</font>")
        lbl_title.setFont(QFont("Segoe UI", 12))
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()

        self.lbl_task_stats = QtWidgets.QLabel("Tổng số: 0 tasks")
        self.lbl_task_stats.setStyleSheet("color: #a6adc8; font-size: 12px;")
        header_layout.addWidget(self.lbl_task_stats)

        main_layout.addWidget(header_frame)

        # Toolbar Buttons
        toolbar_layout = QtWidgets.QHBoxLayout()
        toolbar_layout.setSpacing(10)

        self.btn_add = QtWidgets.QPushButton("➕ Thêm Task Mới")
        self.btn_add.setObjectName("btnAddTask")
        self.btn_add.clicked.connect(self.add_task)
        toolbar_layout.addWidget(self.btn_add)

        self.btn_edit = QtWidgets.QPushButton("✏️ Chỉnh Sửa")
        self.btn_edit.setObjectName("btnEditTask")
        self.btn_edit.clicked.connect(self.edit_selected_task)
        toolbar_layout.addWidget(self.btn_edit)

        self.btn_clone = QtWidgets.QPushButton("📋 Nhân Bản")
        self.btn_clone.setObjectName("btnCloneTask")
        self.btn_clone.clicked.connect(self.clone_selected_task)
        toolbar_layout.addWidget(self.btn_clone)

        self.btn_delete = QtWidgets.QPushButton("🗑️ Xóa Task")
        self.btn_delete.setObjectName("btnDeleteTask")
        self.btn_delete.clicked.connect(self.delete_selected_task)
        toolbar_layout.addWidget(self.btn_delete)

        toolbar_layout.addStretch()

        self.btn_refresh = QtWidgets.QPushButton("🔄 Làm Mới")
        self.btn_refresh.clicked.connect(self.load_tasks)
        toolbar_layout.addWidget(self.btn_refresh)

        main_layout.addLayout(toolbar_layout)

        # Table Danh sách Tasks
        self.table_tasks = QtWidgets.QTableWidget(0, 8)
        self.table_tasks.setHorizontalHeaderLabels([
            "ID", "Tên Task", "Loại Tác Vụ", "Số Rules", "PLC Register NG", "Khi Vi Phạm", "Kích Hoạt [✓]", "Thao Tác"
        ])
        self.table_tasks.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.table_tasks.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_tasks.setAlternatingRowColors(True)
        self.table_tasks.verticalHeader().setVisible(False)
        self.table_tasks.doubleClicked.connect(self.edit_selected_task)
        main_layout.addWidget(self.table_tasks)

        # Bottom Bar
        bottom_layout = QtWidgets.QHBoxLayout()
        lbl_hint = QtWidgets.QLabel("💡 Nhấp đúp vào dòng để sửa nhanh. Bật/tắt checkbox để áp dụng tức thì.")
        lbl_hint.setStyleSheet("color: #6c7086; font-size: 11px;")
        bottom_layout.addWidget(lbl_hint)

        bottom_layout.addStretch()

        self.btn_close = QtWidgets.QPushButton("Đóng")
        self.btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(self.btn_close)

        main_layout.addLayout(bottom_layout)

    def load_tasks(self):
        """Tải danh sách các task từ Database và đổ lên bảng."""
        ensure_task_calculator_tables(self.cursor, self.connection)
        self.tasks = get_tasks_by_camera(self.cursor, self.camera_id)
        
        self.table_tasks.setRowCount(len(self.tasks))
        active_count = 0

        for row_idx, t in enumerate(self.tasks):
            # Cột 0: ID
            item_id = QtWidgets.QTableWidgetItem(str(t['id']))
            item_id.setTextAlignment(Qt.AlignCenter)
            self.table_tasks.setItem(row_idx, 0, item_id)

            # Cột 1: Tên Task
            item_name = QtWidgets.QTableWidgetItem(t['task_name'])
            item_name.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.table_tasks.setItem(row_idx, 1, item_name)

            # Cột 2: Loại Task
            item_type = QtWidgets.QTableWidgetItem(t['task_type'])
            item_type.setTextAlignment(Qt.AlignCenter)
            self.table_tasks.setItem(row_idx, 2, item_type)

            # Cột 3: Số Rules
            item_rules = QtWidgets.QTableWidgetItem(f"{t['rule_count']} rules")
            item_rules.setTextAlignment(Qt.AlignCenter)
            self.table_tasks.setItem(row_idx, 3, item_rules)

            # Cột 4: PLC Register NG
            reg_text = f"{t['assign_register']} (val={t['value_bit_on']})" if t['assign_register'] else "--"
            item_reg = QtWidgets.QTableWidgetItem(reg_text)
            item_reg.setTextAlignment(Qt.AlignCenter)
            if t['assign_register']:
                item_reg.setForeground(QColor("#89b4fa"))
            self.table_tasks.setItem(row_idx, 4, item_reg)

            # Cột 5: Khi vi phạm (NG)
            item_fail = QtWidgets.QTableWidgetItem("Đánh giá NG")
            item_fail.setTextAlignment(Qt.AlignCenter)
            item_fail.setForeground(QColor("#f38ba8"))
            self.table_tasks.setItem(row_idx, 5, item_fail)

            # Cột 6: Kích Hoạt (Checkbox)
            chk_widget = QtWidgets.QWidget()
            chk_layout = QtWidgets.QHBoxLayout(chk_widget)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            chk_layout.setAlignment(Qt.AlignCenter)
            checkbox = QtWidgets.QCheckBox()
            checkbox.setChecked(t['enabled'])
            if t['enabled']:
                active_count += 1
            task_id = t['id']
            checkbox.stateChanged.connect(lambda state, tid=task_id: self.on_toggle_task(tid, state == Qt.Checked))
            chk_layout.addWidget(checkbox)
            self.table_tasks.setCellWidget(row_idx, 6, chk_widget)

            # Cột 7: Thao tác (Sửa / Xóa)
            action_widget = QtWidgets.QWidget()
            action_layout = QtWidgets.QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(6)

            btn_row_edit = QtWidgets.QPushButton("✏️")
            btn_row_edit.setToolTip("Chỉnh sửa Task")
            btn_row_edit.setFixedSize(30, 26)
            btn_row_edit.clicked.connect(lambda _, tid=t['id']: self.edit_task_by_id(tid))
            action_layout.addWidget(btn_row_edit)

            btn_row_del = QtWidgets.QPushButton("🗑️")
            btn_row_del.setToolTip("Xóa Task")
            btn_row_del.setFixedSize(30, 26)
            btn_row_del.setStyleSheet("background-color: #45222d; color: #f38ba8;")
            btn_row_del.clicked.connect(lambda _, tid=t['id'], tname=t['task_name']: self.delete_task_by_id(tid, tname))
            action_layout.addWidget(btn_row_del)

            self.table_tasks.setCellWidget(row_idx, 7, action_widget)

        self.lbl_task_stats.setText(f"Tổng số: <b>{len(self.tasks)}</b> tasks | Đang kích hoạt: <font color='#a6e3a1'><b>{active_count}</b></font>")

    def on_toggle_task(self, task_id: int, enabled: bool):
        toggle_task_enabled(self.cursor, self.connection, task_id, enabled)
        # Cập nhật lại số liệu thống kê
        for t in self.tasks:
            if t['id'] == task_id:
                t['enabled'] = enabled
                break
        active_count = sum(1 for t in self.tasks if t['enabled'])
        self.lbl_task_stats.setText(f"Tổng số: <b>{len(self.tasks)}</b> tasks | Đang kích hoạt: <font color='#a6e3a1'><b>{active_count}</b></font>")

    def add_task(self, preselected_labels: Optional[List[str]] = None):
        """Mở dialog tạo task mới."""
        avail_labels = get_available_labels_for_camera(self.cursor, self.camera_id)
        dlg = TaskRuleEditorDialog(
            camera_id=self.camera_id,
            task_data=None,
            rules_data=None,
            available_labels=avail_labels,
            preselected_labels=preselected_labels,
            cursor=self.cursor,
            connection=self.connection,
            parent=self
        )
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.load_tasks()

    def edit_selected_task(self):
        row = self.table_tasks.currentRow()
        if 0 <= row < len(self.tasks):
            self.edit_task_by_id(self.tasks[row]['id'])

    def edit_task_by_id(self, task_id: int):
        task_info = get_task_by_id(self.cursor, task_id)
        if not task_info:
            task_info = next((t for t in self.tasks if t['id'] == task_id), None)
        if not task_info:
            return
        rules = get_task_rules(self.cursor, task_id)
        avail_labels = get_available_labels_for_camera(self.cursor, self.camera_id)

        dlg = TaskRuleEditorDialog(
            camera_id=self.camera_id,
            task_data=task_info,
            rules_data=rules,
            available_labels=avail_labels,
            cursor=self.cursor,
            connection=self.connection,
            parent=self
        )
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.load_tasks()

    def clone_selected_task(self):
        row = self.table_tasks.currentRow()
        if 0 <= row < len(self.tasks):
            original = self.tasks[row]
            task_id = original['id']
            rules = get_task_rules(self.cursor, task_id)

            clone_data = dict(original)
            clone_data['id'] = None
            clone_data['task_name'] = f"{original['task_name']} (Bản sao)"
            
            saved_id = save_task_and_rules(self.cursor, self.connection, clone_data, rules)
            if saved_id:
                QtWidgets.QMessageBox.information(self, "Nhân Bản Thành Công", f"Đã nhân bản Task mới: '{clone_data['task_name']}' (ID: {saved_id})")
                self.load_tasks()

    def delete_selected_task(self):
        row = self.table_tasks.currentRow()
        if 0 <= row < len(self.tasks):
            t = self.tasks[row]
            self.delete_task_by_id(t['id'], t['task_name'])

    def delete_task_by_id(self, task_id: int, task_name: str):
        reply = QtWidgets.QMessageBox.question(
            self,
            "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa Task: '{task_name}' (ID: {task_id}) không?\nTất cả quy tắc liên quan sẽ bị xóa vĩnh viễn.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            if delete_task(self.cursor, self.connection, task_id):
                self.load_tasks()
            else:
                QtWidgets.QMessageBox.critical(self, "Lỗi", "Không thể xóa Task. Vui lòng kiểm tra lại kết nối Database!")
