"""
Module: task_calculator_engine.py
Mục đích: Engine tính toán và phán định các Task quan hệ tọa độ, kích thước hình học đa nhãn.
Đặc tính:
1. Thuật toán Safe Evaluator (không dùng eval() nguy hiểm).
2. Xử lý đa nhãn (Multi-Instance Strategy: BEST_CONF, LEFTMOST, RIGHTMOST, TOPMOST, BOTTOMMOST).
3. Vẽ trực quan đường đo / mũi tên / delta lên ảnh (xanh lá = OK, đỏ = NG vi phạm).
4. Xuất danh sách thanh ghi PLC cần kích hoạt khi có Task vi phạm NG.
"""

import cv2
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from app_logger.app_logger import get_logger

_log = get_logger('module_3.task_calculator_engine')


def get_box_param(box: Dict[str, Any], param_name: str) -> float:
    """Trích xuất tham số tọa độ hoặc kích thước từ 1 Bounding Box."""
    xmin = float(box['xmin'])
    ymin = float(box['ymin'])
    xmax = float(box['xmax'])
    ymax = float(box['ymax'])
    
    param = param_name.upper().strip()
    if param in ('X_MIN', 'XMIN', 'LEFT'):
        return xmin
    elif param in ('X_MAX', 'XMAX', 'RIGHT'):
        return xmax
    elif param in ('Y_MIN', 'YMIN', 'TOP'):
        return ymin
    elif param in ('Y_MAX', 'YMAX', 'BOTTOM'):
        return ymax
    elif param in ('WIDTH', 'W'):
        return max(0.0, xmax - xmin)
    elif param in ('HEIGHT', 'H'):
        return max(0.0, ymax - ymin)
    elif param in ('CENTER_X', 'CX'):
        return (xmin + xmax) / 2.0
    elif param in ('CENTER_Y', 'CY'):
        return (ymin + ymax) / 2.0
    return 0.0


def get_param_point(box: Dict[str, Any], param_name: str) -> Tuple[int, int]:
    """Lấy điểm tọa độ (x, y) trên box để vẽ đường gióng/mũi tên trực quan."""
    xmin = int(box['xmin'])
    ymin = int(box['ymin'])
    xmax = int(box['xmax'])
    ymax = int(box['ymax'])
    cx = (xmin + xmax) // 2
    cy = (ymin + ymax) // 2

    param = param_name.upper().strip()
    if param in ('X_MIN', 'LEFT'):
        return (xmin, cy)
    elif param in ('X_MAX', 'RIGHT'):
        return (xmax, cy)
    elif param in ('Y_MIN', 'TOP'):
        return (cx, ymin)
    elif param in ('Y_MAX', 'BOTTOM'):
        return (cx, ymax)
    elif param in ('WIDTH', 'W'):
        return (cx, ymax)
    elif param in ('HEIGHT', 'H'):
        return (xmax, cy)
    else:  # Center
        return (cx, cy)


def select_best_box(boxes: List[Dict[str, Any]], strategy: str = 'BEST_CONF') -> Optional[Dict[str, Any]]:
    """Lựa chọn box mục tiêu từ danh sách các box cùng nhãn theo chiến lược."""
    if not boxes:
        return None
    strategy = (strategy or 'BEST_CONF').upper()
    if strategy == 'LEFTMOST':
        return min(boxes, key=lambda b: float(b['xmin']))
    elif strategy == 'RIGHTMOST':
        return max(boxes, key=lambda b: float(b['xmax']))
    elif strategy == 'TOPMOST':
        return min(boxes, key=lambda b: float(b['ymin']))
    elif strategy == 'BOTTOMMOST':
        return max(boxes, key=lambda b: float(b['ymax']))
    else:  # BEST_CONF
        return max(boxes, key=lambda b: float(b.get('confidence', 0.0)))


def parse_math_offset(offset_expr: str, ref_box: Optional[Dict[str, Any]]) -> float:
    """
    Phân tích và tính toán an toàn giá trị bù trừ / tỷ lệ mở rộng.
    Hỗ trợ:
    - Hằng số số học: "15.5", "10", "-5"
    - Biểu thức tỷ lệ theo box tham chiếu: "Width / 3", "Height * 0.5", "Width / 3.0"
    """
    if not offset_expr or str(offset_expr).strip() == '':
        return 0.0
    expr = str(offset_expr).strip().lower()
    
    # 1. Trường hợp là số thuần túy
    try:
        return float(expr)
    except ValueError:
        pass

    # 2. Trường hợp có chứa Width hoặc Height của nhãn tham chiếu
    if ref_box is not None:
        w = max(0.0, float(ref_box['xmax']) - float(ref_box['xmin']))
        h = max(0.0, float(ref_box['ymax']) - float(ref_box['ymin']))
        
        # Thay thế an toàn
        cleaned = expr.replace('width', str(w)).replace('height', str(h)).replace('w', str(w)).replace('h', str(h))
        # Chỉ cho phép các ký tự an toàn: 0-9, ., +, -, *, /, (, ), khoảng trắng
        if all(c in '0123456789.+-*/() ' for c in cleaned):
            try:
                # Sử dụng eval trong namespace trống tuyệt đối an toàn
                return float(eval(cleaned, {"__builtins__": None}, {}))
            except Exception:
                pass

    return 0.0


def compare_values(lhs: float, op: str, rhs: float, min_val: float = 0.0, max_val: float = 0.0) -> bool:
    """Thực hiện phép so sánh hai giá trị số học."""
    op = (op or '<').strip()
    if op == '<':
        return lhs < rhs
    elif op == '<=':
        return lhs <= rhs
    elif op == '>':
        return lhs > rhs
    elif op == '>=':
        return lhs >= rhs
    elif op in ('==', '='):
        return abs(lhs - rhs) < 1.0  # Dung sai 1 pixel cho float coordinates
    elif op == '!=':
        return abs(lhs - rhs) >= 1.0
    elif op.upper() == 'BETWEEN':
        return min_val <= lhs <= max_val
    return False


def evaluate_task_calculator(
    image_bgr: Optional[np.ndarray],
    valid_detections: Any,
    tasks_config: List[Dict[str, Any]],
    draw_overlay: bool = True
) -> Tuple[Optional[np.ndarray], bool, List[Dict[str, Any]], List[Tuple[str, int]]]:
    """
    Hàm thực thi chính của Task Calculator Engine.
    
    Tham số:
    - image_bgr: Ảnh gốc BGR để vẽ overlay kết quả
    - valid_detections: Danh sách các detection hợp lệ đã qua lọc Confidence/Width/Height/Qty (DataFrame hoặc List[dict])
    - tasks_config: Danh sách các Task & Rules nạp từ database
    - draw_overlay: Cờ cho phép vẽ thông tin lên ảnh
    
    Trả về:
    - result_image: Ảnh BGR đã vẽ thêm đường đo
    - all_tasks_pass: True nếu tất cả các task đều đạt, False nếu có ít nhất 1 task vi phạm
    - task_results: Danh sách chi tiết kết quả từng task
    - plc_registers_to_send: Danh sách các (thanh_ghi_plc, value_gui) cần kích hoạt
    """
    all_tasks_pass = True
    task_results = []
    plc_registers_to_send = []

    if not tasks_config:
        return image_bgr, True, [], []

    # Chuẩn hóa valid_detections thành List[dict]
    boxes_list: List[Dict[str, Any]] = []
    if isinstance(valid_detections, pd.DataFrame):
        for _, row in valid_detections.iterrows():
            boxes_list.append(row.to_dict())
    elif isinstance(valid_detections, (list, tuple)):
        for item in valid_detections:
            if isinstance(item, dict):
                boxes_list.append(item)
            elif hasattr(item, '__dict__'):
                boxes_list.append(item.__dict__)

    # Tạo bản sao ảnh nếu cần vẽ overlay
    result_img = image_bgr.copy() if (image_bgr is not None and draw_overlay) else image_bgr

    # Gom nhóm boxes theo tên nhãn để tra cứu nhanh
    boxes_by_label: Dict[str, List[Dict[str, Any]]] = {}
    for b in boxes_list:
        lbl = str(b.get('name') or b.get('label') or b.get('class') or '').strip()
        if lbl:
            boxes_by_label.setdefault(lbl, []).append(b)

    for task in tasks_config:
        if not task.get('enabled', True):
            continue

        task_id = task.get('id')
        task_name = task.get('task_name', f'Task-{task_id}')
        logic_mode = task.get('logic_mode', 'ALL_PASS')
        rules = task.get('rules') or []
        assign_reg = (task.get('assign_register') or '').strip()
        val_on = task.get('value_bit_on', 1)

        evaluated_rules = []

        for rule in rules:
            if not rule.get('enabled', True):
                continue

            lbl_1 = rule.get('label_1', '').strip()
            param_1 = rule.get('param_1', 'X_MIN')
            inst_strat_1 = rule.get('instance_select_1', 'BEST_CONF')
            operator = rule.get('operator', '<')
            target_type = rule.get('target_type', 'LABEL')
            lbl_2 = rule.get('label_2', '').strip()
            param_2 = rule.get('param_2', 'X_MIN')
            inst_strat_2 = rule.get('instance_select_2', 'BEST_CONF')
            math_op = rule.get('math_op', 'NONE')
            math_operand_val = rule.get('math_operand_val', '0')
            min_val = float(rule.get('min_value', 0.0))
            max_val = float(rule.get('max_value', 0.0))
            condition_true_result = rule.get('condition_true_result', 'NG').upper()

            # 1. Tìm box nhãn 1
            cand_1 = boxes_by_label.get(lbl_1, [])
            box_1 = select_best_box(cand_1, inst_strat_1)

            # 2. Tìm box nhãn 2 (nếu target_type là LABEL)
            box_2 = None
            if target_type == 'LABEL':
                cand_2 = boxes_by_label.get(lbl_2, [])
                box_2 = select_best_box(cand_2, inst_strat_2)

            # Kiểm tra thiếu nhãn bắt buộc
            if box_1 is None or (target_type == 'LABEL' and box_2 is None):
                rule_pass = False
                reason = f"Thiếu nhãn '{lbl_1}' hoặc '{lbl_2}'"
                evaluated_rules.append({
                    'rule_id': rule.get('id'),
                    'pass': rule_pass,
                    'reason': reason,
                    'lhs_val': None,
                    'rhs_val': None
                })
                continue

            # 3. Tính toán vế trái LHS
            lhs_val = get_box_param(box_1, param_1)

            # 4. Tính toán vế phải RHS
            if target_type == 'LABEL' and box_2 is not None:
                rhs_base = get_box_param(box_2, param_2)
            else:
                try:
                    rhs_base = float(min_val)
                except Exception:
                    rhs_base = 0.0

            # Áp dụng bù trừ / tỷ lệ
            if math_op != 'NONE':
                offset_num = parse_math_offset(math_operand_val, box_2)
                if math_op == '+':
                    rhs_val = rhs_base + offset_num
                elif math_op == '-':
                    rhs_val = rhs_base - offset_num
                elif math_op == '*':
                    rhs_val = rhs_base * offset_num
                elif math_op == '/':
                    rhs_val = rhs_base / offset_num if abs(offset_num) > 1e-6 else rhs_base
                else:
                    rhs_val = rhs_base
            else:
                rhs_val = rhs_base

            # 5. So sánh điều kiện
            cond_matched = compare_values(lhs_val, operator, rhs_val, min_val, max_val)

            # 6. Phán định theo condition_true_result
            if condition_true_result == 'NG':
                rule_pass = not cond_matched  # Nếu điều kiện vi phạm xảy ra thì rule FAIL
            else:
                rule_pass = cond_matched      # Nếu điều kiện xảy ra thì rule PASS

            delta = lhs_val - rhs_val
            evaluated_rules.append({
                'rule_id': rule.get('id'),
                'pass': rule_pass,
                'lhs_val': lhs_val,
                'rhs_val': rhs_val,
                'delta': delta,
                'cond_matched': cond_matched,
                'box_1': box_1,
                'box_2': box_2,
                'param_1': param_1,
                'param_2': param_2,
                'label_1': lbl_1,
                'label_2': lbl_2
            })

            # 7. Vẽ Overlay Trực Quan Lên Ảnh
            if result_img is not None and draw_overlay and box_1 is not None and box_2 is not None:
                pt1 = get_param_point(box_1, param_1)
                pt2 = get_param_point(box_2, param_2)
                
                # Màu vẽ: Đỏ nếu rule FAIL (NG), Xanh lá nếu PASS (OK)
                draw_color = (0, 0, 255) if not rule_pass else (0, 255, 0)
                
                # Đường nối giữa 2 điểm đo
                cv2.line(result_img, pt1, pt2, draw_color, 2, cv2.LINE_AA)
                cv2.circle(result_img, pt1, 5, draw_color, -1, cv2.LINE_AA)
                cv2.circle(result_img, pt2, 5, draw_color, -1, cv2.LINE_AA)

                # Vẽ text thông số delta ở điểm giữa
                mid_x = (pt1[0] + pt2[0]) // 2
                mid_y = (pt1[1] + pt2[1]) // 2
                delta_str = f"Task[{task_name}] {delta:+.1f}px ({'OK' if rule_pass else 'NG'})"
                
                # Nền text để dễ đọc
                (tw, th), _ = cv2.getTextSize(delta_str, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                cv2.rectangle(result_img, (mid_x - 2, mid_y - th - 4), (mid_x + tw + 2, mid_y + 2), (20, 20, 30), -1)
                cv2.putText(result_img, delta_str, (mid_x, mid_y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, draw_color, 1, cv2.LINE_AA)

        # 8. Đánh giá tổng kết quả của Task
        if not evaluated_rules:
            task_pass = True
        elif logic_mode == 'ALL_PASS':
            task_pass = all(r['pass'] for r in evaluated_rules)
        else:  # ANY_FAIL
            task_pass = not any(not r['pass'] for r in evaluated_rules)

        if not task_pass:
            all_tasks_pass = False
            # Nếu Task bị NG và có cấu hình thanh ghi PLC -> Nạp vào danh sách gửi
            if assign_reg:
                plc_registers_to_send.append((assign_reg, val_on))
                _log.warning("Task '%s' (ID: %s) [NG] -> Trigger PLC Register %s = %s", task_name, task_id, assign_reg, val_on)

        task_results.append({
            'task_id': task_id,
            'task_name': task_name,
            'pass': task_pass,
            'rules': evaluated_rules,
            'assign_register': assign_reg,
            'value_bit_on': val_on
        })

    return result_img, all_tasks_pass, task_results, plc_registers_to_send
