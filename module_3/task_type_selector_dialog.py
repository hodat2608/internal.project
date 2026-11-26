"""
Module: task_type_selector_dialog.py
Mục đích: Hộp thoại lựa chọn loại tác vụ kiểm tra khi người dùng nhấn "Thêm Task Mới":
  Option 1: Task Rule Calculator (Hình học, khoảng cách, tọa độ đơn ảnh)
  Option 2: Cross-Shot Multi-Image Defect Aggregation (Tổng hợp phế phẩm liên ảnh trong chu kỳ đa shot, khoanh vùng ROI)
"""

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt


class TaskTypeCard(QtWidgets.QFrame):
    """Card hiển thị lựa chọn loại tác vụ với hiệu ứng hover và phản hồi nhấn trực quan (Không viền)."""
    clicked = QtCore.pyqtSignal(str)

    def __init__(self, task_type: str, icon_str: str, title: str, tag: str, tag_color: str, desc_lines: list, parent=None):
        super().__init__(parent)
        self.task_type = task_type
        self.setCursor(Qt.PointingHandCursor)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setObjectName(f"card_{task_type}")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header: Icon + Title + Tag
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(10)

        lbl_icon = QtWidgets.QLabel(icon_str)
        lbl_icon.setStyleSheet("font-size: 30px; border: none; background: transparent;")
        header_layout.addWidget(lbl_icon)

        title_col = QtWidgets.QVBoxLayout()
        title_col.setSpacing(2)

        lbl_title = QtWidgets.QLabel(title)
        lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #0f172a; border: none; background: transparent;")
        title_col.addWidget(lbl_title)

        lbl_tag = QtWidgets.QLabel(tag)
        lbl_tag.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 600;
            color: {tag_color};
            background: #f1f5f9;
            padding: 2px 6px;
            border-radius: 4px;
            border: none;
        """)
        lbl_tag.setFixedHeight(20)
        title_col.addWidget(lbl_tag)

        header_layout.addLayout(title_col)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Khoảng cách thay cho đường kẻ ngang (đã bỏ border/line)
        layout.addSpacing(4)

        # Description list
        for line in desc_lines:
            lbl_desc = QtWidgets.QLabel(f"• {line}")
            lbl_desc.setWordWrap(True)
            lbl_desc.setStyleSheet("font-size: 12px; color: #475569; line-height: 1.4; border: none; background: transparent;")
            layout.addWidget(lbl_desc)

        layout.addStretch()

        # Action Button (Không viền)
        btn_select = QtWidgets.QPushButton(f"Chọn {title} →")
        btn_select.setCursor(Qt.PointingHandCursor)
        btn_select.setStyleSheet(f"""
            QPushButton {{
                background-color: #077500;
                color: #FFFFFF;
                font-weight: 600;
                font-size: 12px;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
            }}
            QPushButton:hover {{
                background-color: {tag_color};
                color: #ffffff;
                border: none;
            }}
        """)
        btn_select.clicked.connect(lambda: self.clicked.emit(self.task_type))
        layout.addWidget(btn_select)

        # Card Style (Không viền, dùng màu nền để phân biệt trạng thái hover)
        self.setStyleSheet(f"""
            QFrame#card_{task_type} {{
                background-color: #E4E4E4;
                border: none;
                border-radius: 12px;
            }}
            QFrame#card_{task_type}:hover {{
                background-color: #C5C5C5;
                border: none;
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.task_type)
        super().mousePressEvent(event)


class TaskTypeSelectorDialog(QtWidgets.QDialog):
    """
    Hộp thoại cho phép người dùng chọn tạo loại Task (Giao diện phẳng, không viền).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chọn Loại Tác Vụ Mới (New Task Type)")
        self.resize(1080, 560)
        self.setMinimumSize(980, 520)
        self.setModal(True)
        self.selected_type = 'RELATION_COORDINATE'

        # Nền tổng thể hơi xám nhẹ (#f8fafc) để làm nổi bật Card trắng (#ffffff) mà không cần viền
        self.setStyleSheet("QDialog { background-color: #f8fafc; border: none; }")

        self._init_ui()

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Header Title
        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(4)
        lbl_main = QtWidgets.QLabel("CHỌN LOẠI KIỂM TRA CHO TASK MỚI")
        lbl_main.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b; border: none;")
        title_box.addWidget(lbl_main)

        lbl_sub = QtWidgets.QLabel(
            "Vui lòng chọn loại tác vụ kiểm tra phù hợp với yêu cầu thực tế của sản phẩm trên dây chuyền:"
        )
        lbl_sub.setStyleSheet("font-size: 12px; color: #64748b; border: none;")
        title_box.addWidget(lbl_sub)
        main_layout.addLayout(title_box)

        # Cards Layout
        cards_layout = QtWidgets.QHBoxLayout()
        cards_layout.setSpacing(16)

        # Card 1: Task Rule Calculator (Hình học đơn ảnh)
        card_calc = TaskTypeCard(
            task_type='RELATION_COORDINATE',
            icon_str="📐",
            title="Task Rule Calculator",
            tag="Đơn Ảnh / Hình Học & Tọa Độ",
            tag_color="#2563eb",
            desc_lines=[
                "Kiểm tra kích thước, khoảng cách tâm, khoảng cách mép giữa các nhãn.",
                "Toán tử so sánh: >, <, ==, IN_RANGE, INSIDE, OVERLAP, v.v.",
                "Phán định ngay trên từng khung hình ảnh riêng lẻ."
            ],
            parent=self
        )
        card_calc.clicked.connect(self._on_type_selected)
        cards_layout.addWidget(card_calc)

        # Card 2: ROI Zone Inspector (Khoanh vùng đa vùng & Mask cho từng Model)
        card_roi = TaskTypeCard(
            task_type='ROI_ZONE_INSPECTION',
            icon_str="🖼️",
            title="ROI Zone Inspector",
            tag="Đơn Model / Khoanh Vùng & Vùng Che",
            tag_color="#0284c7",
            desc_lines=[
                "Khoanh vùng đa vùng (Multi-Zone ROI) độc lập cho từng góc chụp của Model.",
                "🟢 Inspection Zone: Bắt lỗi nếu nhãn mục tiêu xuất hiện trong vùng.",
                "🔴 Mask Zone: Triệt tiêu phản xạ, bóng lóa, viền khuôn gá.",
                "🔵 Presence Zone: Bắt buộc phải có linh kiện (≥ số lượng tối thiểu)."
            ],
            parent=self
        )
        card_roi.clicked.connect(self._on_type_selected)
        cards_layout.addWidget(card_roi)

        # Card 3: Cross-Shot Multi-Image Defect Aggregation (Liên Model)
        card_multishot = TaskTypeCard(
            task_type='MULTI_SHOT_AGGREGATION',
            icon_str="🔄",
            title="Cross-Shot Aggregation",
            tag="Đa Ảnh / Chu Kỳ Liên Model",
            tag_color="#7c3aed",
            desc_lines=[
                "Tổng hợp phế phẩm liên ảnh trong chu kỳ đa shot (Ví dụ: NG ≥ 2 lần trong 5 ảnh mới phán định NG).",
                "Liên kết tất cả các Tab Model tương ứng với từng shot chụp của Camera.",
                "Phán định theo tổ hợp shot chỉ định hoặc chuỗi lỗi liên tiếp.",
                "Đồng bộ chu kỳ tự động theo tín hiệu counter từ hệ thống."
            ],
            parent=self
        )
        card_multishot.clicked.connect(self._on_type_selected)
        cards_layout.addWidget(card_multishot)

        main_layout.addLayout(cards_layout)

        # Bottom Bar
        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.addStretch()

        btn_cancel = QtWidgets.QPushButton("Hủy Bỏ")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedSize(100, 34)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #e2e8f0;
                color: #475569;
                border: none;
                border-radius: 6px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #cbd5e1;
                color: #0f172a;
                border: none;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        bottom_layout.addWidget(btn_cancel)

        main_layout.addLayout(bottom_layout)

    def _on_type_selected(self, task_type: str):
        self.selected_type = task_type
        self.accept()
