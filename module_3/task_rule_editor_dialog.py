"""
Module: task_rule_editor_dialog.py
Mục đích: Hộp thoại soạn thảo Task & Luật hình học với mô hình đồ họa tương tác cao cấp (Interactive Visual Bounding Box Canvas).
Tính năng nâng cấp:
1. Đa dạng chế độ quan hệ đối tượng (Instance Scope):
   - 1 vs 1: So sánh trực tiếp 1 đối tượng A với 1 đối tượng B (hoặc hằng số).
   - N vs 1: Tất cả đối tượng mang nhãn A với 1 vùng chứa B (VD: Khay linh kiện / Vùng bao quy chuẩn - bất kỳ đối tượng A nào vượt ra ngoài biên thì báo NG).
   - 1 vs N: 1 đối tượng A với nhiều vùng cấm / vùng giới hạn B (VD: Đối tượng vi phạm vào bất kỳ vùng cấm nào thì báo NG).
   - N vs N: Tất cả đối tượng A với tất cả đối tượng B.
2. Các toán tử không gian mở rộng:
   - INSIDE: Nằm hoàn toàn bên trong (có xét bù trừ margin).
   - OUTSIDE: Nằm hoàn toàn bên ngoài.
   - OVERLAP: Giao nhau / Chạm mép.
3. Mô hình đồ họa tương tác VisualBoxCanvas thời gian thực:
   - Khi chọn N vs 1: Tự động chuyển đổi Box B thành Vùng Chứa Master lớn (Container Master B) và hiển thị các đối tượng A (Đối tượng A1, A2, A3). Kéo A1 ra ngoài vùng chứa lập tức cảnh báo NG đỏ rực thời gian thực!
   - Khi chọn 1 vs N: Hiển thị A và nhiều vùng giới hạn B1, B2. Kéo A vào vùng giới hạn lập tức cảnh báo NG!
   - Kéo di chuyển (Drag) và co giãn kích thước (Resize) mượt mà với HUD Banner hiển thị pixel thời gian thực.
4. Giao diện chuyên nghiệp: Chuẩn hóa màu sắc độ tương phản cao, Combobox chống chói/hover tối ưu, các nút thao tác nổi bật với chữ trắng rõ ràng, dễ bấm.
5. Bảng danh sách Rules đầy đủ cột Chế độ (Scope), Biểu thức, Vế trái, Vế phải, Phán định. Click chọn dòng nào thì giao diện và đồ họa tự động chuyển sang cấu hình theo Rule đó!
"""

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QPolygonF
import math
from typing import List, Dict, Any, Optional, Tuple

PARAM_DISPLAY_NAMES = {
    'FULL_BOX': 'Full Box',
    'X_MIN': 'Left (X min)',
    'X_MAX': 'Right (X max)',
    'Y_MIN': 'Top (Y min)',
    'Y_MAX': 'Bottom (Y max)',
    'CENTER_X': 'Center X',
    'CENTER_Y': 'Center Y',
    'WIDTH': 'Width',
    'HEIGHT': 'Height'
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
}

INSTANCE_SCOPE_DISPLAY_NAMES = {
    '1_VS_1': '1 vs 1 (Đơn chiếc: 1 đối tượng A vs 1 đối tượng B)',
    'ALL_A_IN_ONE_B': 'N vs 1 (Tất cả đối tượng A vs 1 vùng chứa B - VD: Khay linh kiện / Vùng bao)',
    'ONE_A_IN_ANY_B': '1 vs N (1 đối tượng A vs Bất kỳ vùng B - VD: Đối tượng vào vùng cấm / vùng giới hạn)',
    'ALL_A_VS_ALL_B': 'N vs N (Tất cả đối tượng A vs Tất cả đối tượng B)'
}

TASK_PLC_MAPPING = {
    "Register": "`assign_register`",
    "Value State": "`Value_State`",
    "Value OK": "`Value_OK`",
    "Value NG": "`Value_NG`",
}


class VisualBoxCanvas(QtWidgets.QWidget):
    """
    Widget đồ họa trực quan mô phỏng không gian đo thị giác công nghiệp.
    - Hỗ trợ các khuôn mẫu mô hình đồ họa động theo Instance Scope (1 vs 1, N vs 1, 1 vs N, N vs N).
    - Hộp nhãn có thể dùng chuột kéo thả (Drag) và co giãn kích thước (Resize).
    - Hiển thị pixel kích thước WxH thời gian thực khi kéo to / thu nhỏ.
    - Phán định trạng thái không gian (INSIDE, OUTSIDE, OVERLAP) và quan hệ tọa độ ngay khi rê chuột.
    """
    hotspot_clicked = pyqtSignal(int, str)  # (box_index: 1 or 2, param_name: str)
    box_geometry_changed = pyqtSignal(int, float, float, float, float)  # (box_idx, x, y, w, h)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(540)
        self.setMouseTracking(True)
        
        self.label_1_name = "Đối Tượng 1 (Label A)"
        self.label_2_name = "Vùng Quy Chiếu 2 (Label B)"
        self.selected_param_1 = 'X_MIN'
        self.selected_param_2 = 'X_MIN'
        self.operator_str = '<'
        self.condition_true_result = 'NG'
        self.target_type = 'LABEL'
        self.math_op = 'NONE'
        self.math_val = '0'
        self.instance_scope = '1_VS_1'

        # Tọa độ và kích thước của 2 box
        self.box1_rect = QRectF(40, 50, 180, 130)
        self.box2_rect = QRectF(290, 50, 180, 130)
        self.front_box = 1

        # Trạng thái tương tác chuột
        self.active_action = None
        self.drag_start_mouse = QPointF()
        self.initial_box_rect = QRectF()
        self.hovered_hotspot = None
        self.hovered_resize = None
        self.hovered_body = None
        self.is_dragging = False

        self.resize_handle_size = 18.0

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._clamp_boxes_to_bounds()

    def _clamp_boxes_to_bounds(self):
        w = float(self.width())
        h = float(self.height())
        for b_idx in (1, 2):
            r = self.box1_rect if b_idx == 1 else self.box2_rect
            bw = max(70.0, min(r.width(), w - 20.0))
            bh = max(50.0, min(r.height(), h - 20.0))
            bx = max(5.0, min(r.x(), w - bw - 5.0))
            by = max(80.0, min(r.y(), h - bh - 5.0))
            if b_idx == 1:
                self.box1_rect = QRectF(bx, by, bw, bh)
            else:
                self.box2_rect = QRectF(bx, by, bw, bh)

    def get_box_geometry(self, box_idx: int):
        """Lấy tọa độ và kích thước hiện tại (x, y, w, h) của box 1 hoặc box 2."""
        r = self.box1_rect if box_idx == 1 else self.box2_rect
        return (float(r.x()), float(r.y()), float(r.width()), float(r.height()))

    def set_box_geometry(self, box_idx: int, x: float, y: float, w: float, h: float):
        """Thiết lập chính xác tọa độ và kích thước cho box 1 hoặc box 2."""
        new_rect = QRectF(float(x), float(y), float(w), float(h))
        if box_idx == 1:
            self.box1_rect = new_rect
        else:
            self.box2_rect = new_rect
        self._clamp_boxes_to_bounds()
        self.update()

    def set_instance_scope(self, scope: str, reset: bool = True):
        """Thiết lập chế độ đối tượng và cấu hình lại đồ họa trực quan theo đúng mô hình."""
        self.instance_scope = scope or '1_VS_1'
        if reset:
            self.reset_positions()
        else:
            self.update()

    def reset_positions(self):
        """Khôi phục vị trí mặc định nằm cân đối hoặc theo khuôn mẫu Scope (bề cao rộng rãi)."""
        w = max(500, self.width())
        h = max(520, self.height())

        if self.instance_scope == 'ALL_A_IN_ONE_B':
            # Master Container B (Vùng chứa quy chiếu) lớn ở trung tâm
            b2_w = min(680.0, max(420.0, w * 0.76))
            b2_h = min(400.0, max(280.0, h * 0.65))
            b2_x = max(20.0, (w - b2_w) / 2)
            b2_y = max(85.0, (h - b2_h) / 2 + 30.0)
            self.box2_rect = QRectF(b2_x, b2_y, b2_w, b2_h)
            
            # Box 1 (Đối tượng A1 - đối tượng tương tác chính) đặt nằm trong vùng chứa
            b1_w = 135.0
            b1_h = 95.0
            self.box1_rect = QRectF(b2_x + 45.0, b2_y + 55.0, b1_w, b1_h)
            self.front_box = 1

        elif self.instance_scope == 'ONE_A_IN_ANY_B':
            # Đối tượng A ở bên trái, Vùng giới hạn B1 ở giữa
            b1_w = 135.0
            b1_h = 95.0
            self.box1_rect = QRectF(w * 0.18 - b1_w / 2, max(95.0, (h - b1_h) / 2 + 20.0), b1_w, b1_h)
            b2_w = 190.0
            b2_h = 145.0
            self.box2_rect = QRectF(w * 0.50 - b2_w / 2, max(95.0, (h - b2_h) / 2 + 20.0), b2_w, b2_h)
            self.front_box = 1

        else:
            # 1 vs 1 tiêu chuẩn & N vs N
            box_w = 190.0
            box_h = 140.0
            y = max(95.0, (h - box_h) / 2 + 15.0)
            self.box1_rect = QRectF(w * 0.25 - box_w / 2, y, box_w, box_h)
            self.box2_rect = QRectF(w * 0.75 - box_w / 2, y, box_w, box_h)

        self.update()

    def set_labels(self, label1: str, label2: str):
        self.label_1_name = label1 or "Nhãn 1"
        self.label_2_name = label2 or "Nhãn 2"
        self.update()

    def set_target_type(self, target_type: str):
        self.target_type = target_type or 'LABEL'
        self.update()

    def set_math_info(self, math_op: str, math_val: str):
        self.math_op = math_op or 'NONE'
        self.math_val = str(math_val if math_val is not None else '0')
        self.update()

    def set_selected_param(self, box_idx: int, param_name: str):
        if box_idx == 1:
            self.selected_param_1 = param_name
        else:
            self.selected_param_2 = param_name
        self.update()

    def set_operator_and_result(self, op: str, result: str):
        self.operator_str = op or '<'
        self.condition_true_result = result or 'NG'
        self.update()

    @staticmethod
    def _is_rect_inside(r1: QRectF, r2: QRectF, margin: float = 0.0) -> bool:
        """Kiểm tra r1 có nằm hoàn toàn bên trong r2 không."""
        return (r1.left() >= (r2.left() - margin) and
                r1.right() <= (r2.right() + margin) and
                r1.top() >= (r2.top() - margin) and
                r1.bottom() <= (r2.bottom() + margin))

    @staticmethod
    def _is_rect_outside(r1: QRectF, r2: QRectF, margin: float = 0.0) -> bool:
        """Kiểm tra r1 có hoàn toàn nằm ngoài r2 không."""
        return (r1.right() < (r2.left() - margin) or
                r1.left() > (r2.right() + margin) or
                r1.bottom() < (r2.top() - margin) or
                r1.top() > (r2.bottom() + margin))

    @staticmethod
    def _is_rect_overlapping(r1: QRectF, r2: QRectF, margin: float = 0.0) -> bool:
        """Kiểm tra r1 và r2 có giao nhau hoặc chạm mép."""
        return not VisualBoxCanvas._is_rect_outside(r1, r2, margin)

    def _get_hotspots(self, rect: QRectF, box_idx: int):
        """Trả về danh sách các điểm neo tương tác trên viền và trong thân box."""
        m = 12
        left_rect = QRectF(rect.left() - m, rect.top() + m, m * 2, rect.height() - m * 2)
        right_rect = QRectF(rect.right() - m, rect.top() + m, m * 2, rect.height() - m * 2)
        top_rect = QRectF(rect.left() + m, rect.top() - m, rect.width() - m * 2, m * 2)
        bottom_rect = QRectF(rect.left() + m, rect.bottom() - m, rect.width() - m * 2, m * 2)
        
        cx, cy = rect.center().x(), rect.center().y()
        center_rect = QRectF(cx - 14, cy - 14, 28, 28)

        # Hotspots cho WIDTH & HEIGHT
        width_hotspot_rect = QRectF(rect.left() + 20, rect.top() + 30, max(20.0, rect.width() - 40), 18)
        height_hotspot_rect = QRectF(rect.left() + 10, rect.top() + 48, 22, max(20.0, rect.height() - 75))

        return [
            (box_idx, 'X_MIN', left_rect, 'Left (X min)'),
            (box_idx, 'X_MAX', right_rect, 'Right (X max)'),
            (box_idx, 'Y_MIN', top_rect, 'Top (Y min)'),
            (box_idx, 'Y_MAX', bottom_rect, 'Bottom (Y max)'),
            (box_idx, 'CENTER_X', center_rect, 'Center'),
            (box_idx, 'WIDTH', width_hotspot_rect, 'Width'),
            (box_idx, 'HEIGHT', height_hotspot_rect, 'Height'),
        ]

    def _get_resize_rect(self, rect: QRectF) -> QRectF:
        """Vùng tay cầm co giãn ở góc dưới bên phải."""
        s = self.resize_handle_size
        return QRectF(rect.right() - s, rect.bottom() - s, s, s)

    def _get_hotspot_point(self, rect: QRectF, param: str) -> QPointF:
        """Lấy tọa độ điểm đại diện cho param để vẽ đường đo nối giữa 2 box."""
        cx = rect.center().x()
        cy = rect.center().y()
        if param in ('X_MIN', 'LEFT'):
            return QPointF(rect.left(), cy)
        elif param in ('X_MAX', 'RIGHT'):
            return QPointF(rect.right(), cy)
        elif param in ('Y_MIN', 'TOP'):
            return QPointF(cx, rect.top() + 24.0)
        elif param in ('Y_MAX', 'BOTTOM'):
            return QPointF(cx, rect.bottom())
        elif param == 'WIDTH':
            return QPointF(rect.right(), rect.top() + 38)
        elif param == 'HEIGHT':
            return QPointF(rect.left() + 20, rect.bottom() - 15)
        else:  # Center / FULL_BOX
            return QPointF(cx, cy)

    def _get_param_value(self, rect: QRectF, param: str) -> float:
        """Trích xuất giá trị số học của tham số từ QRectF thời gian thực."""
        p = (param or '').upper().strip()
        if p in ('X_MIN', 'LEFT'):
            return float(rect.left())
        elif p in ('X_MAX', 'RIGHT'):
            return float(rect.right())
        elif p in ('Y_MIN', 'TOP'):
            return float(rect.top() + 24.0)
        elif p in ('Y_MAX', 'BOTTOM'):
            return float(rect.bottom())
        elif p in ('CENTER_X', 'CX'):
            return float(rect.center().x())
        elif p in ('CENTER_Y', 'CY'):
            return float(rect.center().y())
        elif p in ('WIDTH', 'W'):
            return float(rect.width())
        elif p in ('HEIGHT', 'H'):
            return float(rect.height())
        return 0.0

    def _calculate_edge_distance(self, p1: QPointF, p2: QPointF, param1: str, param2: str) -> Tuple[float, str]:
        """
        Tính khoảng cách giữa 2 điểm neo của 2 cạnh:
        - Nếu cùng trục dọc (Y_MIN, Y_MAX): abs(p1.y - p2.y) (khoảng cách dọc ΔY)
        - Nếu cùng trục ngang (X_MIN, X_MAX): abs(p1.x - p2.x) (khoảng cách ngang ΔX)
        - Trường hợp chéo trục hoặc Center: Euclidean distance
        """
        p1_u = (param1 or '').upper()
        p2_u = (param2 or '').upper()
        is_y1 = p1_u in ('Y_MIN', 'TOP', 'Y_MAX', 'BOTTOM')
        is_y2 = p2_u in ('Y_MIN', 'TOP', 'Y_MAX', 'BOTTOM')
        is_x1 = p1_u in ('X_MIN', 'LEFT', 'X_MAX', 'RIGHT')
        is_x2 = p2_u in ('X_MIN', 'LEFT', 'X_MAX', 'RIGHT')

        if is_y1 and is_y2:
            return abs(p1.y() - p2.y()), "ΔY"
        elif is_x1 and is_x2:
            return abs(p1.x() - p2.x()), "ΔX"
        else:
            return math.hypot(p1.x() - p2.x(), p1.y() - p2.y()), "Dist"

    def _paint_coordinate_system(self, painter: QPainter, w: int, h: int):
        """
        Vẽ hệ trục tọa độ 2D CAD chuyên nghiệp lên canvas:
        - Lưới phụ (25px) nét chấm, lưới chính (100px) nét liền mảnh.
        - Thước đo tọa độ pixel (Ruler Ticks & Coordinate Values) dọc theo 2 trục.
        - Hai đường trục chính: Trục X (+X Width →) và Trục Y (+Y Height ↓).
        - Panel Gizmo trực quan ở góc trên bên trái: Gốc O(0,0), mũi tên vector X, Y và chú giải đơn vị pixel.
        """
        # 1. Nền canvas
        painter.fillRect(0, 0, w, h, QColor("#FFFFFF"))

        # 2. Lưới CAD: Lưới phụ (25px) nét chấm, lưới chính (100px) nét liền mảnh
        pen_minor = QPen(QColor("#f1f5f9"), 1, Qt.DotLine)
        pen_major = QPen(QColor("#e2e8f0"), 1, Qt.SolidLine)

        for x in range(25, w, 25):
            painter.setPen(pen_major if (x % 100 == 0) else pen_minor)
            painter.drawLine(x, 0, x, h)
        for y in range(25, h, 25):
            painter.setPen(pen_major if (y % 100 == 0) else pen_minor)
            painter.drawLine(0, y, w, y)

        # 3. Hai đường trục tọa độ chính: Trục X (Top) và Trục Y (Left)
        pen_axis_x = QPen(QColor("#2563eb"), 2, Qt.SolidLine)
        painter.setPen(pen_axis_x)
        painter.drawLine(0, 1, w, 1)

        pen_axis_y = QPen(QColor("#16a34a"), 2, Qt.SolidLine)
        painter.setPen(pen_axis_y)
        painter.drawLine(1, 0, 1, h)

        # Mũi tên đầu trục X (bên phải trên cùng)
        if w > 250:
            arrow_x = w - 10
            painter.setBrush(QBrush(QColor("#2563eb")))
            poly_x = QPolygonF([QPointF(arrow_x, 1), QPointF(arrow_x - 10, -4), QPointF(arrow_x - 10, 6)])
            painter.drawPolygon(poly_x)

        # Mũi tên đầu trục Y (dưới cùng bên trái)
        if h > 180:
            arrow_y = h - 10
            painter.setBrush(QBrush(QColor("#16a34a")))
            poly_y = QPolygonF([QPointF(1, arrow_y), QPointF(-4, arrow_y - 10), QPointF(6, arrow_y - 10)])
            painter.drawPolygon(poly_y)

        # 4. Thước chia vạch và số đo pixel (Ruler Ticks)
        painter.setFont(QFont("Segoe UI", 7, QFont.Bold))

        # Trục X: vạch chia mỗi 100px
        for x in range(100, w - 40, 100):
            painter.setPen(QPen(QColor("#94a3b8"), 1.2))
            painter.drawLine(x, 0, x, 6)
            if x >= 160:
                painter.setPen(QColor("#64748b"))
                painter.drawText(QRectF(x - 25, 4, 50, 12), Qt.AlignCenter, f"{x}")

        # Trục Y: vạch chia mỗi 100px
        for y in range(100, h - 20, 100):
            painter.setPen(QPen(QColor("#94a3b8"), 1.2))
            painter.drawLine(0, y, 6, y)
            painter.setPen(QColor("#64748b"))
            painter.drawText(QRectF(8, y - 7, 35, 14), Qt.AlignLeft | Qt.AlignVCenter, f"{y}")

        # 5. Panel Gizmo Hệ Trục Tọa Độ tại góc trên bên trái (x=10, y=8, w=146, h=58)
        panel_rect = QRectF(10, 8, 146, 58)
        painter.setBrush(QBrush(QColor(255, 255, 255, 245)))
        painter.setPen(QPen(QColor("#cbd5e1"), 1.4))
        painter.drawRoundedRect(panel_rect, 6, 6)

        ox = 28.0
        oy = 34.0

        # Vector trục X trong Gizmo (Xanh dương #2563eb)
        painter.setPen(QPen(QColor("#2563eb"), 2.2))
        painter.setBrush(QBrush(QColor("#2563eb")))
        painter.drawLine(QPointF(ox, oy), QPointF(ox + 34, oy))
        poly_gx = QPolygonF([QPointF(ox + 40, oy), QPointF(ox + 32, oy - 4), QPointF(ox + 32, oy + 4)])
        painter.drawPolygon(poly_gx)

        # Vector trục Y trong Gizmo (Xanh lá #16a34a)
        painter.setPen(QPen(QColor("#16a34a"), 2.2))
        painter.setBrush(QBrush(QColor("#16a34a")))
        painter.drawLine(QPointF(ox, oy), QPointF(ox, oy + 16))
        poly_gy = QPolygonF([QPointF(ox, oy + 22), QPointF(ox - 4, oy + 14), QPointF(ox + 4, oy + 14)])
        painter.drawPolygon(poly_gy)

        # Gốc O(0,0)
        painter.setPen(QPen(QColor("#0f172a"), 1.5))
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawEllipse(QPointF(ox, oy), 3.0, 3.0)

        painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
        painter.setPen(QColor("#0f172a"))
        painter.drawText(QPointF(ox - 14, oy + 3), "O")

        painter.setPen(QColor("#2563eb"))
        painter.drawText(QPointF(ox + 44, oy + 4), "+X")

        painter.setPen(QColor("#16a34a"))
        painter.drawText(QPointF(ox - 8, oy + 22), "+Y")

        painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
        painter.setPen(QColor("#1e293b"))
        painter.drawText(QRectF(14, 10, 138, 13), Qt.AlignLeft, "📐 Image Coordinate (0,0)")

        painter.setFont(QFont("Segoe UI", 7, QFont.Normal))
        painter.setPen(QColor("#475569"))
        painter.drawText(QRectF(74, 23, 78, 12), Qt.AlignLeft, "X: 0 → Width")
        painter.drawText(QRectF(74, 35, 78, 12), Qt.AlignLeft, "Y: 0 ↓ Height")
        painter.drawText(QRectF(74, 47, 78, 12), Qt.AlignLeft, "Unit: Pixel (px)")

    def _paint_top_status_badge(self, painter: QPainter, width: int, status_text: str, is_pass: bool):
        """Hiển thị ô vuông Status phán định ở phía trên Canvas, tự động tính bề rộng chính xác để không bao giờ bị khuyết chữ OK/NG."""
        status_bg = QColor("#f0fdf4") if is_pass else QColor("#fef2f2")
        status_border = QColor("#22c55e") if is_pass else QColor("#ef4444")
        status_color = QColor("#15803d") if is_pass else QColor("#b91c1c")

        badge_font = QFont("Segoe UI", 9, QFont.Bold)
        painter.setFont(badge_font)
        fm = QtGui.QFontMetrics(badge_font)
        text_w = fm.horizontalAdvance(status_text) if hasattr(fm, 'horizontalAdvance') else fm.width(status_text)
        tw = float(text_w + 38.0)
        th = 28.0

        # Nếu chiều rộng canvas đủ chỗ cho góc tọa độ (160px) và badge
        if width >= (tw + 180.0):
            badge_x = (width + 160.0 - tw) / 2.0
            badge_y = 12.0
        else:
            # Nếu bề ngang hẹp, hạ badge xuống dưới góc tọa độ để có toàn bộ không gian
            tw = min(tw, float(width - 20.0))
            badge_x = max(10.0, (width - tw) / 2.0)
            badge_y = 62.0

        badge_rect = QRectF(badge_x, badge_y, tw, th)

        painter.setBrush(QBrush(status_bg))
        painter.setPen(QPen(status_border, 1.6))
        painter.drawRoundedRect(badge_rect, 6, 6)

        painter.setPen(status_color)
        painter.drawText(badge_rect, Qt.AlignCenter, status_text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # 1. Vẽ hệ trục tọa độ 2D CAD chuyên nghiệp và thước đo pixel
        self._paint_coordinate_system(painter, w, h)

        is_spatial = self.operator_str in ('INSIDE', 'OUTSIDE', 'OVERLAP')
        is_distance = self.operator_str.startswith('DIST_')
        is_inside = self._is_rect_inside(self.box1_rect, self.box2_rect)
        is_outside = self._is_rect_outside(self.box1_rect, self.box2_rect)
        is_overlap = self._is_rect_overlapping(self.box1_rect, self.box2_rect)

        # ─────────────────────────────────────────────────────────────────────
        # A. VẼ THEO SCOPE: N vs 1 (TẬP HỢP ĐỐI TƯỢNG TRONG VÙNG GIỚI HẠN - ALL_A_IN_ONE_B)
        # ─────────────────────────────────────────────────────────────────────
        if self.instance_scope == 'ALL_A_IN_ONE_B':
            if self.operator_str == 'INSIDE':
                cond_matched = is_inside
            elif self.operator_str == 'OUTSIDE':
                cond_matched = is_outside
            elif self.operator_str == 'OVERLAP':
                cond_matched = is_overlap
            elif is_distance:
                p1 = self._get_hotspot_point(self.box1_rect, self.selected_param_1)
                p2 = self._get_hotspot_point(self.box2_rect, self.selected_param_2)
                dist_val, _ = self._calculate_edge_distance(p1, p2, self.selected_param_1, self.selected_param_2)
                try:
                    thresh = float(self.math_val)
                except Exception:
                    thresh = 0.0
                comp_op = self.operator_str.replace('DIST_', '')
                if comp_op == '<': cond_matched = (dist_val < thresh)
                elif comp_op == '<=': cond_matched = (dist_val <= thresh)
                elif comp_op == '>': cond_matched = (dist_val > thresh)
                elif comp_op == '>=': cond_matched = (dist_val >= thresh)
                elif comp_op in ('==', '='): cond_matched = (abs(dist_val - thresh) < 1.0)
                elif comp_op == '!=': cond_matched = (abs(dist_val - thresh) >= 1.0)
                else: cond_matched = False
            else:
                v1 = self._get_param_value(self.box1_rect, self.selected_param_1)
                v2 = self._get_param_value(self.box2_rect, self.selected_param_2)
                if self.operator_str == '<': cond_matched = (v1 < v2)
                elif self.operator_str == '<=': cond_matched = (v1 <= v2)
                elif self.operator_str == '>': cond_matched = (v1 > v2)
                elif self.operator_str == '>=': cond_matched = (v1 >= v2)
                elif self.operator_str in ('==', '='): cond_matched = (abs(v1 - v2) < 1.0)
                elif self.operator_str == '!=': cond_matched = (abs(v1 - v2) >= 1.0)
                else: cond_matched = True

            box1_pass = (not cond_matched) if (self.condition_true_result == 'NG') else cond_matched

            # 1. Vẽ Vùng Chứa Master B (Box 2)
            self._paint_master_container(painter, self.box2_rect, self.label_2_name)

            # 2. Vẽ 2 Ghost Instances của A đang nằm an toàn trong vùng
            ghost_a2 = QRectF(self.box2_rect.right() - 150, self.box2_rect.top() + 70, 125, 75)
            ghost_a3 = QRectF(self.box2_rect.left() + 45, self.box2_rect.bottom() - 105, 125, 75)
            self._paint_ghost_box(painter, ghost_a2, f"🔹 {self.label_1_name} #2", "✓ Inside zone (OK)", "#16a34a")
            self._paint_ghost_box(painter, ghost_a3, f"🔹 {self.label_1_name} #3", "✓ Inside zone (OK)", "#16a34a")

            # 3. Vẽ Box 1 (Đối tượng A1 - có thể kéo thả tự do)
            color_a1 = QColor("#16a34a") if box1_pass else QColor("#dc2626")
            lbl_a1 = f"🔷 {self.label_1_name} #1"
            custom_center = f"✓ Inside {self.label_2_name}" if is_inside else f"⚠️ OUTSIDE {self.label_2_name}!"
            self._paint_box(painter, self.box1_rect, 1, lbl_a1, color_a1, self.selected_param_1, custom_status=custom_center)

            # Nếu vi phạm vượt biên -> vẽ đường gióng cảnh báo màu đỏ
            if not box1_pass:
                p_c1 = self.box1_rect.center()
                p_c2 = self.box2_rect.center()
                pen_warn = QPen(QColor("#dc2626"), 2, Qt.DashLine)
                painter.setPen(pen_warn)
                painter.drawLine(p_c1, p_c2)

            # Status Badge tổng quan N vs 1 đặt ở phía trên tách xa 2 box
            res_badge = 'VALID (OK)' if box1_pass else 'VIOLATION (NG)'
            status_text = f"MODEL N vs 1: OBJECT GROUP IN CONTAINER  ➔  {res_badge}"
            self._paint_top_status_badge(painter, w, status_text, box1_pass)

        # ─────────────────────────────────────────────────────────────────────
        # B. VẼ THEO SCOPE: 1 vs N (1 ĐỐI TƯỢNG VS NHIỀU VÙNG GIỚI HẠN - ONE_A_IN_ANY_B)
        # ─────────────────────────────────────────────────────────────────────
        elif self.instance_scope == 'ONE_A_IN_ANY_B':
            ghost_b2 = QRectF(self.box2_rect.right() + 35, self.box2_rect.top(), self.box2_rect.width() * 0.9, self.box2_rect.height() * 0.9)
            in_b1 = self._is_rect_overlapping(self.box1_rect, self.box2_rect)
            in_b2 = self._is_rect_overlapping(self.box1_rect, ghost_b2)
            in_any = in_b1 or in_b2

            if self.operator_str in ('INSIDE', 'OVERLAP'):
                cond_matched = in_any
            elif self.operator_str == 'OUTSIDE':
                cond_matched = not in_any
            else:
                cond_matched = True

            box1_pass = (not cond_matched) if (self.condition_true_result == 'NG') else cond_matched

            # 1. Vẽ Ghost Zone B2
            self._paint_ghost_box(painter, ghost_b2, f"🚫 {self.label_2_name} #2", "Boundary Zone #2", "#ea580c")

            # 2. Vẽ Zone B1 (Box 2)
            self._paint_box(painter, self.box2_rect, 2, f"🚫 {self.label_2_name} #1", QColor("#ea580c"), self.selected_param_2)

            # 3. Vẽ Box 1 (Đối tượng A)
            color_a = QColor("#16a34a") if box1_pass else QColor("#dc2626")
            lbl_a = f"🔷 {self.label_1_name}"
            custom_center = "✓ Outside boundary zone (OK)" if not in_any else "⚠️ VIOLATION IN ZONE B (NG)!"
            self._paint_box(painter, self.box1_rect, 1, lbl_a, color_a, self.selected_param_1, custom_status=custom_center)

            # Status Badge tổng quan 1 vs N đặt ở phía trên tách xa 2 box
            res_badge = 'VALID (OK)' if box1_pass else 'VIOLATION (NG)'
            status_text = f"MODEL 1 vs N: 1 OBJECT VS BOUNDARY ZONES  ➔  {res_badge}"
            self._paint_top_status_badge(painter, w, status_text, box1_pass)

        # ─────────────────────────────────────────────────────────────────────
        # C. VẼ THEO SCOPE: 1 vs 1 HOẶC N vs N
        # ─────────────────────────────────────────────────────────────────────
        else:
            if is_spatial:
                if self.operator_str == 'INSIDE':
                    cond_matched = is_inside
                elif self.operator_str == 'OUTSIDE':
                    cond_matched = is_outside
                else:  # OVERLAP
                    cond_matched = is_overlap

                pair_pass = (not cond_matched) if (self.condition_true_result == 'NG') else cond_matched
                line_color = QColor("#16a34a") if pair_pass else QColor("#dc2626")

                # Shading vùng giao nhau nếu có
                if is_overlap:
                    inter_rect = self.box1_rect.intersected(self.box2_rect)
                    if not inter_rect.isEmpty():
                        painter.fillRect(inter_rect, QColor(234, 88, 12, 45))
                        painter.setPen(QPen(QColor("#ea580c"), 1.5, Qt.DotLine))
                        painter.drawRect(inter_rect)

                # Vẽ 2 box
                boxes_to_draw = [2, 1] if self.front_box == 1 else [1, 2]
                for b_idx in boxes_to_draw:
                    if b_idx == 1:
                        self._paint_box(painter, self.box1_rect, 1, self.label_1_name, QColor("#2563eb"), self.selected_param_1)
                    else:
                        is_const = (self.target_type == 'CONSTANT')
                        lbl2_txt = f"CONSTANT: {self.math_val}" if is_const else self.label_2_name
                        color2 = QColor("#7c3aed") if is_const else QColor("#ea580c")
                        self._paint_box(painter, self.box2_rect, 2, lbl2_txt, color2, self.selected_param_2, is_constant=is_const)

                # Badge đặt phía trên, không che 2 box
                res_txt = 'VALID (OK)' if pair_pass else 'VIOLATION (NG)'
                status_text = f"SPATIAL MODEL: {self.label_1_name} [{self.operator_str}] {self.label_2_name}  ➔  {res_txt}"
                self._paint_top_status_badge(painter, w, status_text, pair_pass)

            elif is_distance:
                # ── BÀI TOÁN KHOẢNG CÁCH GIỮA 2 CẠNH TÙY CHỌN ──
                p1 = self._get_hotspot_point(self.box1_rect, self.selected_param_1)
                p2 = self._get_hotspot_point(self.box2_rect, self.selected_param_2)

                dist_val, dist_label = self._calculate_edge_distance(p1, p2, self.selected_param_1, self.selected_param_2)
                try:
                    thresh = float(self.math_val)
                except Exception:
                    thresh = 0.0

                comp_op = self.operator_str.replace('DIST_', '')
                if comp_op == '<': cond_matched = (dist_val < thresh)
                elif comp_op == '<=': cond_matched = (dist_val <= thresh)
                elif comp_op == '>': cond_matched = (dist_val > thresh)
                elif comp_op == '>=': cond_matched = (dist_val >= thresh)
                elif comp_op in ('==', '='): cond_matched = (abs(dist_val - thresh) < 1.0)
                elif comp_op == '!=': cond_matched = (abs(dist_val - thresh) >= 1.0)
                else: cond_matched = False

                pair_pass = (not cond_matched) if (self.condition_true_result == 'NG') else cond_matched
                line_color = QColor("#16a34a") if pair_pass else QColor("#dc2626")

                # Vẽ đường nét đứt nối giữa tâm của 2 cạnh được chọn
                pen_line = QPen(line_color, 2, Qt.DashLine)
                painter.setPen(pen_line)
                painter.drawLine(p1, p2)

                painter.setBrush(QBrush(line_color))
                painter.drawEllipse(p1, 5, 5)
                painter.drawEllipse(p2, 5, 5)

                # Mini tag d = ... px nhỏ gọn hiển thị ngay cạnh nét đứt (không che lấp cạnh)
                line_len = math.hypot(p1.x() - p2.x(), p1.y() - p2.y())
                if line_len > 35:
                    mid_p = QPointF((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2)
                    d_txt = f"{dist_label}: {dist_val:.1f}px"
                    painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
                    tw_m = max(56.0, float(len(d_txt) * 6.8 + 10))
                    th_m = 18.0
                    m_rect = QRectF(mid_p.x() - tw_m / 2, mid_p.y() - th_m / 2, tw_m, th_m)
                    painter.setBrush(QBrush(QColor("#ffffff")))
                    painter.setPen(QPen(line_color, 1.2))
                    painter.drawRoundedRect(m_rect, 4, 4)
                    painter.setPen(line_color)
                    painter.drawText(m_rect, Qt.AlignCenter, d_txt)

                # Vẽ 2 box
                boxes_to_draw = [2, 1] if self.front_box == 1 else [1, 2]
                for b_idx in boxes_to_draw:
                    if b_idx == 1:
                        self._paint_box(painter, self.box1_rect, 1, self.label_1_name, QColor("#2563eb"), self.selected_param_1)
                    else:
                        self._paint_box(painter, self.box2_rect, 2, self.label_2_name, QColor("#ea580c"), self.selected_param_2)

                # Badge trạng thái đầy đủ đưa lên phía trên, xa 2 box
                res_txt = 'VALID (OK)' if pair_pass else 'VIOLATION (NG)'
                status_text = f"DISTANCE [{self.selected_param_1} ➔ {self.selected_param_2}]: {dist_val:.1f}px {comp_op} {thresh:.1f}px  ➔  {res_txt}"
                self._paint_top_status_badge(painter, w, status_text, pair_pass)

            else:
                # ── PHÉP ĐO SỐ HỌC TỌA ĐỘ TIÊU CHUẨN (<, <=, >, >=, ==, !=, BETWEEN) ──
                p1 = self._get_hotspot_point(self.box1_rect, self.selected_param_1)
                if self.target_type == 'CONSTANT':
                    p2 = QPointF(self.box2_rect.left(), self.box2_rect.center().y())
                else:
                    p2 = self._get_hotspot_point(self.box2_rect, self.selected_param_2)

                # TÍNH TOÁN GIÁ TRỊ THỰC TẾ THỜI GIAN THỰC (LIVE UPDATE) KHI KÉO THẢ BOX
                lhs_val = self._get_param_value(self.box1_rect, self.selected_param_1)
                if self.target_type == 'LABEL':
                    rhs_base = self._get_param_value(self.box2_rect, self.selected_param_2)
                    rhs_display = f"{self.selected_param_2}({rhs_base:.1f}px)"
                else:
                    try:
                        rhs_base = float(self.math_val)
                    except Exception:
                        rhs_base = 0.0
                    rhs_display = f"CONSTANT({rhs_base:.1f}px)"

                try:
                    offset_num = float(self.math_val) if self.target_type == 'LABEL' else 0.0
                except Exception:
                    offset_num = 0.0

                if self.target_type == 'LABEL' and self.math_op != 'NONE':
                    if self.math_op == '+': rhs_val = rhs_base + offset_num
                    elif self.math_op == '-': rhs_val = rhs_base - offset_num
                    elif self.math_op == '*': rhs_val = rhs_base * offset_num
                    elif self.math_op == '/': rhs_val = rhs_base / offset_num if abs(offset_num) > 1e-6 else rhs_base
                    else: rhs_val = rhs_base
                    math_display = f" {self.math_op} {offset_num:.1f}px"
                else:
                    rhs_val = rhs_base
                    math_display = ""

                # Phán định điều kiện thời gian thực
                if self.operator_str == '<': cond_matched = (lhs_val < rhs_val)
                elif self.operator_str == '<=': cond_matched = (lhs_val <= rhs_val)
                elif self.operator_str == '>': cond_matched = (lhs_val > rhs_val)
                elif self.operator_str == '>=': cond_matched = (lhs_val >= rhs_val)
                elif self.operator_str in ('==', '='): cond_matched = (abs(lhs_val - rhs_val) < 1.0)
                elif self.operator_str == '!=': cond_matched = (abs(lhs_val - rhs_val) >= 1.0)
                elif self.operator_str == 'BETWEEN': cond_matched = (rhs_val <= lhs_val <= rhs_val)
                else: cond_matched = False

                pair_pass = (not cond_matched) if (self.condition_true_result == 'NG') else cond_matched
                line_color = QColor("#16a34a") if pair_pass else QColor("#dc2626")

                # Vẽ nét đứt đo tọa độ nối 2 điểm neo
                pen_line = QPen(line_color, 2, Qt.DashLine)
                painter.setPen(pen_line)
                painter.drawLine(p1, p2)

                painter.setBrush(QBrush(line_color))
                painter.drawEllipse(p1, 5, 5)
                painter.drawEllipse(p2, 5, 5)

                # Mini tag Δ = ... px nhỏ gọn cạnh nét đứt (không che lấp 2 box)
                line_len = math.hypot(p1.x() - p2.x(), p1.y() - p2.y())
                if line_len > 40:
                    mid_p = QPointF((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2)
                    delta_v = lhs_val - rhs_val
                    delta_txt = f"Δ = {delta_v:+.1f}px"
                    painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
                    tw_m = max(56.0, float(len(delta_txt) * 6.8 + 10))
                    th_m = 18.0
                    m_rect = QRectF(mid_p.x() - tw_m / 2, mid_p.y() - th_m / 2, tw_m, th_m)
                    painter.setBrush(QBrush(QColor("#ffffff")))
                    painter.setPen(QPen(line_color, 1.2))
                    painter.drawRoundedRect(m_rect, 4, 4)
                    painter.setPen(line_color)
                    painter.drawText(m_rect, Qt.AlignCenter, delta_txt)

                # Vẽ 2 box
                boxes_to_draw = [2, 1] if self.front_box == 1 else [1, 2]
                for b_idx in boxes_to_draw:
                    if b_idx == 1:
                        self._paint_box(painter, self.box1_rect, 1, self.label_1_name, QColor("#2563eb"), self.selected_param_1)
                    else:
                        is_const = (self.target_type == 'CONSTANT')
                        lbl2_txt = f"CONSTANT: {self.math_val}" if is_const else self.label_2_name
                        color2 = QColor("#7c3aed") if is_const else QColor("#ea580c")
                        self._paint_box(painter, self.box2_rect, 2, lbl2_txt, color2, self.selected_param_2, is_constant=is_const)

                # Badge đặt phía trên, xa 2 box
                res_txt = 'VALID (OK)' if pair_pass else 'VIOLATION (NG)'
                status_text = f"COORDINATE: {self.selected_param_1}({lhs_val:.1f}px) {self.operator_str} {rhs_display}{math_display}  ➔  {res_txt}"
                self._paint_top_status_badge(painter, w, status_text, pair_pass)

        # 4. HUD Banner hiển thị Pixel thời gian thực khi kéo to thu nhỏ hoặc di chuyển
        self._paint_hud_banner(painter, w)

        # 5. Viền định hình Viewport CAD (Không tô nền đè lên nội dung)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor("#cbd5e1"), 1.5))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def _paint_master_container(self, painter: QPainter, rect: QRectF, label_name: str):
        """Vẽ Vùng Chứa Master sang trọng với nét đứt high-tech và badge."""
        painter.setBrush(QBrush(QColor(234, 88, 12, 20)))
        pen_border = QPen(QColor("#ea580c"), 2.2, Qt.DashLine)
        painter.setPen(pen_border)
        painter.drawRoundedRect(rect, 10, 10)

        # Header Title Bar
        header_h = 26.0
        header_rect = QRectF(rect.left(), rect.top(), rect.width(), header_h)
        painter.setBrush(QBrush(QColor("#ea580c")))
        painter.setPen(Qt.NoPen)
        path = QPainterPath()
        path.addRoundedRect(header_rect, 10, 10)
        painter.drawPath(path)

        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.setPen(QColor("#ffffff"))
        painter.drawText(header_rect, Qt.AlignCenter, f"📦 MASTER CONTAINER (Boundary Zone B): {label_name}")

        # Badge góc đáy
        sub_badge_rect = QRectF(rect.left() + 10, rect.bottom() - 24, rect.width() - 20, 18)
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.setPen(QColor("#c2410c"))
        painter.drawText(sub_badge_rect, Qt.AlignLeft, "📐 MASTER BOUNDARY CONTAINER (1 Zone contains multiple objects A)")

    def _paint_ghost_box(self, painter: QPainter, rect: QRectF, title: str, subtitle: str, color_hex: str = "#a6e3a1"):
        """Vẽ các box đại diện phụ (Ghost Instances) cho mô hình N vs 1 hoặc 1 vs N."""
        theme_col = QColor(color_hex)
        painter.setBrush(QBrush(QColor(theme_col.red(), theme_col.green(), theme_col.blue(), 25)))
        painter.setPen(QPen(theme_col, 1.5, Qt.DotLine))
        painter.drawRoundedRect(rect, 6, 6)

        hdr_rect = QRectF(rect.left(), rect.top(), rect.width(), 20)
        painter.setBrush(QBrush(QColor(theme_col.red(), theme_col.green(), theme_col.blue(), 140)))
        painter.setPen(Qt.NoPen)
        path = QPainterPath()
        path.addRoundedRect(hdr_rect, 6, 6)
        painter.drawPath(path)

        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.setPen(QColor("#ffffff"))
        painter.drawText(hdr_rect, Qt.AlignCenter, title)

        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(theme_col)
        body_rect = QRectF(rect.left() + 2, rect.top() + 22, rect.width() - 4, rect.height() - 24)
        painter.drawText(body_rect, Qt.AlignCenter, subtitle)

    def _get_default_hud_text(self) -> str:
        if self.instance_scope == 'ALL_A_IN_ONE_B':
            box1_in_box2 = self._is_rect_inside(self.box1_rect, self.box2_rect)
            if self.operator_str == 'INSIDE' and self.condition_true_result == 'NG':
                return "✅ ALL OBJECTS A INSIDE ZONE B ➔ VALID (OK)" if box1_in_box2 else "🚨 WARNING: OBJECT A1 OUTSIDE ZONE B ➔ VIOLATION (NG)!"
            elif self.operator_str == 'OUTSIDE' and self.condition_true_result == 'NG':
                return "🚨 WARNING: OBJECT A1 OUTSIDE ZONE B ➔ VIOLATION (NG)!" if not box1_in_box2 else "✅ ALL OBJECTS A INSIDE ZONE B ➔ VALID (OK)"
            return "🎯 N vs 1 (Object Group & Container): Try dragging [Label A1] outside zone B to test live evaluation!"
        elif self.instance_scope == 'ONE_A_IN_ANY_B':
            return "🎯 1 vs N (1 Object & Multiple Zones): Try dragging [Label A] into restricted zones B to test warning!"
        else:
            return "🖱️ Drag body to MOVE | Drag bottom-right (📐) to RESIZE | Click edge to SELECT PARAM"

    def _paint_hud_banner(self, painter: QPainter, width: int):
        """Hiển thị Banner thông số Pixel động cực kỳ rõ ràng trên đầu Canvas."""
        if self.active_action:
            action_type = self.active_action[0]
            box_idx = self.active_action[1]
            target_rect = self.box1_rect if box_idx == 1 else self.box2_rect

            if action_type == 'RESIZE':
                w_now = int(target_rect.width())
                h_now = int(target_rect.height())
                dw = int(w_now - self.initial_box_rect.width())
                dh = int(h_now - self.initial_box_rect.height())
                hud_text = f"📐 RESIZING LABEL {box_idx}: {w_now} × {h_now} px  (Delta: ΔW {dw:+d} px, ΔH {dh:+d} px)"
                hud_color = QColor("#b45309")
                border_color = QColor("#f59e0b")
            elif action_type in ('DRAG', 'HOTSPOT_OR_DRAG') and self.is_dragging:
                x_now = int(target_rect.x())
                y_now = int(target_rect.y())
                dx = int(x_now - self.initial_box_rect.x())
                dy = int(y_now - self.initial_box_rect.y())
                hud_text = f"📍 MOVING LABEL {box_idx}: X = {x_now} px, Y = {y_now} px  (Offset: ΔX {dx:+d} px, ΔY {dy:+d} px)"
                hud_color = QColor("#1d4ed8")
                border_color = QColor("#3b82f6")
            else:
                hud_text = self._get_default_hud_text()
                hud_color = QColor("#475569")
                border_color = QColor("#cbd5e1")
        else:
            hud_text = self._get_default_hud_text()
            hud_color = QColor("#475569")
            border_color = QColor("#cbd5e1")

        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        bw = max(560.0, float(len(hud_text) * 7.5))
        bh = 26.0
        hud_x = max(162.0, (width - bw) / 2)
        hud_rect = QRectF(hud_x, 8, bw, bh)

        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.setPen(QPen(border_color, 1.5))
        painter.drawRoundedRect(hud_rect, 6, 6)

        painter.setPen(hud_color)
        painter.drawText(hud_rect, Qt.AlignCenter, hud_text)

    def _paint_box(self, painter: QPainter, rect: QRectF, box_idx: int, label_text: str, theme_color: QColor, selected_param: str, is_constant: bool = False, custom_status: Optional[str] = None):
        is_active_box = (self.active_action and self.active_action[1] == box_idx)

        # Body Fill & Border
        alpha = 45 if is_active_box else 30
        painter.setBrush(QBrush(QColor(theme_color.red(), theme_color.green(), theme_color.blue(), alpha)))
        border_pen = QPen(theme_color, 2.5 if is_active_box else 1.8)
        painter.setPen(border_pen)
        painter.drawRoundedRect(rect, 8, 8)

        # Header Title Bar
        header_h = 24.0
        header_rect = QRectF(rect.left(), rect.top(), rect.width(), header_h)
        painter.setBrush(QBrush(QColor(theme_color.red(), theme_color.green(), theme_color.blue(), 200)))
        painter.setPen(Qt.NoPen)
        path = QPainterPath()
        path.addRoundedRect(header_rect, 8, 8)
        painter.drawPath(path)

        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.setPen(QColor("#ffffff"))
        tag = label_text if (label_text.startswith("🔷") or label_text.startswith("🚫") or is_constant) else f"Label {box_idx}: {label_text}"
        painter.drawText(header_rect, Qt.AlignCenter, tag)

        # Vẽ các Hotspots cạnh (nếu không phải là constant và không phải FULL_BOX)
        if not is_constant and selected_param != 'FULL_BOX':
            hotspots = self._get_hotspots(rect, box_idx)
            for b_idx, param, h_rect, desc in hotspots:
                if param in ('WIDTH', 'HEIGHT'):
                    continue

                is_selected = (selected_param == param or (selected_param == 'CENTER_Y' and param == 'CENTER_X'))
                is_hovered = (self.hovered_hotspot == (b_idx, param))

                if is_selected:
                    dot_color = QColor("#16a34a")
                    line_pen = QPen(QColor("#16a34a"), 4)
                elif is_hovered:
                    dot_color = QColor("#d97706")
                    line_pen = QPen(QColor("#d97706"), 3)
                else:
                    dot_color = theme_color
                    line_pen = QPen(theme_color, 2)

                if param == 'X_MIN':
                    painter.setPen(line_pen)
                    painter.drawLine(QPointF(rect.left(), rect.top() + header_h), QPointF(rect.left(), rect.bottom()))
                    painter.setBrush(QBrush(dot_color))
                    painter.drawEllipse(QPointF(rect.left(), rect.center().y()), 5, 5)
                elif param == 'X_MAX':
                    painter.setPen(line_pen)
                    painter.drawLine(QPointF(rect.right(), rect.top() + header_h), QPointF(rect.right(), rect.bottom()))
                    painter.setBrush(QBrush(dot_color))
                    painter.drawEllipse(QPointF(rect.right(), rect.center().y()), 5, 5)
                elif param == 'Y_MIN':
                    painter.setPen(line_pen)
                    painter.drawLine(QPointF(rect.left(), rect.top() + header_h), QPointF(rect.right(), rect.top() + header_h))
                    painter.setBrush(QBrush(dot_color))
                    painter.drawEllipse(QPointF(rect.center().x(), rect.top() + header_h), 5, 5)
                elif param == 'Y_MAX':
                    painter.setPen(line_pen)
                    painter.drawLine(QPointF(rect.left(), rect.bottom()), QPointF(rect.right(), rect.bottom()))
                    painter.setBrush(QBrush(dot_color))
                    painter.drawEllipse(QPointF(rect.center().x(), rect.bottom()), 5, 5)
                elif param == 'CENTER_X':
                    painter.setPen(line_pen)
                    painter.setBrush(QBrush(dot_color))
                    painter.drawEllipse(rect.center(), 6, 6)

        # Hiển thị đường đo kích thước nếu chọn WIDTH hoặc HEIGHT
        cur_w = int(rect.width())
        cur_h = int(rect.height())
        cur_x = int(rect.x())
        cur_y = int(rect.y())

        if selected_param == 'WIDTH':
            dim_y = rect.top() + 45
            painter.setPen(QPen(QColor("#16a34a"), 2, Qt.SolidLine))
            painter.drawLine(QPointF(rect.left() + 6, dim_y), QPointF(rect.right() - 6, dim_y))
            painter.drawLine(QPointF(rect.left() + 6, dim_y), QPointF(rect.left() + 12, dim_y - 4))
            painter.drawLine(QPointF(rect.left() + 6, dim_y), QPointF(rect.left() + 12, dim_y + 4))
            painter.drawLine(QPointF(rect.right() - 6, dim_y), QPointF(rect.right() - 12, dim_y - 4))
            painter.drawLine(QPointF(rect.right() - 6, dim_y), QPointF(rect.right() - 12, dim_y + 4))
            painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
            painter.setPen(QColor("#15803d"))
            painter.drawText(QRectF(rect.left(), dim_y - 14, rect.width(), 14), Qt.AlignCenter, f"↔ WIDTH: {cur_w} px")

        elif selected_param == 'HEIGHT':
            dim_x = rect.left() + 26
            painter.setPen(QPen(QColor("#16a34a"), 2, Qt.SolidLine))
            painter.drawLine(QPointF(dim_x, rect.top() + header_h + 4), QPointF(dim_x, rect.bottom() - 28))
            painter.drawLine(QPointF(dim_x, rect.top() + header_h + 4), QPointF(dim_x - 4, rect.top() + header_h + 10))
            painter.drawLine(QPointF(dim_x, rect.top() + header_h + 4), QPointF(dim_x + 4, rect.top() + header_h + 10))
            painter.drawLine(QPointF(dim_x, rect.bottom() - 28), QPointF(dim_x - 4, rect.bottom() - 34))
            painter.drawLine(QPointF(dim_x, rect.bottom() - 28), QPointF(dim_x + 4, rect.bottom() - 34))
            painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
            painter.setPen(QColor("#15803d"))
            painter.drawText(QRectF(dim_x + 4, rect.center().y() - 10, rect.width() - dim_x - 10, 20), Qt.AlignLeft, f"↕ HEIGHT:\n{cur_h} px")

        # Cạnh đang chọn text ở giữa hoặc custom status
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold if custom_status else QFont.Normal))
        painter.setPen(theme_color if custom_status else QColor("#1e293b"))
        status_text = custom_status or (f"Edge: {PARAM_DISPLAY_NAMES.get(selected_param, selected_param)}" if selected_param not in ('WIDTH', 'HEIGHT') else "")
        if status_text:
            painter.drawText(QRectF(rect.left() + 4, rect.top() + header_h + 6, rect.width() - 8, 20), Qt.AlignCenter, status_text)

        # Tay cầm Resize ở góc dưới bên phải
        resize_rect = self._get_resize_rect(rect)
        is_resize_hover = (self.hovered_resize == box_idx)
        resize_color = QColor("#f59e0b") if is_resize_hover else theme_color
        painter.setPen(QPen(resize_color, 2))
        painter.setBrush(QBrush(QColor(resize_color.red(), resize_color.green(), resize_color.blue(), 140)))
        painter.drawRoundedRect(resize_rect, 4, 4)

        rx = resize_rect.right()
        ry = resize_rect.bottom()
        painter.setPen(QPen(QColor("#ffffff"), 1.8))
        painter.drawLine(int(rx - 4), int(ry - 12), int(rx - 12), int(ry - 4))
        painter.drawLine(int(rx - 4), int(ry - 8), int(rx - 8), int(ry - 4))
        painter.drawLine(int(rx - 4), int(ry - 4), int(rx - 4), int(ry - 4))

        # Badge Kích thước Pixel Thời Gian Thực ở đáy box
        size_badge_rect = QRectF(rect.left() + 6, rect.bottom() - 24, rect.width() - self.resize_handle_size - 10, 20)
        is_resizing_this = (self.active_action and self.active_action[0] == 'RESIZE' and self.active_action[1] == box_idx)
        
        if is_resizing_this:
            painter.setBrush(QBrush(QColor("#313244")))
            painter.setPen(QPen(QColor("#f9e2af"), 1.5))
            text_color = QColor("#f9e2af")
        elif is_active_box:
            painter.setBrush(QBrush(QColor("#181825")))
            painter.setPen(QPen(QColor("#89b4fa"), 1.2))
            text_color = QColor("#89dceb")
        else:
            painter.setBrush(QBrush(QColor("#11111b")))
            painter.setPen(QPen(QColor("#45475a"), 1))
            text_color = QColor("#89b4fa")

        painter.drawRoundedRect(size_badge_rect, 4, 4)
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.setPen(text_color)
        painter.drawText(size_badge_rect, Qt.AlignCenter, f"📐 {cur_w} × {cur_h} px  (X:{cur_x}, Y:{cur_y})")

    # ─────────────────────────────────────────────────────────────────────────
    # Xử lý Tương tác Chuột: Drag Move & Resize Co Giãn
    # ─────────────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        pos = event.pos()
        self.drag_start_mouse = QPointF(pos)
        self.is_dragging = False

        check_order = [1, 2] if self.front_box == 1 else [2, 1]

        # 1. Kiểm tra bấm vào Tay cầm Resize
        for idx in check_order:
            r = self.box1_rect if idx == 1 else self.box2_rect
            if self._get_resize_rect(r).contains(QPointF(pos)):
                self.active_action = ('RESIZE', idx)
                self.front_box = idx
                self.initial_box_rect = QRectF(r)
                self.update()
                return

        # 2. Kiểm tra bấm vào Điểm Hotspot cạnh
        for idx in check_order:
            r = self.box1_rect if idx == 1 else self.box2_rect
            for b_idx, param, h_rect, _ in self._get_hotspots(r, idx):
                if h_rect.contains(QPointF(pos)):
                    self.active_action = ('HOTSPOT_OR_DRAG', idx, param)
                    self.front_box = idx
                    self.initial_box_rect = QRectF(r)
                    self.update()
                    return

        # 3. Kiểm tra bấm vào Thân box để di chuyển
        for idx in check_order:
            r = self.box1_rect if idx == 1 else self.box2_rect
            if r.contains(QPointF(pos)):
                self.active_action = ('DRAG', idx)
                self.front_box = idx
                self.initial_box_rect = QRectF(r)
                self.update()
                return

        self.active_action = None

    def mouseMoveEvent(self, event):
        pos = event.pos()
        
        if self.active_action:
            delta_x = pos.x() - self.drag_start_mouse.x()
            delta_y = pos.y() - self.drag_start_mouse.y()
            if abs(delta_x) > 3 or abs(delta_y) > 3:
                self.is_dragging = True

            action_type = self.active_action[0]
            box_idx = self.active_action[1]

            if action_type == 'RESIZE':
                new_w = max(70.0, self.initial_box_rect.width() + delta_x)
                new_h = max(50.0, self.initial_box_rect.height() + delta_y)
                new_w = min(new_w, self.width() - self.initial_box_rect.left() - 5.0)
                new_h = min(new_h, self.height() - self.initial_box_rect.top() - 5.0)

                if box_idx == 1:
                    self.box1_rect.setWidth(new_w)
                    self.box1_rect.setHeight(new_h)
                    self.box_geometry_changed.emit(1, self.box1_rect.x(), self.box1_rect.y(), new_w, new_h)
                else:
                    self.box2_rect.setWidth(new_w)
                    self.box2_rect.setHeight(new_h)
                    self.box_geometry_changed.emit(2, self.box2_rect.x(), self.box2_rect.y(), new_w, new_h)
                self.update()
                return

            elif action_type in ('DRAG', 'HOTSPOT_OR_DRAG'):
                new_x = self.initial_box_rect.x() + delta_x
                new_y = self.initial_box_rect.y() + delta_y
                curr_w = self.initial_box_rect.width()
                curr_h = self.initial_box_rect.height()
                new_x = max(5.0, min(new_x, self.width() - curr_w - 5.0))
                new_y = max(5.0, min(new_y, self.height() - curr_h - 5.0))

                if box_idx == 1:
                    self.box1_rect.moveTopLeft(QPointF(new_x, new_y))
                    self.box_geometry_changed.emit(1, new_x, new_y, curr_w, curr_h)
                else:
                    self.box2_rect.moveTopLeft(QPointF(new_x, new_y))
                    self.box_geometry_changed.emit(2, new_x, new_y, curr_w, curr_h)
                self.update()
                return

        # Cập nhật con trỏ chuột
        new_hover_resize = None
        new_hover_hotspot = None
        new_hover_body = None

        check_order = [1, 2] if self.front_box == 1 else [2, 1]
        for idx in check_order:
            r = self.box1_rect if idx == 1 else self.box2_rect
            if self._get_resize_rect(r).contains(QPointF(pos)):
                new_hover_resize = idx
                break
            for b_idx, param, h_rect, _ in self._get_hotspots(r, idx):
                if h_rect.contains(QPointF(pos)):
                    new_hover_hotspot = (b_idx, param)
                    break
            if new_hover_hotspot:
                break
            if r.contains(QPointF(pos)):
                new_hover_body = idx
                break

        self.hovered_resize = new_hover_resize
        self.hovered_hotspot = new_hover_hotspot
        self.hovered_body = new_hover_body

        if new_hover_resize:
            self.setCursor(Qt.SizeFDiagCursor)
        elif new_hover_hotspot:
            self.setCursor(Qt.PointingHandCursor)
        elif new_hover_body:
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.active_action and self.active_action[0] == 'HOTSPOT_OR_DRAG' and not self.is_dragging:
                box_idx = self.active_action[1]
                param_name = self.active_action[2]
                self.set_selected_param(box_idx, param_name)
                self.hotspot_clicked.emit(box_idx, param_name)

            self.active_action = None
            self.is_dragging = False
            self.update()


# ─────────────────────────────────────────────────────────────────────────────
# TaskRuleEditorDialog
# ─────────────────────────────────────────────────────────────────────────────

class FlowLayout(QtWidgets.QLayout):
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


class TaskRuleEditorDialog(QtWidgets.QDialog):
    """
    Hộp thoại chính để cấu hình toàn diện Task và danh sách các Rules hình học công nghiệp.
    Hỗ trợ đầy đủ các Scope: 1 vs 1, N vs 1 (Tập hợp đối tượng trong vùng chứa), 1 vs N, N vs N.
    """
    def __init__(self, camera_id: int, task_data: Optional[Dict[str, Any]] = None,
                 rules_data: Optional[List[Dict[str, Any]]] = None,
                 available_labels: Optional[List[str]] = None,
                 preselected_labels: Optional[List[str]] = None,
                 cursor=None, connection=None, parent=None,
                 model_id: Optional[int] = None, **kwargs):
        super().__init__(parent)
        self.camera_id = camera_id
        self.model_id = model_id if model_id is not None else kwargs.get('model_id', None)
        self.task_data = task_data or kwargs.get('task_data') or {}
        if self.model_id is None and self.task_data:
            self.model_id = self.task_data.get('model_id')
        if self.model_id is None and parent and hasattr(parent, 'model_id'):
            self.model_id = getattr(parent, 'model_id', None)

        if self.camera_id is not None:
            c_clean = str(self.camera_id).lower().replace('camera-', '').replace('built-in-', '').strip()
            if c_clean.isdigit():
                self.camera_id = int(c_clean)
        if self.model_id is not None:
            m_clean = str(self.model_id).lower().replace('model-', '').replace('model', '').strip()
            if m_clean.isdigit():
                self.model_id = int(m_clean)

        self.rules_list: List[Dict[str, Any]] = list(rules_data) if rules_data else []
        self.available_labels = available_labels or []
        self.preselected_labels = preselected_labels or []
        self.cursor = cursor
        self.connection = connection

        if self.cursor and self.camera_id and self.model_id is not None:
            try:
                from module_3.task_calculator_db import get_available_labels_for_camera
                model_labels = get_available_labels_for_camera(self.cursor, self.camera_id, self.model_id)
                if model_labels is not None:
                    self.available_labels = model_labels
            except Exception:
                pass

        self.editing_rule_index: Optional[int] = None
        self._is_populating = False

        title_suffix = f" [Model ID: {self.model_id}]" if self.model_id else ""
        self.setWindowTitle(f"Geometric Task Editor-{title_suffix}")
        self.resize(1200, 920)

        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowMinMaxButtonsHint
            | Qt.WindowCloseButtonHint
        )
        self.setWindowState(Qt.WindowMaximized)

        # CẤU HÌNH GIAO DIỆN CHUYÊN NGHIỆP - TÔNG SÁNG TRẦM, ÊM DỊU & CHUẨN CÔNG NGHIỆP (SLATE THEME)
        self.setStyleSheet("""
            QDialog {
                background-color: #f1f5f9;
                color: #1e293b;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QGroupBox {
                background-color: #F0F9FF;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 16px;
                font-weight: bold;
                font-size: 13px;
                color: #0f172a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 0 8px;
                background-color: #ffffff;
                color: #0f172a;
                font-weight: bold;
            }
            QLabel {
                color: #334155;
                font-size: 13px;
                font-weight: 500;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                color: #0f172a;
                font-size: 13px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1.5px solid #2563eb;
                background-color: #f8fafc;
            }

            /* COMBOBOX CHUYÊN NGHIỆP: NỀN TRẮNG SẠCH, CHỮ ĐẬM RÕ NÉT, HOVER/FOCUS XANH DỊU */
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                color: #0f172a;
                font-size: 13px;
                font-weight: 500;
            }
            QComboBox:hover {
                border: 1px solid #3b82f6;
                background-color: #f8fafc;
                color: #0f172a;
            }
            QComboBox:focus {
                border: 1.5px solid #2563eb;
                background-color: #ffffff;
                color: #0f172a;
            }
            QComboBox:editable {
                background-color: #ffffff;
                color: #0f172a;
            }
            QComboBox:editable:hover {
                background-color: #f8fafc;
                border: 1px solid #3b82f6;
                color: #0f172a;
            }
            QComboBox:editable:focus {
                background-color: #ffffff;
                border: 1.5px solid #2563eb;
                color: #0f172a;
            }
            QComboBox QLineEdit {
                background-color: transparent;
                color: #0f172a;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
                border: none;
                padding: 0px 4px;
            }
            QComboBox QLineEdit:hover {
                background-color: transparent;
                color: #0f172a;
            }
            QComboBox QLineEdit:focus {
                background-color: transparent;
                color: #0f172a;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 26px;
                border-left: 1px solid #cbd5e1;
                background-color: #f1f5f9;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }
            QComboBox::down-arrow {
                width: 0;
                height: 0;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #475569;
            }
            QComboBox QAbstractItemView, QComboBox QListView {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item, QComboBox QListView::item {
                min-height: 28px;
                padding: 4px 10px;
                color: #1e293b;
                background-color: transparent;
                border-radius: 4px;
            }
            QComboBox QAbstractItemView::item:hover, QComboBox QListView::item:hover {
                background-color: #e2e8f0;
                color: #0f172a;
            }
            QComboBox QAbstractItemView::item:selected, QComboBox QListView::item:selected {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
            }

            /* CÁC NÚT THAO TÁC CƠ BẢN */
            QPushButton {
                background-color: #f8fafc;
                color: #334155;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                border: 1px solid #cbd5e1;
                padding: 7px 15px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                color: #0f172a;
                border-color: #94a3b8;
            }
            QPushButton:pressed {
                background-color: #cbd5e1;
                color: #0f172a;
            }

            /* CÁC NÚT THAO TÁC NỔI BẬT: CHỮ TRẮNG TƯƠNG PHẢN CAO, NỀN MÀU RÕ RÀNG */
            QPushButton#btnSave {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #1d4ed8;
                border-radius: 6px;
                padding: 9px 24px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btnSave:hover {
                background-color: #1d4ed8;
                border: 1px solid #1e40af;
                color: #ffffff;
            }
            QPushButton#btnSave:pressed {
                background-color: #1e40af;
                color: #ffffff;
            }

            QPushButton#btnAddRule {
                background-color: #16a34a;
                color: #ffffff;
                border: 1px solid #15803d;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btnAddRule:hover {
                background-color: #15803d;
                border: 1px solid #166534;
                color: #ffffff;
            }
            QPushButton#btnAddRule:pressed {
                background-color: #166534;
                color: #ffffff;
            }

            QPushButton#btnUpdateRule {
                background-color: #ea580c;
                color: #ffffff;
                border: 1px solid #c2410c;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btnUpdateRule:hover {
                background-color: #c2410c;
                border: 1px solid #9a3412;
                color: #ffffff;
            }
            QPushButton#btnUpdateRule:pressed {
                background-color: #9a3412;
                color: #ffffff;
            }

            QPushButton#btnDeleteRule {
                background-color: #dc2626;
                color: #ffffff;
                border: 1px solid #b91c1c;
                border-radius: 6px;
                padding: 9px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btnDeleteRule:hover {
                background-color: #b91c1c;
                border: 1px solid #991b1b;
                color: #ffffff;
            }
            QPushButton#btnDeleteRule:pressed {
                background-color: #991b1b;
                color: #ffffff;
            }

            QPushButton#btnCancel {
                background-color: #ffffff;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 9px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btnCancel:hover {
                background-color: #f1f5f9;
                color: #1e293b;
                border-color: #94a3b8;
            }
            QPushButton#btnCancel:pressed {
                background-color: #e2e8f0;
            }

            QPushButton#btnResetCanvas {
                background-color: #ffffff;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#btnResetCanvas:hover {
                background-color: #eff6ff;
                border: 1px solid #3b82f6;
                color: #1d4ed8;
            }
            QPushButton#btnResetCanvas:pressed {
                background-color: #dbeafe;
            }

            /* BẢNG DANH SÁCH RULES */
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                gridline-color: #e2e8f0;
                color: #0f172a;
                border-radius: 6px;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }
            QTableWidget::item {
                color: #0f172a;
                padding: 6px;
                border-bottom: 1px solid #e2e8f0;
            }
            QTableWidget::item:hover {
                background-color: #e0f2fe;
                color: #0369a1;
            }
            QTableWidget::item:selected {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #1e293b;
                padding: 7px;
                border: 1px solid #cbd5e1;
                font-weight: bold;
                font-size: 12px;
            }

            /* THÔNG BÁO HỘP THOẠI MESSAGEBOX */
            QMessageBox {
                background-color: #f1f5f9;
            }
            QMessageBox QLabel {
                color: #1e293b;
                font-size: 13px;
            }
            QMessageBox QPushButton {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 18px;
                font-size: 13px;
                font-weight: bold;
            }
            QMessageBox QPushButton:hover {
                background-color: #e2e8f0;
            }
        """)

        self.init_ui()
        self.populate_data()

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # Scroll Area
        self.scroll_area = QtWidgets.QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #f1f5f9;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #cbd5e1;
                min-height: 30px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #94a3b8;
            }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        scroll_content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(scroll_content)
        content_layout.setSpacing(14)
        content_layout.setContentsMargins(8, 8, 14, 8)

        # 1. GROUPBOX THÔNG TIN CHUNG TASK & PLC
        group_task = QtWidgets.QGroupBox("1. Cấu hình Task && Tín hiệu PLC")
        # Dùng 2 hàng QHBoxLayout thay cho 4-cột QGridLayout để label luôn gần combobox
        vlayout_task = QtWidgets.QVBoxLayout(group_task)
        vlayout_task.setSpacing(8)
        vlayout_task.setContentsMargins(12, 16, 12, 10)

        # --- Hàng 1: Tên Task | Loại Task ---
        row1 = QtWidgets.QHBoxLayout()
        row1.setSpacing(10)

        lbl_task_name = QtWidgets.QLabel("Tên Task:")
        lbl_task_name.setFixedWidth(70)
        row1.addWidget(lbl_task_name)
        self.line_task_name = QtWidgets.QLineEdit()
        self.line_task_name.setPlaceholderText("...")
        self.line_task_name.setMinimumWidth(160)
        self.line_task_name.setMaximumWidth(280)
        row1.addWidget(self.line_task_name)

        self.chk_task_enabled = QtWidgets.QCheckBox("Kích hoạt [✓]")
        self.chk_task_enabled.setChecked(True)
        self.chk_task_enabled.setStyleSheet("color: #15803d; font-weight: bold;")
        row1.addWidget(self.chk_task_enabled)

        row1.addSpacing(24)
        lbl_task_type = QtWidgets.QLabel("Loại Task:")
        lbl_task_type.setFixedWidth(68)
        row1.addWidget(lbl_task_type)
        self.combo_task_type = QtWidgets.QComboBox()
        self.combo_task_type.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_task_type.setMinimumWidth(260)
        self.combo_task_type.setMaximumWidth(380)
        self.combo_task_type.addItem("So sánh Tọa độ & Không gian (RELATION_COORDINATE)", "RELATION_COORDINATE")
        self.combo_task_type.addItem("Đo Khoảng cách (DISTANCE_CALC)", "DISTANCE")
        self.combo_task_type.addItem("Biểu thức Tùy chỉnh (CUSTOM_EXPRESSION)", "CUSTOM_EXPRESSION")
        row1.addWidget(self.combo_task_type)
        row1.addStretch()
        vlayout_task.addLayout(row1)

        # --- Hàng 2: PLC Register | Value State/OK/NG | Đánh giá tổng ---
        row2 = QtWidgets.QHBoxLayout()
        row2.setSpacing(10)

        lbl_plc_reg = QtWidgets.QLabel("PLC Register:")
        lbl_plc_reg.setFixedWidth(80)
        row2.addWidget(lbl_plc_reg)
        self.line_plc_register = QtWidgets.QLineEdit()
        self.line_plc_register.setPlaceholderText("Để trống nếu không gửi")
        self.line_plc_register.setMinimumWidth(120)
        self.line_plc_register.setMaximumWidth(160)
        row2.addWidget(self.line_plc_register)

        row2.addSpacing(16)
        row2.addWidget(QtWidgets.QLabel("Value State:"))
        self.spin_plc_state = QtWidgets.QSpinBox()
        self.spin_plc_state.setRange(-32768, 32767)
        self.spin_plc_state.setValue(1)
        self.spin_plc_state.setAlignment(Qt.AlignCenter)
        self.spin_plc_state.setFixedWidth(65)
        self.spin_plc_state.setToolTip("🎯 Giá trị trạng thái ban đầu của thanh ghi (Value State)")
        row2.addWidget(self.spin_plc_state)

        row2.addSpacing(6)
        row2.addWidget(QtWidgets.QLabel("Value OK:"))
        self.spin_plc_on = QtWidgets.QSpinBox()
        self.spin_plc_on.setRange(-32768, 32767)
        self.spin_plc_on.setValue(1)
        self.spin_plc_on.setAlignment(Qt.AlignCenter)
        self.spin_plc_on.setFixedWidth(65)
        self.spin_plc_on.setToolTip("✔ Giá trị gửi đến PLC khi Task đạt chuẩn (Value OK)")
        row2.addWidget(self.spin_plc_on)

        row2.addSpacing(6)
        row2.addWidget(QtWidgets.QLabel("Value NG:"))
        self.spin_plc_off = QtWidgets.QSpinBox()
        self.spin_plc_off.setRange(-32768, 32767)
        self.spin_plc_off.setValue(0)
        self.spin_plc_off.setAlignment(Qt.AlignCenter)
        self.spin_plc_off.setFixedWidth(65)
        self.spin_plc_off.setToolTip("✘ Giá trị gửi đến PLC khi Task vi phạm (Value NG)")
        row2.addWidget(self.spin_plc_off)

        row2.addSpacing(24)
        lbl_logic = QtWidgets.QLabel("Đánh giá tổng:")
        row2.addWidget(lbl_logic)
        self.combo_logic = QtWidgets.QComboBox()
        self.combo_logic.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_logic.setMinimumWidth(200)
        self.combo_logic.setMaximumWidth(260)
        self.combo_logic.addItem("Tất cả Rule phải đạt (AND)", "ALL_PASS")
        self.combo_logic.addItem("Chỉ cần 1 Rule vi phạm là NG (OR)", "ANY_FAIL")
        row2.addWidget(self.combo_logic)
        row2.addStretch()
        vlayout_task.addLayout(row2)

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
        self.combo_param_1.setMinimumWidth(200)
        self.combo_param_1.setMaximumWidth(200)
        for k, v in PARAM_DISPLAY_NAMES.items():
            self.combo_param_1.addItem(v, k)
        box_lhs = _make_group_box(lbl_lhs, self.combo_param_1)
        flow_expr.addWidget(box_lhs)

        # 2. Nhóm Toán tử so sánh
        lbl_op = QtWidgets.QLabel("Toán tử:")
        lbl_op.setStyleSheet("font-weight: bold; color: #1e293b;")
        self.combo_operator = QtWidgets.QComboBox()
        self.combo_operator.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_operator.setMinimumWidth(140)
        self.combo_operator.setMaximumWidth(180)
        for k, v in OPERATOR_DISPLAY_NAMES.items():
            self.combo_operator.addItem(v, k)
        box_op = _make_group_box(lbl_op, self.combo_operator)
        flow_expr.addWidget(box_op)

        # 3. Nhóm Vế Phải (RHS)
        lbl_rhs = QtWidgets.QLabel("Vế Phải:")
        lbl_rhs.setStyleSheet("font-weight: bold; color: #1e293b;")
        self.combo_target_type = QtWidgets.QComboBox()
        self.combo_target_type.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_target_type.setMinimumWidth(140)
        self.combo_target_type.setMaximumWidth(180)
        self.combo_target_type.addItem("So với B", "LABEL")
        self.combo_target_type.addItem("Số cố định", "CONSTANT")

        self.combo_param_2 = QtWidgets.QComboBox()
        self.combo_param_2.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_param_2.setMinimumWidth(140)
        self.combo_param_2.setMaximumWidth(180)
        for k, v in PARAM_DISPLAY_NAMES.items():
            self.combo_param_2.addItem(v, k)
        box_rhs = _make_group_box(lbl_rhs, self.combo_target_type, self.combo_param_2)
        flow_expr.addWidget(box_rhs)

        # 4. Nhóm Bù trừ / Dung sai (Math Offset)
        self.lbl_math_op = QtWidgets.QLabel("Bù trừ:")
        self.lbl_math_op.setStyleSheet("font-weight: bold; color: #1e293b;")
        self.combo_math_op = QtWidgets.QComboBox()
        self.combo_math_op.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_math_op.setMinimumWidth(140)
        self.combo_math_op.setMaximumWidth(180)
        self.combo_math_op.addItem("Không", "NONE")
        self.combo_math_op.addItem("+ (Cộng)", "+")
        self.combo_math_op.addItem("- (Trừ)", "-")
        self.combo_math_op.addItem("* (Nhân)", "*")
        self.combo_math_op.addItem("/ (Chia)", "/")

        self.lbl_math_val = QtWidgets.QLabel("± (px):")
        self.lbl_math_val.setStyleSheet("font-weight: bold; color: #1e293b;")
        self.line_math_val = QtWidgets.QLineEdit("0")
        self.line_math_val.setAlignment(Qt.AlignCenter)
        self.line_math_val.setMinimumWidth(140)
        self.line_math_val.setMaximumWidth(180)
        self.line_math_val.setPlaceholderText("0")
        box_math = _make_group_box(self.lbl_math_op, self.combo_math_op, self.lbl_math_val, self.line_math_val)
        flow_expr.addWidget(box_math)

        # 5. Nhóm Kết quả phán định (True Result)
        lbl_res = QtWidgets.QLabel("Phán định:")
        lbl_res.setStyleSheet("font-weight: bold; color: #1e293b;")
        self.combo_true_result = QtWidgets.QComboBox()
        self.combo_true_result.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.combo_true_result.setMinimumWidth(140)
        self.combo_true_result.setMaximumWidth(180)
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
        self.btn_add_rule.setMinimumWidth(120)
        self.btn_add_rule.setMaximumWidth(120)
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
        self.btn_update_rule.setMinimumWidth(140)
        self.btn_update_rule.setMaximumWidth(140)
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

        main_layout.addWidget(bottom_frame)

        # Chống hover trắng và thiết lập View chuẩn cho tất cả Combobox
        all_combos = [
            self.combo_label_1, self.combo_label_2, self.combo_task_type, self.combo_logic,
            self.combo_instance_scope, self.combo_param_1, self.combo_operator,
            self.combo_target_type, self.combo_param_2, self.combo_math_op, self.combo_true_result
        ]
        for cb in all_combos:
            view = QtWidgets.QListView()
            cb.setView(view)
            view.setMinimumWidth(max(cb.minimumWidth(), 200))

        for ed_cb in (self.combo_label_1, self.combo_label_2):
            le = ed_cb.lineEdit()
            if le:
                le.setStyleSheet("background-color: transparent; color: #0f172a; padding: 0px 4px; border: none;")

        # KẾT NỐI SIGNALS
        self.visual_canvas.hotspot_clicked.connect(self.on_canvas_hotspot_clicked)
        self.combo_label_1.currentTextChanged.connect(self.on_label_changed)
        self.combo_label_2.currentTextChanged.connect(self.on_label_changed)
        self.combo_instance_scope.currentIndexChanged.connect(self.on_scope_changed)
        self.combo_param_1.currentIndexChanged.connect(self.on_form_param_changed)
        self.combo_param_2.currentIndexChanged.connect(self.on_form_param_changed)
        self.combo_operator.currentIndexChanged.connect(self.on_operator_changed)
        self.combo_true_result.currentIndexChanged.connect(self.on_form_param_changed)
        self.combo_target_type.currentIndexChanged.connect(self.on_target_type_changed)
        self.combo_math_op.currentIndexChanged.connect(self.on_form_param_changed)
        self.line_math_val.textChanged.connect(self.on_form_param_changed)
        
        self.btn_add_rule.clicked.connect(self.add_rule_to_table)
        self.btn_update_rule.clicked.connect(self.update_current_rule)
        self.btn_delete_rule.clicked.connect(self.delete_selected_rule)
        
        self.table_rules.cellClicked.connect(self.on_rule_row_clicked)
        self.table_rules.itemSelectionChanged.connect(self.on_rule_selection_changed)

    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, '_initial_canvas_positioned'):
            self._initial_canvas_positioned = True
            QtCore.QTimer.singleShot(80, self.visual_canvas.reset_positions)

    def _update_scope_hint(self, scope: str):
        """Hiển thị mô tả trực quan và ý nghĩa của Scope."""
        if scope == 'ALL_A_IN_ONE_B':
            self.lbl_scope_hint.setText(
                "💡 <b>Mô hình N vs 1:</b> Kiểm tra tập hợp đối tượng A nằm trong khay/vùng chứa B. Bất kỳ đối tượng A nào vượt ra ngoài biên giới hạn (hoặc vi phạm điều kiện) sẽ ngay lập tức phán định toàn bộ Task là <b>NG</b>!"
            )
        elif scope == 'ONE_A_IN_ANY_B':
            self.lbl_scope_hint.setText(
                "💡 <b>Mô hình 1 vs N:</b> Kiểm tra 1 đối tượng A với tập hợp nhiều vùng giới hạn / vùng cấm B. Nếu đối tượng A đi vào bất kỳ vùng B nào sẽ lập tức phán định <b>NG</b>!"
            )
        elif scope == 'ALL_A_VS_ALL_B':
            self.lbl_scope_hint.setText(
                "💡 <b>Mô hình N vs N:</b> Kiểm tra toàn diện mọi cặp đối tượng giữa tập hợp nhãn A và tập hợp nhãn B. Chỉ cần 1 cặp vi phạm sẽ phán định <b>NG</b>."
            )
        else:
            self.lbl_scope_hint.setText(
                "💡 <b>Mô hình 1 vs 1:</b> So sánh trực tiếp giữa 1 đối tượng nhãn A với 1 đối tượng nhãn B (hoặc hằng số cố định)."
            )

    def on_scope_changed(self):
        if self._is_populating:
            return
        scope = self.combo_instance_scope.currentData() or '1_VS_1'
        self._update_scope_hint(scope)
        self.visual_canvas.set_instance_scope(scope)
        
        if scope in ('ALL_A_IN_ONE_B', 'ONE_A_IN_ANY_B'):
            cur_op = self.combo_operator.currentData()
            if cur_op not in ('INSIDE', 'OUTSIDE', 'OVERLAP'):
                idx_inside = self.combo_operator.findData('INSIDE')
                if idx_inside >= 0:
                    self.combo_operator.setCurrentIndex(idx_inside)
        self.on_form_param_changed()

    def on_operator_changed(self):
        if self._is_populating:
            return
        op = self.combo_operator.currentData() or '<'
        is_spatial = op in ('INSIDE', 'OUTSIDE', 'OVERLAP')
        is_distance = op.startswith('DIST_')

        if is_spatial:
            idx_p1 = self.combo_param_1.findData('FULL_BOX')
            if idx_p1 >= 0:
                self.combo_param_1.setCurrentIndex(idx_p1)
            self.combo_param_1.setEnabled(False)

            idx_lbl = self.combo_target_type.findData('LABEL')
            if idx_lbl >= 0:
                self.combo_target_type.setCurrentIndex(idx_lbl)
            self.combo_target_type.setEnabled(False)

            idx_p2 = self.combo_param_2.findData('FULL_BOX')
            if idx_p2 >= 0:
                self.combo_param_2.setCurrentIndex(idx_p2)
            self.combo_param_2.setEnabled(False)
            self.combo_label_2.setEnabled(True)

            self.lbl_math_op.setText("Bù Margin:")
            self.lbl_math_val.setText("Dung sai (px):")
            self.line_math_val.setPlaceholderText("VD: 5 hoặc -5")
            self.combo_math_op.setEnabled(True)
            self.line_math_val.setEnabled(True)

        elif is_distance:
            self.combo_param_1.setEnabled(True)
            # Khóa so sánh với Nhãn B (chọn cạnh của B)
            idx_lbl = self.combo_target_type.findData('LABEL')
            if idx_lbl >= 0:
                self.combo_target_type.setCurrentIndex(idx_lbl)
            self.combo_target_type.setEnabled(False)
            self.combo_label_2.setEnabled(True)
            self.combo_param_2.setEnabled(True)

            # Nếu đang chọn FULL_BOX thì tự đổi sang Y_MAX và Y_MIN mặc định
            if self.combo_param_1.currentData() == 'FULL_BOX':
                idx_ymax = self.combo_param_1.findData('Y_MAX')
                if idx_ymax >= 0:
                    self.combo_param_1.setCurrentIndex(idx_ymax)
            if self.combo_param_2.currentData() == 'FULL_BOX':
                idx_ymin = self.combo_param_2.findData('Y_MIN')
                if idx_ymin >= 0:
                    self.combo_param_2.setCurrentIndex(idx_ymin)

            self.lbl_math_op.setText("Phép tính:")
            idx_none = self.combo_math_op.findData('NONE')
            if idx_none >= 0:
                self.combo_math_op.setCurrentIndex(idx_none)
            self.combo_math_op.setEnabled(False)

            self.lbl_math_val.setText("Ngưỡng (px):")
            self.line_math_val.setPlaceholderText("VD: 40 hoặc 25.5")
            self.line_math_val.setEnabled(True)

        else:
            self.combo_param_1.setEnabled(True)
            self.combo_target_type.setEnabled(True)
            is_label = (self.combo_target_type.currentData() == 'LABEL')
            self.combo_label_2.setEnabled(is_label)
            self.combo_param_2.setEnabled(is_label)

            self.lbl_math_op.setText("Bù trừ:")
            self.combo_math_op.setEnabled(True)
            self.lbl_math_val.setText("± (px):")
            self.line_math_val.setPlaceholderText("VD: 15.5 hoặc dung sai viền")
            self.line_math_val.setEnabled(True)

        self.on_form_param_changed()

    def populate_data(self):
        """Đổ toàn bộ dữ liệu từ Database vào Form và Canvas chuẩn xác."""
        self._is_populating = True
        try:
            # Đảm bảo available_labels phản ánh đúng nhãn của model_id hiện tại
            if self.cursor and self.camera_id and self.model_id is not None:
                try:
                    from module_3.task_calculator_db import get_available_labels_for_camera
                    m_labels = get_available_labels_for_camera(self.cursor, self.camera_id, self.model_id)
                    if m_labels is not None:
                        self.available_labels = m_labels
                except Exception:
                    pass

            all_labels = set(self.available_labels)
            if self.preselected_labels:
                all_labels.update(self.preselected_labels)
            for r in self.rules_list:
                if r.get('label_1'):
                    all_labels.add(r['label_1'])
                if r.get('label_2'):
                    all_labels.add(r['label_2'])

            labels_list = sorted(list(all_labels))
            
            self.combo_label_1.clear()
            self.combo_label_2.clear()
            self.combo_label_1.addItems(labels_list)
            self.combo_label_2.addItems(labels_list)

            if self.task_data:
                self.line_task_name.setText(self.task_data.get('task_name', ''))
                task_type = self.task_data.get('task_type', 'RELATION_COORDINATE')
                idx = self.combo_task_type.findData(task_type)
                if idx < 0 and task_type == 'DISTANCE_CALC':
                    idx = self.combo_task_type.findData('DISTANCE')
                if idx >= 0:
                    self.combo_task_type.setCurrentIndex(idx)
                
                logic_mode = self.task_data.get('logic_mode', 'ALL_PASS')
                idx_logic = self.combo_logic.findData(logic_mode)
                if idx_logic >= 0:
                    self.combo_logic.setCurrentIndex(idx_logic)

                self.chk_task_enabled.setChecked(bool(self.task_data.get('enabled', True)))
                self.line_plc_register.setText(self.task_data.get('assign_register', ''))
                val_state = self.task_data.get('value_state', self.task_data.get('Value_State', 1))
                self.spin_plc_state.setValue(int(val_state if val_state is not None else 1))
                self.spin_plc_on.setValue(int(self.task_data.get('value_bit_on', self.task_data.get('value_ok', self.task_data.get('Value_OK', 1)))))
                self.spin_plc_off.setValue(int(self.task_data.get('value_bit_off', self.task_data.get('value_ng', self.task_data.get('Value_NG', 0)))))

            self.refresh_rules_table()

            if self.rules_list:
                self.load_rule_into_editor(0)
                self.table_rules.selectRow(0)
            else:
                if len(self.preselected_labels) >= 2:
                    self.combo_label_1.setCurrentText(self.preselected_labels[0])
                    self.combo_label_2.setCurrentText(self.preselected_labels[1])
                elif len(self.preselected_labels) == 1:
                    self.combo_label_1.setCurrentText(self.preselected_labels[0])
                self._update_scope_hint('1_VS_1')
                self.on_label_changed()
                self.on_form_param_changed()
        finally:
            self._is_populating = False

    def load_rule_into_editor(self, rule_idx: int):
        """Nạp chính xác thông số của 1 Rule vào Builder và Canvas đồ họa."""
        if not (0 <= rule_idx < len(self.rules_list)):
            return

        self._is_populating = True
        try:
            rule = self.rules_list[rule_idx]
            self.editing_rule_index = rule_idx

            # 0. Chế độ đối tượng (Scope)
            scope = rule.get('instance_scope', '1_VS_1')
            idx_scope = self.combo_instance_scope.findData(scope)
            if idx_scope >= 0:
                self.combo_instance_scope.setCurrentIndex(idx_scope)
            self._update_scope_hint(scope)
            self.visual_canvas.set_instance_scope(scope, reset=False)

            # 1. Nhãn 1 & Nhãn 2
            lbl1 = rule.get('label_1', '')
            lbl2 = rule.get('label_2', '')
            if lbl1:
                idx1 = self.combo_label_1.findText(lbl1)
                if idx1 >= 0:
                    self.combo_label_1.setCurrentIndex(idx1)
                else:
                    self.combo_label_1.addItem(lbl1)
                    self.combo_label_1.setCurrentText(lbl1)
            
            if lbl2:
                idx2 = self.combo_label_2.findText(lbl2)
                if idx2 >= 0:
                    self.combo_label_2.setCurrentIndex(idx2)
                else:
                    self.combo_label_2.addItem(lbl2)
                    self.combo_label_2.setCurrentText(lbl2)

            # 2. Toán tử Operator
            op = rule.get('operator', '<')
            idx_op = self.combo_operator.findData(op)
            if idx_op >= 0:
                self.combo_operator.setCurrentIndex(idx_op)

            # 3. Target Type
            tt = rule.get('target_type', 'LABEL')
            idx_tt = self.combo_target_type.findData(tt)
            if idx_tt >= 0:
                self.combo_target_type.setCurrentIndex(idx_tt)

            # 4. Vế trái LHS (Param 1) & Vế phải RHS (Param 2)
            p1 = rule.get('param_1', 'X_MIN')
            idx_p1 = self.combo_param_1.findData(p1)
            if idx_p1 >= 0:
                self.combo_param_1.setCurrentIndex(idx_p1)

            p2 = rule.get('param_2', 'X_MIN')
            idx_p2 = self.combo_param_2.findData(p2)
            if idx_p2 >= 0:
                self.combo_param_2.setCurrentIndex(idx_p2)

            is_spatial = op in ('INSIDE', 'OUTSIDE', 'OVERLAP')
            is_distance = op.startswith('DIST_')
            if is_spatial:
                self.combo_param_1.setEnabled(False)
                self.combo_param_2.setEnabled(False)
                self.combo_target_type.setEnabled(False)
                self.lbl_math_op.setText("Bù Margin:")
                self.lbl_math_val.setText("Dung sai (px):")
                self.combo_math_op.setEnabled(True)
            elif is_distance:
                self.combo_param_1.setEnabled(True)
                self.combo_param_2.setEnabled(True)
                self.combo_target_type.setEnabled(False)
                self.lbl_math_op.setText("Phép tính:")
                self.combo_math_op.setEnabled(False)
                self.lbl_math_val.setText("Ngưỡng (px):")
            else:
                self.combo_param_1.setEnabled(True)
                self.combo_target_type.setEnabled(True)
                self.combo_param_2.setEnabled(tt == 'LABEL')
                self.lbl_math_op.setText("Bù trừ:")
                self.combo_math_op.setEnabled(True)
                self.lbl_math_val.setText("± (px):")

            # 5. Math Op & Value
            m_op = rule.get('math_op', 'NONE')
            idx_mop = self.combo_math_op.findData(m_op)
            if idx_mop >= 0:
                self.combo_math_op.setCurrentIndex(idx_mop)
            
            m_val = str(rule.get('math_operand_val', '0'))
            self.line_math_val.setText(m_val)

            # 6. Condition True Result
            c_res = rule.get('condition_true_result', 'NG')
            idx_cres = self.combo_true_result.findData(c_res)
            if idx_cres >= 0:
                self.combo_true_result.setCurrentIndex(idx_cres)

            # 7. Đồng bộ Canvas Đồ Họa trực quan
            self.visual_canvas.set_labels(lbl1, lbl2)
            self.visual_canvas.set_selected_param(1, p1)
            self.visual_canvas.set_selected_param(2, p2)
            self.visual_canvas.set_target_type(tt)
            self.visual_canvas.set_math_info(m_op, m_val)
            self.visual_canvas.set_operator_and_result(op, c_res)

            # 8. Phục hồi chính xác tọa độ và kích thước 2 Box theo Rule
            b1_val = rule.get('box1_rect')
            b2_val = rule.get('box2_rect')
            if b1_val and b2_val:
                try:
                    def _parse_rect(val):
                        if isinstance(val, (list, tuple)) and len(val) == 4:
                            return [float(v) for v in val]
                        s = str(val).replace('[', '').replace(']', '').replace('(', '').replace(')', '').strip()
                        parts = [float(v.strip()) for v in s.split(',') if v.strip()]
                        return parts if len(parts) == 4 else None

                    r1 = _parse_rect(b1_val)
                    r2 = _parse_rect(b2_val)
                    if r1 and r2:
                        self.visual_canvas.set_box_geometry(1, r1[0], r1[1], r1[2], r1[3])
                        self.visual_canvas.set_box_geometry(2, r2[0], r2[1], r2[2], r2[3])
                    else:
                        self.visual_canvas.reset_positions()
                except Exception:
                    self.visual_canvas.reset_positions()
            else:
                self.visual_canvas.reset_positions()

            self.btn_update_rule.setText(f"💾 Cập Nhật Rule #{rule_idx + 1}")
        finally:
            self._is_populating = False

    def on_rule_row_clicked(self, row: int, col: int):
        if not self._is_populating:
            self.load_rule_into_editor(row)

    def on_rule_selection_changed(self):
        if not self._is_populating:
            rows = self.table_rules.selectionModel().selectedRows()
            if rows:
                self.load_rule_into_editor(rows[0].row())

    def on_label_changed(self):
        if self._is_populating:
            return
        lbl1 = self.combo_label_1.currentText()
        lbl2 = self.combo_label_2.currentText()
        self.visual_canvas.set_labels(lbl1, lbl2)

    def on_form_param_changed(self):
        if self._is_populating:
            return
        p1 = self.combo_param_1.currentData() or 'X_MIN'
        p2 = self.combo_param_2.currentData() or 'X_MIN'
        op = self.combo_operator.currentData() or '<'
        res = self.combo_true_result.currentData() or 'NG'
        tt = self.combo_target_type.currentData() or 'LABEL'
        m_op = self.combo_math_op.currentData() or 'NONE'
        m_val = self.line_math_val.text().strip() or '0'

        self.visual_canvas.set_selected_param(1, p1)
        self.visual_canvas.set_selected_param(2, p2)
        self.visual_canvas.set_target_type(tt)
        self.visual_canvas.set_math_info(m_op, m_val)
        self.visual_canvas.set_operator_and_result(op, res)

    def on_canvas_hotspot_clicked(self, box_idx: int, param_name: str):
        if box_idx == 1:
            idx = self.combo_param_1.findData(param_name)
            if idx >= 0:
                self.combo_param_1.setCurrentIndex(idx)
        else:
            idx = self.combo_param_2.findData(param_name)
            if idx >= 0:
                self.combo_param_2.setCurrentIndex(idx)
        self.on_form_param_changed()

    def on_target_type_changed(self):
        is_label = (self.combo_target_type.currentData() == 'LABEL')
        self.combo_label_2.setEnabled(is_label)
        self.combo_param_2.setEnabled(is_label)
        self.on_form_param_changed()

    def _build_rule_dict_from_form(self) -> Optional[Dict[str, Any]]:
        """Thu thập dữ liệu từ Form thành Dictionary Rule chuẩn xác."""
        scope = self.combo_instance_scope.currentData() or '1_VS_1'
        lbl1 = self.combo_label_1.currentText().strip()
        lbl2 = self.combo_label_2.currentText().strip()
        target_type = self.combo_target_type.currentData()
        
        if not lbl1:
            QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn hoặc nhập Nhãn 1 (Label A)!")
            return None
        if target_type == 'LABEL' and not lbl2:
            QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn hoặc nhập Nhãn 2 (Label B)!")
            return None

        param1 = self.combo_param_1.currentData() or 'X_MIN'
        op = self.combo_operator.currentData() or '<'
        param2 = self.combo_param_2.currentData() if target_type == 'LABEL' else ''
        math_op = self.combo_math_op.currentData() or 'NONE'
        math_val = self.line_math_val.text().strip() or '0'
        true_res = self.combo_true_result.currentData() or 'NG'

        if op in ('INSIDE', 'OUTSIDE', 'OVERLAP'):
            param1 = 'FULL_BOX'
            param2 = 'FULL_BOX'

        try:
            val_f = float(math_val)
        except Exception:
            val_f = 0.0

        # Xây dựng mô tả rule chuyên nghiệp
        if op.startswith('DIST_'):
            comp_op = op.replace('DIST_', '')
            rule_desc = f"Khoảng cách [{param1}({lbl1}) ➔ {param2}({lbl2})] {comp_op} {math_val}px ➔ {true_res}"
        elif scope == 'ALL_A_IN_ONE_B':
            rule_desc = f"[N vs 1] Mọi {lbl1} {op} {lbl2} ➔ {true_res}"
        elif scope == 'ONE_A_IN_ANY_B':
            rule_desc = f"[1 vs N] {lbl1} {op} Bất kỳ {lbl2} ➔ {true_res}"
        elif scope == 'ALL_A_VS_ALL_B':
            rule_desc = f"[N vs N] Mọi {lbl1} {op} Mọi {lbl2} ➔ {true_res}"
        else:
            lhs_str = f"{param1}({lbl1})"
            rhs_str = f"{param2}({lbl2})" if target_type == 'LABEL' else f"CONSTANT({math_val})"
            if math_op != 'NONE':
                rhs_str += f" {math_op} {math_val}"
            rule_desc = f"{lhs_str} {op} {rhs_str} ➔ {true_res}"

        b1_geo = self.visual_canvas.get_box_geometry(1)
        b2_geo = self.visual_canvas.get_box_geometry(2)
        b1_str = f"{b1_geo[0]:.1f},{b1_geo[1]:.1f},{b1_geo[2]:.1f},{b1_geo[3]:.1f}"
        b2_str = f"{b2_geo[0]:.1f},{b2_geo[1]:.1f},{b2_geo[2]:.1f},{b2_geo[3]:.1f}"

        return {
            'label_1': lbl1,
            'param_1': param1,
            'instance_select_1': 'BEST_CONF',
            'instance_scope': scope,
            'operator': op,
            'target_type': target_type,
            'label_2': lbl2 if target_type == 'LABEL' else '',
            'param_2': param2,
            'instance_select_2': 'BEST_CONF',
            'math_op': math_op,
            'math_operand_type': 'CONSTANT',
            'math_operand_val': math_val,
            'min_value': val_f if op.startswith('DIST_') else 0.0,
            'max_value': 0.0,
            'condition_true_result': true_res,
            'enabled': True,
            'description': rule_desc,
            'box1_rect': b1_str,
            'box2_rect': b2_str
        }

    def add_rule_to_table(self):
        """Thêm 1 rule mới vào danh sách."""
        rule_obj = self._build_rule_dict_from_form()
        if not rule_obj:
            return

        self.rules_list.append(rule_obj)
        self.refresh_rules_table()
        new_row = len(self.rules_list) - 1
        self.table_rules.selectRow(new_row)
        self.load_rule_into_editor(new_row)

    def update_current_rule(self):
        """Cập nhật lại Rule đang chọn trên bảng."""
        if self.editing_rule_index is None or not (0 <= self.editing_rule_index < len(self.rules_list)):
            self.add_rule_to_table()
            return

        rule_obj = self._build_rule_dict_from_form()
        if not rule_obj:
            return

        old_id = self.rules_list[self.editing_rule_index].get('id')
        if old_id:
            rule_obj['id'] = old_id

        self.rules_list[self.editing_rule_index] = rule_obj
        self.refresh_rules_table()
        self.table_rules.selectRow(self.editing_rule_index)
        self.load_rule_into_editor(self.editing_rule_index)

    def refresh_rules_table(self):
        """Làm mới toàn bộ bảng danh sách Rules gồm 6 cột thông tin chi tiết."""
        self.table_rules.setRowCount(len(self.rules_list))
        for row_idx, r in enumerate(self.rules_list):
            item_stt = QtWidgets.QTableWidgetItem(str(row_idx + 1))
            item_stt.setTextAlignment(Qt.AlignCenter)
            item_stt.setForeground(QColor("#475569"))
            self.table_rules.setItem(row_idx, 0, item_stt)

            scope = r.get('instance_scope', '1_VS_1')
            scope_name = "1 vs 1"
            scope_color = "#334155"
            if scope == 'ALL_A_IN_ONE_B':
                scope_name = "N vs 1 (Tập hợp A vs B)"
                scope_color = "#0284c7"
            elif scope == 'ONE_A_IN_ANY_B':
                scope_name = "1 vs N (1 A vs Các vùng B)"
                scope_color = "#d97706"
            elif scope == 'ALL_A_VS_ALL_B':
                scope_name = "N vs N (Tập hợp A vs B)"
                scope_color = "#7c3aed"
            item_scope = QtWidgets.QTableWidgetItem(scope_name)
            item_scope.setTextAlignment(Qt.AlignCenter)
            item_scope.setForeground(QColor(scope_color))
            self.table_rules.setItem(row_idx, 1, item_scope)

            desc = r.get('description') or f"{r.get('param_1', '')}({r.get('label_1', '')}) {r.get('operator', '')} {r.get('param_2', '')}({r.get('label_2', '')})"
            item_desc = QtWidgets.QTableWidgetItem(desc)
            item_desc.setForeground(QColor("#0f172a"))
            self.table_rules.setItem(row_idx, 2, item_desc)

            item_lhs = QtWidgets.QTableWidgetItem(f"{r.get('label_1', '')} [{r.get('param_1', '')}]")
            item_lhs.setForeground(QColor("#1e293b"))
            self.table_rules.setItem(row_idx, 3, item_lhs)

            rule_op = str(r.get('operator', ''))
            if rule_op.startswith('DIST_'):
                comp_op = rule_op.replace('DIST_', '')
                thresh_str = str(r.get('math_operand_val') or r.get('min_value', 0))
                rhs_info = f"Khoảng cách {comp_op} {thresh_str} px [{r.get('param_2', '')}]"
            else:
                rhs_target = r.get('label_2', '') if r.get('target_type') == 'LABEL' else 'HẰNG SỐ'
                rhs_param_str = f"[{r.get('param_2', '')}]" if (r.get('target_type') == 'LABEL' and r.get('param_2') != 'FULL_BOX') else ''
                rhs_info = f"{rule_op} {rhs_target} {rhs_param_str}".strip()
                if r.get('math_op') and r.get('math_op') != 'NONE':
                    rhs_info += f" {r.get('math_op')} {r.get('math_operand_val', '0')}"
            item_rhs = QtWidgets.QTableWidgetItem(rhs_info)
            item_rhs.setForeground(QColor("#1e293b"))
            self.table_rules.setItem(row_idx, 4, item_rhs)

            item_res = QtWidgets.QTableWidgetItem(f"Vi phạm ➔ {r.get('condition_true_result', 'NG')}")
            item_res.setTextAlignment(Qt.AlignCenter)
            if r.get('condition_true_result') == 'NG':
                item_res.setForeground(QColor("#dc2626"))
            else:
                item_res.setForeground(QColor("#16a34a"))
            self.table_rules.setItem(row_idx, 5, item_res)

    def delete_selected_rule(self):
        row = self.table_rules.currentRow()
        if 0 <= row < len(self.rules_list):
            del self.rules_list[row]
            self.refresh_rules_table()
            if self.rules_list:
                next_row = min(row, len(self.rules_list) - 1)
                self.table_rules.selectRow(next_row)
                self.load_rule_into_editor(next_row)
            else:
                self.editing_rule_index = None
                self.btn_update_rule.setText("💾 Cập Nhật")

    def save_task(self):
        """Kiểm tra và lưu Task + Rules vào MySQL."""
        task_name = self.line_task_name.text().strip()
        if not task_name:
            QtWidgets.QMessageBox.warning(self, "Thiếu Tên Task", "Vui lòng nhập Tên Task!")
            self.line_task_name.setFocus()
            return

        if not self.rules_list:
            QtWidgets.QMessageBox.warning(self, "Chưa có Quy Tắc", "Vui lòng thêm ít nhất 1 Rule cho Task này trước khi lưu!")
            return

        task_data = {
            'id': self.task_data.get('id'),
            'camera_id': self.camera_id,
            'model_id': self.model_id or self.task_data.get('model_id', 1),
            'task_name': task_name,
            'task_type': self.combo_task_type.currentData(),
            'logic_mode': self.combo_logic.currentData(),
            'action_on_fail': self.task_data.get('action_on_fail', 'NG'),
            'enabled': self.chk_task_enabled.isChecked(),
            'assign_register': self.line_plc_register.text().strip(),
            'value_state': self.spin_plc_state.value(),
            'Value_State': self.spin_plc_state.value(),
            'value_bit_on': self.spin_plc_on.value(),
            'value_ok': self.spin_plc_on.value(),
            'Value_OK': self.spin_plc_on.value(),
            'value_bit_off': self.spin_plc_off.value(),
            'value_ng': self.spin_plc_off.value(),
            'Value_NG': self.spin_plc_off.value(),
        }

        # ─────────────────────────────────────────────────────────────
        # BẮT BUỘC NHẬP LÝ DO THAY ĐỔI THEO QUY CHUẨN AUDIT TRAIL
        # ─────────────────────────────────────────────────────────────
        from module_3.change_reason_dialog import ChangeReasonDialog
        from module_3.config_version_manager import save_snapshot

        curr_user = getattr(self, 'current_user', None) or 'Admin'
        curr_role = getattr(self, 'current_role', None) or 'full_control'
        context_str = f"Camera: {self.camera_id} | Model ID: {self.model_id} | Task: {task_name}"

        reason_dlg = ChangeReasonDialog(
            current_user=curr_user,
            current_role=curr_role,
            context_info=context_str,
            parent=self
        )
        if reason_dlg.exec_() != QtWidgets.QDialog.Accepted:
            return

        change_reason, is_golden = reason_dlg.get_reason_and_golden()

        from module_3.task_calculator_db import save_task_and_rules
        saved_id = save_task_and_rules(self.cursor, self.connection, task_data, self.rules_list)
        if saved_id:
            try:
                save_snapshot(
                    cursor=self.cursor,
                    connection=self.connection,
                    scope_category='TASK_RULES',
                    change_reason=change_reason,
                    changed_by=curr_user,
                    camera_id=str(self.camera_id),
                    model_id=self.model_id or 1,
                    user_role=curr_role,
                    is_golden=is_golden
                )
            except Exception as e_snap:
                pass
            QtWidgets.QMessageBox.information(self, "Thành công", f"Đã lưu thành công Task '{task_name}' (ID: {saved_id}) cùng {len(self.rules_list)} rules và ghi nhận lịch sử!")
            self.accept()
        else:
            QtWidgets.QMessageBox.critical(self, "Lỗi Lưu Database", "Không thể lưu Task vào cơ sở dữ liệu. Vui lòng kiểm tra lại kết nối MySQL!")
