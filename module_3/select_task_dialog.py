"""
Module: select_task_dialog.py
Mục đích: Hộp thoại popup khi người dùng chọn nhiều dòng nhãn trên tableView và nhấn "Thêm vào Task".
Cho phép:
- Xem danh sách các nhãn đang được chọn.
- Chọn thêm vào 1 Task đã có của Camera HOẶC Tạo 1 Task mới.
- Bấm "Xác nhận & Cấu hình" sẽ mở TaskRuleEditorDialog với các nhãn đã chọn được điền sẵn.
"""

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from typing import List, Dict, Any, Optional

from module_3.task_calculator_db import get_tasks_by_camera, get_task_rules, get_available_labels_for_camera
from module_3.task_rule_editor_dialog import TaskRuleEditorDialog


class SelectTaskForLabelsDialog(QtWidgets.QDialog):
    def __init__(self, camera_id: int, model_id: int, selected_labels: List[str], cursor=None, connection=None, parent=None):
        super().__init__(parent)
        self.camera_id = camera_id
        self.model_id = model_id
        self.selected_labels = selected_labels
        self.cursor = cursor
        self.connection = connection
        self.tasks: List[Dict[str, Any]] = []

        self.setWindowTitle("Thêm Nhãn vào Task Calculator")
        self.resize(500, 320)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #cdd6f4;
            }
            QComboBox, QLineEdit {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 6px 10px;
                color: #ffffff;
                font-size: 13px;
            }
            QPushButton {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 7px 15px;
                color: #cdd6f4;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45475a;
                color: #ffffff;
            }
            QPushButton#btnConfirm {
                background-color: #89b4fa;
                color: #11111b;
                border: none;
            }
            QPushButton#btnConfirm:hover {
                background-color: #b4befe;
            }
            QRadioButton {
                color: #cdd6f4;
                font-size: 13px;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
        """)

        self.init_ui()
        self.load_camera_tasks()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        # Header info: Nhãn đã chọn
        lbl_header = QtWidgets.QLabel("🏷️ <b>Các nhãn đang được chọn từ bảng:</b>")
        lbl_header.setStyleSheet("font-size: 14px; color: #89b4fa;")
        layout.addWidget(lbl_header)

        tags_frame = QtWidgets.QFrame()
        tags_frame.setStyleSheet("background-color: #181825; border-radius: 6px; padding: 8px;")
        tags_layout = QtWidgets.QHBoxLayout(tags_frame)
        tags_layout.setSpacing(6)
        
        for lbl in self.selected_labels:
            badge = QtWidgets.QLabel(f" {lbl} ")
            badge.setStyleSheet("background-color: #45475a; color: #a6e3a1; border-radius: 4px; padding: 3px 6px; font-weight: bold;")
            tags_layout.addWidget(badge)
        tags_layout.addStretch()
        layout.addWidget(tags_frame)

        # Lựa chọn: Tạo mới hay Thêm vào task có sẵn
        layout.addWidget(QtWidgets.QLabel("🎯 <b>Chọn hành động:</b>"))

        self.radio_new_task = QtWidgets.QRadioButton("Tạo một Task mới cho các nhãn này")
        self.radio_new_task.setChecked(True)
        self.radio_new_task.toggled.connect(self.on_radio_toggled)
        layout.addWidget(self.radio_new_task)

        layout_new_name = QtWidgets.QHBoxLayout()
        layout_new_name.setContentsMargins(24, 0, 0, 0)
        self.line_new_task_name = QtWidgets.QLineEdit()
        default_name = f"Ktra " + " - ".join(self.selected_labels[:2]) if self.selected_labels else "Task Mới"
        self.line_new_task_name.setText(default_name)
        self.line_new_task_name.setPlaceholderText("Nhập tên Task mới...")
        layout_new_name.addWidget(self.line_new_task_name)
        layout.addLayout(layout_new_name)

        self.radio_existing_task = QtWidgets.QRadioButton("Thêm vào một Task đã có của Camera")
        self.radio_existing_task.toggled.connect(self.on_radio_toggled)
        layout.addWidget(self.radio_existing_task)

        layout_existing = QtWidgets.QHBoxLayout()
        layout_existing.setContentsMargins(24, 0, 0, 0)
        self.combo_tasks = QtWidgets.QComboBox()
        self.combo_tasks.setEnabled(False)
        layout_existing.addWidget(self.combo_tasks)
        layout.addLayout(layout_existing)

        layout.addStretch()

        # Nút xác nhận
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_cancel = QtWidgets.QPushButton("Hủy")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        btn_layout.addStretch()

        self.btn_confirm = QtWidgets.QPushButton("Tiếp Tục Soạn Thảo Luật ➜")
        self.btn_confirm.setObjectName("btnConfirm")
        self.btn_confirm.clicked.connect(self.confirm_and_open_editor)
        btn_layout.addWidget(self.btn_confirm)

        layout.addLayout(btn_layout)

    def load_camera_tasks(self):
        self.tasks = get_tasks_by_camera(self.cursor, self.camera_id, self.model_id)
        self.combo_tasks.clear()
        if self.tasks:
            for t in self.tasks:
                self.combo_tasks.addItem(f"#{t['id']} - {t['task_name']} ({t['rule_count']} rules)", t['id'])
        else:
            self.combo_tasks.addItem("Chưa có Task nào cho Camera này", None)
            self.radio_existing_task.setEnabled(False)

    def on_radio_toggled(self):
        is_existing = self.radio_existing_task.isChecked()
        self.combo_tasks.setEnabled(is_existing and len(self.tasks) > 0)
        self.line_new_task_name.setEnabled(not is_existing)

    def confirm_and_open_editor(self):
        avail_labels = get_available_labels_for_camera(self.cursor, self.camera_id, self.model_id)
        # Bổ sung các nhãn vừa chọn vào danh sách nếu chưa có
        for lbl in self.selected_labels:
            if lbl not in avail_labels:
                avail_labels.append(lbl)

        if self.radio_new_task.isChecked():
            task_name = self.line_new_task_name.text().strip() or "Task Mới"
            task_data = {
                'id': None,
                'camera_id': self.camera_id,
                'model_id': self.model_id,
                'task_name': task_name,
                'task_type': 'RELATION_COORDINATE',
                'logic_mode': 'ALL_PASS',
                'action_on_fail': 'NG',
                'enabled': True,
                'assign_register': '',
                'value_bit_on': 1,
                'value_bit_off': 0,
            }
            rules_data = []
        else:
            selected_task_id = self.combo_tasks.currentData()
            if not selected_task_id:
                QtWidgets.QMessageBox.warning(self, "Chưa chọn Task", "Vui lòng chọn 1 Task từ danh sách!")
                return
            task_data = next((t for t in self.tasks if t['id'] == selected_task_id), None)
            rules_data = get_task_rules(self.cursor, selected_task_id)

        self.accept()

        # Mở TaskRuleEditorDialog với nhãn đã chọn
        editor = TaskRuleEditorDialog(
            camera_id=self.camera_id,
            model_id=self.model_id,
            task_data=task_data,
            rules_data=rules_data,
            available_labels=avail_labels,
            preselected_labels=self.selected_labels,
            cursor=self.cursor,
            connection=self.connection,
            parent=self.parent()
        )
        editor.exec_()
