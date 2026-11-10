import os
import sys

TARGET_FILE = r"c:\project_vision\intenal\module_3\task_rule_editor_dialog.py"

with open(TARGET_FILE, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update PARAM_DISPLAY_NAMES and OPERATOR_DISPLAY_NAMES
old_params = """PARAM_DISPLAY_NAMES = {
    'FULL_BOX': 'Toàn bộ Box (Bounding Box)',
    'X_MIN': 'Left (X min)',
    'X_MAX': 'Right (X max)',
    'Y_MIN': 'Top (Y min)',
    'Y_MAX': 'Bottom (Y max)',
    'CENTER_X': 'Center X',
    'CENTER_Y': 'Center Y',
    'WIDTH': 'Width (Chiều rộng)',
    'HEIGHT': 'Height (Chiều cao)'
}

OPERATOR_DISPLAY_NAMES = {
    '<': '< (Nhỏ hơn)',
    '<=': '<= (Nhỏ hơn hoặc bằng)',
    '>': '> (Lớn hơn)',
    '>=': '>= (Lớn hơn hoặc bằng)',
    '==': '== (Bằng nhau)',
    '!=': '!= (Khác nhau)',
    'BETWEEN': 'Trong khoảng (Min <= X <= Max)',
    'INSIDE': 'Nằm trong (INSIDE: Toàn bộ A nằm trong B)',
    'OUTSIDE': 'Nằm ngoài (OUTSIDE: A hoàn toàn ngoài B)',
    'OVERLAP': 'Giao nhau / Chạm (OVERLAP: A chạm mép hoặc cắt B)',
    'DIST_<': 'Khoảng cách < (Khoảng cách giữa 2 cạnh < Ngưỡng)',
    'DIST_<=': 'Khoảng cách <= (Khoảng cách giữa 2 cạnh <= Ngưỡng)',
    'DIST_>': 'Khoảng cách > (Khoảng cách giữa 2 cạnh > Ngưỡng)',
    'DIST_>=': 'Khoảng cách >= (Khoảng cách giữa 2 cạnh >= Ngưỡng)',
    'DIST_==': 'Khoảng cách == (Khoảng cách giữa 2 cạnh == Ngưỡng)',
    'DIST_!=': 'Khoảng cách != (Khoảng cách giữa 2 cạnh != Ngưỡng)'
}"""

new_params = """PARAM_DISPLAY_NAMES = {
    'FULL_BOX': 'Toàn bộ Box',
    'X_MIN': 'Left (X min)',
    'X_MAX': 'Right (X max)',
    'Y_MIN': 'Top (Y min)',
    'Y_MAX': 'Bottom (Y max)',
    'CENTER_X': 'Center X',
    'CENTER_Y': 'Center Y',
    'WIDTH': 'Width (Rộng)',
    'HEIGHT': 'Height (Cao)'
}

OPERATOR_DISPLAY_NAMES = {
    '<': '< (Nhỏ hơn)',
    '<=': '<= (Nhỏ hơn =)',
    '>': '> (Lớn hơn)',
    '>=': '>= (Lớn hơn =)',
    '==': '== (Bằng nhau)',
    '!=': '!= (Khác nhau)',
    'BETWEEN': 'Trong khoảng',
    'INSIDE': 'Trong vùng (INSIDE)',
    'OUTSIDE': 'Ngoài vùng (OUTSIDE)',
    'OVERLAP': 'Giao cắt (OVERLAP)',
    'DIST_<': 'Khoảng cách <',
    'DIST_<=': 'Khoảng cách <=',
    'DIST_>': 'Khoảng cách >',
    'DIST_>=': 'Khoảng cách >=',
    'DIST_==': 'Khoảng cách ==',
    'DIST_!=': 'Khoảng cách !='
}"""

if old_params in text:
    text = text.replace(old_params, new_params)
    print("PARAM_DISPLAY_NAMES & OPERATOR_DISPLAY_NAMES updated.")
else:
    print("Warning: old_params block not matched directly, checking normalized...")
    # Normalize CRLF/LF if needed
    text_lf = text.replace("\r\n", "\n")
    old_params_lf = old_params.replace("\r\n", "\n")
    if old_params_lf in text_lf:
        text = text_lf.replace(old_params_lf, new_params.replace("\r\n", "\n"))
        print("PARAM_DISPLAY_NAMES & OPERATOR_DISPLAY_NAMES updated via LF normalization.")
    else:
        print("ERROR: old_params could not be found!")
        sys.exit(1)

# 2. Insert FlowLayout class before TaskRuleEditorDialog
flow_layout_code = '''class FlowLayout(QtWidgets.QLayout):
    """
    Layout tự động xếp các nhóm đối tượng trên cùng 1 hàng theo kích thước tự nhiên.
    Khi bề ngang không đủ chỗ hoặc cửa sổ thu nhỏ, các nhóm đối tượng tự động xuống dòng
    một cách mượt mà, chuyên nghiệp mà không bị kéo giãn quá cỡ.
    """
    def __init__(self, parent=None, margin=0, spacing=8):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QtCore.QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        effective_rect = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0
        spacing = self.spacing()

        for item in self.itemList:
            wid = item.widget()
            space_x = spacing
            space_y = spacing
            item_w = item.sizeHint().width()
            item_h = item.sizeHint().height()

            if wid:
                if wid.maximumWidth() < 16777215:
                    item_w = min(item_w, wid.maximumWidth())
                if wid.minimumWidth() > 0:
                    item_w = max(item_w, wid.minimumWidth())
                if wid.maximumHeight() < 16777215:
                    item_h = min(item_h, wid.maximumHeight())
                if wid.minimumHeight() > 0:
                    item_h = max(item_h, wid.minimumHeight())

            next_x = x + item_w + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item_w + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), QtCore.QSize(item_w, item_h)))

            x = next_x
            line_height = max(line_height, item_h)

        return y + line_height - rect.y() + margins.bottom()


'''

target_class_header = "class TaskRuleEditorDialog(QtWidgets.QDialog):"
if "class FlowLayout(QtWidgets.QLayout):" not in text:
    text = text.replace(target_class_header, flow_layout_code + target_class_header)
    print("FlowLayout inserted.")
else:
    print("FlowLayout already present.")

# 3. Replace the entire init_ui UI construction section from group_task to main_layout.addWidget(bottom_frame)
old_ui_start = '        # 1. GROUPBOX THÔNG TIN CHUNG TASK & PLC'
old_ui_end = '        main_layout.addWidget(bottom_frame)'

start_pos = text.find(old_ui_start)
end_pos = text.find(old_ui_end)

if start_pos == -1 or end_pos == -1:
    print(f"ERROR: UI block markers not found: start_pos={start_pos}, end_pos={end_pos}")
    sys.exit(1)

end_pos += len(old_ui_end)

new_ui_section = '''        # 1. GROUPBOX THÔNG TIN CHUNG TASK & PLC
        group_task = QtWidgets.QGroupBox("1. Cấu hình Task && Tín hiệu PLC")
        grid_task = QtWidgets.QGridLayout(group_task)
        grid_task.setSpacing(10)
        grid_task.setContentsMargins(12, 16, 12, 12)

        grid_task.addWidget(QtWidgets.QLabel("Tên Task:"), 0, 0)
        task_name_box = QtWidgets.QHBoxLayout()
        task_name_box.setSpacing(8)
        self.line_task_name = QtWidgets.QLineEdit()
        self.line_task_name.setPlaceholderText("...")
        self.line_task_name.setMinimumWidth(160)
        self.line_task_name.setMaximumWidth(280)
        task_name_box.addWidget(self.line_task_name)

        self.chk_task_enabled = QtWidgets.QCheckBox("Kích hoạt [✓]")
        self.chk_task_enabled.setChecked(True)
        self.chk_task_enabled.setStyleSheet("color: #15803d; font-weight: bold;")
        task_name_box.addWidget(self.chk_task_enabled)
        task_name_box.addStretch()
        grid_task.addLayout(task_name_box, 0, 1)

        grid_task.addWidget(QtWidgets.QLabel("Loại Task:"), 0, 2)
        task_type_box = QtWidgets.QHBoxLayout()
        task_type_box.setSpacing(8)
        self.combo_task_type = QtWidgets.QComboBox()
        self.combo_task_type.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_task_type.setMinimumWidth(260)
        self.combo_task_type.setMaximumWidth(350)
        self.combo_task_type.addItem("So sánh Tọa độ & Không gian (RELATION_COORDINATE)", "RELATION_COORDINATE")
        self.combo_task_type.addItem("Đo Khoảng cách (DISTANCE_CALC)", "DISTANCE")
        self.combo_task_type.addItem("Biểu thức Tùy chỉnh (CUSTOM_EXPRESSION)", "CUSTOM_EXPRESSION")
        task_type_box.addWidget(self.combo_task_type)
        task_type_box.addStretch()
        grid_task.addLayout(task_type_box, 0, 3)

        grid_task.addWidget(QtWidgets.QLabel("PLC Register:"), 1, 0)
        plc_reg_box = QtWidgets.QHBoxLayout()
        plc_reg_box.setSpacing(8)
        self.line_plc_register = QtWidgets.QLineEdit()
        self.line_plc_register.setPlaceholderText("Để trống nếu không gửi")
        self.line_plc_register.setMinimumWidth(120)
        self.line_plc_register.setMaximumWidth(170)
        plc_reg_box.addWidget(self.line_plc_register)
        plc_reg_box.addStretch()
        grid_task.addLayout(plc_reg_box, 1, 1)

        layout_plc_vals = QtWidgets.QHBoxLayout()
        layout_plc_vals.setSpacing(8)
        layout_plc_vals.addWidget(QtWidgets.QLabel("Value State:"))
        self.spin_plc_state = QtWidgets.QSpinBox()
        self.spin_plc_state.setRange(-32768, 32767)
        self.spin_plc_state.setValue(1)
        self.spin_plc_state.setAlignment(Qt.AlignCenter)
        self.spin_plc_state.setFixedWidth(65)
        self.spin_plc_state.setToolTip("🎯 Giá trị trạng thái ban đầu của thanh ghi (Value State)")
        layout_plc_vals.addWidget(self.spin_plc_state)

        layout_plc_vals.addWidget(QtWidgets.QLabel("Value OK:"))
        self.spin_plc_on = QtWidgets.QSpinBox()
        self.spin_plc_on.setRange(-32768, 32767)
        self.spin_plc_on.setValue(1)
        self.spin_plc_on.setAlignment(Qt.AlignCenter)
        self.spin_plc_on.setFixedWidth(65)
        self.spin_plc_on.setToolTip("✔ Giá trị gửi đến PLC khi Task đạt chuẩn (Value OK)")
        layout_plc_vals.addWidget(self.spin_plc_on)

        layout_plc_vals.addWidget(QtWidgets.QLabel("Value NG:"))
        self.spin_plc_off = QtWidgets.QSpinBox()
        self.spin_plc_off.setRange(-32768, 32767)
        self.spin_plc_off.setValue(0)
        self.spin_plc_off.setAlignment(Qt.AlignCenter)
        self.spin_plc_off.setFixedWidth(65)
        self.spin_plc_off.setToolTip("✘ Giá trị gửi đến PLC khi Task vi phạm (Value NG)")
        layout_plc_vals.addWidget(self.spin_plc_off)
        layout_plc_vals.addStretch()
        grid_task.addLayout(layout_plc_vals, 1, 2)

        layout_logic = QtWidgets.QHBoxLayout()
        layout_logic.setSpacing(8)
        layout_logic.addWidget(QtWidgets.QLabel("Đánh giá tổng:"))
        self.combo_logic = QtWidgets.QComboBox()
        self.combo_logic.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_logic.setMinimumWidth(200)
        self.combo_logic.setMaximumWidth(260)
        self.combo_logic.addItem("Tất cả Rule phải đạt (AND)", "ALL_PASS")
        self.combo_logic.addItem("Chỉ cần 1 Rule vi phạm là NG (OR)", "ANY_FAIL")
        layout_logic.addWidget(self.combo_logic)
        layout_logic.addStretch()
        grid_task.addLayout(layout_logic, 1, 3)

        grid_task.setColumnStretch(0, 0)
        grid_task.setColumnStretch(1, 1)
        grid_task.setColumnStretch(2, 0)
        grid_task.setColumnStretch(3, 1)

        content_layout.addWidget(group_task)

        # 2. GROUPBOX MÔ HÌNH ĐỒ HỌA TRỰC QUAN & SOẠN THẢO LUẬT
        group_rule = QtWidgets.QGroupBox("2. Mô Hình Đồ Họa Đa Đối Tượng (Interactive Canvas)")
        vlayout_rule = QtWidgets.QVBoxLayout(group_rule)
        vlayout_rule.setSpacing(10)

        # Chọn 2 Nhãn mục tiêu + Nút Reset vị trí Canvas
        layout_label_select = QtWidgets.QHBoxLayout()
        layout_label_select.setSpacing(8)
        layout_label_select.addWidget(QtWidgets.QLabel("🔵 Chọn Nhãn 1 (Label A):"))
        self.combo_label_1 = QtWidgets.QComboBox()
        self.combo_label_1.setEditable(True)
        self.combo_label_1.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_label_1.setMinimumWidth(150)
        self.combo_label_1.setMaximumWidth(240)
        layout_label_select.addWidget(self.combo_label_1)

        layout_label_select.addSpacing(16)
        layout_label_select.addWidget(QtWidgets.QLabel("🟠 Chọn Nhãn 2 (Label B):"))
        self.combo_label_2 = QtWidgets.QComboBox()
        self.combo_label_2.setEditable(True)
        self.combo_label_2.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_label_2.setMinimumWidth(150)
        self.combo_label_2.setMaximumWidth(240)
        layout_label_select.addWidget(self.combo_label_2)

        layout_label_select.addSpacing(16)
        self.btn_reset_canvas = QtWidgets.QPushButton("↺ Đặt lại vị trí")
        self.btn_reset_canvas.setObjectName("btnResetCanvas")
        self.btn_reset_canvas.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.btn_reset_canvas.setToolTip("Khôi phục vị trí mặc định theo khuôn mẫu mô hình đang chọn")
        self.btn_reset_canvas.setFixedWidth(120)
        self.btn_reset_canvas.setFixedHeight(32)
        self.btn_reset_canvas.setStyleSheet("""
            QPushButton#btnResetCanvas {
                background-color: #ffffff;
                color: #334155 !important;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#btnResetCanvas:hover {
                background-color: #eff6ff;
                border: 1px solid #3b82f6;
                color: #1d4ed8 !important;
            }
            QPushButton#btnResetCanvas:pressed {
                background-color: #dbeafe;
            }
        """)
        self.btn_reset_canvas.clicked.connect(lambda: self.visual_canvas.reset_positions())
        layout_label_select.addWidget(self.btn_reset_canvas)
        layout_label_select.addStretch()

        vlayout_rule.addLayout(layout_label_select)

        # CHỌN CHẾ ĐỘ QUAN HỆ ĐỐI TƯỢNG (INSTANCE SCOPE)
        layout_scope = QtWidgets.QHBoxLayout()
        layout_scope.setSpacing(8)
        layout_scope.addWidget(QtWidgets.QLabel("🔍 Chế độ quan hệ đối tượng (Scope):"))
        self.combo_instance_scope = QtWidgets.QComboBox()
        self.combo_instance_scope.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_instance_scope.setMinimumWidth(260)
        self.combo_instance_scope.setMaximumWidth(400)
        for k, v in INSTANCE_SCOPE_DISPLAY_NAMES.items():
            self.combo_instance_scope.addItem(v, k)
        layout_scope.addWidget(self.combo_instance_scope)
        layout_scope.addStretch()
        vlayout_rule.addLayout(layout_scope)

        self.lbl_scope_hint = QtWidgets.QLabel()
        self.lbl_scope_hint.setStyleSheet("color: #2563eb; font-size: 12px; font-style: italic; margin-bottom: 2px;")
        self.lbl_scope_hint.setWordWrap(True)
        vlayout_rule.addWidget(self.lbl_scope_hint)

        # Widget Visual Canvas tương tác kéo thả & co giãn
        self.visual_canvas = VisualBoxCanvas()
        vlayout_rule.addWidget(self.visual_canvas)

        # Thanh thiết lập biểu thức quy tắc (Rule Expression Builder - FlowLayout xếp gọn trên 1 hàng)
        expr_frame = QtWidgets.QFrame()
        expr_frame.setObjectName("exprFrame")
        expr_frame.setStyleSheet("""
            QFrame#exprFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 6px;
            }
        """)
        flow_expr = FlowLayout(expr_frame, margin=4, spacing=10)

        def _make_group_box(*widgets, spacing=5):
            box = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(box)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(spacing)
            layout.setAlignment(Qt.AlignVCenter)
            for w in widgets:
                layout.addWidget(w)
            return box

        # 1. Nhóm Vế Trái (LHS)
        lbl_lhs = QtWidgets.QLabel("Vế Trái:")
        lbl_lhs.setStyleSheet("font-weight: bold; color: #1e293b;")
        self.combo_param_1 = QtWidgets.QComboBox()
        self.combo_param_1.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_param_1.setMinimumWidth(115)
        self.combo_param_1.setMaximumWidth(150)
        for k, v in PARAM_DISPLAY_NAMES.items():
            self.combo_param_1.addItem(v, k)
        box_lhs = _make_group_box(lbl_lhs, self.combo_param_1)
        flow_expr.addWidget(box_lhs)

        # 2. Nhóm Toán tử so sánh
        lbl_op = QtWidgets.QLabel("Toán tử:")
        lbl_op.setStyleSheet("font-weight: bold; color: #1e293b;")
        self.combo_operator = QtWidgets.QComboBox()
        self.combo_operator.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_operator.setMinimumWidth(110)
        self.combo_operator.setMaximumWidth(140)
        for k, v in OPERATOR_DISPLAY_NAMES.items():
            self.combo_operator.addItem(v, k)
        box_op = _make_group_box(lbl_op, self.combo_operator)
        flow_expr.addWidget(box_op)

        # 3. Nhóm Vế Phải (RHS)
        lbl_rhs = QtWidgets.QLabel("Vế Phải:")
        lbl_rhs.setStyleSheet("font-weight: bold; color: #1e293b;")
        self.combo_target_type = QtWidgets.QComboBox()
        self.combo_target_type.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_target_type.setMinimumWidth(100)
        self.combo_target_type.setMaximumWidth(125)
        self.combo_target_type.addItem("So với B", "LABEL")
        self.combo_target_type.addItem("Số cố định", "CONSTANT")

        self.combo_param_2 = QtWidgets.QComboBox()
        self.combo_param_2.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_param_2.setMinimumWidth(115)
        self.combo_param_2.setMaximumWidth(150)
        for k, v in PARAM_DISPLAY_NAMES.items():
            self.combo_param_2.addItem(v, k)
        box_rhs = _make_group_box(lbl_rhs, self.combo_target_type, self.combo_param_2)
        flow_expr.addWidget(box_rhs)

        # 4. Nhóm Bù trừ / Dung sai (Math Offset)
        self.lbl_math_op = QtWidgets.QLabel("Bù trừ:")
        self.lbl_math_op.setStyleSheet("font-weight: bold; color: #1e293b;")
        self.combo_math_op = QtWidgets.QComboBox()
        self.combo_math_op.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_math_op.setMinimumWidth(75)
        self.combo_math_op.setMaximumWidth(95)
        self.combo_math_op.addItem("Không", "NONE")
        self.combo_math_op.addItem("+ (Cộng)", "+")
        self.combo_math_op.addItem("- (Trừ)", "-")
        self.combo_math_op.addItem("* (Nhân)", "*")
        self.combo_math_op.addItem("/ (Chia)", "/")

        self.lbl_math_val = QtWidgets.QLabel("± (px):")
        self.lbl_math_val.setStyleSheet("font-weight: bold; color: #1e293b;")
        self.line_math_val = QtWidgets.QLineEdit("0")
        self.line_math_val.setAlignment(Qt.AlignCenter)
        self.line_math_val.setMinimumWidth(50)
        self.line_math_val.setMaximumWidth(68)
        self.line_math_val.setPlaceholderText("0")
        box_math = _make_group_box(self.lbl_math_op, self.combo_math_op, self.lbl_math_val, self.line_math_val)
        flow_expr.addWidget(box_math)

        # 5. Nhóm Kết quả phán định (True Result)
        lbl_res = QtWidgets.QLabel("Khi đúng:")
        lbl_res.setStyleSheet("font-weight: bold; color: #1e293b;")
        self.combo_true_result = QtWidgets.QComboBox()
        self.combo_true_result.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_true_result.setMinimumWidth(105)
        self.combo_true_result.setMaximumWidth(125)
        self.combo_true_result.addItem("Đánh giá NG", "NG")
        self.combo_true_result.addItem("Đánh giá OK", "OK")
        box_res = _make_group_box(lbl_res, self.combo_true_result)
        flow_expr.addWidget(box_res)

        # 6. Nhóm Thao tác Rule (Thêm mới & Cập nhật)
        self.btn_add_rule = QtWidgets.QPushButton("+ Thêm Mới")
        self.btn_add_rule.setObjectName("btnAddRule")
        self.btn_add_rule.setToolTip("Thêm một rule mới vào danh sách")
        self.btn_add_rule.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.btn_add_rule.setFixedHeight(32)
        self.btn_add_rule.setMinimumWidth(85)
        self.btn_add_rule.setMaximumWidth(105)
        self.btn_add_rule.setStyleSheet("""
            QPushButton#btnAddRule {
                background-color: #16a34a;
                color: #ffffff !important;
                border: 1px solid #15803d;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#btnAddRule:hover {
                background-color: #15803d;
                border: 1px solid #166534;
                color: #ffffff !important;
            }
            QPushButton#btnAddRule:pressed {
                background-color: #166534;
                color: #ffffff !important;
            }
        """)

        self.btn_update_rule = QtWidgets.QPushButton("💾 Cập Nhật")
        self.btn_update_rule.setObjectName("btnUpdateRule")
        self.btn_update_rule.setToolTip("Cập nhật lại rule đang chọn trên bảng")
        self.btn_update_rule.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.btn_update_rule.setFixedHeight(32)
        self.btn_update_rule.setMinimumWidth(85)
        self.btn_update_rule.setMaximumWidth(105)
        self.btn_update_rule.setStyleSheet("""
            QPushButton#btnUpdateRule {
                background-color: #ea580c;
                color: #ffffff !important;
                border: 1px solid #c2410c;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#btnUpdateRule:hover {
                background-color: #c2410c;
                border: 1px solid #9a3412;
                color: #ffffff !important;
            }
            QPushButton#btnUpdateRule:pressed {
                background-color: #9a3412;
                color: #ffffff !important;
            }
        """)
        box_actions = _make_group_box(self.btn_add_rule, self.btn_update_rule, spacing=6)
        flow_expr.addWidget(box_actions)

        vlayout_rule.addWidget(expr_frame)
        content_layout.addWidget(group_rule)

        # 3. BẢNG DANH SÁCH RULES CỦA TASK
        group_table = QtWidgets.QGroupBox("3. Danh sách các Quy Tắc (Rules) trong Task này (Nhấp vào dòng để chỉnh sửa && xem mô hình)")
        vlayout_table = QtWidgets.QVBoxLayout(group_table)

        self.table_rules = QtWidgets.QTableWidget(0, 6)
        self.table_rules.setHorizontalHeaderLabels([
            "STT", "Chế độ (Scope)", "Biểu Thức Quy Tắc (Rule)", "Vế Trái (LHS)", "Toán Tử & Vế Phải (RHS)", "Phán Định"
        ])
        self.table_rules.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.table_rules.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.table_rules.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.table_rules.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.table_rules.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        self.table_rules.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
        self.table_rules.verticalHeader().setDefaultSectionSize(32)
        self.table_rules.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_rules.setAlternatingRowColors(True)
        self.table_rules.setMinimumHeight(280)
        vlayout_table.addWidget(self.table_rules)

        content_layout.addWidget(group_table)

        self.scroll_area.setWidget(scroll_content)
        main_layout.addWidget(self.scroll_area, 1)

        # 4. ACTION BUTTONS BOTTOM
        bottom_frame = QtWidgets.QFrame()
        bottom_frame.setObjectName("bottomFrame")
        bottom_frame.setStyleSheet("""
            QFrame#bottomFrame {
                background-color: #e2e8f0;
                border-top: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        layout_bottom = QtWidgets.QHBoxLayout(bottom_frame)
        layout_bottom.setContentsMargins(8, 4, 8, 4)

        self.btn_delete_rule = QtWidgets.QPushButton("🗑️ Xóa Rule đã chọn")
        self.btn_delete_rule.setObjectName("btnDeleteRule")
        self.btn_delete_rule.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.btn_delete_rule.setFixedHeight(34)
        self.btn_delete_rule.setMinimumWidth(150)
        self.btn_delete_rule.setStyleSheet("""
            QPushButton#btnDeleteRule {
                background-color: #dc2626;
                color: #ffffff !important;
                border: 1px solid #b91c1c;
                border-radius: 6px;
                padding: 6px 18px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btnDeleteRule:hover {
                background-color: #b91c1c;
                border: 1px solid #991b1b;
                color: #ffffff !important;
            }
            QPushButton#btnDeleteRule:pressed {
                background-color: #991b1b;
                color: #ffffff !important;
            }
        """)
        layout_bottom.addWidget(self.btn_delete_rule)

        layout_bottom.addStretch()

        self.btn_cancel = QtWidgets.QPushButton("Hủy Bỏ")
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.btn_cancel.setFixedHeight(34)
        self.btn_cancel.setMinimumWidth(100)
        self.btn_cancel.setStyleSheet("""
            QPushButton#btnCancel {
                background-color: #ffffff;
                color: #475569 !important;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btnCancel:hover {
                background-color: #f1f5f9;
                color: #1e293b !important;
                border-color: #94a3b8;
            }
            QPushButton#btnCancel:pressed {
                background-color: #e2e8f0;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        layout_bottom.addWidget(self.btn_cancel)

        self.btn_save = QtWidgets.QPushButton("💾 Lưu Task && Áp Dụng")
        self.btn_save.setObjectName("btnSave")
        self.btn_save.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.btn_save.setFixedHeight(34)
        self.btn_save.setMinimumWidth(160)
        self.btn_save.setStyleSheet("""
            QPushButton#btnSave {
                background-color: #2563eb;
                color: #ffffff !important;
                border: 1px solid #1d4ed8;
                border-radius: 6px;
                padding: 6px 24px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btnSave:hover {
                background-color: #1d4ed8;
                border: 1px solid #1e40af;
                color: #ffffff !important;
            }
            QPushButton#btnSave:pressed {
                background-color: #1e40af;
                color: #ffffff !important;
            }
        """)
        self.btn_save.clicked.connect(self.save_task)
        layout_bottom.addWidget(self.btn_save)

        main_layout.addWidget(bottom_frame)'''

text = text[:start_pos] + new_ui_section + text[end_pos:]
print("UI section replaced.")

# 4. Update dropdown popup view sizes in init_ui
old_all_combos = """        all_combos = [
            self.combo_label_1, self.combo_label_2, self.combo_task_type, self.combo_logic,
            self.combo_instance_scope, self.combo_param_1, self.combo_operator,
            self.combo_target_type, self.combo_param_2, self.combo_math_op, self.combo_true_result
        ]
        for cb in all_combos:
            cb.setView(QtWidgets.QListView())"""

new_all_combos = """        all_combos = [
            self.combo_label_1, self.combo_label_2, self.combo_task_type, self.combo_logic,
            self.combo_instance_scope, self.combo_param_1, self.combo_operator,
            self.combo_target_type, self.combo_param_2, self.combo_math_op, self.combo_true_result
        ]
        for cb in all_combos:
            view = QtWidgets.QListView()
            cb.setView(view)
            view.setMinimumWidth(max(cb.minimumWidth(), 200))"""

if old_all_combos in text:
    text = text.replace(old_all_combos, new_all_combos)
    print("all_combos view minimum width updated.")
else:
    print("Checking normalized all_combos...")
    text_lf = text.replace("\r\n", "\n")
    if old_all_combos.replace("\r\n", "\n") in text_lf:
        text = text_lf.replace(old_all_combos.replace("\r\n", "\n"), new_all_combos.replace("\r\n", "\n"))
        print("all_combos view minimum width updated via LF.")

# 5. Update on_operator_changed label texts
text = text.replace('self.lbl_math_op.setText("Phép bù trừ Margin:")', 'self.lbl_math_op.setText("Bù Margin:")')
text = text.replace('self.lbl_math_val.setText("Dung sai Margin (px):")', 'self.lbl_math_val.setText("Dung sai (px):")')
text = text.replace('self.lbl_math_val.setText("Ngưỡng khoảng cách (px):")', 'self.lbl_math_val.setText("Ngưỡng (px):")')
text = text.replace('self.lbl_math_op.setText("Phép bù trừ / Dung sai:")', 'self.lbl_math_op.setText("Bù trừ:")')
text = text.replace('self.lbl_math_val.setText("Giá trị bù trừ (px):")', 'self.lbl_math_val.setText("± (px):")')

with open(TARGET_FILE, "w", encoding="utf-8") as f:
    f.write(text)

print("SUCCESS: target file updated successfully!")

