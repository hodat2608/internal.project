import os
import sys

ultralytics_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'ultralytics'))
if ultralytics_path not in sys.path:
    sys.path.insert(0, ultralytics_path)

from ultralytics import YOLO
import numpy as np
import cv2
from module_3.task_calculator_engine import evaluate_task_calculator as _eval_engine
import torch
from _source.v5.v5 import v5s, get_model_config, COLOR_OK, COLOR_NG, draw_detections, _normalize_key_model, InspectionItemList
from module_3.handle_option_models import COLUMN_MAPPING
from app_logger.app_logger import get_logger as _get_logger
from collections import Counter
from module_3.multishot_aggregation_engine import is_label_managed_by_multishot
from module_3.multishot_aggregation_engine import evaluate_multishot_tasks
from module_3.roi_zone_engine import evaluate_roi_zone_tasks
_log = _get_logger('source.v8')



LOGO_WATERMARK = "Detected by YOLO V8 Architecture"
class v8s(v5s):
    def __init__(self, model_path, device):
        self.model = YOLO(model_path, task='detect').to(device=device.split('-')[0])
        self.keys_mapping = list(COLUMN_MAPPING.keys())

    def run_model(self, image: np.ndarray, model_loader, pyuic, camera, key_model, *args, **kwargs):
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

        imgsz = int(pyuic.comboBox_imgsz.currentText())
        conf_thr_global = int(pyuic.spinBox_confidenc_score.value()) / 100

        with torch.inference_mode():
            results = model_loader(
                image,
                imgsz=imgsz,
                conf=conf_thr_global,
            )
        
        boxes = results[0].boxes
        xyxy_arr = boxes.xyxy.cpu().numpy()
        cls_arr = boxes.cls.cpu().numpy()
        conf_arr = boxes.conf.cpu().numpy()
        names = results[0].names
        
        cfg_rows = get_model_config(pyuic, self.keys_mapping)
 
        label_cfg: dict[str, dict] = {}
        for cfg in cfg_rows:
            lbl = cfg.get('label')
            if lbl and 'quantity' in cfg and lbl not in label_cfg:
                label_cfg[lbl] = cfg
 
        valid_names: list[str] = []
        draw_candidates: list[dict] = []   

        num_dets = len(cls_arr)
        for i in range(num_dets):
            cls_id = int(cls_arr[i])
            label_name = names[cls_id] if isinstance(names, (list, tuple)) and cls_id < len(names) else names.get(cls_id, str(cls_id)) if isinstance(names, dict) else str(cls_id)
            cfg = label_cfg.get(label_name)
 
            if cfg is None or not cfg['join']:
                continue
 
            xmin, ymin, xmax, ymax = xyxy_arr[i]
            width      = xmax - xmin
            height     = ymax - ymin
            confidence = float(conf_arr[i])
 
            if confidence < cfg['conf_thr']:
                continue
            if (width  < cfg['wmin'] or width  > cfg['wmax'] or
                height < cfg['hmin'] or height > cfg['hmax']):
                continue

            valid_names.append(label_name)
            draw_candidates.append({
                'x1'   : int(xmin),
                'y1'   : int(ymin),
                'x2'   : int(xmax),
                'y2'   : int(ymax),
                'label': label_name,
                'conf' : confidence,
                'color': COLOR_OK,
            })

        flag          = True
        list_register = {}
        fail_labels   = InspectionItemList()
        ng_registers  = set()


        name_counts = Counter(valid_names)

        # Lấy danh sách task được cấu hình cho model hiện tại
        processor = getattr(pyuic, 'processor', None)
        active_tasks_dict = getattr(processor, 'active_tasks', {}) if processor else {}
        if not isinstance(active_tasks_dict, dict) and hasattr(processor, 'dict_active_tasks'):
            active_tasks_dict = getattr(processor, 'dict_active_tasks', {})

        tasks_for_model = []
        if isinstance(active_tasks_dict, dict):
            if key_model in active_tasks_dict:
                tasks_for_model = active_tasks_dict[key_model]
            else:
                target_norm = _normalize_key_model(key_model)
                if target_norm:
                    for k, v in active_tasks_dict.items():
                        if _normalize_key_model(k) == target_norm:
                            tasks_for_model = v
                            break
        elif isinstance(active_tasks_dict, list):
            tasks_for_model = active_tasks_dict

        for cfg in cfg_rows:
            if not cfg.get('join'):
                continue
            if 'quantity' not in cfg:
                continue

            label          = str(cfg.get('label') or '').strip()
            is_ok_rule     = bool(cfg.get('ok'))
            is_ng_rule     = bool(cfg.get('ng'))

            if is_label_managed_by_multishot(label, tasks_for_model):
                if not is_ok_rule and not is_ng_rule:
                    continue

            detected_count = name_counts.get(label, 0)
            reg            = str(cfg.get('register') or '').strip()

            try:
                target_qty = int(cfg.get('quantity', 0))
            except (ValueError, TypeError):
                target_qty = 0

            is_label_ng = False

            if is_ok_rule and not is_ng_rule:
                if detected_count != target_qty:
                    is_label_ng = True
            elif is_ng_rule and not is_ok_rule:
                ng_target = target_qty if target_qty > 0 else 1
                if detected_count >= ng_target:
                    is_label_ng = True
            elif is_ok_rule and is_ng_rule:
                is_label_ng = True

            if is_label_ng:
                flag = False
                fail_labels.append({
                    'type': 'LABEL',
                    'label': label,
                    'status': 'NG',
                    'is_ng': True,
                    'count': detected_count,
                    'target': target_qty,
                    'text': f"{label} - sl: {detected_count}"
                })
                if reg and any(c.isdigit() for c in reg):
                    ng_registers.add(reg)
                    v_ng = cfg.get('value_ng')
                    if v_ng is None:
                        v_ng = cfg.get('Value_NG')
                    if v_ng is not None and str(v_ng).strip() != "" and str(v_ng).strip().lower() not in ('none', 'no value', 'null'):
                        try:
                            list_register[reg] = int(v_ng)
                        except (ValueError, TypeError):
                            list_register[reg] = v_ng
                    else:
                        list_register.pop(reg, None)
            else:
                if is_ok_rule or is_ng_rule:
                    fail_labels.append({
                        'type': 'LABEL',
                        'label': label,
                        'status': 'OK',
                        'is_ng': False,
                        'count': detected_count,
                        'target': target_qty,
                        'text': f"{label} - sl: {detected_count}"
                    })

                if reg and any(c.isdigit() for c in reg):
                    # BẢO VỆ NG -> TUYỆT ĐỐI KHÔNG GHI ĐÈ BẰNG VALUE OK!
                    if reg not in ng_registers:
                        v_ok = cfg.get('value_ok')
                        if v_ok is None:
                            v_ok = cfg.get('Value_OK')
                        if v_ok is not None and str(v_ok).strip() != "" and str(v_ok).strip().lower() not in ('none', 'no value', 'null'):
                            try:
                                list_register[reg] = int(v_ok)
                            except (ValueError, TypeError):
                                list_register[reg] = v_ok

        exact_ng_labels = {
            item['label'] for item in fail_labels
            if isinstance(item, dict) and item.get('is_ng') and item.get('type') == 'LABEL' and item.get('label')
        }

        for d in draw_candidates:
            if d.get('label') in exact_ng_labels:
                d['color'] = COLOR_NG

        enabled_tasks = [t for t in tasks_for_model if t.get('enabled', True) and (t.get('rules') or t.get('multishot_rule') or t.get('task_type') == 'MULTI_SHOT_AGGREGATION' or t.get('task_type') == 'ROI_ZONE_INSPECTION' or t.get('roi_rule'))]
        if enabled_tasks:
            image, flag, list_register = self.evaluate_task_calculator(
                image, draw_candidates, pyuic, flag, list_register,
                tasks_config=enabled_tasks,
                key_model=key_model,
                fail_labels=fail_labels,
                ng_registers=ng_registers,
                current_count=kwargs.get('current_count'),
                shot_complete=kwargs.get('shot_complete')
            )

        result_image_rgb = draw_detections(image, draw_candidates, fail_labels)

        final_cfg_rows = [dict(c) for c in cfg_rows if 'quantity' in c]
        if tasks_for_model:
            for t in tasks_for_model:
                t_reg = str(t.get('assign_register') or '').strip()
                if t_reg and any(c.isdigit() for c in t_reg):
                    val_state = t.get('value_state', t.get('Value_State'))
                    final_cfg_rows.append({
                        'label': f"Task:{t.get('task_name', '')}",
                        'register': t_reg,
                        'value_state': val_state,
                        'value_ok': t.get('value_ok', t.get('Value_OK', t.get('value_bit_on'))),
                        'value_ng': t.get('value_ng', t.get('Value_NG', t.get('value_bit_off'))),
                        'value': val_state,
                        'join': bool(t.get('enabled', True)),
                        'enabled': bool(t.get('enabled', True)),
                    })
        return result_image_rgb, flag, list_register, LOGO_WATERMARK, final_cfg_rows

    def evaluate_task_calculator(
        self,
        image_rgb: np.ndarray,
        draw_candidates: list,
        pyuic,
        flag: bool,
        list_register: dict,
        tasks_config: list = None,
        key_model: tuple = None,
        fail_labels: set = None,
        ng_registers: set = None,
        *args,
        **kwargs
    ):
        """
        Hàm riêng biệt thực hiện kiểm tra các Task quan hệ tọa độ & kích thước hình học đa nhãn.
        - draw_candidates: danh sách các box hợp lệ (đã qua lọc conf & size ở Bước 1)
        - pyuic: UI object chứa danh sách active_tasks
        - flag: cờ phán định hiện tại (từ lọc nhãn thông thường)
        - list_register: danh sách thanh ghi PLC cần gửi
        - tasks_config: danh sách task đã được phân định theo đúng key_model
        - key_model: tuple định danh (camera, model), ví dụ ('camera-1', 'model-1')
        """
        if tasks_config is None:
            processor = getattr(pyuic, 'processor', None)
            active_tasks_dict = getattr(processor, 'active_tasks', {}) if processor else {}
            if not isinstance(active_tasks_dict, dict) and hasattr(processor, 'dict_active_tasks'):
                active_tasks_dict = getattr(processor, 'dict_active_tasks', {})

            if isinstance(active_tasks_dict, dict):
                if key_model in active_tasks_dict:
                    tasks_config = active_tasks_dict[key_model]
                elif key_model:
                    target_norm = _normalize_key_model(key_model)
                    if target_norm:
                        for k, v in active_tasks_dict.items():
                            if _normalize_key_model(k) == target_norm:
                                tasks_config = v
                                break
            elif isinstance(active_tasks_dict, list):
                tasks_config = active_tasks_dict

        if not tasks_config:
            return image_rgb, flag, list_register

        if ng_registers is None:
            ng_registers = set()

        try:
            valid_boxes = []
            for d in draw_candidates:
                valid_boxes.append({
                    'xmin': d['x1'],
                    'ymin': d['y1'],
                    'xmax': d['x2'],
                    'ymax': d['y2'],
                    'name': d['label'],
                    'confidence': d.get('conf', 1.0),
                    '_orig_candidate': d
                })

            geo_tasks = [t for t in tasks_config if t.get('task_type') not in ('MULTI_SHOT_AGGREGATION', 'ROI_ZONE_INSPECTION') and t.get('rules')]
            multishot_tasks = [t for t in tasks_config if t.get('task_type') == 'MULTI_SHOT_AGGREGATION']
            roi_tasks = [t for t in tasks_config if t.get('task_type') == 'ROI_ZONE_INSPECTION']

            task_results = []
            plc_to_send = []

            # 1. Đánh giá Task Rule Calculator (Hình học đơn ảnh)
            if geo_tasks:
                res_img, task_all_pass, g_results, g_plc = _eval_engine(
                    image_bgr=image_rgb,
                    valid_detections=valid_boxes,
                    tasks_config=geo_tasks,
                    draw_overlay=True
                )
                if res_img is not None:
                    image_rgb = res_img
                if not task_all_pass:
                    flag = False
                if g_results:
                    task_results.extend(g_results)
                if g_plc:
                    plc_to_send.extend(g_plc)

            # 2. Đánh giá Cross-Shot Multi-Image Defect Aggregation (Chu kỳ đa shot)
            if multishot_tasks:
                res_img_ms, ms_all_pass, ms_results, ms_plc = evaluate_multishot_tasks(
                    image_rgb=image_rgb,
                    valid_detections=valid_boxes,
                    multishot_tasks=multishot_tasks,
                    key_model=key_model,
                    current_count=kwargs.get('current_count'),
                    shot_complete=kwargs.get('shot_complete'),
                    draw_overlay=True
                )
                if res_img_ms is not None:
                    image_rgb = res_img_ms
                if not ms_all_pass:
                    flag = False
                if ms_results:
                    task_results.extend(ms_results)
                if ms_plc:
                    plc_to_send.extend(ms_plc)

            # 3. Đánh giá ROI Zone Inspector (Khoanh vùng ROI & Vùng che đa vùng cho Model)
            if roi_tasks:
                res_img_roi, roi_all_pass, roi_results, roi_plc = evaluate_roi_zone_tasks(
                    image_rgb=image_rgb,
                    valid_detections=valid_boxes,
                    roi_tasks=roi_tasks,
                    key_model=key_model,
                    draw_overlay=True
                )
                if res_img_roi is not None:
                    image_rgb = res_img_roi
                if not roi_all_pass:
                    flag = False
                if roi_results:
                    task_results.extend(roi_results)
                if roi_plc:
                    plc_to_send.extend(roi_plc)

            # Xử lý các thanh ghi trả về từ Task Calculator: BẢO VỆ NG THẮNG OK TUYỆT ĐỐI
            for reg, val in plc_to_send:
                reg_str = str(reg or '').strip()
                if not reg_str:
                    continue

                is_task_ng = False
                if task_results:
                    for t in task_results:
                        if str(t.get('assign_register') or '').strip() == reg_str:
                            if not t.get('pass'):
                                is_task_ng = True
                                break

                val_valid = (val is not None and str(val).strip() != "" and str(val).strip().lower() not in ('none', 'no value', 'null'))

                if is_task_ng:
                    ng_registers.add(reg_str)
                    if val_valid:
                        try:
                            list_register[reg_str] = int(val)
                        except (ValueError, TypeError):
                            list_register[reg_str] = val
                    else:
                        list_register.pop(reg_str, None)
                else:
                    # Task OK: chỉ gán giá trị OK nếu thanh ghi này CHƯA TỪNG bị NG bởi bất kỳ label hay task nào!
                    if reg_str not in ng_registers:
                        if val_valid:
                            try:
                                list_register[reg_str] = int(val)
                            except (ValueError, TypeError):
                                list_register[reg_str] = val

            # Trích xuất toàn bộ hạng mục Task vi phạm đưa vào fail_labels để hiển thị lên HUD
            if fail_labels is not None and task_results:
                for t in task_results:
                    t_name = t.get('task_name') or f"Task-{t.get('task_id', '')}"
                    if not t.get('pass'):
                        if t.get('task_type') == 'MULTI_SHOT_AGGREGATION':
                            tgt = t.get('target_label')
                            if tgt:
                                for d in draw_candidates:
                                    if d.get('label') == tgt:
                                        d['color'] = COLOR_NG
                        elif t.get('task_type') == 'ROI_ZONE_INSPECTION':
                            for vb in valid_boxes:
                                if vb.get('is_roi_violation'):
                                    orig = vb.get('_orig_candidate')
                                    if isinstance(orig, dict):
                                        orig['color'] = COLOR_NG
                        failing_rules = [r for r in t.get('rules', []) if not r.get('pass')]
                        if failing_rules:
                            for r in failing_rules:
                                lbl1 = r.get('label_1', '')
                                lbl2 = r.get('label_2', '')
                                op = r.get('operator', '')
                                p1 = r.get('param_1', '')
                                p2 = r.get('param_2', '')
                                reason = r.get('reason')

                                # Tô màu đỏ cho box tham gia vào rule vi phạm
                                for d in draw_candidates:
                                    if d.get('label') in (lbl1, lbl2):
                                        d['color'] = COLOR_NG

                                if reason:
                                    desc = f"{reason}"
                                elif op.startswith('DIST_') or r.get('is_distance'):
                                    comp_op = op.replace('DIST_X_', '').replace('DIST_Y_', '').replace('DIST_', '')
                                    d_val = r.get('lhs_val', 0.0) or 0.0
                                    thresh = r.get('rhs_val', 0.0) or 0.0
                                    pfx = "DistX" if op.startswith('DIST_X_') else ("DistY" if op.startswith('DIST_Y_') else "Dist")
                                    desc = f"{pfx}[{lbl1}.{p1}-{lbl2}.{p2}]: {d_val:.1f}px {comp_op} {thresh:.1f}px"
                                elif op in ('INSIDE', 'OUTSIDE', 'OVERLAP') or r.get('is_spatial'):
                                    desc = f"{lbl1} {op} {lbl2}"
                                else:
                                    v1 = r.get('lhs_val')
                                    v2 = r.get('rhs_val')
                                    if v1 is not None and v2 is not None:
                                        desc = f"{lbl1}.{p1} {op} {lbl2}.{p2} ({v1:.1f}px vs {v2:.1f}px)"
                                    else:
                                        desc = f"{lbl1}.{p1} {op} {lbl2}.{p2}"

                                fail_labels.append({
                                    'type': 'TASK',
                                    'label': t_name,
                                    'status': 'NG',
                                    'is_ng': True,
                                    'text': f"Task: {t_name} [{desc}]"
                                })
                        else:
                            fail_labels.append({
                                'type': 'TASK',
                                'label': t_name,
                                'status': 'NG',
                                'is_ng': True,
                                'text': t.get('desc') or t.get('text') or f"Task: {t_name} (Vi phạm)"
                            })
                    else:
                        fail_labels.append({
                            'type': 'TASK',
                            'label': t_name,
                            'status': 'OK',
                            'is_ng': False,
                            'text': t.get('desc') or t.get('text') or f"Task: {t_name} (OK)"
                        })

        except Exception as e:
            print("Error in evaluate_task_calculator (v8):", e)

        return image_rgb, flag, list_register
