"""
Module: multishot_aggregation_engine.py
Mục đích: Engine thực thi theo thời gian thực (Real-time Evaluation Engine) cho
bài toán "Cross-Shot Multi-Image Defect Aggregation" (Tổng hợp phế phẩm liên ảnh trong chu kỳ đa shot).

Bao gồm:
- Bộ theo dõi chu kỳ đa luồng an toàn (Thread-safe Cycle Tracker) phân biệt theo (camera, task_id).
- Tự động đồng bộ tiến trình chu kỳ theo counter thực tế (current_count & shot_complete) từ hệ thống main_core.py.
- Lọc tọa độ phế phẩm theo vùng ROI hình chữ nhật (In-Bounds / Out-Bounds).
- Phán định theo 3 chế độ: THRESHOLD_COUNT (ngưỡng số ảnh NG), SPECIFIC_SHOTS (shot chỉ định), CONSECUTIVE (lỗi liên tiếp).
- Trả về cờ all_pass, kết quả phán định, danh sách ghi thanh ghi PLC (assign_register, value_ok/value_ng).
- Vẽ trực quan vùng ROI và trạng thái chu kỳ lên hình ảnh (Overlay).
"""

import json
import time
import threading
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from app_logger.app_logger import get_logger

_log = get_logger('module_3.multishot_aggregation_engine')

_CYCLE_LOCK = threading.RLock()
# Cấu trúc lưu trữ trạng thái chu kỳ: (camera_key, task_id) -> state_dict
_MULTISHOT_CYCLE_STATES: Dict[Tuple[str, int], Dict[str, Any]] = {}
# Quản lý chu kỳ cấp Camera để đồng bộ khóa thanh ghi NG xuyên suốt chu kỳ: camera_key -> {'last_shot': int, 'ng_registers': set()}
_MULTISHOT_CAM_CYCLES: Dict[str, Dict[str, Any]] = {}


def _normalize_cam_key(key_model) -> str:
    """Chuẩn hóa khóa định danh camera từ key_model."""
    if isinstance(key_model, (tuple, list)) and len(key_model) > 0:
        c_str = str(key_model[0] or '').lower().strip()
        c_num = c_str.removeprefix('camera-').removeprefix('built-in-')
        return f"camera-{c_num}"
    if isinstance(key_model, str):
        c_num = key_model.lower().strip().removeprefix('camera-').removeprefix('built-in-')
        return f"camera-{c_num}"
    return "camera-1"


def reset_multishot_cycle(key_model=None, task_id: Optional[int] = None):
    """Reset trạng thái chu kỳ cho 1 task hoặc toàn bộ camera khi cần."""
    with _CYCLE_LOCK:
        if key_model is None and task_id is None:
            _MULTISHOT_CYCLE_STATES.clear()
            _MULTISHOT_CAM_CYCLES.clear()
            _log.info("Reset all multishot cycle states.")
            return

        cam_key = _normalize_cam_key(key_model) if key_model else None
        keys_to_del = []
        for (k_cam, k_tid) in _MULTISHOT_CYCLE_STATES.keys():
            if (cam_key is None or k_cam == cam_key) and (task_id is None or k_tid == task_id):
                keys_to_del.append((k_cam, k_tid))
        for k in keys_to_del:
            _MULTISHOT_CYCLE_STATES.pop(k, None)
        if cam_key and task_id is None:
            _MULTISHOT_CAM_CYCLES.pop(cam_key, None)


def is_label_managed_by_multishot(label: str, multishot_tasks: List[Dict[str, Any]]) -> bool:
    """
    Kiểm tra xem 1 nhãn có đang được quản lý bởi một Task Multi-Shot Aggregation đang bật hay không.
    Nếu có, quy trình kiểm tra nhãn đơn lẻ thông thường sẽ nhường quyền phán định cho Multi-Shot Engine.
    """
    if not label or not multishot_tasks:
        return False
    target = label.strip().lower()
    for t in multishot_tasks:
        if not t.get('enabled', True):
            continue
        rule = t.get('multishot_rule') or {}
        task_lbl = str(rule.get('target_label') or '').strip().lower()
        if task_lbl == target:
            return True
    return False


def _has_consecutive(numbers: List[int], k: int) -> bool:
    """Kiểm tra danh sách số nguyên đã sắp xếp có k phần tử liên tiếp hay không."""
    if len(numbers) < k or k <= 1:
        return len(numbers) >= k
    count = 1
    for i in range(1, len(numbers)):
        if numbers[i] == numbers[i - 1] + 1:
            count += 1
            if count >= k:
                return True
        elif numbers[i] != numbers[i - 1]:
            count = 1
    return count >= k


def evaluate_multishot_tasks(
    image_rgb: np.ndarray,
    valid_detections: List[Dict[str, Any]],
    multishot_tasks: List[Dict[str, Any]],
    key_model: tuple = None,
    current_count: Optional[int] = None,
    shot_complete: Optional[int] = None,
    draw_overlay: bool = True
) -> Tuple[np.ndarray, bool, List[Dict[str, Any]], List[Tuple[str, Any]]]:
    """
    Hàm thực thi kiểm tra toàn bộ các task Multi-Shot Aggregation trong frame ảnh hiện tại.

    Tham số:
    - image_rgb: Ảnh đầu vào dạng numpy array RGB
    - valid_detections: Danh sách các detection hợp lệ [ {xmin, ymin, xmax, ymax, name, confidence}, ... ]
    - multishot_tasks: Danh sách các task loại MULTI_SHOT_AGGREGATION đã được kích hoạt (enabled=True)
    - key_model: Tuple định danh (camera, model), ví dụ ('camera-1', 'model-1')
    - current_count: Số thứ tự shot hiện tại trong chu kỳ được truyền từ main_core.py
    - shot_complete: Tổng số shot cấu hình của chu kỳ được truyền từ main_core.py
    - draw_overlay: Cờ cho phép vẽ ROI và chỉ số chu kỳ lên ảnh

    Trả về:
    - result_image: Ảnh sau khi vẽ overlay
    - all_pass: True nếu tất cả các task đều đạt, False nếu có task bị NG
    - task_results: Danh sách chi tiết kết quả từng task
    - plc_to_send: Danh sách các lệnh ghi PLC [(register, value), ...]
    """
    if not multishot_tasks:
        return image_rgb, True, [], []

    cam_key = _normalize_cam_key(key_model)
    img_h, img_w = image_rgb.shape[:2]

    all_pass = True
    task_results = []
    plc_to_send = []

    # 1. Quản lý chu kỳ cấp Camera để đồng bộ hóa thanh ghi NG xuyên suốt các Shot
    with _CYCLE_LOCK:
        cam_cycle = _MULTISHOT_CAM_CYCLES.setdefault(cam_key, {'last_shot': 0, 'ng_registers': set()})
        if current_count is not None:
            try:
                c_shot_cam = int(current_count)
            except (ValueError, TypeError):
                c_shot_cam = 1
            if (c_shot_cam == 1 and cam_cycle['last_shot'] != 1) or (c_shot_cam < cam_cycle['last_shot']):
                cam_cycle['ng_registers'].clear()
                _log.info("[%s] Bắt đầu chu kỳ đa shot mới theo counter (Shot %d)", cam_key, c_shot_cam)
            cam_cycle['last_shot'] = c_shot_cam

    # Sao chép ảnh để vẽ nếu cần
    annotated_img = image_rgb.copy() if draw_overlay else image_rgb

    for t in multishot_tasks:
        if not t.get('enabled', True):
            continue

        task_id = t.get('id') or 0
        task_name = t.get('task_name') or f"MultiShot-{task_id}"
        rule = t.get('multishot_rule') or {}

        target_label = str(rule.get('target_label') or '').strip()

        # Xác định số shot của chu kỳ: Ưu tiên lấy từ shot_complete (hệ thống/PLC trong main_core)
        cycle_shots = int(shot_complete) if (shot_complete is not None and int(shot_complete) > 0) else int(rule.get('cycle_shots') or 5)

        agg_mode = str(rule.get('aggregation_mode') or 'THRESHOLD_COUNT')
        min_ng_shots = int(rule.get('min_ng_shots') or 2)
        specific_shots_str = str(rule.get('specific_shots') or '')

        # 1. Lọc các box phế phẩm của target_label trong frame này
        matching_boxes = []
        for d in valid_detections:
            d_name = str(d.get('name') or d.get('label') or '').strip().lower()
            if d_name == target_label.lower():
                matching_boxes.append(d)

        shot_has_defect = (len(matching_boxes) > 0)
        shot_defect_count = len(matching_boxes)

        # 3. Cập nhật tiến trình chu kỳ trong Bộ Theo Dõi (Thread-safe) dựa vào current_count từ main_core
        state_key = (cam_key, task_id)
        with _CYCLE_LOCK:
            state = _MULTISHOT_CYCLE_STATES.setdefault(state_key, {
                'last_shot_index': 0,
                'ng_shot_indices': set(),
                'cycle_ng_confirmed': False
            })

            if current_count is not None:
                try:
                    c_shot = int(current_count)
                except (ValueError, TypeError):
                    c_shot = 1

                # Tự động nhận diện chu kỳ mới khi current_count == 1 (từ shot trước > 1) hoặc khi count quay vòng (c_shot < last_shot_index)
                if (c_shot == 1 and state.get('last_shot_index', 0) != 1) or (c_shot < state.get('last_shot_index', 0)):
                    state['ng_shot_indices'].clear()
                    state['cycle_ng_confirmed'] = False
                    _log.info("[%s - %s] Bắt đầu chu kỳ mới theo counter (Shot %d/%d)",
                              cam_key, task_name, c_shot, cycle_shots)

                state['last_shot_index'] = c_shot
                current_shot = c_shot
            else:
                # Fallback khi không truyền current_count (chạy test frame đơn lẻ)
                last = state.get('last_shot_index', 0)
                if last >= cycle_shots or last <= 0:
                    current_shot = 1
                    state['ng_shot_indices'].clear()
                    state['cycle_ng_confirmed'] = False
                    with _CYCLE_LOCK:
                        cam_cycle['ng_registers'].clear()
                else:
                    current_shot = last + 1
                state['last_shot_index'] = current_shot

            # Kiểm tra xem Shot này có nằm trong danh sách các Shot/Model tham gia kiểm tra hay không
            participating_shots_str = str(rule.get('participating_shots') or '').strip()
            if participating_shots_str:
                allowed_shots = {int(s.strip()) for s in participating_shots_str.split(',') if s.strip().isdigit()}
                if allowed_shots and (current_shot not in allowed_shots):
                    # Shot này không thuộc phạm vi kiểm tra của task
                    shot_has_defect = False

            if shot_has_defect:
                state['ng_shot_indices'].add(current_shot)

            total_ng_shots = len(state['ng_shot_indices'])

            # 4. Phán định theo Aggregation Mode
            is_cycle_ng = False

            if state['cycle_ng_confirmed']:
                # Nếu chu kỳ này trước đó đã chốt NG thì tiếp tục giữ NG
                is_cycle_ng = True
            elif agg_mode == 'SPECIFIC_SHOTS':
                # Quy tắc: Chỉ định chính xác các Shot (ví dụ: Shot 1 & Shot 2)
                required_shots = {int(s.strip()) for s in specific_shots_str.split(',') if s.strip().isdigit()}
                if required_shots and required_shots.issubset(state['ng_shot_indices']):
                    is_cycle_ng = True
                    state['cycle_ng_confirmed'] = True
            elif agg_mode == 'CONSECUTIVE':
                # Quy tắc: Bị lỗi liên tiếp >= K shot
                sorted_shots = sorted(state['ng_shot_indices'])
                if _has_consecutive(sorted_shots, min_ng_shots):
                    is_cycle_ng = True
                    state['cycle_ng_confirmed'] = True
            else:
                # Quy tắc mặc định: THRESHOLD_COUNT (Số shot lỗi >= min_ng_shots)
                if total_ng_shots >= min_ng_shots:
                    is_cycle_ng = True
                    state['cycle_ng_confirmed'] = True

            assign_reg = str(t.get('assign_register') or '').strip()
            if is_cycle_ng and assign_reg:
                cam_cycle['ng_registers'].add(assign_reg)

        # Đánh giá kết quả Task
        task_pass = not is_cycle_ng
        if not task_pass:
            all_pass = False

        # Mô tả hiển thị HUD (Hiển thị đầy đủ tiến trình Shot và số lỗi tích lũy trong HUD)
        lbl_info = f": {target_label}" if target_label and target_label.lower() not in task_name.lower() else ""
        title_str = f"[{task_name}{lbl_info}]"

        if is_cycle_ng:
            desc_text = f"{title_str} Shot {current_shot}/{cycle_shots} | Defect: {total_ng_shots} NG (Cycle NG)"
        elif shot_has_defect:
            desc_text = f"{title_str} Shot {current_shot}/{cycle_shots} | Defect: {total_ng_shots} NG (Under Threshold {min_ng_shots})"
        elif total_ng_shots > 0:
            desc_text = f"{title_str} Shot {current_shot}/{cycle_shots} | Defect: {total_ng_shots} NG (Keep OK)"
        else:
            desc_text = f"{title_str} Shot {current_shot}/{cycle_shots} | Defect: 0 NG"

        # 5. Xử lý thanh ghi PLC: BẢO VỆ NG THẮNG OK TUYỆT ĐỐI (ĐỒNG BỘ HOÀN TOÀN)
        val_state = t.get('value_state', 1)
        val_ok = t.get('value_bit_on', t.get('value_ok', 1))
        val_ng = t.get('value_bit_off', t.get('value_ng', 0))

        if assign_reg:
            if is_cycle_ng:
                # Task này NG: gửi Value NG và lập tức xóa bỏ mọi Value OK đã thêm trước đó trong lượt chạy này cho thanh ghi này
                plc_to_send = [(r, v) for r, v in plc_to_send if str(r).strip() != assign_reg]
                plc_to_send.append((assign_reg, val_ng))
            else:
                # Task này OK: TUYỆT ĐỐI CHỈ gửi Value OK nếu thanh ghi này CHƯA TỪNG bị NG trong chu kỳ này!
                with _CYCLE_LOCK:
                    reg_is_ng = (assign_reg in cam_cycle.get('ng_registers', set()))
                if not reg_is_ng:
                    if not any(str(r).strip() == assign_reg for r, _ in plc_to_send):
                        plc_to_send.append((assign_reg, val_ok))
                else:
                    _log.warning(
                        "[%s] BẢO VỆ NG: Task '%s' [OK] nhưng thanh ghi %s đã chốt NG chu kỳ từ task khác -> Tuyệt đối không gửi Value OK!",
                        cam_key, task_name, assign_reg
                    )

        task_results.append({
            'task_id': task_id,
            'task_name': task_name,
            'pass': task_pass,
            'is_ng': is_cycle_ng,
            'status': 'NG' if is_cycle_ng else 'OK',
            'desc': desc_text,
            'text': desc_text,
            'target_label': target_label,
            'current_shot': current_shot,
            'cycle_shots': cycle_shots,
            'total_ng_shots': total_ng_shots,
            'assign_register': assign_reg,
            'value_state': val_state,
            'value_bit_on': val_ok,
            'value_bit_off': val_ng,
            'matching_boxes': matching_boxes
        })

    return annotated_img, all_pass, task_results, plc_to_send

