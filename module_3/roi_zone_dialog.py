"""
Module: roi_zone_dialog.py
Mục đích: Hộp thoại cấu hình độc lập cho "ROI Zone Inspector" (Khoanh Vùng ROI & Vùng Che Đa Vùng).
Phạm vi: ĐỘC LẬP THEO TỪNG TAB MODEL (Phù hợp với từng góc chụp riêng biệt của mỗi Shot trên dây chuyền).

Tính năng:
1. MultiZoneCanvasWidget:
   - Tải ảnh phôi mẫu hoặc snapshot từ camera.
   - Thao tác đa vùng trực quan: Kéo chuột vẽ vùng mới, bấm chọn vùng, di chuyển (move), co giãn (8 resize handles).
   - Tự do phân loại từng vùng:
     * INSPECTION (🟢 Vùng Kiểm Tra Lỗi): Bắt lỗi nếu nhãn mục tiêu xuất hiện trong vùng.
     * EXCLUSION (🔴 Vùng Che / Bỏ Qua Nhiễu): Triệt tiêu bóng lóa, logo cố định, khuôn cắt.
     * PRESENCE (🔵 Vùng Hiện Diện Linh Kiện): Bắt buộc phải có linh kiện (≥ min_count), thiếu là NG.
2. Tích hợp thanh ghi PLC đồng bộ 100% với Task Rule Calculator:
   - assign_register, value_state, value_ok, value_ng, action_on_fail.
3. Lưu trữ vào bảng task_roi_rules và đồng bộ tức thì vào RAM Process_Model.dict_active_tasks.
"""

import json
import os
import uuid
import cv2
import numpy as np
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, QRectF, QPointF, QRect, QPoint
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QImage, QPixmap, QCursor, QPainterPath

from app_logger.app_logger import get_logger
from module_3.task_calculator_db import (
    save_roi_task_and_rule,
    get_roi_rule
)

_log = get_logger('module_3.roi_zone_dialog')

# 8 Handle identifiers
HANDLE_NONE = 0
HANDLE_TL = 1
HANDLE_T  = 2
HANDLE_TR = 3
HANDLE_R  = 4
HANDLE_BR = 5
HANDLE_B  = 6
HANDLE_BL = 7
HANDLE_L  = 8
HANDLE_SIZE = 8


class MultiZoneCanvasWidget(QtWidgets.QWidget):
    """
    Widget hiển thị ảnh phôi mẫu và cho phép tương tác đa vùng ROI (Multi-Zone ROI).
    Hỗ trợ:
    - Kéo chuột tạo vùng mới
    - Chọn vùng, di chuyển vùng (drag move)
    - Co giãn vùng qua 8 handles (resize handles)
    - Xóa vùng bằng phím Delete
    - Tọa độ chuẩn hóa (0.0 -> 1.0)
    """
    zoneSelected = QtCore.pyqtSignal(int)
    zonesChanged = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 420)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        self.pixmap: QPixmap = None
        self.image_w = 0
        self.image_h = 0

        # Danh sách các vùng ROI: [ { 'id', 'name', 'zone_type', 'rect': [x1,y1,x2,y2], 'target_label', 'min_count' }, ... ]
        self.zones = []
        self.selected_idx = -1

        # Trạng thái chuột tương tác
        self._interaction_mode = 'NONE'  # 'NONE', 'CREATING', 'MOVING', 'RESIZING'
        self._active_handle = HANDLE_NONE
        self._drag_start_pos = None
        self._drag_current_pos = None
        self._original_rect = None  # [x1, y1, x2, y2] normalized khi bắt đầu drag/resize

    def load_image_from_path(self, file_path: str) -> bool:
        """Tải ảnh từ tệp tin cục bộ."""
        if not os.path.exists(file_path):
            return False
        pm = QPixmap(file_path)
        if pm.isNull():
            return False
        self.pixmap = pm
        self.image_w = pm.width()
        self.image_h = pm.height()
        self.update()
        return True

    def load_image_from_numpy(self, img_rgb: np.ndarray) -> bool:
        """Tải ảnh trực tiếp từ mảng numpy RGB (ví dụ từ camera)."""
        if img_rgb is None or img_rgb.size == 0:
            return False
        h, w = img_rgb.shape[:2]
        bytes_per_line = 3 * w
        qimg = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.pixmap = QPixmap.fromImage(qimg)
        self.image_w = w
        self.image_h = h
        self.update()
        return True

    def set_zones(self, zones_list: list):
        """Đặt danh sách các vùng ROI hiện có."""
        self.zones = []
        for z in (zones_list or []):
            if isinstance(z, dict):
                rect = z.get('rect', [0.1, 0.1, 0.4, 0.4])
                self.zones.append({
                    'id': str(z.get('id') or uuid.uuid4().hex[:6]),
                    'name': str(z.get('name') or f"Vùng_{len(self.zones)+1}"),
                    'zone_type': str(z.get('zone_type') or 'INSPECTION').upper(),
                    'rect': [
                        max(0.0, min(1.0, float(rect[0]))),
                        max(0.0, min(1.0, float(rect[1]))),
                        max(0.0, min(1.0, float(rect[2]))),
                        max(0.0, min(1.0, float(rect[3])))
                    ],
                    'target_label': str(z.get('target_label') or 'ALL'),
                    'min_count': int(z.get('min_count', 1)),
                    'follow_label_enabled': bool(z.get('follow_label_enabled', False)),
                    'anchor_label': str(z.get('anchor_label') or ''),
                    'follow_mode': str(z.get('follow_mode') or 'CENTER')
                })
        self.selected_idx = 0 if self.zones else -1
        self.update()
        self.zonesChanged.emit()
        self.zoneSelected.emit(self.selected_idx)

    def get_zones(self) -> list:
        """Lấy danh sách các vùng ROI đã chuẩn hóa."""
        return self.zones

    def add_new_zone(self, zone_type='INSPECTION', target_label='ALL', rect=None, follow_label_enabled=False, anchor_label='', follow_mode='CENTER'):
        """Thêm thủ công một vùng ROI mới."""
        if rect is None:
            rect = [0.15, 0.15, 0.55, 0.55]
        new_z = {
            'id': uuid.uuid4().hex[:6],
            'name': f"Vùng {len(self.zones)+1}",
            'zone_type': zone_type,
            'rect': rect,
            'target_label': target_label,
            'min_count': 1 if zone_type == 'PRESENCE' else 0,
            'follow_label_enabled': follow_label_enabled,
            'anchor_label': anchor_label,
            'follow_mode': follow_mode
        }
        self.zones.append(new_z)
        self.selected_idx = len(self.zones) - 1
        self.update()
        self.zonesChanged.emit()
        self.zoneSelected.emit(self.selected_idx)

    def delete_selected_zone(self):
        """Xóa vùng đang được chọn."""
        if 0 <= self.selected_idx < len(self.zones):
            self.zones.pop(self.selected_idx)
            if self.selected_idx >= len(self.zones):
                self.selected_idx = len(self.zones) - 1
            self.update()
            self.zonesChanged.emit()
            self.zoneSelected.emit(self.selected_idx)

    def clear_all_zones(self):
        """Xóa toàn bộ các vùng ROI."""
        self.zones.clear()
        self.selected_idx = -1
        self.update()
        self.zonesChanged.emit()
        self.zoneSelected.emit(-1)

    def select_zone(self, index: int):
        """Chọn vùng theo chỉ mục."""
        if 0 <= index < len(self.zones):
            self.selected_idx = index
        else:
            self.selected_idx = -1
        self.update()
        self.zoneSelected.emit(self.selected_idx)

    # ----------------------- TÍNH TOÁN HÌNH HỌC & CANVAS -----------------------
    def _get_draw_rect(self) -> QRect:
        """Tính toán khung vẽ ảnh giữ nguyên tỷ lệ (aspect ratio)."""
        w, h = self.width(), self.height()
        if not self.pixmap or self.pixmap.isNull():
            return QRect(12, 12, max(10, w - 24), max(10, h - 24))

        pw, ph = self.pixmap.width(), self.pixmap.height()
        scale = min((w - 24) / max(1, pw), (h - 24) / max(1, ph))
        tw = int(pw * scale)
        th = int(ph * scale)
        tx = (w - tw) // 2
        ty = (h - th) // 2
        return QRect(tx, ty, tw, th)

    def _norm_to_px(self, norm_rect: list, draw_rect: QRect) -> QRect:
        """Chuyển tọa độ chuẩn hóa [x1, y1, x2, y2] sang QRect pixel trên màn hình."""
        x1, y1, x2, y2 = norm_rect
        px1 = draw_rect.left() + int(x1 * draw_rect.width())
        py1 = draw_rect.top() + int(y1 * draw_rect.height())
        pw = int((x2 - x1) * draw_rect.width())
        ph = int((y2 - y1) * draw_rect.height())
        return QRect(px1, py1, max(2, pw), max(2, ph))

    def _px_to_norm(self, px_pt: QPoint, draw_rect: QRect) -> tuple:
        """Chuyển tọa độ pixel widget sang tọa độ chuẩn hóa (0.0 - 1.0)."""
        nx = (px_pt.x() - draw_rect.left()) / max(1.0, float(draw_rect.width()))
        ny = (px_pt.y() - draw_rect.top()) / max(1.0, float(draw_rect.height()))
        return max(0.0, min(1.0, nx)), max(0.0, min(1.0, ny))

    def _get_handles_for_rect(self, qrect: QRect) -> dict:
        """Trả về vị trí 8 handles của hình chữ nhật pixel."""
        x1, y1, x2, y2 = qrect.left(), qrect.top(), qrect.right(), qrect.bottom()
        mx = (x1 + x2) // 2
        my = (y1 + y2) // 2
        hs = HANDLE_SIZE // 2
        return {
            HANDLE_TL: QRect(x1 - hs, y1 - hs, HANDLE_SIZE, HANDLE_SIZE),
            HANDLE_T:  QRect(mx - hs, y1 - hs, HANDLE_SIZE, HANDLE_SIZE),
            HANDLE_TR: QRect(x2 - hs, y1 - hs, HANDLE_SIZE, HANDLE_SIZE),
            HANDLE_R:  QRect(x2 - hs, my - hs, HANDLE_SIZE, HANDLE_SIZE),
            HANDLE_BR: QRect(x2 - hs, y2 - hs, HANDLE_SIZE, HANDLE_SIZE),
            HANDLE_B:  QRect(mx - hs, y2 - hs, HANDLE_SIZE, HANDLE_SIZE),
            HANDLE_BL: QRect(x1 - hs, y2 - hs, HANDLE_SIZE, HANDLE_SIZE),
            HANDLE_L:  QRect(x1 - hs, my - hs, HANDLE_SIZE, HANDLE_SIZE),
        }

    def _hit_test_handle(self, pt: QPoint, qrect: QRect) -> int:
        """Kiểm tra xem điểm pt có trúng vào handle nào trong 8 handle không."""
        handles = self._get_handles_for_rect(qrect)
        for h_id, h_rect in handles.items():
            if h_rect.adjusted(-2, -2, 2, 2).contains(pt):
                return h_id
        return HANDLE_NONE

    # ----------------------- VẼ GIAO DIỆN (PAINT EVENT) -----------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Nền canvas tối chuyên nghiệp
        painter.fillRect(self.rect(), QColor("#0f172a"))
        draw_rect = self._get_draw_rect()

        if self.pixmap and not self.pixmap.isNull():
            painter.drawPixmap(draw_rect, self.pixmap)
        else:
            # Lưới placeholder khi chưa tải ảnh
            painter.setPen(QPen(QColor("#1e293b"), 1, Qt.DotLine))
            step = 32
            for x in range(draw_rect.left(), draw_rect.right(), step):
                painter.drawLine(x, draw_rect.top(), x, draw_rect.bottom())
            for y in range(draw_rect.top(), draw_rect.bottom(), step):
                painter.drawLine(draw_rect.left(), y, draw_rect.right(), y)

            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
            painter.drawText(
                draw_rect, Qt.AlignCenter,
                "Chưa có ảnh mẫu\nNhấn '📂 Tải Ảnh Mẫu' hoặc '📸 Lấy Ảnh Camera'\nKéo chuột vẽ trực tiếp các vùng ROI lên khung nhìn"
            )

        # Viền bao quanh khung ảnh
        painter.setPen(QPen(QColor("#334155"), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(draw_rect)

        # =========================================================================
        # HIỆU ỨNG LÀM ĐEN MỜ / HIGHLIGHT VÙNG ROI (DIMMING & HIGHLIGHT EFFECT)
        # =========================================================================
        # 1. Với các vùng INSPECTION & PRESENCE (Khu vực bắt lỗi / kiểm tra linh kiện):
        #    -> Vùng NGOÀI các ROI này sẽ bị làm đen mờ (dimmed) để làm nổi bật (highlight) khu vực kiểm tra.
        clear_rects = []
        for z in self.zones:
            z_type = z.get('zone_type', 'INSPECTION')
            if z_type in ('INSPECTION', 'PRESENCE'):
                clear_rects.append(self._norm_to_px(z['rect'], draw_rect))

        # Nếu đang kéo chuột vẽ vùng mới (Drafting) và chưa phải EXCLUSION:
        if self._interaction_mode == 'CREATING' and self._drag_start_pos and self._drag_current_pos:
            x1 = min(self._drag_start_pos.x(), self._drag_current_pos.x())
            y1 = min(self._drag_start_pos.y(), self._drag_current_pos.y())
            w = abs(self._drag_start_pos.x() - self._drag_current_pos.x())
            h = abs(self._drag_start_pos.y() - self._drag_current_pos.y())
            clear_rects.append(QRect(x1, y1, w, h))

        if clear_rects:
            full_path = QPainterPath()
            full_path.addRect(QRectF(draw_rect))
            keep_clear_path = QPainterPath()
            for r in clear_rects:
                keep_clear_path.addRect(QRectF(r))
            outside_dim_path = full_path.subtracted(keep_clear_path)
            # Phủ lớp mờ đen bán trong suốt ngoài vùng kiểm tra (Highlight Spotlight)
            painter.fillPath(outside_dim_path, QColor(0, 0, 0, 140))

        # 2. Với vùng EXCLUSION (Vùng Che / Bỏ Qua Nhiễu):
        #    -> Vùng BÊN TRONG ROI EXCLUSION sẽ bị làm đen mờ (che / mask), ngoài vùng giữ ảnh gốc
        for z in self.zones:
            if z.get('zone_type') == 'EXCLUSION':
                ex_box = self._norm_to_px(z['rect'], draw_rect)
                painter.fillRect(ex_box, QColor(0, 0, 0, 160))

        # Vẽ từng vùng ROI
        for idx, z in enumerate(self.zones):
            is_sel = (idx == self.selected_idx)
            z_type = z.get('zone_type', 'INSPECTION')
            q_box = self._norm_to_px(z['rect'], draw_rect)
            is_follow = bool(z.get('follow_label_enabled', False))
            anchor_lbl = str(z.get('anchor_label') or '')

            # Phối màu theo loại vùng
            if z_type == 'EXCLUSION':
                border_color = QColor(239, 68, 68)   # Đỏ cam (Mask / Che nhiễu)
                fill_color = QColor(239, 68, 68, 30)
                type_tag = "MASK (CHE)"
            elif z_type == 'PRESENCE':
                border_color = QColor(59, 130, 246)  # Xanh dương (Hiện diện)
                fill_color = QColor(59, 130, 246, 30)
                type_tag = f"HIỆN DIỆN (≥{z.get('min_count', 1)})"
            else:  # INSPECTION
                border_color = QColor(16, 185, 129)  # Xanh ngọc (Kiểm tra lỗi)
                fill_color = QColor(16, 185, 129, 30)
                type_tag = "KIỂM TRA"

            # Fill
            painter.fillRect(q_box, fill_color)

            # Border
            if is_sel:
                pen = QPen(QColor(245, 158, 11), 2.5, Qt.DashLine)  # Hổ phách nếu đang chọn
            else:
                pen = QPen(border_color, 1.8, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(q_box)

            # Badge tiêu đề vùng (hiển thị kèm icon bám nhãn 🎯 nếu kích hoạt)
            follow_str = f" 🎯{anchor_lbl}" if is_follow and anchor_lbl else (" 🎯Follow" if is_follow else "")
            badge_text = f"[{type_tag}{follow_str}] {z.get('name', '')} ({z.get('target_label', 'ALL')})"
            painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
            fm = painter.fontMetrics()
            tw = fm.width(badge_text) + 12
            th = fm.height() + 4

            bx = q_box.left()
            by = max(draw_rect.top(), q_box.top() - th - 2)
            badge_rect = QRect(bx, by, tw, th)

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(border_color if not is_sel else QColor(245, 158, 11)))
            painter.drawRoundedRect(badge_rect, 3, 3)

            painter.setPen(QColor("#ffffff") if not is_sel else QColor("#0f172a"))
            painter.drawText(badge_rect, Qt.AlignCenter, badge_text)

            # Nếu là vùng bám nhãn định vị: Vẽ biểu tượng tâm ngắm (crosshair target) ở tâm ROI
            if is_follow:
                mcx = q_box.center().x()
                mcy = q_box.center().y()
                painter.setPen(QPen(border_color if not is_sel else QColor(245, 158, 11), 1.5, Qt.DashLine))
                painter.drawLine(mcx - 10, mcy, mcx + 10, mcy)
                painter.drawLine(mcx, mcy - 10, mcx, mcy + 10)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPoint(mcx, mcy), 5, 5)

            # Nếu đang chọn: Vẽ 8 resize handles
            if is_sel:
                handles = self._get_handles_for_rect(q_box)
                painter.setPen(QPen(QColor(245, 158, 11), 1.5))
                painter.setBrush(QBrush(QColor("#ffffff")))
                for h_rect in handles.values():
                    painter.drawRect(h_rect)

        # Vẽ vùng đang được kéo tạo mới (Drafting)
        if self._interaction_mode == 'CREATING' and self._drag_start_pos and self._drag_current_pos:
            x1 = min(self._drag_start_pos.x(), self._drag_current_pos.x())
            y1 = min(self._drag_start_pos.y(), self._drag_current_pos.y())
            w = abs(self._drag_start_pos.x() - self._drag_current_pos.x())
            h = abs(self._drag_start_pos.y() - self._drag_current_pos.y())
            draft_rect = QRect(x1, y1, w, h)

            painter.fillRect(draft_rect, QColor(16, 185, 129, 60))
            painter.setPen(QPen(QColor(16, 185, 129), 2, Qt.DashLine))
            painter.drawRect(draft_rect)

    # ----------------------- SỰ KIỆN CHUỘT (INTERACTION) -----------------------
    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        draw_rect = self._get_draw_rect()
        pt = event.pos()

        # Kiểm tra click vào handles của vùng đang chọn trước
        if 0 <= self.selected_idx < len(self.zones):
            sel_rect = self._norm_to_px(self.zones[self.selected_idx]['rect'], draw_rect)
            handle = self._hit_test_handle(pt, sel_rect)
            if handle != HANDLE_NONE:
                self._interaction_mode = 'RESIZING'
                self._active_handle = handle
                self._drag_start_pos = pt
                self._original_rect = list(self.zones[self.selected_idx]['rect'])
                return

        # Kiểm tra click vào bên trong một vùng nào đó
        clicked_zone_idx = -1
        for idx in reversed(range(len(self.zones))):
            z_rect = self._norm_to_px(self.zones[idx]['rect'], draw_rect)
            if z_rect.contains(pt):
                clicked_zone_idx = idx
                break

        if clicked_zone_idx >= 0:
            self.selected_idx = clicked_zone_idx
            self._interaction_mode = 'MOVING'
            self._drag_start_pos = pt
            self._original_rect = list(self.zones[clicked_zone_idx]['rect'])
            self.update()
            self.zoneSelected.emit(self.selected_idx)
            return

        # Nếu click vào vùng trống trong khung ảnh -> Bắt đầu vẽ tạo vùng mới
        if draw_rect.contains(pt):
            self.selected_idx = -1
            self._interaction_mode = 'CREATING'
            self._drag_start_pos = pt
            self._drag_current_pos = pt
            self.update()
            self.zoneSelected.emit(-1)

    def mouseMoveEvent(self, event):
        draw_rect = self._get_draw_rect()
        pt = event.pos()

        # 1. Đang kéo tạo vùng mới
        if self._interaction_mode == 'CREATING':
            self._drag_current_pos = pt
            self.update()
            return

        # 2. Đang di chuyển vùng (Move)
        if self._interaction_mode == 'MOVING' and 0 <= self.selected_idx < len(self.zones):
            dx_norm = (pt.x() - self._drag_start_pos.x()) / max(1.0, float(draw_rect.width()))
            dy_norm = (pt.y() - self._drag_start_pos.y()) / max(1.0, float(draw_rect.height()))

            ox1, oy1, ox2, oy2 = self._original_rect
            w = ox2 - ox1
            h = oy2 - oy1

            nx1 = max(0.0, min(1.0 - w, ox1 + dx_norm))
            ny1 = max(0.0, min(1.0 - h, oy1 + dy_norm))
            nx2 = nx1 + w
            ny2 = ny1 + h

            self.zones[self.selected_idx]['rect'] = [round(nx1, 4), round(ny1, 4), round(nx2, 4), round(ny2, 4)]
            self.update()
            self.zonesChanged.emit()
            return

        # 3. Đang co giãn vùng (Resize)
        if self._interaction_mode == 'RESIZING' and 0 <= self.selected_idx < len(self.zones):
            dx_norm = (pt.x() - self._drag_start_pos.x()) / max(1.0, float(draw_rect.width()))
            dy_norm = (pt.y() - self._drag_start_pos.y()) / max(1.0, float(draw_rect.height()))

            ox1, oy1, ox2, oy2 = self._original_rect
            nx1, ny1, nx2, ny2 = ox1, oy1, ox2, oy2

            if self._active_handle in (HANDLE_TL, HANDLE_L, HANDLE_BL):
                nx1 = max(0.0, min(ox2 - 0.02, ox1 + dx_norm))
            if self._active_handle in (HANDLE_TR, HANDLE_R, HANDLE_BR):
                nx2 = max(ox1 + 0.02, min(1.0, ox2 + dx_norm))
            if self._active_handle in (HANDLE_TL, HANDLE_T, HANDLE_TR):
                ny1 = max(0.0, min(oy2 - 0.02, oy1 + dy_norm))
            if self._active_handle in (HANDLE_BL, HANDLE_B, HANDLE_BR):
                ny2 = max(oy1 + 0.02, min(1.0, oy2 + dy_norm))

            self.zones[self.selected_idx]['rect'] = [round(nx1, 4), round(ny1, 4), round(nx2, 4), round(ny2, 4)]
            self.update()
            self.zonesChanged.emit()
            return

        # 4. Di chuột bình thường -> Đổi icon con trỏ chuột phù hợp
        if 0 <= self.selected_idx < len(self.zones):
            sel_rect = self._norm_to_px(self.zones[self.selected_idx]['rect'], draw_rect)
            handle = self._hit_test_handle(pt, sel_rect)
            if handle in (HANDLE_TL, HANDLE_BR):
                self.setCursor(Qt.SizeFDiagCursor)
                return
            elif handle in (HANDLE_TR, HANDLE_BL):
                self.setCursor(Qt.SizeBDiagCursor)
                return
            elif handle in (HANDLE_T, HANDLE_B):
                self.setCursor(Qt.SizeVerCursor)
                return
            elif handle in (HANDLE_L, HANDLE_R):
                self.setCursor(Qt.SizeHorCursor)
                return
            elif sel_rect.contains(pt):
                self.setCursor(Qt.SizeAllCursor)
                return

        # Kiểm tra hover trên các vùng khác
        for z in self.zones:
            if self._norm_to_px(z['rect'], draw_rect).contains(pt):
                self.setCursor(Qt.PointingHandCursor)
                return

        if draw_rect.contains(pt):
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        draw_rect = self._get_draw_rect()

        if self._interaction_mode == 'CREATING' and self._drag_start_pos and self._drag_current_pos:
            nx1, ny1 = self._px_to_norm(self._drag_start_pos, draw_rect)
            nx2, ny2 = self._px_to_norm(self._drag_current_pos, draw_rect)

            rx1, rx2 = min(nx1, nx2), max(nx1, nx2)
            ry1, ry2 = min(ny1, ny2), max(ny1, ny2)

            # Tối thiểu kích thước 2%
            if (rx2 - rx1) >= 0.02 and (ry2 - ry1) >= 0.02:
                new_zone = {
                    'id': uuid.uuid4().hex[:6],
                    'name': f"Vùng {len(self.zones)+1}",
                    'zone_type': 'INSPECTION',
                    'rect': [round(rx1, 4), round(ry1, 4), round(rx2, 4), round(ry2, 4)],
                    'target_label': 'ALL',
                    'min_count': 0,
                    'follow_label_enabled': False,
                    'anchor_label': '',
                    'follow_mode': 'CENTER'
                }
                self.zones.append(new_zone)
                self.selected_idx = len(self.zones) - 1
                self.zonesChanged.emit()
                self.zoneSelected.emit(self.selected_idx)

        self._interaction_mode = 'NONE'
        self._active_handle = HANDLE_NONE
        self._drag_start_pos = None
        self._drag_current_pos = None
        self._original_rect = None
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete and 0 <= self.selected_idx < len(self.zones):
            self.delete_selected_zone()
        else:
            super().keyPressEvent(event)


# ==============================================================================
# ROI ZONE EDITOR DIALOG (CỬA SỔ CẤU HÌNH TÁC VỤ KHOANH VÙNG ROI)
# ==============================================================================
class RoiZoneEditorDialog(QtWidgets.QDialog):
    """
    Dialog cấu hình độc lập cho 'ROI Zone Inspector' (Khoanh Vùng ROI & Vùng Che Đa Vùng).
    Phạm vi: Riêng cho 1 tab Model tương ứng (single model scope).
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

        self.setWindowTitle(f"🖼️ Cấu Hình Khoanh Vùng ROI & Vùng Che - Model {self.model_id}")
        self.resize(1300, 750)
        self.setMinimumSize(1300, 750)

        self._updating_form = False
        self._init_ui()
        self._load_data_to_form()

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(12)

        # Header Bar
        header_layout = QtWidgets.QHBoxLayout()
        header_title = QtWidgets.QLabel("🖼️ ROI ZONE INSPECTOR (KHOANH VÙNG ROI & VÙNG CHE ĐA VÙNG)")
        header_title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        header_title.setStyleSheet("color: #0f172a;")
        header_layout.addWidget(header_title)

        header_layout.addStretch()

        badge_scope = QtWidgets.QLabel(f"Camera: {self.camera_id} | Tab Model: {self.model_id} (Góc Chụp Riêng Biệt)")
        badge_scope.setToolTip("Task ROI này hoạt động độc lập cho riêng Model/Góc chụp này, không làm ảnh hưởng đến các góc chụp khác.")
        badge_scope.setStyleSheet("""
            background-color: #e0f2fe;
            color: #0369a1;
            font-weight: bold;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
        """)
        header_layout.addWidget(badge_scope)
        main_layout.addLayout(header_layout)

        # Content 2 columns
        body_layout = QtWidgets.QHBoxLayout()
        body_layout.setSpacing(16)

        # ------------------- CỘT TRÁI: Multi-Zone Canvas & Tools -------------------
        left_box = QtWidgets.QGroupBox("🎨 Khung Vẽ Vùng ROI Trực Quan (Interactive Multi-Zone Canvas)")
        left_box.setStyleSheet("""
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
        """)
        left_layout = QtWidgets.QVBoxLayout(left_box)
        left_layout.setSpacing(8)

        # Top Tools Layout
        tools_layout = QtWidgets.QHBoxLayout()
        tools_layout.setSpacing(8)

        self.btn_load_img = QtWidgets.QPushButton("📂 Tải Ảnh Mẫu")
        self.btn_load_img.setCursor(Qt.PointingHandCursor)
        self.btn_load_img.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        self.btn_load_img.clicked.connect(self._on_load_sample_image)
        tools_layout.addWidget(self.btn_load_img)

        self.btn_add_zone = QtWidgets.QPushButton("➕ Thêm Vùng ROI")
        self.btn_add_zone.setCursor(Qt.PointingHandCursor)
        self.btn_add_zone.setStyleSheet("""
            QPushButton {
                background-color: #ecfdf5;
                color: #047857;
                border: 1px solid #a7f3d0;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #d1fae5; }
        """)
        self.btn_add_zone.clicked.connect(lambda: self.canvas.add_new_zone('INSPECTION'))
        tools_layout.addWidget(self.btn_add_zone)

        self.btn_del_zone = QtWidgets.QPushButton("🗑️ Xóa Vùng Chọn")
        self.btn_del_zone.setCursor(Qt.PointingHandCursor)
        self.btn_del_zone.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                color: #b91c1c;
                border: 1px solid #fca5a5;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #fecaca; }
        """)
        self.btn_del_zone.clicked.connect(self._on_delete_selected_zone)
        tools_layout.addWidget(self.btn_del_zone)

        self.btn_clear_all = QtWidgets.QPushButton("🧹 Xóa Hết")
        self.btn_clear_all.setCursor(Qt.PointingHandCursor)
        self.btn_clear_all.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                color: #64748b;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #f1f5f9; color: #0f172a; }
        """)
        self.btn_clear_all.clicked.connect(self._on_clear_all_zones)
        tools_layout.addWidget(self.btn_clear_all)

        tools_layout.addStretch()
        left_layout.addLayout(tools_layout)

        # MultiZone Canvas
        self.canvas = MultiZoneCanvasWidget(self)
        self.canvas.zoneSelected.connect(self._on_canvas_zone_selected)
        self.canvas.zonesChanged.connect(self._on_canvas_zones_changed)
        left_layout.addWidget(self.canvas, 1)

        # Bottom Info Bar for Canvas
        self.lbl_canvas_status = QtWidgets.QLabel("💡 Mẹo: Kéo chuột trên canvas để vẽ vùng mới. Bấm vào vùng để di chuyển hoặc kéo 8 điểm góc để co giãn.")
        self.lbl_canvas_status.setStyleSheet("font-size: 11px; color: #64748b;")
        left_layout.addWidget(self.lbl_canvas_status)

        body_layout.addWidget(left_box, 6)

        # ------------------- CỘT PHẢI: Danh Sách Vùng & Cấu Hình PLC -------------------
        right_scroll = QtWidgets.QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 1. Định danh tác vụ
        grp_info = QtWidgets.QGroupBox("📋 1. Định Danh Tác Vụ")
        grp_info.setStyleSheet(left_box.styleSheet())
        layout_info = QtWidgets.QFormLayout(grp_info)
        layout_info.setSpacing(8)

        self.txt_task_name = QtWidgets.QLineEdit()
        self.txt_task_name.setPlaceholderText(f"Ví dụ: Kiem_Tra_ROI_Model_{self.model_id}")
        layout_info.addRow("Tên Task:", self.txt_task_name)

        self.chk_task_enabled = QtWidgets.QCheckBox("Kích hoạt hoạt động [✓]")
        self.chk_task_enabled.setChecked(True)
        layout_info.addRow("Trạng Thái:", self.chk_task_enabled)

        right_layout.addWidget(grp_info)

        # 2. Chi tiết Vùng ROI được chọn
        grp_zone_detail = QtWidgets.QGroupBox("🎯 2. Chi Tiết Vùng ROI Được Chọn")
        grp_zone_detail.setStyleSheet(left_box.styleSheet())
        layout_zd = QtWidgets.QFormLayout(grp_zone_detail)
        layout_zd.setSpacing(8)

        # Bảng danh sách các vùng
        self.table_zones = QtWidgets.QTableWidget(0, 5)
        self.table_zones.setHorizontalHeaderLabels(["Tên Vùng", "Loại Vùng", "Nhãn Áp Dụng", "Bám Nhãn", "Tọa Độ"])
        self.table_zones.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.table_zones.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_zones.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table_zones.setFixedHeight(120)
        self.table_zones.itemSelectionChanged.connect(self._on_table_zone_selection_changed)
        layout_zd.addRow(self.table_zones)

        self.txt_zone_name = QtWidgets.QLineEdit()
        self.txt_zone_name.textChanged.connect(self._on_zone_field_changed)
        layout_zd.addRow("Tên Vùng:", self.txt_zone_name)

        self.combo_zone_type = QtWidgets.QComboBox()
        self.combo_zone_type.addItems([
            "🟢 INSPECTION (Vùng Kiểm Tra Bắt Lỗi)",
            "🔴 EXCLUSION (Vùng Che / Bỏ Qua Nhiễu)",
            "🔵 PRESENCE (Vùng Kiểm Tra Hiện Diện)"
        ])
        self.combo_zone_type.currentIndexChanged.connect(self._on_zone_type_changed)
        layout_zd.addRow("Loại Vùng:", self.combo_zone_type)

        self.combo_zone_label = QtWidgets.QComboBox()
        self.combo_zone_label.setEditable(True)
        self.combo_zone_label.addItem("ALL (Tất cả nhãn)")
        for lbl in self.available_labels:
            self.combo_zone_label.addItem(lbl)
        self.combo_zone_label.currentTextChanged.connect(self._on_zone_field_changed)
        layout_zd.addRow("Nhãn Áp Dụng:", self.combo_zone_label)

        self.spin_min_count = QtWidgets.QSpinBox()
        self.spin_min_count.setRange(1, 100)
        self.spin_min_count.setValue(1)
        self.spin_min_count.valueChanged.connect(self._on_zone_field_changed)
        layout_zd.addRow("Số lượng tối thiểu:", self.spin_min_count)

        # --- TÙY CHỌN: TỌA ĐỘ VÙNG ROI FOLLOW THEO TỌA ĐỘ NHÃN ĐƯỢC CHỌN ---
        self.chk_follow_label = QtWidgets.QCheckBox("🎯 Bám theo nhãn định vị (ROI Follows Label)")
        self.chk_follow_label.setStyleSheet("font-weight: 600; color: #0f172a;")
        self.chk_follow_label.toggled.connect(self._on_follow_label_toggled)
        layout_zd.addRow("Chế Độ Định Vị:", self.chk_follow_label)

        self.combo_anchor_label = QtWidgets.QComboBox()
        self.combo_anchor_label.setEditable(True)
        for lbl in self.available_labels:
            self.combo_anchor_label.addItem(lbl)
        self.combo_anchor_label.currentTextChanged.connect(self._on_zone_field_changed)
        layout_zd.addRow("Nhãn Định Vị (Anchor):", self.combo_anchor_label)

        self.combo_follow_mode = QtWidgets.QComboBox()
        self.combo_follow_mode.addItem("Tâm nhãn (Giữ kích thước ROI vẽ)", "CENTER")
        self.combo_follow_mode.addItem("Khớp khung Bounding Box của nhãn", "BBOX")
        self.combo_follow_mode.currentIndexChanged.connect(self._on_zone_field_changed)
        layout_zd.addRow("Kiểu Bám Tọa Độ:", self.combo_follow_mode)

        self.lbl_zone_hint = QtWidgets.QLabel()
        self.lbl_zone_hint.setWordWrap(True)
        self.lbl_zone_hint.setStyleSheet("""
            background-color: #f8fafc;
            border-left: 3px solid #10b981;
            color: #334155;
            padding: 6px 8px;
            font-size: 11px;
            border-radius: 0 4px 4px 0;
        """)
        layout_zd.addRow(self.lbl_zone_hint)

        right_layout.addWidget(grp_zone_detail)

        # 3. Cấu hình thanh ghi PLC
        grp_plc = QtWidgets.QGroupBox("🔌 3. Tín Hiệu Thanh Ghi PLC")
        grp_plc.setStyleSheet(left_box.styleSheet())
        layout_plc = QtWidgets.QFormLayout(grp_plc)
        layout_plc.setSpacing(8)

        self.txt_plc_register = QtWidgets.QLineEdit()
        self.txt_plc_register.setPlaceholderText("Ví dụ: D110, M20, R300... (Để trống nếu không gửi)")
        layout_plc.addRow("Thanh ghi PLC:", self.txt_plc_register)

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
        layout_plc.addRow("Khi vi phạm:", self.combo_action_fail)

        self.txt_description = QtWidgets.QLineEdit()
        self.txt_description.setPlaceholderText("Ghi chú nghiệp vụ...")
        layout_plc.addRow("Ghi chú / Mô tả:", self.txt_description)

        right_layout.addWidget(grp_plc)
        right_layout.addStretch()

        right_scroll.setWidget(right_widget)
        body_layout.addWidget(right_scroll, 5)

        main_layout.addLayout(body_layout)

        # Bottom Buttons Bar
        bottom_layout = QtWidgets.QHBoxLayout()
        lbl_guide = QtWidgets.QLabel("💡 Gợi ý: Mỗi tab Model đại diện cho một góc chụp riêng. Cấu hình ROI sẽ chỉ áp dụng cho riêng Model này.")
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
                background-color: #0284c7;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        self.btn_save.clicked.connect(self._on_save_config)
        bottom_layout.addWidget(self.btn_save)

        main_layout.addLayout(bottom_layout)

    # ----------------------- TẢI DỮ LIỆU & ĐỒNG BỘ FORM -----------------------
    def _load_data_to_form(self):
        self._updating_form = True

        # Basic Info
        tname = self.task_data.get('task_name') or f"ROI_Inspection_Model_{self.model_id}"
        self.txt_task_name.setText(tname)
        self.chk_task_enabled.setChecked(bool(self.task_data.get('enabled', True)))

        # PLC
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

        self.txt_description.setText(str(self.rule_data.get('description', '') or ''))

        # Load Zones
        zones = self.rule_data.get('zones', [])
        if not zones:
            # Vùng mặc định mẫu nếu task mới hoàn toàn
            zones = [{
                'id': uuid.uuid4().hex[:6],
                'name': 'Vùng Kiểm Tra 1',
                'zone_type': 'INSPECTION',
                'rect': [0.1, 0.1, 0.6, 0.6],
                'target_label': 'ALL',
                'min_count': 0,
                'follow_label_enabled': False,
                'anchor_label': self.available_labels[0] if self.available_labels else '',
                'follow_mode': 'CENTER'
            }]
        self.canvas.set_zones(zones)
        self._updating_form = False

        self._refresh_zones_table()
        self._update_zone_detail_fields(self.canvas.selected_idx)

    def _refresh_zones_table(self):
        """Cập nhật lại bảng danh sách các vùng."""
        zones = self.canvas.get_zones()
        self.table_zones.blockSignals(True)
        self.table_zones.setRowCount(len(zones))
        for row, z in enumerate(zones):
            item_name = QtWidgets.QTableWidgetItem(z.get('name', ''))
            item_type = QtWidgets.QTableWidgetItem(z.get('zone_type', 'INSPECTION'))
            item_lbl = QtWidgets.QTableWidgetItem(z.get('target_label', 'ALL'))

            is_follow = bool(z.get('follow_label_enabled', False))
            anchor = str(z.get('anchor_label') or '')
            follow_text = f"🎯 {anchor}" if is_follow and anchor else ("🎯 Có" if is_follow else "— Cố định")
            item_follow = QtWidgets.QTableWidgetItem(follow_text)

            rect = z.get('rect', [0, 0, 1, 1])
            coord_str = f"[{rect[0]:.2f}, {rect[1]:.2f}, {rect[2]:.2f}, {rect[3]:.2f}]"
            item_coord = QtWidgets.QTableWidgetItem(coord_str)

            self.table_zones.setItem(row, 0, item_name)
            self.table_zones.setItem(row, 1, item_type)
            self.table_zones.setItem(row, 2, item_lbl)
            self.table_zones.setItem(row, 3, item_follow)
            self.table_zones.setItem(row, 4, item_coord)

        if 0 <= self.canvas.selected_idx < len(zones):
            self.table_zones.selectRow(self.canvas.selected_idx)
        else:
            self.table_zones.clearSelection()
        self.table_zones.blockSignals(False)

    def _update_zone_detail_fields(self, index: int):
        """Cập nhật dữ liệu vào các control chi tiết của vùng được chọn."""
        zones = self.canvas.get_zones()
        if index < 0 or index >= len(zones):
            # Không chọn vùng nào
            self.txt_zone_name.setEnabled(False)
            self.combo_zone_type.setEnabled(False)
            self.combo_zone_label.setEnabled(False)
            self.spin_min_count.setEnabled(False)
            self.chk_follow_label.setEnabled(False)
            self.combo_anchor_label.setEnabled(False)
            self.combo_follow_mode.setEnabled(False)
            self.txt_zone_name.setText("")
            self.lbl_zone_hint.setText("Chưa chọn vùng ROI nào. Hãy kéo chuột trên canvas để vẽ vùng mới hoặc bấm chọn một vùng.")
            return

        self._updating_form = True
        z = zones[index]
        self.txt_zone_name.setEnabled(True)
        self.combo_zone_type.setEnabled(True)
        self.combo_zone_label.setEnabled(True)
        self.chk_follow_label.setEnabled(True)

        self.txt_zone_name.setText(z.get('name', ''))

        z_type = z.get('zone_type', 'INSPECTION').upper()
        if z_type == 'EXCLUSION':
            self.combo_zone_type.setCurrentIndex(1)
        elif z_type == 'PRESENCE':
            self.combo_zone_type.setCurrentIndex(2)
        else:
            self.combo_zone_type.setCurrentIndex(0)

        # Label
        target_lbl = z.get('target_label', 'ALL')
        idx_lbl = self.combo_zone_label.findText(target_lbl)
        if idx_lbl >= 0:
            self.combo_zone_label.setCurrentIndex(idx_lbl)
        else:
            self.combo_zone_label.setEditText(target_lbl)

        # Min Count
        self.spin_min_count.setValue(int(z.get('min_count', 1)))

        # Follow Label
        is_follow = bool(z.get('follow_label_enabled', False))
        self.chk_follow_label.setChecked(is_follow)
        self.combo_anchor_label.setEnabled(is_follow)
        self.combo_follow_mode.setEnabled(is_follow)

        anchor_lbl = str(z.get('anchor_label') or '')
        if not anchor_lbl and self.available_labels:
            anchor_lbl = self.available_labels[0]
        idx_anchor = self.combo_anchor_label.findText(anchor_lbl)
        if idx_anchor >= 0:
            self.combo_anchor_label.setCurrentIndex(idx_anchor)
        else:
            self.combo_anchor_label.setEditText(anchor_lbl)

        f_mode = str(z.get('follow_mode') or 'CENTER').upper()
        idx_mode = self.combo_follow_mode.findData(f_mode)
        if idx_mode >= 0:
            self.combo_follow_mode.setCurrentIndex(idx_mode)
        else:
            self.combo_follow_mode.setCurrentIndex(0)

        self._on_zone_type_changed(self.combo_zone_type.currentIndex())
        self._updating_form = False

    def _on_follow_label_toggled(self, checked: bool):
        self.combo_anchor_label.setEnabled(checked)
        self.combo_follow_mode.setEnabled(checked)
        if not self._updating_form:
            self._on_zone_field_changed()

    def _on_zone_type_changed(self, idx: int):
        is_follow = self.chk_follow_label.isChecked()
        anchor_text = f" (🎯 Bám nhãn '{self.combo_anchor_label.currentText().strip()}')" if is_follow else ""

        if idx == 0:  # INSPECTION
            self.spin_min_count.setEnabled(False)
            self.lbl_zone_hint.setStyleSheet("background-color: #f8fafc; border-left: 3px solid #10b981; color: #334155; padding: 6px 8px; font-size: 11px;")
            self.lbl_zone_hint.setText(f"👉 <b>🟢 Vùng Kiểm Tra Bắt Lỗi (Inspection){anchor_text}:</b> Vùng này được highlight sáng rõ (ngoài vùng bị làm đen mờ). Bất kỳ phế phẩm nào xuất hiện bên trong sẽ kích hoạt lỗi <b>NG</b>.")
        elif idx == 1:  # EXCLUSION
            self.spin_min_count.setEnabled(False)
            self.lbl_zone_hint.setStyleSheet("background-color: #f8fafc; border-left: 3px solid #ef4444; color: #334155; padding: 6px 8px; font-size: 11px;")
            self.lbl_zone_hint.setText(f"👉 <b>🔴 Vùng Che Bỏ Qua (Mask){anchor_text}:</b> Vùng này bị làm đen mờ (che). Mọi phế phẩm phát hiện bên trong vùng này sẽ bị <b>bỏ qua (Mask)</b> để triệt tiêu bóng lóa hoặc mép khuôn.")
        else:  # PRESENCE
            self.spin_min_count.setEnabled(True)
            self.lbl_zone_hint.setStyleSheet("background-color: #f8fafc; border-left: 3px solid #3b82f6; color: #334155; padding: 6px 8px; font-size: 11px;")
            self.lbl_zone_hint.setText(f"👉 <b>🔵 Vùng Hiện Diện Linh Kiện (Presence){anchor_text}:</b> Vùng này được highlight sáng rõ. Bắt buộc phải có linh kiện xuất hiện bên trong (≥ số lượng tối thiểu), nếu thiếu sẽ phán định <b>NG</b>.")

        if not self._updating_form:
            self._on_zone_field_changed()

    def _on_zone_field_changed(self):
        if self._updating_form:
            return
        idx = self.canvas.selected_idx
        zones = self.canvas.get_zones()
        if 0 <= idx < len(zones):
            z = zones[idx]
            z['name'] = self.txt_zone_name.text().strip() or f"Vùng {idx+1}"

            type_idx = self.combo_zone_type.currentIndex()
            if type_idx == 1:
                z['zone_type'] = 'EXCLUSION'
            elif type_idx == 2:
                z['zone_type'] = 'PRESENCE'
            else:
                z['zone_type'] = 'INSPECTION'

            lbl_txt = self.combo_zone_label.currentText().strip()
            if lbl_txt.startswith("ALL"):
                z['target_label'] = 'ALL'
            else:
                z['target_label'] = lbl_txt

            z['min_count'] = self.spin_min_count.value()

            z['follow_label_enabled'] = self.chk_follow_label.isChecked()
            z['anchor_label'] = self.combo_anchor_label.currentText().strip()
            z['follow_mode'] = self.combo_follow_mode.currentData() or 'CENTER'

            self.canvas.update()
            self._refresh_zones_table()

    def _on_canvas_zone_selected(self, index: int):
        self._refresh_zones_table()
        self._update_zone_detail_fields(index)

    def _on_canvas_zones_changed(self):
        self._refresh_zones_table()
        if 0 <= self.canvas.selected_idx < len(self.canvas.get_zones()):
            z = self.canvas.get_zones()[self.canvas.selected_idx]
            rect = z['rect']
            follow_info = f" | 🎯 Bám nhãn: '{z.get('anchor_label')}'" if z.get('follow_label_enabled') else " | 📌 Tọa độ cố định"
            self.lbl_canvas_status.setText(
                f"🎯 Đang chọn: {z['name']} "
                f"| Tọa độ: X1={rect[0]:.3f}, Y1={rect[1]:.3f}, X2={rect[2]:.3f}, Y2={rect[3]:.3f} "
                f"(Kích thước: {((rect[2]-rect[0])*100):.1f}% x {((rect[3]-rect[1])*100):.1f}%){follow_info}"
            )

    def _on_table_zone_selection_changed(self):
        selected_rows = self.table_zones.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            self.canvas.select_zone(row)

    def _on_load_sample_image(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Chọn Ảnh Mẫu Phôi Sản Phẩm", "",
            "Hình Ảnh (*.png *.jpg *.jpeg *.bmp);;Tất Cả (*.*)"
        )
        if file_path:
            loaded = self.canvas.load_image_from_path(file_path)
            if not loaded:
                QtWidgets.QMessageBox.warning(self, "Lỗi", "Không thể đọc tệp ảnh đã chọn.")

    def _on_delete_selected_zone(self):
        self.canvas.delete_selected_zone()

    def _on_clear_all_zones(self):
        if QtWidgets.QMessageBox.question(
            self, "Xác Nhận", "Bạn có chắc chắn muốn xóa tất cả các vùng ROI hiện tại?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        ) == QtWidgets.QMessageBox.Yes:
            self.canvas.clear_all_zones()

    # ----------------------- LƯU CẤU HÌNH VÀ ĐỒNG BỘ -----------------------
    def _on_save_config(self):
        task_name = self.txt_task_name.text().strip()
        if not task_name:
            QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập Tên Task!")
            self.txt_task_name.setFocus()
            return

        zones = self.canvas.get_zones()
        if not zones:
            QtWidgets.QMessageBox.warning(self, "Chưa có vùng ROI", "Vui lòng vẽ ít nhất một vùng ROI kiểm tra trên khung nhìn!")
            return

        # Prepare Task Data (Đơn Model Scope)
        task_data = {
            'id': self.task_data.get('id'),
            'camera_id': self.camera_id,
            'model_id': self.model_id,
            'task_name': task_name,
            'task_type': 'ROI_ZONE_INSPECTION',
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

        rule_data = {
            'zones': zones,
            'default_target': '',
            'action_mode': 'DEFECT_FILTER',
            'description': self.txt_description.text().strip()
        }

        saved_id = save_roi_task_and_rule(self.cursor, self.connection, task_data, rule_data)
        if not saved_id:
            QtWidgets.QMessageBox.critical(self, "Lỗi Database", "Không thể lưu cấu hình Task ROI vào cơ sở dữ liệu!")
            return

        task_data['id'] = saved_id

        # Đồng bộ trực tiếp vào bộ nhớ RAM Process_Model.dict_active_tasks CHO RIÊNG TAB MODEL NÀY
        try:
            from module_3.handle_option_models import Process_Model
            cam_str = str(self.camera_id).lower().replace("camera-", "").replace("built-in-", "").strip()
            mod_str = str(self.model_id).lower().replace("model-", "").replace("model", "").strip()

            if hasattr(Process_Model, 'dict_active_tasks') and isinstance(Process_Model.dict_active_tasks, dict):
                # Khóa Model dạng ('camera-X', 'model-Y')
                for km, tlist in Process_Model.dict_active_tasks.items():
                    if isinstance(km, (tuple, list)) and len(km) >= 2:
                        c_k = str(km[0]).lower().replace("camera-", "").replace("built-in-", "").strip()
                        m_k = str(km[1]).lower().replace("model-", "").replace("model", "").strip()
                        if c_k == cam_str and m_k == mod_str and isinstance(tlist, list):
                            found = False
                            for mem_task in tlist:
                                if mem_task.get('id') == saved_id:
                                    mem_task.update(task_data)
                                    mem_task['roi_rule'] = rule_data
                                    found = True
                                    break
                            if not found:
                                new_t = dict(task_data)
                                new_t['id'] = saved_id
                                new_t['roi_rule'] = rule_data
                                tlist.append(new_t)
        except Exception as e:
            _log.warning("Lỗi đồng bộ bộ nhớ RAM Process_Model cho Task ROI: %s", e)

        QtWidgets.QMessageBox.information(
            self, "Thành Công",
            f"Đã lưu thành công Task ROI '{task_name}' (ID: {saved_id}) cho Model {self.model_id}!\nCấu hình gồm {len(zones)} vùng đã được kích hoạt tức thì."
        )
        self.accept()

