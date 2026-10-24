"""
Module: task_calculator_engine.py
Mục đích: Engine tính toán và phán định các Task quan hệ tọa độ, kích thước hình học và không gian đa nhãn.
Đặc tính:
1. Thuật toán Safe Evaluator (không dùng eval() nguy hiểm).
2. Xử lý đa chế độ quan hệ đối tượng (Instance Scope):
   - 1 vs 1: So sánh trực tiếp 1 đối tượng A với 1 đối tượng B (hoặc hằng số).
   - N vs 1 (ALL_A_IN_ONE_B): Mọi đối tượng mang nhãn A được kiểm tra với vật thể chứa B (VD: Tập hợp linh kiện trong khay chứa / Vùng giới hạn). Bất kỳ đối tượng A nào vi phạm/vượt ra ngoài biên thì Rule bị NG!
   - 1 vs N (ONE_A_IN_ANY_B): 1 đối tượng A kiểm tra với tập hợp nhiều vùng cấm/giới hạn B (VD: Chi tiết/sản phẩm đi vào bất kỳ vùng cấm nào thì NG).
   - N vs N (ALL_A_VS_ALL_B): Toàn bộ đối tượng A kiểm tra với toàn bộ đối tượng B.
3. Hỗ trợ toán tử không gian mở rộng: INSIDE (nằm trong), OUTSIDE (nằm ngoài), OVERLAP (giao/chạm).
4. Vẽ trực quan đường đo / mũi tên / delta / highlight các box vi phạm đỏ rực lên ảnh (xanh lá = OK, đỏ = NG vi phạm).
5. Xuất danh sách thanh ghi PLC cần kích hoạt khi có Task vi phạm NG.
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
    else:  # Center / FULL_BOX
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
    - Biểu thức tỷ lệ theo box tham chiếu: "Width / 3", "Height * 0.5"
    """
    if not offset_expr or str(offset_expr).strip() == '':
        return 0.0
    expr = str(offset_expr).strip().lower()
    
    try:
        return float(expr)
    except ValueError:
        pass

    if ref_box is not None:
        w = max(0.0, float(ref_box['xmax']) - float(ref_box['xmin']))
        h = max(0.0, float(ref_box['ymax']) - float(ref_box['ymin']))
        cleaned = expr.replace('width', str(w)).replace('height', str(h)).replace('w', str(w)).replace('h', str(h))
        if all(c in '0123456789.+-*/() ' for c in cleaned):
            try:
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
        return abs(lhs - rhs) < 1.0
    elif op == '!=':
        return abs(lhs - rhs) >= 1.0
    elif op.upper() == 'BETWEEN':
        return min_val <= lhs <= max_val
    return False


def is_box_inside(box_a: Dict[str, Any], box_b: Dict[str, Any], margin: float = 0.0) -> bool:
    """
    Kiểm tra Box A có nằm hoàn toàn bên trong Box B hay không (có xét bù trừ margin).
    margin > 0 cho phép A được vượt quá mép B 1 khoảng margin mà vẫn tính là bên trong.
    margin < 0 yêu cầu A phải lùi sâu vào trong B ít nhất |margin| pixel.
    """
    ax1, ay1, ax2, ay2 = float(box_a['xmin']), float(box_a['ymin']), float(box_a['xmax']), float(box_a['ymax'])
    bx1, by1, bx2, by2 = float(box_b['xmin']), float(box_b['ymin']), float(box_b['xmax']), float(box_b['ymax'])
    return (ax1 >= (bx1 - margin) and
            ay1 >= (by1 - margin) and
            ax2 <= (bx2 + margin) and
            ay2 <= (by2 + margin))


def is_box_outside(box_a: Dict[str, Any], box_b: Dict[str, Any], margin: float = 0.0) -> bool:
    """
    Kiểm tra Box A có hoàn toàn nằm ngoài Box B (không chạm/không giao nhau).
    """
    ax1, ay1, ax2, ay2 = float(box_a['xmin']), float(box_a['ymin']), float(box_a['xmax']), float(box_a['ymax'])
    bx1, by1, bx2, by2 = float(box_b['xmin']), float(box_b['ymin']), float(box_b['xmax']), float(box_b['ymax'])
    return (ax2 < (bx1 - margin) or
            ax1 > (bx2 + margin) or
            ay2 < (by1 - margin) or
            ay1 > (by2 + margin))


def is_box_overlapping(box_a: Dict[str, Any], box_b: Dict[str, Any], margin: float = 0.0) -> bool:
    """
    Kiểm tra Box A và Box B có giao nhau (hoặc chạm mép).
    """
    return not is_box_outside(box_a, box_b, margin)


def evaluate_single_pair(
    box_1: Dict[str, Any],
    box_2: Optional[Dict[str, Any]],
    rule: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Đánh giá điều kiện giữa 1 Box A và 1 Box B (hoặc hằng số) theo quy tắc rule.
    Trả về dict chứa:
    - cond_matched: bool (điều kiện so sánh có xảy ra không)
    - pass: bool (kết quả sau khi đối chiếu condition_true_result)
    - lhs_val, rhs_val, delta
    - is_spatial: bool
    """
    param_1 = rule.get('param_1', 'X_MIN')
    operator = (rule.get('operator') or '<').upper().strip()
    target_type = rule.get('target_type', 'LABEL')
    param_2 = rule.get('param_2', 'X_MIN')
    math_op = rule.get('math_op', 'NONE')
    math_operand_val = rule.get('math_operand_val', '0')
    min_val = float(rule.get('min_value', 0.0))
    max_val = float(rule.get('max_value', 0.0))
    condition_true_result = rule.get('condition_true_result', 'NG').upper()

    margin = parse_math_offset(math_operand_val, box_2) if math_op != 'NONE' else 0.0

    # 1. Các toán tử không gian (Spatial Operators)
    if operator in ('INSIDE', 'OUTSIDE', 'OVERLAP'):
        if box_2 is None:
            return {
                'cond_matched': False,
                'pass': False,
                'lhs_val': 0.0,
                'rhs_val': 0.0,
                'delta': 0.0,
                'is_spatial': True,
                'operator': operator,
                'reason': 'Thiếu box mục tiêu để so sánh không gian'
            }

        if operator == 'INSIDE':
            cond_matched = is_box_inside(box_1, box_2, margin)
        elif operator == 'OUTSIDE':
            cond_matched = is_box_outside(box_1, box_2, margin)
        else:  # OVERLAP
            cond_matched = is_box_overlapping(box_1, box_2, margin)

        if condition_true_result == 'NG':
            pair_pass = not cond_matched
        else:
            pair_pass = cond_matched

        return {
            'cond_matched': cond_matched,
            'pass': pair_pass,
            'lhs_val': 1.0 if cond_matched else 0.0,
            'rhs_val': 1.0,
            'delta': 0.0,
            'is_spatial': True,
            'operator': operator
        }

    # 2. Các toán tử số học tọa độ / kích thước (<, <=, >, >=, ==, !=, BETWEEN)
    lhs_val = get_box_param(box_1, param_1)
    if target_type == 'LABEL' and box_2 is not None:
        rhs_base = get_box_param(box_2, param_2)
    else:
        try:
            rhs_base = float(min_val)
        except Exception:
            rhs_base = 0.0

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

    cond_matched = compare_values(lhs_val, operator, rhs_val, min_val, max_val)
    if condition_true_result == 'NG':
        pair_pass = not cond_matched
    else:
        pair_pass = cond_matched

    delta = lhs_val - rhs_val
    return {
        'cond_matched': cond_matched,
        'pass': pair_pass,
        'lhs_val': lhs_val,
        'rhs_val': rhs_val,
        'delta': delta,
        'is_spatial': False,
        'operator': operator
    }


def evaluate_task_calculator(
    image_bgr: Optional[np.ndarray],
    valid_detections: Any,
    tasks_config: List[Dict[str, Any]],
    draw_overlay: bool = True
) -> Tuple[Optional[np.ndarray], bool, List[Dict[str, Any]], List[Tuple[str, int]]]:
    """
    Hàm thực thi chính của Task Calculator Engine.
    Hỗ trợ đầy đủ các Scope: 1_VS_1, ALL_A_IN_ONE_B, ONE_A_IN_ANY_B, ALL_A_VS_ALL_B.
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

    # Gom nhóm boxes theo tên nhãn
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
            inst_scope = (rule.get('instance_scope') or '1_VS_1').upper().strip()
            operator = (rule.get('operator') or '<').upper().strip()
            target_type = rule.get('target_type', 'LABEL')
            lbl_2 = rule.get('label_2', '').strip()
            param_2 = rule.get('param_2', 'X_MIN')
            inst_strat_2 = rule.get('instance_select_2', 'BEST_CONF')

            cand_1 = boxes_by_label.get(lbl_1, [])
            cand_2 = boxes_by_label.get(lbl_2, []) if target_type == 'LABEL' else []

            # ─────────────────────────────────────────────────────────────────
            # TRƯỜNG HỢP 1: N vs 1 (ALL_A_IN_ONE_B - TẬP HỢP ĐỐI TƯỢNG TRONG VÙNG CHỨA)
            # ─────────────────────────────────────────────────────────────────
            if inst_scope == 'ALL_A_IN_ONE_B':
                box_2 = select_best_box(cand_2, inst_strat_2)
                if box_2 is None:
                    evaluated_rules.append({
                        'rule_id': rule.get('id'),
                        'pass': False,
                        'scope': inst_scope,
                        'reason': f"Thiếu nhãn vùng chứa '{lbl_2}'",
                        'lhs_val': None, 'rhs_val': None
                    })
                    continue

                if not cand_1:
                    evaluated_rules.append({
                        'rule_id': rule.get('id'),
                        'pass': False,
                        'scope': inst_scope,
                        'reason': f"Không tìm thấy đối tượng '{lbl_1}' nào",
                        'lhs_val': None, 'rhs_val': None
                    })
                    continue

                violating_boxes = []
                passing_boxes = []
                for b1 in cand_1:
                    res = evaluate_single_pair(b1, box_2, rule)
                    if not res['pass']:
                        violating_boxes.append((b1, res))
                    else:
                        passing_boxes.append((b1, res))

                rule_pass = (len(violating_boxes) == 0)
                evaluated_rules.append({
                    'rule_id': rule.get('id'),
                    'pass': rule_pass,
                    'scope': inst_scope,
                    'total_count': len(cand_1),
                    'violating_count': len(violating_boxes),
                    'violating_boxes': violating_boxes,
                    'container_box': box_2,
                    'label_1': lbl_1,
                    'label_2': lbl_2,
                    'operator': operator
                })

                # Vẽ Overlay N vs 1 lên ảnh
                if result_img is not None and draw_overlay:
                    # 1. Vẽ Container B (Vùng quy chiếu B)
                    bx1, by1, bx2, by2 = int(box_2['xmin']), int(box_2['ymin']), int(box_2['xmax']), int(box_2['ymax'])
                    cv2.rectangle(result_img, (bx1, by1), (bx2, by2), (255, 165, 0), 2, cv2.LINE_AA)
                    cv2.putText(result_img, f"CONTAINER B: {lbl_2}", (bx1 + 4, max(by1 + 18, 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 2, cv2.LINE_AA)

                    # 2. Vẽ các Box A hợp lệ (Xanh lá)
                    for b1, _ in passing_boxes:
                        x1, y1, x2, y2 = int(b1['xmin']), int(b1['ymin']), int(b1['xmax']), int(b1['ymax'])
                        cv2.rectangle(result_img, (x1, y1), (x2, y2), (0, 255, 0), 1, cv2.LINE_AA)
                        cv2.putText(result_img, f"{lbl_1} (OK)", (x1, max(y1 - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1, cv2.LINE_AA)

                    # 3. Vẽ các Box A vi phạm (Đỏ đậm + đường nối cảnh báo)
                    for b1, res in violating_boxes:
                        x1, y1, x2, y2 = int(b1['xmin']), int(b1['ymin']), int(b1['xmax']), int(b1['ymax'])
                        cv2.rectangle(result_img, (x1, y1), (x2, y2), (0, 0, 255), 3, cv2.LINE_AA)
                        cv2.putText(result_img, f"NG: {lbl_1} ({operator})", (x1, max(y1 - 6, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2, cv2.LINE_AA)
                        # Đường gióng cảnh báo về trung tâm container
                        cx_1 = (x1 + x2) // 2
                        cy_1 = (y1 + y2) // 2
                        cx_2 = (bx1 + bx2) // 2
                        cy_2 = (by1 + by2) // 2
                        cv2.line(result_img, (cx_1, cy_1), (cx_2, cy_2), (0, 0, 255), 1, cv2.LINE_AA)

                    # Banner tóm tắt rule
                    summary_text = f"Rule[{rule.get('rule_name') or task_name}]: {len(violating_boxes)}/{len(cand_1)} vi pham ({'OK' if rule_pass else 'NG'})"
                    cv2.putText(result_img, summary_text, (bx1, min(by2 + 20, result_img.shape[0] - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255) if not rule_pass else (0, 255, 0), 2, cv2.LINE_AA)
                continue

            # ─────────────────────────────────────────────────────────────────
            # TRƯỜNG HỢP 2: 1 vs N (ONE_A_IN_ANY_B - ĐỐI TƯỢNG VS CÁC VÙNG GIỚI HẠN)
            # ─────────────────────────────────────────────────────────────────
            elif inst_scope == 'ONE_A_IN_ANY_B':
                box_1 = select_best_box(cand_1, inst_strat_1)
                if box_1 is None:
                    evaluated_rules.append({
                        'rule_id': rule.get('id'),
                        'pass': False,
                        'scope': inst_scope,
                        'reason': f"Thiếu đối tượng '{lbl_1}'",
                        'lhs_val': None, 'rhs_val': None
                    })
                    continue

                if not cand_2:
                    evaluated_rules.append({
                        'rule_id': rule.get('id'),
                        'pass': True,
                        'scope': inst_scope,
                        'reason': f"Không có vùng '{lbl_2}' nào",
                        'lhs_val': None, 'rhs_val': None
                    })
                    continue

                violating_zones = []
                for b2 in cand_2:
                    res = evaluate_single_pair(box_1, b2, rule)
                    if not res['pass']:
                        violating_zones.append((b2, res))

                rule_pass = (len(violating_zones) == 0)
                evaluated_rules.append({
                    'rule_id': rule.get('id'),
                    'pass': rule_pass,
                    'scope': inst_scope,
                    'item_box': box_1,
                    'violating_zones': violating_zones,
                    'total_zones': len(cand_2),
                    'label_1': lbl_1,
                    'label_2': lbl_2,
                    'operator': operator
                })

                if result_img is not None and draw_overlay:
                    x1, y1, x2, y2 = int(box_1['xmin']), int(box_1['ymin']), int(box_1['xmax']), int(box_1['ymax'])
                    color_1 = (0, 0, 255) if not rule_pass else (0, 255, 0)
                    cv2.rectangle(result_img, (x1, y1), (x2, y2), color_1, 2 if rule_pass else 3, cv2.LINE_AA)
                    cv2.putText(result_img, f"{lbl_1} ({'OK' if rule_pass else 'NG'})", (x1, max(y1 - 6, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_1, 2, cv2.LINE_AA)

                    for b2 in cand_2:
                        bx1, by1, bx2, by2 = int(b2['xmin']), int(b2['ymin']), int(b2['xmax']), int(b2['ymax'])
                        is_violating_zone = any(b2 is vz[0] for vz in violating_zones)
                        zone_color = (0, 0, 255) if is_violating_zone else (255, 165, 0)
                        cv2.rectangle(result_img, (bx1, by1), (bx2, by2), zone_color, 2 if is_violating_zone else 1, cv2.LINE_AA)
                        cv2.putText(result_img, f"ZONE: {lbl_2}", (bx1, max(by1 - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, zone_color, 1, cv2.LINE_AA)
                continue

            # ─────────────────────────────────────────────────────────────────
            # TRƯỜNG HỢP 3: N vs N (ALL_A_VS_ALL_B)
            # ─────────────────────────────────────────────────────────────────
            elif inst_scope == 'ALL_A_VS_ALL_B':
                if not cand_1 or not cand_2:
                    evaluated_rules.append({
                        'rule_id': rule.get('id'),
                        'pass': False,
                        'scope': inst_scope,
                        'reason': f"Thiếu nhãn '{lbl_1}' hoặc '{lbl_2}'",
                        'lhs_val': None, 'rhs_val': None
                    })
                    continue

                all_violating = []
                for b1 in cand_1:
                    for b2 in cand_2:
                        res = evaluate_single_pair(b1, b2, rule)
                        if not res['pass']:
                            all_violating.append((b1, b2, res))

                rule_pass = (len(all_violating) == 0)
                evaluated_rules.append({
                    'rule_id': rule.get('id'),
                    'pass': rule_pass,
                    'scope': inst_scope,
                    'all_violating': all_violating,
                    'label_1': lbl_1,
                    'label_2': lbl_2,
                    'operator': operator
                })
                continue

            # ─────────────────────────────────────────────────────────────────
            # TRƯỜNG HỢP 4: 1 vs 1 TIÊU CHUẨN (1_VS_1)
            # ─────────────────────────────────────────────────────────────────
            box_1 = select_best_box(cand_1, inst_strat_1)
            box_2 = select_best_box(cand_2, inst_strat_2) if target_type == 'LABEL' else None

            if box_1 is None or (target_type == 'LABEL' and box_2 is None):
                rule_pass = False
                reason = f"Thiếu nhãn '{lbl_1}' hoặc '{lbl_2}'"
                evaluated_rules.append({
                    'rule_id': rule.get('id'),
                    'pass': rule_pass,
                    'scope': inst_scope,
                    'reason': reason,
                    'lhs_val': None,
                    'rhs_val': None
                })
                continue

            res = evaluate_single_pair(box_1, box_2, rule)
            rule_pass = res['pass']
            delta = res.get('delta', 0.0)

            evaluated_rules.append({
                'rule_id': rule.get('id'),
                'pass': rule_pass,
                'scope': inst_scope,
                'lhs_val': res.get('lhs_val'),
                'rhs_val': res.get('rhs_val'),
                'delta': delta,
                'cond_matched': res.get('cond_matched'),
                'box_1': box_1,
                'box_2': box_2,
                'param_1': param_1,
                'param_2': param_2,
                'label_1': lbl_1,
                'label_2': lbl_2,
                'operator': operator
            })

            # Vẽ Overlay 1 vs 1 Lên Ảnh
            if result_img is not None and draw_overlay and box_1 is not None:
                draw_color = (0, 0, 255) if not rule_pass else (0, 255, 0)
                
                if res.get('is_spatial') and box_2 is not None:
                    # Toán tử không gian INSIDE / OUTSIDE / OVERLAP
                    bx1, by1, bx2, by2 = int(box_1['xmin']), int(box_1['ymin']), int(box_1['xmax']), int(box_1['ymax'])
                    cv2.rectangle(result_img, (bx1, by1), (bx2, by2), draw_color, 2, cv2.LINE_AA)
                    cv2.putText(result_img, f"{lbl_1} ({operator}: {'OK' if rule_pass else 'NG'})", (bx1, max(by1 - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, draw_color, 1, cv2.LINE_AA)

                    rx1, ry1, rx2, ry2 = int(box_2['xmin']), int(box_2['ymin']), int(box_2['xmax']), int(box_2['ymax'])
                    cv2.rectangle(result_img, (rx1, ry1), (rx2, ry2), (255, 165, 0), 1, cv2.LINE_AA)
                    cv2.putText(result_img, f"{lbl_2}", (rx1, max(ry1 - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 165, 0), 1, cv2.LINE_AA)
                elif box_2 is not None:
                    # Đo khoảng cách / tọa độ giữa 2 điểm
                    pt1 = get_param_point(box_1, param_1)
                    pt2 = get_param_point(box_2, param_2)
                    cv2.line(result_img, pt1, pt2, draw_color, 2, cv2.LINE_AA)
                    cv2.circle(result_img, pt1, 5, draw_color, -1, cv2.LINE_AA)
                    cv2.circle(result_img, pt2, 5, draw_color, -1, cv2.LINE_AA)

                    mid_x = (pt1[0] + pt2[0]) // 2
                    mid_y = (pt1[1] + pt2[1]) // 2
                    delta_str = f"Task[{task_name}] {delta:+.1f}px ({'OK' if rule_pass else 'NG'})"
                    (tw, th), _ = cv2.getTextSize(delta_str, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                    cv2.rectangle(result_img, (mid_x - 2, mid_y - th - 4), (mid_x + tw + 2, mid_y + 2), (20, 20, 30), -1)
                    cv2.putText(result_img, delta_str, (mid_x, mid_y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, draw_color, 1, cv2.LINE_AA)

        # Đánh giá tổng kết quả của Task
        if not evaluated_rules:
            task_pass = True
        elif logic_mode == 'ALL_PASS':
            task_pass = all(r['pass'] for r in evaluated_rules)
        else:  # ANY_FAIL
            task_pass = not any(not r['pass'] for r in evaluated_rules)

        if not task_pass:
            all_tasks_pass = False
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
