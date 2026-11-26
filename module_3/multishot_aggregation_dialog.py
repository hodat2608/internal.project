"""
Module: multishot_aggregation_dialog.py
Mục đích: Giao diện cấu hình cho "Cross-Shot Multi-Image Defect Aggregation"
(Tổng hợp phế phẩm liên ảnh trong chu kỳ đa shot).
Phạm vi: TOÀN BỘ CHU KỲ / LIÊN TAB MODEL (Camera-Wide Scope).

Tính năng:
1. Cấu hình quy tắc liên shot:
   - Số lượng ảnh trong 1 chu kỳ (Cycle Shots, ví dụ 5 ảnh).
   - Ngưỡng số ảnh NG để chốt lỗi chu kỳ (ví dụ >= 2 ảnh mới NG, 1 ảnh vẫn OK).
   - Phán định theo tổ hợp shot chỉ định (ví dụ Shot 1 & Shot 2).
   - Phán định theo số shot liên tiếp (Consecutive).
   - Lọc theo Shot (Model tương ứng) tham gia kiểm tra (Participating Shots).
   - Tự động đồng bộ chu kỳ theo tín hiệu counter (current_count & shot_complete) từ hệ thống.
2. Đồng bộ hoàn toàn các biến thanh ghi PLC với Task Rule Calculator:
   - assign_register, value_state, value_bit_on (Value OK), value_bit_off (Value NG), action_on_fail.
"""

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from app_logger.app_logger import get_logger
from module_3.task_calculator_db import (
    save_multishot_task_and_rule,
    get_multishot_rule
)

_log = get_logger('module_3.multishot_aggregation_dialog')


class MultiShotAggregationDialog(QtWidgets.QDialog):
    """
    Dialog cấu hình độc lập cho 'Cross-Shot Multi-Image Defect Aggregation'.
    """

    def __init__(
        self,
        camera_id: int,
        model_id: int,
        task_data: dict,
        rule_data: dict = None,
        available_labels: list = None,
        cursor=None,
        connection=None,
        parent=None
    ):
        super().__init__(parent)
        self.camera_id = camera_id
        self.model_id = model_id
        self.task_data = task_data or {}
        self.rule_data = rule_data or {}
        self.available_labels = available_labels or []
        self.cursor = cursor
        self.connection = connection

        self.setWindowTitle("Cấu Hình Tổng Hợp Phế Phẩm Đa Shot (Cross-Shot Defect Aggregation)")
        self.resize(720, 680)
        self.setMinimumSize(680, 620)

        self._init_ui()
        self._load_data_to_form()

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        # Header Bar
        header_layout = QtWidgets.QHBoxLayout()
        header_title = QtWidgets.QLabel("🔄 CROSS-SHOT DEFECT AGGREGATION")
        header_title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        header_title.setStyleSheet("color: #1e293b;")
        header_layout.addWidget(header_title)

        header_layout.addStretch()

        badge_cam = QtWidgets.QLabel(f"Camera: {self.camera_id} | Phạm vi: Toàn Bộ Chu Kỳ (Liên Ảnh)")
        badge_cam.setToolTip("Task này chạy xuyên suốt mọi shot trong chu kỳ của Camera, liên kết tất cả các Tab Model tương ứng với từng shot.")
        badge_cam.setStyleSheet("""
            background-color: #ede9fe;
            color: #6d28d9;
            font-weight: bold;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
        """)
        header_layout.addWidget(badge_cam)
        main_layout.addLayout(header_layout)

        # Scroll Area for Form Content
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)

        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        group_style = """
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #0f172a;
            }
        """

        # Group 1: Thông tin cơ bản
        grp_info = QtWidgets.QGroupBox("📋 1. Định Danh Tác Vụ")
        grp_info.setStyleSheet(group_style)
        layout_info = QtWidgets.QFormLayout(grp_info)
        layout_info.setSpacing(8)

        self.txt_task_name = QtWidgets.QLineEdit()
        self.txt_task_name.setPlaceholderText("Ví dụ: Kiem_Tra_Loi_mh_klk_5_Shot")
        layout_info.addRow("Tên Task:", self.txt_task_name)

        self.combo_target_label = QtWidgets.QComboBox()
        self.combo_target_label.setEditable(True)
        for lbl in self.available_labels:
            self.combo_target_label.addItem(lbl)
        layout_info.addRow("Nhãn Phế Phẩm:", self.combo_target_label)

        self.chk_task_enabled = QtWidgets.QCheckBox("Kích hoạt hoạt động [✓]")
        self.chk_task_enabled.setChecked(True)
        layout_info.addRow("Trạng Thái:", self.chk_task_enabled)

        content_layout.addWidget(grp_info)

        # Group 2: Quy tắc chu kỳ liên ảnh
        grp_rule = QtWidgets.QGroupBox("⚙️ 2. Quy Tắc Chu Kỳ & Tổng Hợp Phế Phẩm")
        grp_rule.setStyleSheet(group_style)
        layout_rule = QtWidgets.QFormLayout(grp_rule)
        layout_rule.setSpacing(8)

        # Số shot trong chu kỳ
        self.spin_cycle_shots = QtWidgets.QSpinBox()
        self.spin_cycle_shots.setRange(1, 100)
        self.spin_cycle_shots.setValue(5)
        self.spin_cycle_shots.valueChanged.connect(self._on_cycle_shots_changed)
        layout_rule.addRow("Số ảnh trong 1 chu kỳ:", self.spin_cycle_shots)

        # Chế độ phán định
        self.combo_agg_mode = QtWidgets.QComboBox()
        self.combo_agg_mode.addItems([
            "Đạt ngưỡng số lần NG (≥ K ảnh NG)",
            "Chỉ định chính xác các Shot (Specific Shots)",
            "Lỗi liên tiếp (≥ K shot liền kề)"
        ])
        self.combo_agg_mode.currentIndexChanged.connect(self._on_agg_mode_changed)
        layout_rule.addRow("Chế độ đánh giá:", self.combo_agg_mode)

        # Sub-widget: Min NG Shots
        self.spin_min_ng_shots = QtWidgets.QSpinBox()
        self.spin_min_ng_shots.setRange(1, 5)
        self.spin_min_ng_shots.setValue(2)
        layout_rule.addRow("Ngưỡng số ảnh NG tối thiểu:", self.spin_min_ng_shots)

        # Sub-widget: Specific Shots input
        self.txt_specific_shots = QtWidgets.QLineEdit()
        self.txt_specific_shots.setPlaceholderText("Ví dụ: 1, 2 (Shot 1 VÀ Shot 2 đều NG)")
        layout_rule.addRow("Shot chỉ định:", self.txt_specific_shots)

        # Sub-widget: Participating Shots input
        self.txt_participating_shots = QtWidgets.QLineEdit()
        self.txt_participating_shots.setPlaceholderText("Trống = Mọi Shot (1..N) / Ví dụ: 1, 2")
        self.txt_participating_shots.setToolTip("Chỉ định các Shot (tương ứng với Model xử lý shot đó) tham gia kiểm tra. Để trống để kiểm tra tất cả các Model trong chu kỳ.")
        layout_rule.addRow("Áp dụng cho Shot (Model):", self.txt_participating_shots)

        # Hướng dẫn quy tắc trực quan
        self.lbl_rule_hint = QtWidgets.QLabel()
        self.lbl_rule_hint.setWordWrap(True)
        self.lbl_rule_hint.setStyleSheet("""
            background-color: #f8fafc;
            border-left: 3px solid #3b82f6;
            color: #334155;
            padding: 6px 10px;
            font-size: 11px;
            border-radius: 0 4px 4px 0;
        """)
        layout_rule.addRow(self.lbl_rule_hint)

        content_layout.addWidget(grp_rule)

        # Group 3: Cấu hình thanh ghi PLC (ĐỒNG BỘ 100% VỚI TASK RULE CALCULATOR)
        grp_plc = QtWidgets.QGroupBox("🔌 3. Tín Hiệu Thanh Ghi PLC (Giao Tiếp & Phán Định)")
        grp_plc.setStyleSheet(group_style)
        layout_plc = QtWidgets.QFormLayout(grp_plc)
        layout_plc.setSpacing(8)

        self.txt_plc_register = QtWidgets.QLineEdit()
        self.txt_plc_register.setPlaceholderText("Ví dụ: D100, M10, R200... (Để trống nếu không gửi)")
        layout_plc.addRow("Thanh ghi PLC (Register):", self.txt_plc_register)

        self.spin_plc_state = QtWidgets.QSpinBox()
        self.spin_plc_state.setRange(-32768, 65535)
        self.spin_plc_state.setValue(1)
        layout_plc.addRow("Value State:", self.spin_plc_state)

        plc_val_layout = QtWidgets.QHBoxLayout()
        self.spin_plc_ok = QtWidgets.QSpinBox()
        self.spin_plc_ok.setRange(-32768, 65535)
        self.spin_plc_ok.setValue(1)
        plc_val_layout.addWidget(QtWidgets.QLabel("Value OK:"))
        plc_val_layout.addWidget(self.spin_plc_ok)

        self.spin_plc_ng = QtWidgets.QSpinBox()
        self.spin_plc_ng.setRange(-32768, 65535)
        self.spin_plc_ng.setValue(0)
        plc_val_layout.addWidget(QtWidgets.QLabel("Value NG:"))
        plc_val_layout.addWidget(self.spin_plc_ng)
        layout_plc.addRow("Giá trị gửi PLC:", plc_val_layout)

        self.combo_action_fail = QtWidgets.QComboBox()
        self.combo_action_fail.addItems(["NG", "WARNING", "IGNORE"])
        layout_plc.addRow("Khi vi phạm chu kỳ:", self.combo_action_fail)

        self.txt_description = QtWidgets.QLineEdit()
        self.txt_description.setPlaceholderText("Ghi chú nghiệp vụ...")
        layout_plc.addRow("Ghi chú / Mô tả:", self.txt_description)

        content_layout.addWidget(grp_plc)
        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        # Bottom Buttons
        bottom_layout = QtWidgets.QHBoxLayout()
        lbl_guide = QtWidgets.QLabel("💡 Lưu ý: Hệ thống sẽ tự động cập nhật vào bộ nhớ RAM chạy tức thì mà không cần khởi động lại.")
        lbl_guide.setStyleSheet("color: #64748b; font-size: 11px;")
        bottom_layout.addWidget(lbl_guide)

        bottom_layout.addStretch()

        self.btn_cancel = QtWidgets.QPushButton("Hủy Bỏ")
        self.btn_cancel.setFixedSize(110, 36)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #e2e8f0; color: #0f172a; }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        bottom_layout.addWidget(self.btn_cancel)

        self.btn_save = QtWidgets.QPushButton("💾 Lưu Cấu Hình")
        self.btn_save.setFixedSize(140, 36)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #6d28d9; }
        """)
        self.btn_save.clicked.connect(self._on_save_config)
        bottom_layout.addWidget(self.btn_save)

        main_layout.addLayout(bottom_layout)

        self._on_agg_mode_changed(0)

    def _load_data_to_form(self):
        """Đổ dữ liệu từ task_data và rule_data lên các trường giao diện."""
        # Task basic info
        tname = self.task_data.get('task_name') or 'MultiShot Task'
        self.txt_task_name.setText(tname)
        self.chk_task_enabled.setChecked(bool(self.task_data.get('enabled', True)))

        # PLC parameters
        self.txt_plc_register.setText(str(self.task_data.get('assign_register') or ''))
        v_state = self.task_data.get('value_state', self.task_data.get('Value_State', 1))
        self.spin_plc_state.setValue(int(v_state if v_state is not None else 1))

        v_ok = self.task_data.get('value_bit_on', self.task_data.get('value_ok', self.task_data.get('Value_OK', 1)))
        self.spin_plc_ok.setValue(int(v_ok if v_ok is not None else 1))

        v_ng = self.task_data.get('value_bit_off', self.task_data.get('value_ng', self.task_data.get('Value_NG', 0)))
        self.spin_plc_ng.setValue(int(v_ng if v_ng is not None else 0))

        act_fail = self.task_data.get('action_on_fail', 'NG')
        idx_act = self.combo_action_fail.findText(act_fail)
        if idx_act >= 0:
            self.combo_action_fail.setCurrentIndex(idx_act)

        # Rule parameters
        target_lbl = self.rule_data.get('target_label') or ''
        if target_lbl:
            idx = self.combo_target_label.findText(target_lbl)
            if idx >= 0:
                self.combo_target_label.setCurrentIndex(idx)
            else:
                self.combo_target_label.setEditText(target_lbl)

        cycle_shots = int(self.rule_data.get('cycle_shots', 5))
        self.spin_cycle_shots.setValue(cycle_shots)

        agg_mode = self.rule_data.get('aggregation_mode', 'THRESHOLD_COUNT')
        if agg_mode == 'SPECIFIC_SHOTS':
            self.combo_agg_mode.setCurrentIndex(1)
        elif agg_mode == 'CONSECUTIVE':
            self.combo_agg_mode.setCurrentIndex(2)
        else:
            self.combo_agg_mode.setCurrentIndex(0)

        min_ng = int(self.rule_data.get('min_ng_shots', 2))
        self.spin_min_ng_shots.setValue(min_ng)
        self.txt_specific_shots.setText(str(self.rule_data.get('specific_shots', '') or ''))
        self.txt_participating_shots.setText(str(self.rule_data.get('participating_shots', '') or ''))
        self.txt_description.setText(str(self.rule_data.get('description', '') or ''))

    def _on_cycle_shots_changed(self, val: int):
        self.spin_min_ng_shots.setMaximum(val)
        self._update_rule_hint()

    def _on_agg_mode_changed(self, index: int):
        if index == 0:  # THRESHOLD_COUNT
            self.spin_min_ng_shots.setEnabled(True)
            self.txt_specific_shots.setEnabled(False)
        elif index == 1:  # SPECIFIC_SHOTS
            self.spin_min_ng_shots.setEnabled(False)
            self.txt_specific_shots.setEnabled(True)
        else:  # CONSECUTIVE
            self.spin_min_ng_shots.setEnabled(True)
            self.txt_specific_shots.setEnabled(False)
        self._update_rule_hint()

    def _update_rule_hint(self):
        idx = self.combo_agg_mode.currentIndex()
        cycle = self.spin_cycle_shots.value()
        lbl = self.combo_target_label.currentText().strip() or "nhãn"

        if idx == 0:
            k = self.spin_min_ng_shots.value()
            self.lbl_rule_hint.setText(
                f"👉 <b>Quy tắc Ngưỡng:</b> Trong chu kỳ <b>{cycle} ảnh</b>, chỉ khi <b>{lbl}</b> "
                f"xuất hiện trong <b>≥ {k} ảnh</b> thì sản phẩm mới bị phán định <b>NG</b>.<br>"
                f"Nếu chỉ xuất hiện &lt; {k} ảnh (ví dụ 1 ảnh nhiễu) thì hệ thống <b>vẫn đánh giá OK</b>."
            )
        elif idx == 1:
            shots_str = self.txt_specific_shots.text().strip() or "1, 2"
            self.lbl_rule_hint.setText(
                f"👉 <b>Quy tắc Chỉ Định:</b> Sản phẩm chỉ bị phán định <b>NG</b> khi đồng thời các shot "
                f"<b>[{shots_str}]</b> đều xuất hiện lỗi <b>{lbl}</b>. Các tổ hợp khác coi như OK."
            )
        else:
            k = self.spin_min_ng_shots.value()
            self.lbl_rule_hint.setText(
                f"👉 <b>Quy tắc Liền Kề:</b> Sản phẩm chỉ bị phán định <b>NG</b> khi xuất hiện lỗi <b>{lbl}</b> "
                f"trong <b>≥ {k} shot liên tiếp nhau</b> trong chu kỳ {cycle} ảnh."
            )

    def _on_save_config(self):
        task_name = self.txt_task_name.text().strip()
        if not task_name:
            QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập Tên Task!")
            self.txt_task_name.setFocus()
            return

        target_label = self.combo_target_label.currentText().strip()
        if not target_label:
            QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn hoặc nhập Nhãn Phế Phẩm!")
            self.combo_target_label.setFocus()
            return

        # Prepare Task Data (Phạm vi toàn Camera / Chu kỳ liên Model)
        task_data = {
            'id': self.task_data.get('id'),
            'camera_id': self.camera_id,
            'model_id': 0,
            'task_name': task_name,
            'task_type': 'MULTI_SHOT_AGGREGATION',
            'logic_mode': 'ALL_PASS',
            'action_on_fail': self.combo_action_fail.currentText(),
            'enabled': self.chk_task_enabled.isChecked(),
            'assign_register': self.txt_plc_register.text().strip(),
            'value_state': self.spin_plc_state.value(),
            'value_bit_on': self.spin_plc_ok.value(),
            'value_ok': self.spin_plc_ok.value(),
            'value_bit_off': self.spin_plc_ng.value(),
            'value_ng': self.spin_plc_ng.value(),
        }

        # Prepare Aggregation Mode
        idx_agg = self.combo_agg_mode.currentIndex()
        if idx_agg == 1:
            agg_mode = 'SPECIFIC_SHOTS'
        elif idx_agg == 2:
            agg_mode = 'CONSECUTIVE'
        else:
            agg_mode = 'THRESHOLD_COUNT'

        rule_data = {
            'target_label': target_label,
            'cycle_shots': self.spin_cycle_shots.value(),
            'aggregation_mode': agg_mode,
            'min_ng_shots': self.spin_min_ng_shots.value(),
            'specific_shots': self.txt_specific_shots.text().strip(),
            'participating_shots': self.txt_participating_shots.text().strip(),
            'roi_enabled': 0,
            'roi_mode': 'IN_BOUNDS',
            'roi_boxes': '',
            'timeout_reset_sec': 0.0,
            'description': self.txt_description.text().strip()
        }

        saved_id = save_multishot_task_and_rule(self.cursor, self.connection, task_data, rule_data)
        if not saved_id:
            QtWidgets.QMessageBox.critical(self, "Lỗi Database", "Không thể lưu cấu hình Task vào cơ sở dữ liệu!")
            return

        task_data['id'] = saved_id

        # Đồng bộ trực tiếp vào bộ nhớ RAM Process_Model.dict_active_tasks CHO TẤT CẢ CÁC MODEL CỦA CAMERA NÀY
        try:
            from module_3.handle_option_models import Process_Model
            cam_str = str(self.camera_id).lower().replace("camera-", "").replace("built-in-", "").strip()

            if hasattr(Process_Model, 'dict_active_tasks') and isinstance(Process_Model.dict_active_tasks, dict):
                for km, tlist in Process_Model.dict_active_tasks.items():
                    c_k = str(km[0] if isinstance(km, (tuple, list)) else km).lower().replace("camera-", "").replace("built-in-", "").strip()
                    if c_k == cam_str and isinstance(tlist, list):
                        found = False
                        for mem_task in tlist:
                            if mem_task.get('id') == saved_id:
                                mem_task.update(task_data)
                                mem_task['multishot_rule'] = rule_data
                                found = True
                                break
                        if not found:
                            new_t = dict(task_data)
                            new_t['id'] = saved_id
                            new_t['multishot_rule'] = rule_data
                            tlist.append(new_t)
        except Exception as e:
            _log.warning("Lỗi đồng bộ bộ nhớ RAM Process_Model: %s", e)

        QtWidgets.QMessageBox.information(
            self, "Thành Công",
            f"Đã lưu thành công Task '{task_name}' (ID: {saved_id})!\nCấu hình đã được áp dụng tức thì vào hệ thống."
        )
        self.accept()
