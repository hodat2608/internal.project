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
    get_multishot_rule,
    get_roi_rule,
    save_roi_task_and_rule,
    save_multishot_task_and_rule,
    delete_task,
    toggle_task_enabled,
    get_available_labels_for_camera,
    save_task_and_rules,
    get_cycle_shots_from_shotxmodel
)
from module_3.task_rule_editor_dialog import TaskRuleEditorDialog
from module_3.task_type_selector_dialog import TaskTypeSelectorDialog
from module_3.multishot_aggregation_dialog import MultiShotAggregationDialog
from module_3.roi_zone_dialog import RoiZoneEditorDialog
from module_2.StyleSheet import *
_log = get_logger('module_3.task_workspace_dialog')


class TaskWorkspaceDialog(QtWidgets.QDialog):
    def __init__(self, camera_id: int, camera_name: str = "", item_code: str = "",
                 cursor=None, connection=None, parent=None,
                 model_id: Optional[int] = None, **kwargs):
        super().__init__(parent)
        self.camera_id = camera_id
        self.model_id = model_id if model_id is not None else kwargs.get('model_id', None)
        if self.camera_id is not None:
            c_str = str(self.camera_id).lower().replace('camera-', '').replace('built-in-', '').strip()
            if c_str.isdigit():
                self.camera_id = int(c_str)
        if self.model_id is not None:
            m_str = str(self.model_id).lower().replace('model-', '').replace('model', '').strip()
            if m_str.isdigit():
                self.model_id = int(m_str)
        self.camera_name = camera_name or f"Camera-{camera_id}"
        self.item_code = item_code or "N/A"
        from module_3.config_version_manager import get_raw_mysql_connection, get_safe_cursor
        self.connection = get_raw_mysql_connection(connection) or connection
        self.cursor = get_safe_cursor(cursor, self.connection) or cursor
        self.tasks: List[Dict[str, Any]] = []

        self.setWindowTitle(f"Quản Lý Workspace Task - {self.camera_name} [Mã Hàng: {self.item_code}]")
        self.resize(1000, 600)
        self.setStyleSheet(TaskWorkspaceDialog_style)

        self.init_ui()
        self.load_tasks()

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Header Info Banner
        header_frame = QtWidgets.QFrame()
        header_frame.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px;")
        header_layout = QtWidgets.QHBoxLayout(header_frame)
        
        lbl_title = QtWidgets.QLabel(f"📷 <b>Camera:</b> <font color='#1d4ed8'><b>{self.camera_name}</b></font> (ID: {self.camera_id}) &nbsp;|&nbsp; 🧩 <b>Model:</b> <font color='#c2410c'><b>{self.model_id}</b></font> &nbsp;|&nbsp; 🏷️ <b>Mã Hàng:</b> <font color='#15803d'><b>{self.item_code}</b></font>")
        lbl_title.setFont(QFont("Segoe UI", 12))
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()

        self.lbl_task_stats = QtWidgets.QLabel("Tổng số: 0 tasks")
        self.lbl_task_stats.setStyleSheet("color: #475569; font-size: 13px; font-weight: 500;")
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

        self.btn_history = QtWidgets.QPushButton("🕒 Lịch Sử Cấu Hình")
        self.btn_history.setStyleSheet(btn_history_setStyleSheet)
        self.btn_history.clicked.connect(self.open_config_history)
        toolbar_layout.addWidget(self.btn_history)

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
        lbl_hint.setStyleSheet("color: #64748b; font-size: 12px;")
        bottom_layout.addWidget(lbl_hint)

        bottom_layout.addStretch()

        self.btn_close = QtWidgets.QPushButton("Đóng")
        self.btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(self.btn_close)

        main_layout.addLayout(bottom_layout)

    def load_tasks(self):
        """Tải danh sách các task từ Database và đổ lên bảng."""
        ensure_task_calculator_tables(self.cursor, self.connection)
        self.tasks = get_tasks_by_camera(self.cursor, self.camera_id, self.model_id)
        
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
            t_type = t.get('task_type', 'RELATION_COORDINATE')
            if t_type == 'MULTI_SHOT_AGGREGATION':
                type_display = "🔄 Multi-Shot (Liên Model)"
            elif t_type == 'ROI_ZONE_INSPECTION':
                type_display = f"🖼️ ROI Zone (Model {t.get('model_id', self.model_id)})"
            else:
                type_display = "📐 Rule Calculator"
            item_type = QtWidgets.QTableWidgetItem(type_display)
            item_type.setTextAlignment(Qt.AlignCenter)
            if t_type == 'MULTI_SHOT_AGGREGATION':
                item_type.setForeground(QColor("#7c3aed"))
            elif t_type == 'ROI_ZONE_INSPECTION':
                item_type.setForeground(QColor("#0284c7"))
            self.table_tasks.setItem(row_idx, 2, item_type)

            # Cột 3: Số Rules / Tóm tắt quy tắc
            if t_type == 'MULTI_SHOT_AGGREGATION':
                rule = t.get('multishot_rule') or {}
                lbl = rule.get('target_label', '')
                cycle_shots_db = get_cycle_shots_from_shotxmodel(self.cursor, self.camera_id) if self.cursor else 0
                shots = cycle_shots_db if cycle_shots_db > 0 else int(rule.get('cycle_shots', 5) or 5)
                min_ng = rule.get('min_ng_shots', 2)
                mode = rule.get('aggregation_mode', 'THRESHOLD_COUNT')
                p_shots = rule.get('participating_shots', '')
                if mode == 'THRESHOLD_COUNT':
                    r_desc = f"Chu kỳ {shots} (≥ {min_ng} NG)"
                elif mode == 'SPECIFIC_SHOTS':
                    r_desc = f"Chu kỳ {shots} (Shot: {rule.get('specific_shots', '')})"
                else:
                    r_desc = f"Chu kỳ {shots} (≥ {min_ng} liên tiếp)"
                if p_shots:
                    r_desc += f" [Shot {p_shots}]"
                if lbl:
                    r_desc = f"[{lbl}] {r_desc}"
                item_rules = QtWidgets.QTableWidgetItem(r_desc)
            elif t_type == 'ROI_ZONE_INSPECTION':
                r_roi = t.get('roi_rule') or {}
                zones = r_roi.get('zones', [])
                n_ins = sum(1 for z in zones if str(z.get('zone_type', '')).upper() == 'INSPECTION')
                n_mask = sum(1 for z in zones if str(z.get('zone_type', '')).upper() == 'EXCLUSION')
                n_pres = sum(1 for z in zones if str(z.get('zone_type', '')).upper() == 'PRESENCE')
                parts = []
                if n_ins > 0:
                    parts.append(f"{n_ins} Inspect")
                if n_mask > 0:
                    parts.append(f"{n_mask} Mask")
                if n_pres > 0:
                    parts.append(f"{n_pres} Presence")
                z_desc = f"{len(zones)} vùng"
                if parts:
                    z_desc += f" [{', '.join(parts)}]"
                item_rules = QtWidgets.QTableWidgetItem(z_desc)
            else:
                item_rules = QtWidgets.QTableWidgetItem(f"{t['rule_count']} rules")
            item_rules.setTextAlignment(Qt.AlignCenter)
            self.table_tasks.setItem(row_idx, 3, item_rules)

            # Cột 4: PLC Register
            v_st = t.get('value_state', 1)
            v_on = t.get('value_bit_on', 1)
            reg_text = f"{t['assign_register']} (st={v_st}, on={v_on})" if t['assign_register'] else "--"
            item_reg = QtWidgets.QTableWidgetItem(reg_text)
            item_reg.setTextAlignment(Qt.AlignCenter)
            if t['assign_register']:
                item_reg.setForeground(QColor("#2563eb"))
            self.table_tasks.setItem(row_idx, 4, item_reg)

            # Cột 5: Khi vi phạm (NG)
            item_fail = QtWidgets.QTableWidgetItem("Đánh giá NG")
            item_fail.setTextAlignment(Qt.AlignCenter)
            item_fail.setForeground(QColor("#dc2626"))
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

            btn_row_edit.setStyleSheet(btn_row_edit_setStyleSheet)

            btn_row_del = QtWidgets.QPushButton("🗑️")
            btn_row_del.setToolTip("Xóa Task")
            btn_row_del.setFixedSize(30, 26)
            btn_row_del.setStyleSheet(btn_row_del_setStyleSheet)
            btn_row_del.clicked.connect(lambda _, tid=t['id'], tname=t['task_name']: self.delete_task_by_id(tid, tname))
            action_layout.addWidget(btn_row_del)

            self.table_tasks.setCellWidget(row_idx, 7, action_widget)

        self.lbl_task_stats.setText(f"Tổng số: <b>{len(self.tasks)}</b> tasks | Đang kích hoạt: <font color='#16a34a'><b>{active_count}</b></font>")

    def on_toggle_task(self, task_id: int, enabled: bool):
        toggle_task_enabled(self.cursor, self.connection, task_id, enabled)
        # Cập nhật lại số liệu thống kê
        for t in self.tasks:
            if t['id'] == task_id:
                t['enabled'] = enabled
                break
        active_count = sum(1 for t in self.tasks if t['enabled'])
        self.lbl_task_stats.setText(f"Tổng số: <b>{len(self.tasks)}</b> tasks | Đang kích hoạt: <font color='#16a34a'><b>{active_count}</b></font>")

        # Đồng bộ ngay lập tức cờ enabled vào bộ nhớ RAM Process_Model.dict_active_tasks cho TOÀN BỘ các tab Model của camera này
        try:
            from module_3.handle_option_models import Process_Model
            cam_str = str(self.camera_name) if getattr(self, 'camera_name', None) else ""
            if not cam_str and getattr(self, 'camera_id', None):
                cam_str = str(self.camera_id)
            cam_num = cam_str.lower().replace("camera-", "").replace("built-in-", "").strip()

            if hasattr(Process_Model, 'dict_active_tasks') and isinstance(Process_Model.dict_active_tasks, dict):
                for km, tlist in Process_Model.dict_active_tasks.items():
                    c_k = str(km[0] if isinstance(km, (tuple, list)) else km).lower().replace("camera-", "").replace("built-in-", "").strip()
                    if c_k == cam_num and isinstance(tlist, list):
                        for mem_task in tlist:
                            if mem_task.get('id') == task_id:
                                mem_task['enabled'] = enabled
        except Exception:
            pass

    def add_task(self, preselected_labels: Optional[List[str]] = None):
        """Mở modal lựa chọn loại task, sau đó mở dialog tương ứng."""
        selector = TaskTypeSelectorDialog(parent=self)
        if selector.exec_() != QtWidgets.QDialog.Accepted:
            return

        selected_type = selector.selected_type

        if selected_type == 'MULTI_SHOT_AGGREGATION':
            # Option 3: Cross-Shot Multi-Image Defect Aggregation Dialog
            # Lấy danh sách nhãn trên TOÀN BỘ các Model của Camera này (Liên Model)
            avail_labels = get_available_labels_for_camera(self.cursor, self.camera_id, model_id=None)
            default_label = preselected_labels[0] if (preselected_labels and len(preselected_labels) > 0) else (avail_labels[0] if avail_labels else '')
            task_data = {
                'id': None,
                'camera_id': self.camera_id,
                'model_id': 0,  # Camera-Wide Scope (Toàn bộ chu kỳ)
                'task_name': f"MultiShot_{default_label or 'Defect'}",
                'task_type': 'MULTI_SHOT_AGGREGATION',
                'logic_mode': 'ALL_PASS',
                'action_on_fail': 'NG',
                'enabled': True,
                'assign_register': '',
                'value_state': 1,
                'Value_State': 1,
                'value_bit_on': 1,
                'value_ok': 1,
                'Value_OK': 1,
                'value_bit_off': 0,
                'value_ng': 0,
                'Value_NG': 0,
            }
            cycle_shots_db = get_cycle_shots_from_shotxmodel(self.cursor, self.camera_id)
            rule_data = {
                'target_label': default_label,
                'cycle_shots': cycle_shots_db,
                'aggregation_mode': 'THRESHOLD_COUNT',
                'min_ng_shots': min(2, cycle_shots_db),
                'specific_shots': '',
                'participating_shots': '',
                'roi_enabled': 0,
                'roi_mode': 'IN_BOUNDS',
                'roi_boxes': '',
                'timeout_reset_sec': 0.0,
                'description': ''
            }
            dlg = MultiShotAggregationDialog(
                camera_id=self.camera_id,
                model_id=0,
                task_data=task_data,
                rule_data=rule_data,
                available_labels=avail_labels,
                cursor=self.cursor,
                connection=self.connection,
                parent=self
            )
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                self.load_tasks()
        elif selected_type == 'ROI_ZONE_INSPECTION':
            # Option 2: ROI Zone Inspector Dialog (Đơn Model Scope - Góc chụp riêng)
            avail_labels = get_available_labels_for_camera(self.cursor, self.camera_id, self.model_id)
            task_data = {
                'id': None,
                'camera_id': self.camera_id,
                'model_id': self.model_id,
                'task_name': f"ROI_Zone_Model_{self.model_id}",
                'task_type': 'ROI_ZONE_INSPECTION',
                'logic_mode': 'ALL_PASS',
                'action_on_fail': 'NG',
                'enabled': True,
                'assign_register': '',
                'value_state': 1,
                'Value_State': 1,
                'value_bit_on': 1,
                'value_ok': 1,
                'Value_OK': 1,
                'value_bit_off': 0,
                'value_ng': 0,
                'Value_NG': 0,
            }
            rule_data = {
                'zones': [],
                'default_target': '',
                'action_mode': 'DEFECT_FILTER',
                'description': ''
            }
            dlg = RoiZoneEditorDialog(
                camera_id=self.camera_id,
                model_id=self.model_id,
                task_data=task_data,
                rule_data=rule_data,
                available_labels=avail_labels,
                cursor=self.cursor,
                connection=self.connection,
                parent=self
            )
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                self.load_tasks()
        else:
            # Option 1: Task Rule Calculator Dialog
            avail_labels = get_available_labels_for_camera(self.cursor, self.camera_id, self.model_id)
            task_data = {
                'id': None,
                'camera_id': self.camera_id,
                'model_id': self.model_id,
                'task_name': 'Task Mới',
                'task_type': 'RELATION_COORDINATE',
                'logic_mode': 'ALL_PASS',
                'action_on_fail': 'NG',
                'enabled': True,
                'assign_register': '',
                'value_state': 1,
                'Value_State': 1,
                'value_bit_on': 1,
                'value_ok': 1,
                'Value_OK': 1,
                'value_bit_off': 0,
                'value_ng': 0,
                'Value_NG': 0,
            }
            dlg = TaskRuleEditorDialog(
                camera_id=self.camera_id,
                model_id=self.model_id,
                task_data=task_data,
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

        target_model_id = task_info.get('model_id') or self.model_id
        t_type = task_info.get('task_type')

        if t_type == 'MULTI_SHOT_AGGREGATION':
            # Multi-Shot: Nhãn được lấy trên TOÀN BỘ các Model của Camera này
            avail_labels = get_available_labels_for_camera(self.cursor, self.camera_id, model_id=None)
            rule = task_info.get('multishot_rule')
            if not rule:
                rule = get_multishot_rule(self.cursor, task_id)
            if not rule:
                rule = {}
            cycle_shots_db = get_cycle_shots_from_shotxmodel(self.cursor, self.camera_id)
            if cycle_shots_db > 0:
                rule['cycle_shots'] = cycle_shots_db
            dlg = MultiShotAggregationDialog(
                camera_id=self.camera_id,
                model_id=target_model_id,
                task_data=task_info,
                rule_data=rule,
                available_labels=avail_labels,
                cursor=self.cursor,
                connection=self.connection,
                parent=self
            )
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                self.load_tasks()
        elif t_type == 'ROI_ZONE_INSPECTION':
            # ROI Zone Inspector: Nhãn được lấy riêng cho Model này
            avail_labels = get_available_labels_for_camera(self.cursor, self.camera_id, target_model_id)
            rule = task_info.get('roi_rule')
            if not rule:
                rule = get_roi_rule(self.cursor, task_id)
            dlg = RoiZoneEditorDialog(
                camera_id=self.camera_id,
                model_id=target_model_id,
                task_data=task_info,
                rule_data=rule,
                available_labels=avail_labels,
                cursor=self.cursor,
                connection=self.connection,
                parent=self
            )
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                self.load_tasks()
        else:
            avail_labels = get_available_labels_for_camera(self.cursor, self.camera_id, target_model_id)
            rules = get_task_rules(self.cursor, task_id)
            dlg = TaskRuleEditorDialog(
                camera_id=self.camera_id,
                model_id=target_model_id,
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
            t_type = original.get('task_type', 'RELATION_COORDINATE')

            clone_data = dict(original)
            clone_data['id'] = None
            clone_data['model_id'] = self.model_id
            clone_data['task_name'] = f"{original['task_name']} (Bản sao)"

            if t_type == 'ROI_ZONE_INSPECTION':
                rule = original.get('roi_rule') or get_roi_rule(self.cursor, task_id) or {}
                saved_id = save_roi_task_and_rule(self.cursor, self.connection, clone_data, rule)
            elif t_type == 'MULTI_SHOT_AGGREGATION':
                rule = original.get('multishot_rule') or get_multishot_rule(self.cursor, task_id) or {}
                saved_id = save_multishot_task_and_rule(self.cursor, self.connection, clone_data, rule)
            else:
                rules = get_task_rules(self.cursor, task_id)
                saved_id = save_task_and_rules(self.cursor, self.connection, clone_data, rules)

            if saved_id:
                QtWidgets.QMessageBox.information(self, "Nhân Bản Thành Công", f"Đã nhân bản Task mới: '{clone_data['task_name']}' (ID: {saved_id})")
                self.load_tasks()

    def delete_selected_task(self):
        row = self.table_tasks.currentRow()
        if 0 <= row < len(self.tasks):
            t = self.tasks[row]
            self.delete_task_by_id(t['id'], t['task_name'])

    def open_config_history(self):
        """Mở giao diện Audit Trail & Diff Viewer cho Task Calculator."""
        from module_3.config_history_dialog import ConfigHistoryDialog
        dlg = ConfigHistoryDialog(
            cursor=self.cursor,
            connection=self.connection,
            current_user="Admin",
            current_role="full_control",
            initial_category='TASK_RULES',
            initial_camera_id=str(self.camera_id),
            initial_model_id=self.model_id,
            parent=self
        )
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.load_tasks()

    def delete_task_by_id(self, task_id: int, task_name: str):
        reply = QtWidgets.QMessageBox.question(
            self,
            "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa Task: '{task_name}' (ID: {task_id}) không?\nTất cả quy tắc liên quan sẽ bị xóa vĩnh viễn.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            from module_3.change_reason_dialog import ChangeReasonDialog
            from module_3.config_version_manager import save_snapshot

            reason_dlg = ChangeReasonDialog(
                current_user="Admin",
                current_role="full_control",
                context_info=f"Xóa Task '{task_name}' (ID: {task_id})",
                parent=self
            )
            if reason_dlg.exec_() != QtWidgets.QDialog.Accepted:
                return

            change_reason, is_golden = reason_dlg.get_reason_and_golden()

            if delete_task(self.cursor, self.connection, task_id):
                try:
                    from module_3.handle_option_models import Process_Model
                    from module_3.multishot_aggregation_engine import reset_multishot_cycle
                    cam_str = str(self.camera_name) if getattr(self, 'camera_name', None) else ""
                    if not cam_str and getattr(self, 'camera_id', None):
                        cam_str = str(self.camera_id)
                    cam_num = cam_str.lower().replace("camera-", "").replace("built-in-", "").strip()

                    reset_multishot_cycle(key_model=f"camera-{cam_num}", task_id=task_id)

                    if hasattr(Process_Model, 'dict_active_tasks') and isinstance(Process_Model.dict_active_tasks, dict):
                        for km, tlist in Process_Model.dict_active_tasks.items():
                            c_k = str(km[0] if isinstance(km, (tuple, list)) else km).lower().replace("camera-", "").replace("built-in-", "").strip()
                            if c_k == cam_num and isinstance(tlist, list):
                                Process_Model.dict_active_tasks[km] = [m for m in tlist if m.get('id') != task_id]
                except Exception:
                    pass

                try:
                    save_snapshot(
                        cursor=self.cursor,
                        connection=self.connection,
                        scope_category='TASK_RULES',
                        change_reason=f"Xóa Task '{task_name}': {change_reason}",
                        changed_by="Admin",
                        camera_id=str(self.camera_id),
                        model_id=self.model_id or 1,
                        user_role="full_control",
                        is_golden=is_golden
                    )
                except Exception as e_snap:
                    pass
                QtWidgets.QMessageBox.information(self, "Thành công", f"Đã xóa thành công Task '{task_name}'!")
                self.load_tasks()
            else:
                QtWidgets.QMessageBox.critical(self, "Lỗi", "Không thể xóa Task. Vui lòng kiểm tra lại kết nối Database!")
