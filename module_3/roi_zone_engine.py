"""
Module: roi_zone_engine.py
Mục đích: Real-time Evaluation Engine cho tác vụ "ROI Zone Inspector" (Khoanh vùng phát hiện ROI trực quan đa vùng).
Phạm vi: ĐỘC LẬP THEO TỪNG TAB MODEL (Phù hợp với từng góc chụp riêng biệt của mỗi Shot trên dây chuyền).

Tính năng nâng cao:
1. Đa vùng kiểm tra (Multi-Zone ROI) với 3 cơ chế chuyên dụng trong thị giác công nghiệp:
   - INSPECTION (🟢 Vùng kiểm tra lỗi): Bắt lỗi nếu xuất hiện nhãn chỉ định trong vùng.
   - EXCLUSION / MASK (🔴 Vùng che / Bỏ qua nhiễu): Triệt tiêu báo động giả ở các khu vực bóng lóa, phản xạ hoặc logo cố định.
   - PRESENCE (🔵 Vùng kiểm tra hiện diện): Bắt buộc phải có linh kiện/nhãn trong vùng (bắt lỗi thiếu ốc, thiếu linh kiện).
2. Lọc theo nhãn cụ thể hoặc tất cả các nhãn (ALL).
3. Đánh giá thời gian thực (Real-time), hỗ trợ hiển thị HUD và giao tiếp PLC (assign_register, value_ok/value_ng).
"""

import cv2
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from app_logger.app_logger import get_logger

_log = get_logger('module_3.roi_zone_engine')


def resolve_dynamic_zones(
    zones: List[Dict[str, Any]],
    detections: List[Dict[str, Any]],
    img_w: int,
    img_h: int
) -> List[Dict[str, Any]]:
    """
    Phân giải danh sách vùng ROI (Multi-Zone):
    - Với vùng cố định (follow_label_enabled=False): Giữ nguyên tọa độ rect.
    - Với vùng bám nhãn (follow_label_enabled=True):
      Tìm các detection có nhãn khớp với anchor_label.
      Với mỗi detection tìm thấy, tạo một vùng ROI động tương ứng:
      + 'CENTER': Tâm ROI trùng tâm của detection anchor, giữ nguyên chiều rộng/cao đã vẽ.
      + 'BBOX': ROI bao trọn toàn bộ khung Bounding Box của detection anchor.
      Nếu không phát hiện thấy nhãn anchor nào:
      Đánh dấu matched_anchor=False để PRESENCE bắt lỗi thiếu anchor,
      còn INSPECTION/EXCLUSION không tạo vùng ảo gây kích hoạt sai.
    """
    resolved = []
    max_w = max(1.0, float(img_w))
    max_h = max(1.0, float(img_h))

    for z in zones:
        if not z.get('follow_label_enabled'):
            resolved.append(dict(z))
            continue

        anchor_lbl = str(z.get('anchor_label') or '').strip().lower()
        if not anchor_lbl:
            resolved.append(dict(z))
            continue

        follow_mode = str(z.get('follow_mode') or 'CENTER').upper()
        orig_rect = z.get('rect', [0, 0, 1, 1])
        if len(orig_rect) != 4:
            orig_rect = [0, 0, 1, 1]

        matching_anchors = []
        for d in detections:
            x1 = float(d.get('x1', d.get('xmin', 0)))
            y1 = float(d.get('y1', d.get('ymin', 0)))
            x2 = float(d.get('x2', d.get('xmax', 0)))
            y2 = float(d.get('y2', d.get('ymax', 0)))
            name = str(d.get('label') or d.get('name') or '').strip().lower()

            if name == anchor_lbl:
                matching_anchors.append((x1, y1, x2, y2))

        if not matching_anchors:
            unmatched_z = dict(z)
            unmatched_z['is_dynamic'] = True
            unmatched_z['matched_anchor'] = False
            unmatched_z['rect'] = [-1.0, -1.0, -1.0, -1.0]
            resolved.append(unmatched_z)
            continue

        zw = abs(orig_rect[2] - orig_rect[0])
        zh = abs(orig_rect[3] - orig_rect[1])

        for ax1, ay1, ax2, ay2 in matching_anchors:
            if follow_mode == 'BBOX':
                rx1 = min(ax1, ax2) / max_w
                ry1 = min(ay1, ay2) / max_h
                rx2 = max(ax1, ax2) / max_w
                ry2 = max(ay1, ay2) / max_h
            else:  # 'CENTER'
                acx = ((ax1 + ax2) / 2.0) / max_w
                acy = ((ay1 + ay2) / 2.0) / max_h
                rx1 = max(0.0, acx - zw / 2.0)
                ry1 = max(0.0, acy - zh / 2.0)
                rx2 = min(1.0, acx + zw / 2.0)
                ry2 = min(1.0, acy + zh / 2.0)

            dyn_z = dict(z)
            dyn_z['rect'] = [round(rx1, 4), round(ry1, 4), round(rx2, 4), round(ry2, 4)]
            dyn_z['is_dynamic'] = True
            dyn_z['matched_anchor'] = True
            resolved.append(dyn_z)

    return resolved


def apply_roi_spatial_filter(
    draw_candidates: List[Dict[str, Any]],
    tasks_for_model: List[Dict[str, Any]],
    img_w: int,
    img_h: int
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Áp dụng bộ lọc không gian ROI (Spatial ROI Filter) lên toàn bộ các detection trước khi phán định nhãn:
    1. EXCLUSION (Vùng che / Bỏ qua nhiễu):
       - Bất kỳ detection nào rơi vào vùng EXCLUSION (khớp target_label hoặc 'ALL') sẽ bị loại bỏ (is_excluded=True).
       - Không tham gia tính số lượng (name_counts) trong bảng parameters, không kích hoạt lỗi NG.
       - Box hiển thị đổi sang màu Cam (Masked / Bỏ qua nhiễu), không bị tô màu đỏ NG.
    2. INSPECTION (Vùng kiểm tra bắt lỗi):
       - Nếu có vùng INSPECTION nhắm vào nhãn (hoặc 'ALL'), bất kỳ detection nào nằm NGOÀI tất cả các vùng INSPECTION
         sẽ được xem là nằm ngoài khu vực kiểm tra (is_outside_roi=True).
       - Không tham gia tính số lượng lỗi cho bảng parameters.
       - Box hiển thị đổi sang màu Xám (Ngoài vùng kiểm tra), không bị tô màu đỏ NG.
    3. PRESENCE (Vùng hiện diện):
       - Không loại bỏ detection mà để evaluate_roi_zone_tasks đánh giá xem có đủ số lượng tối thiểu trong vùng hay không.

    Hỗ trợ cả ROI cố định lẫn ROI bám theo nhãn định vị (Follow Label).

    Trả về:
    - draw_candidates: Danh sách candidates đã được gắn cờ ('is_excluded', 'is_outside_roi', 'color')
    - effective_names: Danh sách tên nhãn hợp lệ (chưa bị che, nằm trong vùng kiểm tra) dùng cho Counter(effective_names)
    """
    if not draw_candidates:
        return draw_candidates, []

    # Thu thập tất cả các task ROI đang kích hoạt (enabled=True)
    roi_tasks = [
        t for t in (tasks_for_model or [])
        if t.get('enabled', True) and (t.get('task_type') == 'ROI_ZONE_INSPECTION' or t.get('roi_rule'))
    ]

    if not roi_tasks:
        return draw_candidates, [d['label'] for d in draw_candidates]

    all_zones = []
    for t in roi_tasks:
        r_rule = t.get('roi_rule') or {}
        zones = r_rule.get('zones', [])
        all_zones.extend(zones)

    if not all_zones:
        return draw_candidates, [d['label'] for d in draw_candidates]

    # Phân giải các vùng động bám theo nhãn (Follow Label)
    resolved_zones = resolve_dynamic_zones(all_zones, draw_candidates, img_w, img_h)

    exclusion_zones = [
        z for z in resolved_zones
        if str(z.get('zone_type', '')).upper() == 'EXCLUSION' and z.get('matched_anchor', True)
    ]
    inspection_zones = [
        z for z in resolved_zones
        if str(z.get('zone_type', '')).upper() == 'INSPECTION' and z.get('matched_anchor', True)
    ]

    effective_names = []
    max_w = max(1.0, float(img_w))
    max_h = max(1.0, float(img_h))

    for d in draw_candidates:
        x1 = float(d.get('x1', 0))
        y1 = float(d.get('y1', 0))
        x2 = float(d.get('x2', 0))
        y2 = float(d.get('y2', 0))
        label_name = str(d.get('label') or '').strip()
        label_lower = label_name.lower()

        cx = ((x1 + x2) / 2.0) / max_w
        cy = ((y1 + y2) / 2.0) / max_h

        # Bước 1: Kiểm tra xem có rơi vào vùng EXCLUSION (Vùng che / bỏ qua nhiễu) hay không
        is_excluded = False
        for ez in exclusion_zones:
            rect = ez.get('rect', [0, 0, 1, 1])
            if len(rect) == 4:
                rx1, ry1, rx2, ry2 = min(rect[0], rect[2]), min(rect[1], rect[3]), max(rect[0], rect[2]), max(rect[1], rect[3])
                tgt = str(ez.get('target_label') or 'ALL').strip().lower()
                if (rx1 <= cx <= rx2) and (ry1 <= cy <= ry2):
                    if tgt in ('all', '', 'tất cả') or label_lower == tgt:
                        is_excluded = True
                        break

        if is_excluded:
            d['is_excluded'] = True
            d['color'] = (255, 140, 0)  # Màu Cam trong hệ RGB (Masked / Bỏ qua nhiễu)
            continue

        # Bước 2: Kiểm tra xem có bị ràng buộc bởi vùng INSPECTION hay không
        matching_iz = [
            iz for iz in inspection_zones
            if str(iz.get('target_label') or 'ALL').strip().lower() in ('all', '', 'tất cả', label_lower)
        ]

        if matching_iz:
            is_in_inspection = False
            for iz in matching_iz:
                rect = iz.get('rect', [0, 0, 1, 1])
                if len(rect) == 4:
                    rx1, ry1, rx2, ry2 = min(rect[0], rect[2]), min(rect[1], rect[3]), max(rect[0], rect[2]), max(rect[1], rect[3])
                    if (rx1 <= cx <= rx2) and (ry1 <= cy <= ry2):
                        is_in_inspection = True
                        break

            if not is_in_inspection:
                # Nằm ngoài tất cả các vùng INSPECTION dành cho nhãn này -> Bỏ qua, không bắt lỗi
                d['is_outside_roi'] = True
                d['color'] = (140, 140, 140)  # Màu Xám trong hệ RGB (Ngoài vùng kiểm tra)
                continue

        # Detection hợp lệ tham gia đánh giá
        d['is_roi_active'] = True
        effective_names.append(label_name)

    return draw_candidates, effective_names


def _draw_dashed_line(
    img: np.ndarray,
    pt1: Tuple[int, int],
    pt2: Tuple[int, int],
    color: Tuple[int, int, int],
    thickness: int = 2,
    dash_length: int = 12,
    gap_length: int = 7
):
    """Vẽ một đường thẳng nét đứt (dashed line) khử răng cưa trên ảnh OpenCV."""
    x1, y1 = pt1
    x2, y2 = pt2
    dist = float(np.hypot(x2 - x1, y2 - y1))
    if dist <= 0:
        return

    dx = (x2 - x1) / dist
    dy = (y2 - y1) / dist
    period = dash_length + gap_length

    curr_d = 0.0
    while curr_d < dist:
        seg_start = curr_d
        seg_end = min(dist, curr_d + dash_length)
        sx = int(round(x1 + seg_start * dx))
        sy = int(round(y1 + seg_start * dy))
        ex = int(round(x1 + seg_end * dx))
        ey = int(round(y1 + seg_end * dy))
        cv2.line(img, (sx, sy), (ex, ey), color, thickness, cv2.LINE_AA)
        curr_d += period


def draw_dashed_rectangle(
    img: np.ndarray,
    pt1: Tuple[int, int],
    pt2: Tuple[int, int],
    color: Tuple[int, int, int],
    thickness: int = 2,
    dash_length: int = 12,
    gap_length: int = 7
):
    """Vẽ hình chữ nhật viền nét đứt (Dashed Rectangle) với độ dày tùy chỉnh trên ảnh OpenCV."""
    x1, y1 = pt1
    x2, y2 = pt2
    rx1, rx2 = min(x1, x2), max(x1, x2)
    ry1, ry2 = min(y1, y2), max(y1, y2)

    _draw_dashed_line(img, (rx1, ry1), (rx2, ry1), color, thickness, dash_length, gap_length)
    _draw_dashed_line(img, (rx2, ry1), (rx2, ry2), color, thickness, dash_length, gap_length)
    _draw_dashed_line(img, (rx2, ry2), (rx1, ry2), color, thickness, dash_length, gap_length)
    _draw_dashed_line(img, (rx1, ry2), (rx1, ry1), color, thickness, dash_length, gap_length)


def evaluate_roi_zone_tasks(
    image_rgb: np.ndarray,
    valid_detections: List[Dict[str, Any]],
    roi_tasks: List[Dict[str, Any]],
    key_model: tuple = None,
    draw_overlay: bool = True
) -> Tuple[np.ndarray, bool, List[Dict[str, Any]], List[Tuple[str, Any]]]:
    """
    Thực thi kiểm tra toàn bộ các task ROI Zone trong frame ảnh hiện tại của Model này.

    Tham số:
    - image_rgb: Ảnh đầu vào dạng numpy RGB
    - valid_detections: Danh sách các detection hợp lệ [ {xmin, ymin, xmax, ymax, name, confidence}, ... ]
    - roi_tasks: Danh sách các task loại ROI_ZONE_INSPECTION đã kích hoạt (enabled=True)
    - key_model: Tuple định danh (camera, model), ví dụ ('camera-1', 'model-1')
    - draw_overlay: Cờ vẽ các vùng ROI lên ảnh

    Trả về:
    - result_image: Ảnh sau khi vẽ overlay các vùng ROI
    - all_pass: True nếu tất cả các task ROI đều đạt, False nếu có task bị NG
    - task_results: Danh sách kết quả chi tiết từng task
    - plc_to_send: Danh sách các lệnh ghi PLC [(register, value), ...]
    """
    if not roi_tasks:
        return image_rgb, True, [], []

    img_h, img_w = image_rgb.shape[:2]
    all_pass = True
    task_results = []
    plc_to_send = []
    _ng_roi_registers = set()

    annotated_img = image_rgb.copy() if draw_overlay else image_rgb

    # Dynamic visual scale dựa theo kích thước ảnh
    base_dim = max(img_w, img_h)
    scale = max(0.5, min(2.5, base_dim / 1280.0))
    border_thickness = max(2, int(round(scale * 2.2)))
    dash_len = max(8, int(round(12 * scale)))
    gap_len = max(5, int(round(7 * scale)))
    font_scale = max(0.40, min(0.9, 0.45 * scale))
    font_thick = max(1, int(round(scale * 0.9)))

    # =========================================================================
    # HIỆU ỨNG LÀM ĐEN MỜ / HIGHLIGHT VÙNG ROI KHI DETECT HIỂN THỊ LÊN UI
    # =========================================================================
    if draw_overlay:
        all_resolved_for_dim = []
        for t in roi_tasks:
            if not t.get('enabled', True):
                continue
            r_rule = t.get('roi_rule') or {}
            z_list = r_rule.get('zones', [])
            if z_list:
                all_resolved_for_dim.extend(resolve_dynamic_zones(z_list, valid_detections, img_w, img_h))

        if all_resolved_for_dim:
            # a. Thu thập các vùng INSPECTION & PRESENCE (khu vực kiểm tra cần giữ sáng rõ)
            bright_boxes = []
            for z in all_resolved_for_dim:
                z_type = str(z.get('zone_type') or 'INSPECTION').upper()
                if z_type in ('INSPECTION', 'PRESENCE') and z.get('matched_anchor', True):
                    rect = z.get('rect', [0, 0, 1, 1])
                    if len(rect) == 4:
                        bx1 = max(0, min(img_w - 1, int(min(rect[0], rect[2]) * img_w)))
                        by1 = max(0, min(img_h - 1, int(min(rect[1], rect[3]) * img_h)))
                        bx2 = max(0, min(img_w, int(max(rect[0], rect[2]) * img_w)))
                        by2 = max(0, min(img_h, int(max(rect[1], rect[3]) * img_h)))
                        if bx2 > bx1 and by2 > by1:
                            bright_boxes.append((bx1, by1, bx2, by2))

            # Nếu có ít nhất 1 vùng INSPECTION hoặc PRESENCE -> Làm đen mờ toàn bộ bên ngoài (Spotlight Highlight)
            if bright_boxes:
                dimmed_img = cv2.convertScaleAbs(annotated_img, alpha=0.45, beta=0)
                for bx1, by1, bx2, by2 in bright_boxes:
                    dimmed_img[by1:by2, bx1:bx2] = image_rgb[by1:by2, bx1:bx2]
                annotated_img = dimmed_img

            # b. Với các vùng EXCLUSION (Vùng Che / Mask): Làm đen mờ BÊN TRONG vùng này
            for z in all_resolved_for_dim:
                z_type = str(z.get('zone_type') or '').upper()
                if z_type == 'EXCLUSION' and z.get('matched_anchor', True):
                    rect = z.get('rect', [0, 0, 1, 1])
                    if len(rect) == 4:
                        ex1 = max(0, min(img_w - 1, int(min(rect[0], rect[2]) * img_w)))
                        ey1 = max(0, min(img_h - 1, int(min(rect[1], rect[3]) * img_h)))
                        ex2 = max(0, min(img_w, int(max(rect[0], rect[2]) * img_w)))
                        ey2 = max(0, min(img_h, int(max(rect[1], rect[3]) * img_h)))
                        if ex2 > ex1 and ey2 > ey1:
                            annotated_img[ey1:ey2, ex1:ex2] = cv2.convertScaleAbs(
                                annotated_img[ey1:ey2, ex1:ex2], alpha=0.40, beta=0
                            )

    for t in roi_tasks:
        if not t.get('enabled', True):
            continue

        task_id = t.get('id') or 0
        task_name = t.get('task_name') or f"ROI-{task_id}"
        rule_data = t.get('roi_rule') or {}
        zones = rule_data.get('zones', [])

        if not zones:
            continue

        task_violations = []
        zone_statuses = []

        # Phân giải các vùng động bám theo nhãn (Follow Label)
        resolved_zones = resolve_dynamic_zones(zones, valid_detections, img_w, img_h)

        # Bước 1: Tiền xử lý tọa độ tâm của từng detection (chuẩn hóa 0.0 - 1.0)
        det_info_list = []
        for d in valid_detections:
            xmin = float(d.get('xmin', 0))
            ymin = float(d.get('ymin', 0))
            xmax = float(d.get('xmax', 0))
            ymax = float(d.get('ymax', 0))
            name = str(d.get('name') or d.get('label') or '').strip()
            cx = ((xmin + xmax) / 2.0) / max(1.0, img_w)
            cy = ((ymin + ymax) / 2.0) / max(1.0, img_h)
            det_info_list.append({
                'raw': d,
                'name': name,
                'cx': cx,
                'cy': cy,
                'is_excluded': False
            })

        # Bước 2: Áp dụng các vùng EXCLUSION (Vùng che / bỏ qua nhiễu) trước tiên
        exclusion_zones = [
            z for z in resolved_zones
            if str(z.get('zone_type', '')).upper() == 'EXCLUSION' and z.get('matched_anchor', True)
        ]
        for ez in exclusion_zones:
            rect = ez.get('rect', [0, 0, 1, 1])
            if len(rect) != 4:
                continue
            ex1, ey1, ex2, ey2 = rect
            target_lbl = str(ez.get('target_label') or 'ALL').strip().lower()

            rx1, ry1, rx2, ry2 = min(ex1, ex2), min(ey1, ey2), max(ex1, ex2), max(ey1, ey2)
            for dinfo in det_info_list:
                if (rx1 <= dinfo['cx'] <= rx2) and (ry1 <= dinfo['cy'] <= ry2):
                    if target_lbl in ('all', '', 'tất cả') or dinfo['name'].lower() == target_lbl:
                        dinfo['is_excluded'] = True

        # Bước 3: Đánh giá từng vùng ROI (INSPECTION, PRESENCE & EXCLUSION)
        for z in resolved_zones:
            z_id = z.get('id', '')
            z_name = z.get('name') or f"Vùng_{z_id}"
            z_type = str(z.get('zone_type') or 'INSPECTION').upper()
            is_follow = bool(z.get('follow_label_enabled', False))
            anchor_lbl = str(z.get('anchor_label') or '')
            matched_anchor = z.get('matched_anchor', True)

            # Xử lý trường hợp vùng bám nhãn nhưng không phát hiện thấy nhãn định vị anchor
            if is_follow and not matched_anchor:
                if z_type == 'PRESENCE':
                    # Vùng hiện diện bắt buộc phải có anchor: Thiếu anchor -> Báo lỗi NG ngay
                    violation_msg = f"{z_name}: Không tìm thấy nhãn định vị anchor '{anchor_lbl}' để kiểm tra hiện diện"
                    task_violations.append(violation_msg)
                    zone_statuses.append({
                        'zone_name': z_name,
                        'zone_type': z_type,
                        'rect': [0, 0, 0, 0],
                        'target_label': str(z.get('target_label') or 'ALL'),
                        'detected_count': 0,
                        'is_violated': True
                    })
                else:
                    # Với INSPECTION / EXCLUSION: Không có anchor -> Không kích hoạt vùng kiểm tra ảo
                    zone_statuses.append({
                        'zone_name': z_name,
                        'zone_type': z_type,
                        'rect': [0, 0, 0, 0],
                        'target_label': str(z.get('target_label') or 'ALL'),
                        'detected_count': 0,
                        'is_violated': False
                    })
                continue

            rect = z.get('rect', [0, 0, 1, 1])
            if len(rect) != 4:
                continue
            x1, y1, x2, y2 = rect
            target_lbl = str(z.get('target_label') or 'ALL').strip().lower()
            min_count = int(z.get('min_count', 1 if z_type == 'PRESENCE' else 0))

            # Tìm các detection nằm trong vùng này mà chưa bị loại bởi EXCLUSION
            inside_dets = []
            rx1, ry1, rx2, ry2 = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
            for dinfo in det_info_list:
                if dinfo['is_excluded'] and z_type != 'EXCLUSION':
                    continue
                if (rx1 <= dinfo['cx'] <= rx2) and (ry1 <= dinfo['cy'] <= ry2):
                    if target_lbl in ('all', '', 'tất cả') or dinfo['name'].lower() == target_lbl:
                        inside_dets.append(dinfo)

            is_zone_violated = False
            violation_msg = ""
            follow_desc = f" (🎯{anchor_lbl})" if is_follow and anchor_lbl else ""

            if z_type == 'INSPECTION':
                # Vùng bắt lỗi: Nếu có phế phẩm trong vùng này -> Vi phạm
                if len(inside_dets) > 0:
                    is_zone_violated = True
                    det_names = ", ".join({d['name'] for d in inside_dets})
                    violation_msg = f"{z_name}{follow_desc}: Phát hiện {len(inside_dets)} lỗi [{det_names}]"
                    # Đánh dấu vi phạm vào detection gốc
                    for dinfo in inside_dets:
                        dinfo['raw']['is_roi_violation'] = True
            elif z_type == 'PRESENCE':
                # Vùng hiện diện: Bắt buộc phải có linh kiện (>= min_count) -> Nếu thiếu -> Vi phạm
                if len(inside_dets) < min_count:
                    is_zone_violated = True
                    violation_msg = f"{z_name}{follow_desc}: Thiếu linh kiện '{target_lbl}' (Có {len(inside_dets)}/{min_count})"
            elif z_type == 'EXCLUSION':
                # Vùng che: Chỉ thống kê số đối tượng được bỏ qua
                pass

            if is_zone_violated:
                task_violations.append(violation_msg)

            zone_statuses.append({
                'zone_name': z_name,
                'zone_type': z_type,
                'rect': rect,
                'target_label': target_lbl,
                'detected_count': len(inside_dets),
                'is_violated': is_zone_violated
            })

            # Bước 4: Vẽ trực quan vùng ROI lên ảnh với VIỀN NÉT ĐỨT (DASHED BORDER)
            if draw_overlay:
                rx1 = int(min(x1, x2) * img_w)
                ry1 = int(min(y1, y2) * img_h)
                rx2 = int(max(x1, x2) * img_w)
                ry2 = int(max(y1, y2) * img_h)

                follow_tag = f" 🎯{anchor_lbl}" if is_follow and anchor_lbl else ""

                if z_type == 'EXCLUSION':
                    color = (255, 140, 0)  # Cam trong hệ RGB (Mask/Bỏ qua)
                    tag_str = f"[MASK{follow_tag}] {z_name}"
                elif z_type == 'PRESENCE':
                    color = (0, 120, 255) if not is_zone_violated else (255, 0, 0)  # Xanh dương / Đỏ nếu thiếu (RGB)
                    tag_str = f"[PRESENCE{follow_tag}] {z_name} ({len(inside_dets)}/{min_count})"
                else:
                    color = (255, 0, 0) if is_zone_violated else (0, 200, 0)  # Đỏ nếu có lỗi / Xanh lá nếu sạch (RGB)
                    tag_str = f"[INSPECT{follow_tag}] {z_name} ({len(inside_dets)})"

                # 1. Vẽ viền nét đứt (Dashed Rectangle) sắc nét và dày hơn giống trong dialog edit
                draw_dashed_rectangle(
                    annotated_img, (rx1, ry1), (rx2, ry2),
                    color=color, thickness=border_thickness,
                    dash_length=dash_len, gap_length=gap_len
                )

                # 2. Nếu là vùng bám nhãn: Vẽ thêm biểu tượng tâm ngắm (crosshair target) ở tâm ROI
                if is_follow and anchor_lbl:
                    mcx = (rx1 + rx2) // 2
                    mcy = (ry1 + ry2) // 2
                    cross_len = max(8, int(10 * scale))
                    cv2.line(annotated_img, (mcx - cross_len, mcy), (mcx + cross_len, mcy), color, max(1, border_thickness - 1), cv2.LINE_AA)
                    cv2.line(annotated_img, (mcx, mcy - cross_len), (mcx, mcy + cross_len), color, max(1, border_thickness - 1), cv2.LINE_AA)
                    cv2.circle(annotated_img, (mcx, mcy), max(4, int(5 * scale)), color, max(1, border_thickness - 1), cv2.LINE_AA)

                # 3. Vẽ nhãn badge tiêu đề vùng ROI với nền mờ sắc nét
                (tw, th), _ = cv2.getTextSize(tag_str, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thick)
                by1 = max(0, ry1 - th - 8)
                by2 = ry1
                cv2.rectangle(annotated_img, (rx1, by1), (rx1 + tw + 8, by2), color, -1)
                cv2.putText(
                    annotated_img,
                    tag_str,
                    (rx1 + 4, ry1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    font_scale,
                    (255, 255, 255),
                    font_thick,
                    cv2.LINE_AA
                )

        # Đánh giá chung cho Task này
        task_pass = (len(task_violations) == 0)
        if not task_pass:
            all_pass = False

        # Mô tả hiển thị cho bảng HUD
        if not task_pass:
            desc_text = f"[{task_name}] " + "; ".join(task_violations)
        else:
            inspect_count = sum(1 for z in zone_statuses if z['zone_type'] == 'INSPECTION')
            desc_text = f"[{task_name}] ROI Đạt ({inspect_count} vùng kiểm tra an toàn)"

        # Xử lý thanh ghi PLC: BẢO VỆ NG THẮNG OK TUYỆT ĐỐI
        assign_reg = str(t.get('assign_register') or '').strip()
        val_state = t.get('value_state', 1)
        val_ok = t.get('value_bit_on', t.get('value_ok', 1))
        val_ng = t.get('value_bit_off', t.get('value_ng', 0))

        if assign_reg:
            if not task_pass:
                _ng_roi_registers.add(assign_reg)
                # BẢO VỆ NG: Xóa bỏ mọi giá trị OK đã thêm trước đó cho thanh ghi này
                plc_to_send = [(r, v) for r, v in plc_to_send if str(r).strip() != assign_reg]
                plc_to_send.append((assign_reg, val_ng))
            else:
                # BẢO VỆ NG: Chỉ thêm giá trị OK nếu thanh ghi này chưa từng bị NG bởi bất kỳ task nào trước đó
                if assign_reg not in _ng_roi_registers:
                    if not any(str(r).strip() == assign_reg for r, _ in plc_to_send):
                        plc_to_send.append((assign_reg, val_ok))
                else:
                    _log.warning("Task ROI '%s' (ID: %s) [OK] nhưng thanh ghi %s đã ghi nhận NG từ task khác -> Bảo vệ NG!", task_name, task_id, assign_reg)

        task_results.append({
            'task_id': task_id,
            'task_name': task_name,
            'task_type': 'ROI_ZONE_INSPECTION',
            'pass': task_pass,
            'is_ng': not task_pass,
            'status': 'OK' if task_pass else 'NG',
            'desc': desc_text,
            'text': desc_text,
            'violations': task_violations,
            'zone_statuses': zone_statuses,
            'assign_register': assign_reg,
            'value_state': val_state,
            'value_bit_on': val_ok,
            'value_bit_off': val_ng
        })

    return annotated_img, all_pass, task_results, plc_to_send

