"""
Module: task_rule_editor_dialog.py
Mục đích: Hộp thoại soạn thảo Task & Luật hình học với mô hình đồ họa tương tác cao cấp (Interactive Visual Bounding Box Canvas).
Tính năng nâng cấp:
1. Hai ô vuông Bounding Box có thể dùng chuột kéo thả (Move / Drag) tự do trong khung.
2. Có thể kéo to / thu nhỏ (Resize / Scale) từng nhãn bằng tay cầm ở góc dưới bên phải.
3. Hiển thị thông số Pixel thời gian thực (W × H px, X, Y) ngay trên từng nhãn khi kéo to thu nhỏ.
4. Nhấp chọn các cạnh (Xmin, Xmax, Ymin, Ymax, Center, Width, Height) để tự động đồng bộ công thức.
5. Khi mở Chỉnh sửa Task, nạp CHÍNH XÁC toàn bộ dữ liệu từ Database: tên task, các vế, toán tử, bù trừ, màu sắc, cạnh đang chọn trên Canvas.
6. Khi click chọn bất kỳ Rule nào trong bảng, giao diện và mô hình đồ họa tự động chuyển sang hiển thị đúng Rule đó.
"""

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath
from typing import List, Dict, Any, Optional

PARAM_DISPLAY_NAMES = {
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
    'BETWEEN': 'Trong khoảng (Min <= X <= Max)'
}


class VisualBoxCanvas(QtWidgets.QWidget):
    """
    Widget đồ họa trực quan mô phỏng không gian đo thị giác AI.
    - 2 Bounding Box có thể kéo di chuyển (Drag) và co giãn kích thước (Resize).
    - Hiển thị pixel kích thước WxH thời gian thực khi kéo to / thu nhỏ.
    - Nhấp chọn cạnh/tọa độ tương tác (Xmin, Xmax, Ymin, Ymax, Center, Width, Height) để tự động gán vào luật kiểm tra.
    - Hiển thị đường đo nối 2 nhãn với toán tử so sánh và phép bù trừ thời gian thực.
    """
    hotspot_clicked = pyqtSignal(int, str)  # (box_index: 1 or 2, param_name: str)
    box_geometry_changed = pyqtSignal(int, float, float, float, float)  # (box_idx, x, y, w, h)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(500)
        self.setMouseTracking(True)
        
        self.label_1_name = "Nhãn 1 (Label A)"
        self.label_2_name = "Nhãn 2 (Label B)"
        self.selected_param_1 = 'X_MIN'
        self.selected_param_2 = 'X_MIN'
        self.operator_str = '<'
        self.condition_true_result = 'NG'
        self.target_type = 'LABEL'
        self.math_op = 'NONE'
        self.math_val = '0'

        # Tọa độ và kích thước của 2 box (có thể di chuyển và resize)
        self.box1_rect = QRectF(40, 50, 180, 130)
        self.box2_rect = QRectF(290, 50, 180, 130)
        self.front_box = 1  # 1 or 2: box nào đang được focus vẽ đè lên trên

        # Trạng thái tương tác chuột
        self.active_action = None  # None, ('DRAG', box_idx), ('RESIZE', box_idx), ('HOTSPOT_OR_DRAG', box_idx, param)
        self.drag_start_mouse = QPointF()
        self.initial_box_rect = QRectF()
        self.hovered_hotspot = None  # (box_idx, param_name)
        self.hovered_resize = None   # box_idx (1 or 2)
        self.hovered_body = None     # box_idx (1 or 2)
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
            bw = max(90.0, min(r.width(), w - 20.0))
            bh = max(65.0, min(r.height(), h - 20.0))
            bx = max(5.0, min(r.x(), w - bw - 5.0))
            by = max(5.0, min(r.y(), h - bh - 5.0))
            if b_idx == 1:
                self.box1_rect = QRectF(bx, by, bw, bh)
            else:
                self.box2_rect = QRectF(bx, by, bw, bh)

    def reset_positions(self):
        """Khôi phục vị trí mặc định nằm cân đối 2 bên."""
        w = max(400, self.width())
        h = max(300, self.height())
        box_w = 180.0
        box_h = 130.0
        y = max(50.0, (h - box_h) / 2 - 20)
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

    def _get_hotspots(self, rect: QRectF, box_idx: int):
        """Trả về danh sách các điểm neo tương tác trên viền và trong thân box."""
        m = 12
        left_rect = QRectF(rect.left() - m, rect.top() + m, m * 2, rect.height() - m * 2)
        right_rect = QRectF(rect.right() - m, rect.top() + m, m * 2, rect.height() - m * 2)
        top_rect = QRectF(rect.left() + m, rect.top() - m, rect.width() - m * 2, m * 2)
        bottom_rect = QRectF(rect.left() + m, rect.bottom() - m, rect.width() - m * 2, m * 2)
        
        cx, cy = rect.center().x(), rect.center().y()
        center_rect = QRectF(cx - 14, cy - 14, 28, 28)

        # Hotspots cho WIDTH & HEIGHT (Click trực tiếp để chọn thông số)
        width_hotspot_rect = QRectF(rect.left() + 20, rect.top() + 30, max(20.0, rect.width() - 40), 18)
        height_hotspot_rect = QRectF(rect.left() + 10, rect.top() + 48, 22, max(20.0, rect.height() - 75))

        return [
            (box_idx, 'X_MIN', left_rect, 'Left (X min)'),
            (box_idx, 'X_MAX', right_rect, 'Right (X max)'),
            (box_idx, 'Y_MIN', top_rect, 'Top (Y min)'),
            (box_idx, 'Y_MAX', bottom_rect, 'Bottom (Y max)'),
            (box_idx, 'CENTER_X', center_rect, 'Center (Tâm)'),
            (box_idx, 'WIDTH', width_hotspot_rect, 'Width (Chiều rộng)'),
            (box_idx, 'HEIGHT', height_hotspot_rect, 'Height (Chiều cao)'),
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
            return QPointF(cx, rect.top())
        elif param in ('Y_MAX', 'BOTTOM'):
            return QPointF(cx, rect.bottom())
        elif param == 'WIDTH':
            return QPointF(rect.right(), rect.top() + 38)
        elif param == 'HEIGHT':
            return QPointF(rect.left() + 20, rect.bottom() - 15)
        else:  # Center
            return QPointF(cx, cy)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # 1. Nền canvas chuyên nghiệp CAD Grid
        painter.fillRect(self.rect(), QColor("#141420"))
        
        pen_grid = QPen(QColor("#1f2033"), 1, Qt.DotLine)
        painter.setPen(pen_grid)
        grid_step = 25
        for x in range(0, w, grid_step):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, grid_step):
            painter.drawLine(0, y, w, y)

        # 2. Vẽ đường liên kết đo giữa 2 Box
        p1 = self._get_hotspot_point(self.box1_rect, self.selected_param_1)
        if self.target_type == 'CONSTANT':
            p2 = QPointF(self.box2_rect.left(), self.box2_rect.center().y())
        else:
            p2 = self._get_hotspot_point(self.box2_rect, self.selected_param_2)

        is_ng = (self.condition_true_result == 'NG')
        line_color = QColor("#f38ba8") if is_ng else QColor("#a6e3a1")
        pen_line = QPen(line_color, 2, Qt.DashLine)
        painter.setPen(pen_line)
        painter.drawLine(p1, p2)

        # Vẽ điểm neo tại 2 đầu liên kết
        painter.setBrush(QBrush(line_color))
        painter.drawEllipse(p1, 5, 5)
        painter.drawEllipse(p2, 5, 5)

        # Badge thông tin công thức ở giữa đường nối
        mid_x = (p1.x() + p2.x()) / 2
        mid_y = (p1.y() + p2.y()) / 2
        
        rhs_display = self.selected_param_2 if self.target_type == 'LABEL' else "HẰNG SỐ"
        math_display = f" {self.math_op} {self.math_val}" if self.math_op != 'NONE' else ""
        res_display = "➔ VI PHẠM (NG)" if is_ng else "➔ HỢP LỆ (OK)"
        op_text = f" {self.selected_param_1} {self.operator_str} {rhs_display}{math_display} {res_display} "

        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        tw = max(160.0, float(len(op_text) * 7.2))
        th = 24.0
        badge_rect = QRectF(mid_x - tw / 2, mid_y - th / 2, tw, th)
        painter.setBrush(QBrush(QColor("#181825")))
        painter.setPen(QPen(line_color, 1.8))
        painter.drawRoundedRect(badge_rect, 6, 6)
        painter.setPen(line_color)
        painter.drawText(badge_rect, Qt.AlignCenter, op_text)

        # 3. Vẽ 2 Hộp Bounding Box theo thứ tự focus (front_box vẽ sau cùng để nằm trên)
        boxes_to_draw = [2, 1] if self.front_box == 1 else [1, 2]
        for b_idx in boxes_to_draw:
            if b_idx == 1:
                self._paint_box(painter, self.box1_rect, 1, self.label_1_name, QColor("#3b82f6"), self.selected_param_1)
            else:
                is_const = (self.target_type == 'CONSTANT')
                lbl2_txt = f"HẰNG SỐ: {self.math_val}" if is_const else self.label_2_name
                color2 = QColor("#cba6f7") if is_const else QColor("#f97316")
                self._paint_box(painter, self.box2_rect, 2, lbl2_txt, color2, self.selected_param_2, is_constant=is_const)

        # 4. HUD Banner hiển thị Pixel thời gian thực khi kéo to thu nhỏ hoặc di chuyển
        self._paint_hud_banner(painter, w)

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
                hud_text = f"📐 ĐANG CO GIÃN NHÃN {box_idx}: {w_now} × {h_now} px  (Độ biến thiên: ΔW {dw:+d} px, ΔH {dh:+d} px)"
                hud_color = QColor("#fab387")
                border_color = QColor("#f9e2af")
            elif action_type in ('DRAG', 'HOTSPOT_OR_DRAG') and self.is_dragging:
                x_now = int(target_rect.x())
                y_now = int(target_rect.y())
                dx = int(x_now - self.initial_box_rect.x())
                dy = int(y_now - self.initial_box_rect.y())
                hud_text = f"📍 ĐANG DI CHUYỂN NHÃN {box_idx}: X = {x_now} px, Y = {y_now} px  (Dịch chuyển: ΔX {dx:+d} px, ΔY {dy:+d} px)"
                hud_color = QColor("#89dceb")
                border_color = QColor("#89b4fa")
            else:
                hud_text = "🖱️ Kéo thân để DI CHUYỂN | Kéo góc dưới-phải (📐) để CO GIÃN | Click cạnh để CHỌN TỌA ĐỘ"
                hud_color = QColor("#a6adc8")
                border_color = QColor("#313244")
        else:
            hud_text = "🖱️ Kéo thân để DI CHUYỂN | Kéo góc dưới-phải (📐) để CO GIÃN | Click cạnh để CHỌN TỌA ĐỘ"
            hud_color = QColor("#a6adc8")
            border_color = QColor("#313244")

        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        bw = max(520.0, float(len(hud_text) * 7.5))
        bh = 26.0
        hud_rect = QRectF((width - bw) / 2, 8, bw, bh)

        painter.setBrush(QBrush(QColor("#181825")))
        painter.setPen(QPen(border_color, 1.5))
        painter.drawRoundedRect(hud_rect, 6, 6)

        painter.setPen(hud_color)
        painter.drawText(hud_rect, Qt.AlignCenter, hud_text)

    def _paint_box(self, painter: QPainter, rect: QRectF, box_idx: int, label_text: str, theme_color: QColor, selected_param: str, is_constant: bool = False):
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

        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.setPen(QColor("#ffffff"))
        tag = f"Nhãn {box_idx}: {label_text}" if not is_constant else label_text
        painter.drawText(header_rect, Qt.AlignCenter, tag)

        # Vẽ các Hotspots cạnh (nếu không phải là constant)
        if not is_constant:
            hotspots = self._get_hotspots(rect, box_idx)
            for b_idx, param, h_rect, desc in hotspots:
                if param in ('WIDTH', 'HEIGHT'):
                    continue  # Sẽ vẽ riêng bên dưới

                is_selected = (selected_param == param or (selected_param == 'CENTER_Y' and param == 'CENTER_X'))
                is_hovered = (self.hovered_hotspot == (b_idx, param))

                if is_selected:
                    dot_color = QColor("#a6e3a1")  # Xanh lá sáng khi được chọn
                    line_pen = QPen(QColor("#a6e3a1"), 4)
                elif is_hovered:
                    dot_color = QColor("#f9e2af")  # Vàng khi hover
                    line_pen = QPen(QColor("#f9e2af"), 3)
                else:
                    dot_color = theme_color
                    line_pen = QPen(theme_color, 2)

                # Highlight cạnh
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
            painter.setPen(QPen(QColor("#a6e3a1"), 2, Qt.SolidLine))
            painter.drawLine(QPointF(rect.left() + 6, dim_y), QPointF(rect.right() - 6, dim_y))
            # Mũi tên 2 đầu
            painter.drawLine(QPointF(rect.left() + 6, dim_y), QPointF(rect.left() + 12, dim_y - 4))
            painter.drawLine(QPointF(rect.left() + 6, dim_y), QPointF(rect.left() + 12, dim_y + 4))
            painter.drawLine(QPointF(rect.right() - 6, dim_y), QPointF(rect.right() - 12, dim_y - 4))
            painter.drawLine(QPointF(rect.right() - 6, dim_y), QPointF(rect.right() - 12, dim_y + 4))
            painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
            painter.setPen(QColor("#a6e3a1"))
            painter.drawText(QRectF(rect.left(), dim_y - 14, rect.width(), 14), Qt.AlignCenter, f"↔ WIDTH: {cur_w} px")

        elif selected_param == 'HEIGHT':
            dim_x = rect.left() + 26
            painter.setPen(QPen(QColor("#a6e3a1"), 2, Qt.SolidLine))
            painter.drawLine(QPointF(dim_x, rect.top() + header_h + 4), QPointF(dim_x, rect.bottom() - 28))
            # Mũi tên 2 đầu
            painter.drawLine(QPointF(dim_x, rect.top() + header_h + 4), QPointF(dim_x - 4, rect.top() + header_h + 10))
            painter.drawLine(QPointF(dim_x, rect.top() + header_h + 4), QPointF(dim_x + 4, rect.top() + header_h + 10))
            painter.drawLine(QPointF(dim_x, rect.bottom() - 28), QPointF(dim_x - 4, rect.bottom() - 34))
            painter.drawLine(QPointF(dim_x, rect.bottom() - 28), QPointF(dim_x + 4, rect.bottom() - 34))
            painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
            painter.setPen(QColor("#a6e3a1"))
            painter.drawText(QRectF(dim_x + 4, rect.center().y() - 10, rect.width() - dim_x - 10, 20), Qt.AlignLeft, f"↕ HEIGHT:\n{cur_h} px")

        # Cạnh đang chọn text ở giữa
        if not (selected_param in ('WIDTH', 'HEIGHT')):
            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QColor("#cdd6f4"))
            status_text = f"Cạnh: {PARAM_DISPLAY_NAMES.get(selected_param, selected_param)}"
            painter.drawText(QRectF(rect.left() + 4, rect.top() + header_h + 8, rect.width() - 8, 20), Qt.AlignCenter, status_text)

        # Tay cầm Resize ở góc dưới bên phải (Handle Grip)
        resize_rect = self._get_resize_rect(rect)
        is_resize_hover = (self.hovered_resize == box_idx)
        resize_color = QColor("#f9e2af") if is_resize_hover else theme_color
        painter.setPen(QPen(resize_color, 2))
        painter.setBrush(QBrush(QColor(resize_color.red(), resize_color.green(), resize_color.blue(), 140)))
        painter.drawRoundedRect(resize_rect, 4, 4)

        # 3 đường gạch chéo biểu tượng co giãn góc
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

        # Ưu tiên kiểm tra box đang ở phía trước (front_box) trước
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

        # 2. Kiểm tra bấm vào Điểm Hotspot cạnh / Width / Height
        for idx in check_order:
            r = self.box1_rect if idx == 1 else self.box2_rect
            for b_idx, param, h_rect, _ in self._get_hotspots(r, idx):
                if h_rect.contains(QPointF(pos)):
                    self.active_action = ('HOTSPOT_OR_DRAG', idx, param)
                    self.front_box = idx
                    self.initial_box_rect = QRectF(r)
                    self.update()
                    return

        # 3. Kiểm tra bấm vào Thân box để di chuyển (Move Drag)
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
        
        # Đang thực hiện kéo di chuyển hoặc co giãn
        if self.active_action:
            delta_x = pos.x() - self.drag_start_mouse.x()
            delta_y = pos.y() - self.drag_start_mouse.y()
            if abs(delta_x) > 3 or abs(delta_y) > 3:
                self.is_dragging = True

            action_type = self.active_action[0]
            box_idx = self.active_action[1]

            if action_type == 'RESIZE':
                # Co giãn kích thước
                new_w = max(90.0, self.initial_box_rect.width() + delta_x)
                new_h = max(65.0, self.initial_box_rect.height() + delta_y)
                
                # Giới hạn trong viền canvas
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
                # Di chuyển thân box
                new_x = self.initial_box_rect.x() + delta_x
                new_y = self.initial_box_rect.y() + delta_y
                
                # Giới hạn trong viền canvas
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

        # Cập nhật con trỏ chuột và trạng thái hover
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
                # Đây là cú click chọn hotspot (không phải kéo di chuyển)
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

class TaskRuleEditorDialog(QtWidgets.QDialog):
    """
    Hộp thoại chính để cấu hình toàn diện Task và danh sách các Rules hình học.
    Hỗ trợ nạp chính xác dữ liệu từ Database, sửa Rule trực tiếp và hiển thị đồ họa.
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
        self.rules_list: List[Dict[str, Any]] = list(rules_data) if rules_data else []
        self.available_labels = available_labels or []
        self.preselected_labels = preselected_labels or []
        self.cursor = cursor
        self.connection = connection

        # Đảm bảo danh sách nhãn chỉ chứa nhãn thuộc tab model hiện tại
        if (not self.available_labels or self.model_id is not None) and self.cursor and self.camera_id:
            try:
                from module_3.task_calculator_db import get_available_labels_for_camera
                model_labels = get_available_labels_for_camera(self.cursor, self.camera_id, self.model_id)
                if model_labels:
                    self.available_labels = model_labels
            except Exception:
                pass

        self.editing_rule_index: Optional[int] = None  # None = Tạo mới, int = Đang sửa rule index
        self._is_populating = False

        title_suffix = f" [Model ID: {self.model_id}]" if self.model_id else ""
        self.setWindowTitle(f"Chỉnh Sửa Task & Quy Tắc Tính Toán Tọa Độ (Geometric Task Editor){title_suffix}")
        self.resize(1100, 800)

        # Cấu hình hiển thị ở chế độ mở rộng (Maximized) kèm đầy đủ nút Phóng to / Thu nhỏ / Đóng
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowMinMaxButtonsHint
            | Qt.WindowCloseButtonHint
        )
        self.setWindowState(Qt.WindowMaximized)
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
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 5px;
                padding: 5px 8px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 1px solid #89b4fa;
            }
            QPushButton {
                background-color: #45475a;
                border: 1px solid #585b70;
                border-radius: 6px;
                padding: 6px 14px;
                color: #cdd6f4;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #585b70;
                color: #ffffff;
            }
            QPushButton#btnSave {
                background-color: #89b4fa;
                color: #11111b;
                border: none;
            }
            QPushButton#btnSave:hover {
                background-color: #b4befe;
            }
            QPushButton#btnAddRule {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton#btnAddRule:hover {
                background-color: #45a049;
            }
            QPushButton#btnUpdateRule {
                background-color: #fab387;
                color: #11111b;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton#btnUpdateRule:hover {
                background-color: #f9e2af;
            }
            QPushButton#btnDeleteRule {
                background-color: #f38ba8;
                color: #11111b;
                border: none;
            }
            QTableWidget {
                background-color: #181825;
                border: 1px solid #313244;
                gridline-color: #313244;
                color: #cdd6f4;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #313244;
                color: #cdd6f4;
                padding: 5px;
                border: 1px solid #45475a;
                font-weight: bold;
            }
        """)

        self.init_ui()
        self.populate_data()

    def init_ui(self):
        # Layout chính của Dialog
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # Scroll Area bao bọc toàn bộ nội dung cấu hình
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
                background-color: #181825;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #45475a;
                min-height: 30px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #585b70;
            }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        # Container chứa toàn bộ GroupBox 1, 2, 3 bên trong ScrollArea
        scroll_content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(scroll_content)
        content_layout.setSpacing(14)
        content_layout.setContentsMargins(8, 8, 14, 8)

        # 1. GROUPBOX THÔNG TIN CHUNG TASK & PLC
        group_task = QtWidgets.QGroupBox("1. Cấu hình Task & Tín hiệu PLC")
        grid_task = QtWidgets.QGridLayout(group_task)
        grid_task.setSpacing(10)

        # Tên Task + Checkbox Kích hoạt
        grid_task.addWidget(QtWidgets.QLabel("Tên Task:"), 0, 0)
        task_name_box = QtWidgets.QHBoxLayout()
        self.line_task_name = QtWidgets.QLineEdit()
        self.line_task_name.setPlaceholderText("VD: Kiểm tra khoảng cách & lệch mép linh kiện A-B")
        task_name_box.addWidget(self.line_task_name, 3)

        self.chk_task_enabled = QtWidgets.QCheckBox("Kích hoạt [✓]")
        self.chk_task_enabled.setChecked(True)
        self.chk_task_enabled.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        task_name_box.addWidget(self.chk_task_enabled, 1)
        grid_task.addLayout(task_name_box, 0, 1)

        # Loại Task
        grid_task.addWidget(QtWidgets.QLabel("Loại Task:"), 0, 2)
        self.combo_task_type = QtWidgets.QComboBox()
        self.combo_task_type.addItem("So sánh Tọa độ Quan hệ (RELATION_COORDINATE)", "RELATION_COORDINATE")
        self.combo_task_type.addItem("Đo Khoảng cách (DISTANCE_CALC)", "DISTANCE")
        self.combo_task_type.addItem("Biểu thức Tùy chỉnh (CUSTOM_EXPRESSION)", "CUSTOM_EXPRESSION")
        self.combo_task_type.setStyleSheet("""
            QComboBox {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 5px;
                padding: 5px 8px;
                color: #ffffff;
                font-size: 13px;
            }
            QComboBox:focus {
                border: 1px solid #89b4fa;
            }
            QComboBox:hover {
                border: 1px solid #89b4fa;
                background-color: white;
                color: black;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url(images/down_arrow.png);
            }
        """)
        grid_task.addWidget(self.combo_task_type, 0, 3)

        # Thanh ghi PLC khi vi phạm NG
        grid_task.addWidget(QtWidgets.QLabel("PLC Register (khi NG):"), 1, 0)
        self.line_plc_register = QtWidgets.QLineEdit()
        self.line_plc_register.setPlaceholderText("VD: D105 hoặc M20 (Để trống nếu không gửi)")
        grid_task.addWidget(self.line_plc_register, 1, 1)

        # Giá trị Bit ON / OFF
        layout_plc_vals = QtWidgets.QHBoxLayout()
        layout_plc_vals.addWidget(QtWidgets.QLabel("Gửi Value:"))
        self.spin_plc_on = QtWidgets.QSpinBox()
        self.spin_plc_on.setRange(-32768, 32767)
        self.spin_plc_on.setValue(1)
        layout_plc_vals.addWidget(self.spin_plc_on)

        layout_plc_vals.addWidget(QtWidgets.QLabel("Reset Value:"))
        self.spin_plc_off = QtWidgets.QSpinBox()
        self.spin_plc_off.setRange(-32768, 32767)
        self.spin_plc_off.setValue(0)
        layout_plc_vals.addWidget(self.spin_plc_off)
        grid_task.addLayout(layout_plc_vals, 1, 2)

        # Logic kết hợp các Rule
        layout_logic = QtWidgets.QHBoxLayout()
        layout_logic.addWidget(QtWidgets.QLabel("Đánh giá tổng:"))
        self.combo_logic = QtWidgets.QComboBox()
        self.combo_logic.addItem("Tất cả Rule phải đạt (AND)", "ALL_PASS")
        self.combo_logic.addItem("Chỉ cần 1 Rule vi phạm là NG (OR)", "ANY_FAIL")
        layout_logic.addWidget(self.combo_logic)
        grid_task.addLayout(layout_logic, 1, 3)

        content_layout.addWidget(group_task)

        # 2. GROUPBOX MÔ HÌNH ĐỒ HỌA TRỰC QUAN & SOẠN THẢO LUẬT
        group_rule = QtWidgets.QGroupBox("2. Bộ Soạn Thảo Luật & Mô Hình Đồ Họa 2 Nhãn (Interactive Canvas)")
        vlayout_rule = QtWidgets.QVBoxLayout(group_rule)
        vlayout_rule.setSpacing(10)

        # Chọn 2 Nhãn mục tiêu + Nút Reset vị trí Canvas
        layout_label_select = QtWidgets.QHBoxLayout()
        layout_label_select.addWidget(QtWidgets.QLabel("🔵 Chọn Nhãn 1 (Label A):"))
        self.combo_label_1 = QtWidgets.QComboBox()
        self.combo_label_1.setEditable(True)
        layout_label_select.addWidget(self.combo_label_1, 2)

        layout_label_select.addSpacing(16)
        layout_label_select.addWidget(QtWidgets.QLabel("🟠 Chọn Nhãn 2 (Label B):"))
        self.combo_label_2 = QtWidgets.QComboBox()
        self.combo_label_2.setEditable(True)
        layout_label_select.addWidget(self.combo_label_2, 2)

        self.btn_reset_canvas = QtWidgets.QPushButton("↺ Đặt lại vị trí")
        self.btn_reset_canvas.setToolTip("Khôi phục vị trí mặc định của 2 hộp nhãn")
        self.btn_reset_canvas.clicked.connect(lambda: self.visual_canvas.reset_positions())
        layout_label_select.addWidget(self.btn_reset_canvas, 1)

        vlayout_rule.addLayout(layout_label_select)

        # Widget Visual Canvas tương tác kéo thả & co giãn
        self.visual_canvas = VisualBoxCanvas()
        vlayout_rule.addWidget(self.visual_canvas)

        # Thanh thiết lập biểu thức quy tắc (Rule Expression Builder)
        expr_frame = QtWidgets.QFrame()
        expr_frame.setStyleSheet("background-color: #181825; border-radius: 6px; padding: 8px;")
        grid_expr = QtWidgets.QGridLayout(expr_frame)
        grid_expr.setSpacing(8)

        # Dòng 1: LHS Operator RHS
        grid_expr.addWidget(QtWidgets.QLabel("Vế Trái (LHS):"), 0, 0)
        self.combo_param_1 = QtWidgets.QComboBox()
        for k, v in PARAM_DISPLAY_NAMES.items():
            self.combo_param_1.addItem(v, k)
        grid_expr.addWidget(self.combo_param_1, 0, 1)

        grid_expr.addWidget(QtWidgets.QLabel("Toán tử so sánh:"), 0, 2)
        self.combo_operator = QtWidgets.QComboBox()
        for k, v in OPERATOR_DISPLAY_NAMES.items():
            self.combo_operator.addItem(v, k)
        grid_expr.addWidget(self.combo_operator, 0, 3)

        grid_expr.addWidget(QtWidgets.QLabel("Vế Phải (RHS):"), 0, 4)
        self.combo_target_type = QtWidgets.QComboBox()
        self.combo_target_type.addItem("So với Nhãn B", "LABEL")
        self.combo_target_type.addItem("So với Số cố định", "CONSTANT")
        grid_expr.addWidget(self.combo_target_type, 0, 5)

        self.combo_param_2 = QtWidgets.QComboBox()
        for k, v in PARAM_DISPLAY_NAMES.items():
            self.combo_param_2.addItem(v, k)
        grid_expr.addWidget(self.combo_param_2, 0, 6)

        # Dòng 2: Math Offset & Kết quả
        grid_expr.addWidget(QtWidgets.QLabel("Phép bù trừ / Tỷ lệ:"), 1, 0)
        self.combo_math_op = QtWidgets.QComboBox()
        self.combo_math_op.addItem("Không bù trừ (NONE)", "NONE")
        self.combo_math_op.addItem("+ (Cộng)", "+")
        self.combo_math_op.addItem("- (Trừ)", "-")
        self.combo_math_op.addItem("* (Nhân)", "*")
        self.combo_math_op.addItem("/ (Chia)", "/")
        grid_expr.addWidget(self.combo_math_op, 1, 1)

        grid_expr.addWidget(QtWidgets.QLabel("Giá trị bù trừ:"), 1, 2)
        self.line_math_val = QtWidgets.QLineEdit("0")
        self.line_math_val.setPlaceholderText("VD: 15.5 hoặc Width/3")
        grid_expr.addWidget(self.line_math_val, 1, 3)

        grid_expr.addWidget(QtWidgets.QLabel("Khi điều kiện Đúng:"), 1, 4)
        self.combo_true_result = QtWidgets.QComboBox()
        self.combo_true_result.addItem("Đánh giá NG (Báo Lỗi)", "NG")
        self.combo_true_result.addItem("Đánh giá OK (Hợp Lệ)", "OK")
        grid_expr.addWidget(self.combo_true_result, 1, 5)

        # Nút Thao tác Rule (Thêm mới & Cập nhật)
        layout_rule_actions = QtWidgets.QHBoxLayout()
        self.btn_add_rule = QtWidgets.QPushButton("+ Thêm Mới")
        self.btn_add_rule.setObjectName("btnAddRule")
        self.btn_add_rule.setToolTip("Thêm một rule mới vào danh sách")
        self.btn_add_rule.setStyleSheet("""
        QPushButton {
            background-color: #313244;
            color: white;
            border: 1px solid #45475a;
            border-radius: 6px;
            padding: 4px;
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        QPushButton:hover {
            background-color: #313244;
            border: 1px solid #89b4fa;
        }
        QPushButton:pressed {
            background-color: #313244;
            border: 1px solid #38bdf8;
        }
        """)
        layout_rule_actions.addWidget(self.btn_add_rule)

        self.btn_update_rule = QtWidgets.QPushButton("💾 Cập Nhật")
        self.btn_update_rule.setObjectName("btnUpdateRule")
        self.btn_update_rule.setToolTip("Cập nhật lại rule đang chọn trên bảng")
        self.btn_update_rule.setStyleSheet("""
        QPushButton {
            background-color: #313244;
            color: white;
            border: 1px solid #45475a;
            border-radius: 6px;
            padding: 4px;
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        QPushButton:hover {
            background-color: #313244;
            border: 1px solid #89b4fa;
        }
        QPushButton:pressed {
            background-color: #313244;
            border: 1px solid #38bdf8;
        }
        """)
        layout_rule_actions.addWidget(self.btn_update_rule)

        grid_expr.addLayout(layout_rule_actions, 1, 6)

        vlayout_rule.addWidget(expr_frame)
        content_layout.addWidget(group_rule)

        # 3. BẢNG DANH SÁCH RULES CỦA TASK
        group_table = QtWidgets.QGroupBox("3. Danh sách các Quy Tắc (Rules) trong Task này (Nhấp vào dòng để chỉnh sửa)")
        vlayout_table = QtWidgets.QVBoxLayout(group_table)

        self.table_rules = QtWidgets.QTableWidget(0, 5)
        self.table_rules.setHorizontalHeaderLabels(["STT", "Biểu Thức Quy Tắc (Rule)", "Vế Trái (LHS)", "Toán Tử & Vế Phải (RHS)", "Thao Tác"])
        self.table_rules.horizontalHeader().setStretchLastSection(True)
        self.table_rules.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.table_rules.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_rules.setAlternatingRowColors(True)
        self.table_rules.setMinimumHeight(300)
        vlayout_table.addWidget(self.table_rules)

        content_layout.addWidget(group_table)

        self.scroll_area.setWidget(scroll_content)
        main_layout.addWidget(self.scroll_area, 1)

        # 4. ACTION BUTTONS BOTTOM (Ghim cố định ở đáy dialog để luôn nhìn thấy và thao tác được)
        bottom_frame = QtWidgets.QFrame()
        bottom_frame.setStyleSheet("background-color: #181825; border-radius: 6px; padding: 4px;")
        layout_bottom = QtWidgets.QHBoxLayout(bottom_frame)
        layout_bottom.setContentsMargins(8, 4, 8, 4)

        self.btn_delete_rule = QtWidgets.QPushButton("🗑️ Xóa Rule đã chọn")
        self.btn_delete_rule.setObjectName("btnDeleteRule")
        layout_bottom.addWidget(self.btn_delete_rule)

        layout_bottom.addStretch()

        self.btn_cancel = QtWidgets.QPushButton("Hủy Bỏ")
        self.btn_cancel.clicked.connect(self.reject)
        layout_bottom.addWidget(self.btn_cancel)

        self.btn_save = QtWidgets.QPushButton("💾 Lưu Task & Áp Dụng")
        self.btn_save.setObjectName("btnSave")
        self.btn_save.clicked.connect(self.save_task)
        layout_bottom.addWidget(self.btn_save)

        main_layout.addWidget(bottom_frame)

        # KẾT NỐI SIGNALS
        self.visual_canvas.hotspot_clicked.connect(self.on_canvas_hotspot_clicked)
        self.combo_label_1.currentTextChanged.connect(self.on_label_changed)
        self.combo_label_2.currentTextChanged.connect(self.on_label_changed)
        self.combo_param_1.currentIndexChanged.connect(self.on_form_param_changed)
        self.combo_param_2.currentIndexChanged.connect(self.on_form_param_changed)
        self.combo_operator.currentIndexChanged.connect(self.on_form_param_changed)
        self.combo_true_result.currentIndexChanged.connect(self.on_form_param_changed)
        self.combo_target_type.currentIndexChanged.connect(self.on_target_type_changed)
        self.combo_math_op.currentIndexChanged.connect(self.on_form_param_changed)
        self.line_math_val.textChanged.connect(self.on_form_param_changed)
        
        self.btn_add_rule.clicked.connect(self.add_rule_to_table)
        self.btn_update_rule.clicked.connect(self.update_current_rule)
        self.btn_delete_rule.clicked.connect(self.delete_selected_rule)
        
        # Bắt sự kiện chọn dòng trong bảng rules để load lên form và canvas
        self.table_rules.cellClicked.connect(self.on_rule_row_clicked)
        self.table_rules.itemSelectionChanged.connect(self.on_rule_selection_changed)

    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, '_initial_canvas_positioned'):
            self._initial_canvas_positioned = True
            QtCore.QTimer.singleShot(80, self.visual_canvas.reset_positions)

    def populate_data(self):
        """Đổ toàn bộ dữ liệu từ Database vào Form và Canvas chuẩn xác."""
        self._is_populating = True
        try:
            # 1. Đổ danh sách nhãn vào Combobox
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

            # 2. Đổ thông tin Task chung từ Database
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
                self.spin_plc_on.setValue(int(self.task_data.get('value_bit_on', 1)))
                self.spin_plc_off.setValue(int(self.task_data.get('value_bit_off', 0)))

            # 3. Đổ danh sách Rules vào bảng
            self.refresh_rules_table()

            # 4. Tự động load Rule đầu tiên (nếu có) lên Form và Canvas đồ họa
            if self.rules_list:
                self.load_rule_into_editor(0)
                self.table_rules.selectRow(0)
            else:
                # Nếu là Task mới tạo từ preselected_labels
                if len(self.preselected_labels) >= 2:
                    self.combo_label_1.setCurrentText(self.preselected_labels[0])
                    self.combo_label_2.setCurrentText(self.preselected_labels[1])
                elif len(self.preselected_labels) == 1:
                    self.combo_label_1.setCurrentText(self.preselected_labels[0])
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

            # 2. Vế trái LHS (Param 1)
            p1 = rule.get('param_1', 'X_MIN')
            idx_p1 = self.combo_param_1.findData(p1)
            if idx_p1 >= 0:
                self.combo_param_1.setCurrentIndex(idx_p1)

            # 3. Toán tử Operator
            op = rule.get('operator', '<')
            idx_op = self.combo_operator.findData(op)
            if idx_op >= 0:
                self.combo_operator.setCurrentIndex(idx_op)

            # 4. Target Type
            tt = rule.get('target_type', 'LABEL')
            idx_tt = self.combo_target_type.findData(tt)
            if idx_tt >= 0:
                self.combo_target_type.setCurrentIndex(idx_tt)
            self.on_target_type_changed()

            # 5. Vế phải RHS (Param 2)
            p2 = rule.get('param_2', 'X_MIN')
            idx_p2 = self.combo_param_2.findData(p2)
            if idx_p2 >= 0:
                self.combo_param_2.setCurrentIndex(idx_p2)

            # 6. Math Op & Value
            m_op = rule.get('math_op', 'NONE')
            idx_mop = self.combo_math_op.findData(m_op)
            if idx_mop >= 0:
                self.combo_math_op.setCurrentIndex(idx_mop)
            
            m_val = str(rule.get('math_operand_val', '0'))
            self.line_math_val.setText(m_val)

            # 7. Condition True Result
            c_res = rule.get('condition_true_result', 'NG')
            idx_cres = self.combo_true_result.findData(c_res)
            if idx_cres >= 0:
                self.combo_true_result.setCurrentIndex(idx_cres)

            # 8. Đồng bộ Canvas Đồ Họa trực quan
            self.visual_canvas.set_labels(lbl1, lbl2)
            self.visual_canvas.set_selected_param(1, p1)
            self.visual_canvas.set_selected_param(2, p2)
            self.visual_canvas.set_target_type(tt)
            self.visual_canvas.set_math_info(m_op, m_val)
            self.visual_canvas.set_operator_and_result(op, c_res)

            self.btn_update_rule.setText(f"💾 Cập Nhật Rule #{rule_idx + 1}")
            self.btn_update_rule.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: white;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 4px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background-color: #313244;
                border: 1px solid #89b4fa;
            }
            QPushButton:pressed {
                background-color: #313244;
                border: 1px solid #38bdf8;
            }
            """)
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
        """Khi click lên canvas, tự động đồng bộ combobox tương ứng."""
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
        """Thu thập dữ liệu từ Form thành Dictionary Rule."""
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

        lhs_str = f"{param1}({lbl1})"
        rhs_str = f"{param2}({lbl2})" if target_type == 'LABEL' else f"CONSTANT({math_val})"
        if math_op != 'NONE':
            rhs_str += f" {math_op} {math_val}"
        rule_desc = f"{lhs_str} {op} {rhs_str}  ==>  {true_res}"

        return {
            'label_1': lbl1,
            'param_1': param1,
            'instance_select_1': 'BEST_CONF',
            'operator': op,
            'target_type': target_type,
            'label_2': lbl2 if target_type == 'LABEL' else '',
            'param_2': param2,
            'instance_select_2': 'BEST_CONF',
            'math_op': math_op,
            'math_operand_type': 'CONSTANT',
            'math_operand_val': math_val,
            'min_value': 0.0,
            'max_value': 0.0,
            'condition_true_result': true_res,
            'enabled': True,
            'description': rule_desc
        }

    def add_rule_to_table(self):
        """Thêm 1 rule mới vào danh sách."""
        rule_obj = self._build_rule_dict_from_form()
        if not rule_obj:
            return

        self.rules_list.append(rule_obj)
        self.refresh_rules_table()
        # Chọn ngay dòng mới thêm
        new_row = len(self.rules_list) - 1
        self.table_rules.selectRow(new_row)
        self.load_rule_into_editor(new_row)

    def update_current_rule(self):
        """Cập nhật lại Rule đang chọn trên bảng với các giá trị vừa chỉnh sửa."""
        if self.editing_rule_index is None or not (0 <= self.editing_rule_index < len(self.rules_list)):
            self.add_rule_to_table()
            return

        rule_obj = self._build_rule_dict_from_form()
        if not rule_obj:
            return

        # Giữ lại id cũ của rule nếu có
        old_id = self.rules_list[self.editing_rule_index].get('id')
        if old_id:
            rule_obj['id'] = old_id

        self.rules_list[self.editing_rule_index] = rule_obj
        self.refresh_rules_table()
        self.table_rules.selectRow(self.editing_rule_index)
        self.load_rule_into_editor(self.editing_rule_index)

    def refresh_rules_table(self):
        self.table_rules.setRowCount(len(self.rules_list))
        for row_idx, r in enumerate(self.rules_list):
            item_stt = QtWidgets.QTableWidgetItem(str(row_idx + 1))
            item_stt.setTextAlignment(Qt.AlignCenter)
            self.table_rules.setItem(row_idx, 0, item_stt)

            desc = r.get('description') or f"{r['param_1']}({r['label_1']}) {r['operator']} {r.get('param_2')}({r.get('label_2')})"
            item_desc = QtWidgets.QTableWidgetItem(desc)
            self.table_rules.setItem(row_idx, 1, item_desc)

            item_lhs = QtWidgets.QTableWidgetItem(f"{r['label_1']} [{r['param_1']}]")
            self.table_rules.setItem(row_idx, 2, item_lhs)

            rhs_target = r.get('label_2') if r.get('target_type') == 'LABEL' else 'HẰNG SỐ'
            rhs_param_str = f"[{r.get('param_2')}]" if r.get('target_type') == 'LABEL' else ''
            rhs_info = f"{r['operator']} {rhs_target} {rhs_param_str}".strip()
            if r.get('math_op') != 'NONE':
                rhs_info += f" {r['math_op']} {r.get('math_operand_val')}"
            item_rhs = QtWidgets.QTableWidgetItem(rhs_info)
            self.table_rules.setItem(row_idx, 3, item_rhs)

            item_res = QtWidgets.QTableWidgetItem(f"Vi phạm ➜ {r.get('condition_true_result', 'NG')}")
            item_res.setTextAlignment(Qt.AlignCenter)
            if r.get('condition_true_result') == 'NG':
                item_res.setForeground(QColor("#f38ba8"))
            else:
                item_res.setForeground(QColor("#a6e3a1"))
            self.table_rules.setItem(row_idx, 4, item_res)

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
            'value_bit_on': self.spin_plc_on.value(),
            'value_bit_off': self.spin_plc_off.value(),
        }

        # Lưu vào Database
        from module_3.task_calculator_db import save_task_and_rules
        saved_id = save_task_and_rules(self.cursor, self.connection, task_data, self.rules_list)
        if saved_id:
            QtWidgets.QMessageBox.information(self, "Thành công", f"Đã lưu thành công Task '{task_name}' (ID: {saved_id}) cùng {len(self.rules_list)} rules!")
            self.accept()
        else:
            QtWidgets.QMessageBox.critical(self, "Lỗi Lưu Database", "Không thể lưu Task vào cơ sở dữ liệu. Vui lòng kiểm tra lại kết nối MySQL!")

