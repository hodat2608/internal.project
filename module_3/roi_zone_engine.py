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

    annotated_img = image_rgb.copy() if draw_overlay else image_rgb

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
        exclusion_zones = [z for z in zones if str(z.get('zone_type', '')).upper() == 'EXCLUSION']
        for ez in exclusion_zones:
            rect = ez.get('rect', [0, 0, 1, 1])
            if len(rect) != 4:
                continue
            ex1, ey1, ex2, ey2 = rect
            target_lbl = str(ez.get('target_label') or 'ALL').strip().lower()

            for dinfo in det_info_list:
                if (ex1 <= dinfo['cx'] <= ex2) and (ey1 <= dinfo['cy'] <= ey2):
                    if target_lbl in ('all', '', 'tất cả') or dinfo['name'].lower() == target_lbl:
                        dinfo['is_excluded'] = True

        # Bước 3: Đánh giá từng vùng ROI (INSPECTION & PRESENCE)
        for z in zones:
            z_id = z.get('id', '')
            z_name = z.get('name') or f"Vùng_{z_id}"
            z_type = str(z.get('zone_type') or 'INSPECTION').upper()
            rect = z.get('rect', [0, 0, 1, 1])
            if len(rect) != 4:
                continue
            x1, y1, x2, y2 = rect
            target_lbl = str(z.get('target_label') or 'ALL').strip().lower()
            min_count = int(z.get('min_count', 1 if z_type == 'PRESENCE' else 0))

            # Tìm các detection nằm trong vùng này mà chưa bị loại bởi EXCLUSION
            inside_dets = []
            for dinfo in det_info_list:
                if dinfo['is_excluded'] and z_type != 'EXCLUSION':
                    continue
                if (x1 <= dinfo['cx'] <= x2) and (y1 <= dinfo['cy'] <= y2):
                    if target_lbl in ('all', '', 'tất cả') or dinfo['name'].lower() == target_lbl:
                        inside_dets.append(dinfo)

            is_zone_violated = False
            violation_msg = ""

            if z_type == 'INSPECTION':
                # Vùng bắt lỗi: Nếu có phế phẩm trong vùng này -> Vi phạm
                if len(inside_dets) > 0:
                    is_zone_violated = True
                    det_names = ", ".join({d['name'] for d in inside_dets})
                    violation_msg = f"{z_name}: Phát hiện {len(inside_dets)} lỗi [{det_names}]"
                    # Đánh dấu vi phạm vào detection gốc
                    for dinfo in inside_dets:
                        dinfo['raw']['is_roi_violation'] = True
            elif z_type == 'PRESENCE':
                # Vùng hiện diện: Bắt buộc phải có linh kiện (>= min_count) -> Nếu thiếu -> Vi phạm
                if len(inside_dets) < min_count:
                    is_zone_violated = True
                    violation_msg = f"{z_name}: Thiếu linh kiện '{target_lbl}' (Có {len(inside_dets)}/{min_count})"
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

            # Bước 4: Vẽ trực quan vùng ROI lên ảnh (Overlay)
            if draw_overlay:
                rx1 = int(x1 * img_w)
                ry1 = int(y1 * img_h)
                rx2 = int(x2 * img_w)
                ry2 = int(y2 * img_h)

                if z_type == 'EXCLUSION':
                    color = (0, 140, 255)  # Cam/Đỏ nhạt (Mask/Bỏ qua)
                    tag_str = f"[MASK] {z_name}"
                elif z_type == 'PRESENCE':
                    color = (255, 120, 0) if not is_zone_violated else (0, 0, 255)  # Xanh dương / Đỏ nếu thiếu
                    tag_str = f"[PRESENCE] {z_name} ({len(inside_dets)}/{min_count})"
                else:
                    color = (0, 0, 255) if is_zone_violated else (0, 200, 0)  # Xanh lá / Đỏ nếu có lỗi
                    tag_str = f"[INSPECT] {z_name} ({len(inside_dets)})"

                cv2.rectangle(annotated_img, (rx1, ry1), (rx2, ry2), color, 2, cv2.LINE_AA)

                # Vẽ nhãn vùng ROI với nền mờ
                (tw, th), _ = cv2.getTextSize(tag_str, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                by1 = max(0, ry1 - th - 6)
                by2 = ry1
                cv2.rectangle(annotated_img, (rx1, by1), (rx1 + tw + 6, by2), color, -1)
                cv2.putText(
                    annotated_img,
                    tag_str,
                    (rx1 + 3, ry1 - 3),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (255, 255, 255),
                    1,
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

        # Xử lý thanh ghi PLC
        assign_reg = str(t.get('assign_register') or '').strip()
        val_state = t.get('value_state', 1)
        val_ok = t.get('value_bit_on', t.get('value_ok', 1))
        val_ng = t.get('value_bit_off', t.get('value_ng', 0))

        if assign_reg:
            val_to_send = val_ok if task_pass else val_ng
            plc_to_send.append((assign_reg, val_to_send))

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

