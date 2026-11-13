import os
import sys

ultralytics_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'ultralytics'))
if ultralytics_path not in sys.path:
    sys.path.insert(0, ultralytics_path)

from ultralytics import YOLO
import numpy as np
import cv2,time
from module_3.task_calculator_engine import evaluate_task_calculator as _eval_engine
import torch
from _source.v5.v5 import v5s, _read_model_config, get_model_config, COLOR_OK, COLOR_NG, draw_detections, _normalize_key_model
from module_3.handle_option_models import COLUMN_MAPPING

LOGO_WATERMARK = "Detected by YOLO V8 Architecture"
class v8s(v5s):
    def __init__(self,model_path,device):
        self.model = YOLO(model_path, task='detect').to(device=device.split('-')[0])
        self.keys_mapping = list(COLUMN_MAPPING.keys())
        self.params           = ['xmax', 'xmin', 'ymax', 'ymin']

    def run_model(self, image: np.ndarray, model_loader, pyuic, camera, key_model, *args, **kwargs):
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

        imgsz = int(pyuic.comboBox_imgsz.currentText())
        conf_thr_global = int(pyuic.spinBox_confidenc_score.value()) / 100

        # Tối ưu: inference_mode không theo dõi gradient, tiết kiệm GPU RAM và tăng tốc độ forward
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
        
        # Tối ưu: Đọc cấu hình từ cache RAM
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
        fail_labels   = set()
        ng_registers  = set()

        # ── Per-label OK / NG quantity check (Tối ưu: Counter O(1) lookup) ────
        from collections import Counter
        name_counts = Counter(valid_names)

        for cfg in cfg_rows:
            if not cfg.get('join'):
                continue
            if 'quantity' not in cfg:
                continue

            label    = cfg.get('label', '')
            ok_count = name_counts.get(label, 0)
            reg      = str(cfg.get('register') or '').strip()

            is_label_ng = False
            if cfg.get('ok') and ok_count != cfg.get('quantity', 0):
                is_label_ng = True

            if cfg.get('ng') and ok_count > 0:
                is_label_ng = True

            if is_label_ng:
                flag = False
                fail_labels.add(f'* {label}')
                if reg and any(c.isdigit() for c in reg):
                    ng_registers.add(reg)
                    list_register[reg] = cfg.get('value_ng', 1)
            else:
                if reg and any(c.isdigit() for c in reg):
                    # BẢO VỆ NG: Nếu thanh ghi này đã từng bị NG bởi nhãn khác trước đó (cùng chung thanh ghi) -> TUYỆT ĐỐI KHÔNG GHI ĐÈ BẰNG VALUE OK!
                    if reg not in ng_registers:
                        list_register[reg] = cfg.get('value_ok', 1)

        # ── Đổi màu đỏ cho các box thuộc nhãn bị NG ──────────────────────────
        for d in draw_candidates:
            if any(d['label'] in x for x in fail_labels if '*' in x):
                d['color'] = COLOR_NG

        # ── Kiểm tra điều kiện Task Calculator đa nhãn theo key_model ─────────
        processor = getattr(pyuic, 'processor', None)
        active_tasks_dict = getattr(processor, 'active_tasks', {}) if processor else {}
        if not isinstance(active_tasks_dict, dict) and hasattr(processor, 'dict_active_tasks'):
            active_tasks_dict = getattr(processor, 'dict_active_tasks', {})

        tasks_for_model = []
        if isinstance(active_tasks_dict, dict):
            # 1. So sánh trực tiếp key_model: ('camera-1', 'model-1')
            if key_model in active_tasks_dict:
                tasks_for_model = active_tasks_dict[key_model]
            else:
                # 2. So sánh chuẩn hoá tuple ('camera-X', 'model-Y')
                target_norm = _normalize_key_model(key_model)
                if target_norm:
                    for k, v in active_tasks_dict.items():
                        if _normalize_key_model(k) == target_norm:
                            tasks_for_model = v
                            break
        elif isinstance(active_tasks_dict, list):
            tasks_for_model = active_tasks_dict

        # QUAN TRỌNG: Thực thi Task Calculator TRƯỚC KHI vẽ HUD và tổng hợp toàn bộ lỗi vào fail_labels
        if tasks_for_model:
            image, flag, list_register = self.evaluate_task_calculator(
                image, draw_candidates, pyuic, flag, list_register,
                tasks_config=tasks_for_model,
                key_model=key_model,
                fail_labels=fail_labels,
                ng_registers=ng_registers
            )

        # ── Chốt toàn bộ kết quả (nhãn + toán tử) rồi mới vẽ Bounding Boxes và HUD ──
        result_image_rgb = draw_detections(image, draw_candidates, fail_labels)

        # Chuẩn bị danh sách cfg_rows độc lập trả về cho main_core (không làm bẩn cache pyuic)
        final_cfg_rows = [dict(c) for c in cfg_rows if 'quantity' in c]
        if tasks_for_model:
            for t in tasks_for_model:
                t_reg = str(t.get('assign_register') or '').strip()
                if t_reg and any(c.isdigit() for c in t_reg):
                    final_cfg_rows.append({
                        'label': f"Task:{t.get('task_name', '')}",
                        'register': t_reg,
                        'value_state': t.get('value_state', t.get('Value_State', 1)),
                        'value_ok': t.get('value_ok', t.get('Value_OK', t.get('value_bit_on', 1))),
                        'value_ng': t.get('value_ng', t.get('Value_NG', t.get('value_bit_off', 0))),
                        'join': True,
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
                    'confidence': d.get('conf', 1.0)
                })

            res_img, task_all_pass, task_results, plc_to_send = _eval_engine(
                image_bgr=image_rgb,
                valid_detections=valid_boxes,
                tasks_config=tasks_config,
                draw_overlay=True
            )

            if res_img is not None:
                image_rgb = res_img

            if not task_all_pass:
                flag = False

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

                if is_task_ng:
                    ng_registers.add(reg_str)
                    list_register[reg_str] = val
                else:
                    # Task OK: chỉ gán giá trị OK nếu thanh ghi này CHƯA TỪNG bị NG bởi bất kỳ label hay task nào!
                    if reg_str not in ng_registers:
                        list_register[reg_str] = val

            # Trích xuất toàn bộ hạng mục Task vi phạm đưa vào fail_labels để hiển thị lên HUD
            if fail_labels is not None and task_results:
                for t in task_results:
                    t_name = t.get('task_name') or f"Task-{t.get('task_id', '')}"
                    if not t.get('pass'):
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
                                    comp_op = op.replace('DIST_', '')
                                    d_val = r.get('lhs_val', 0.0) or 0.0
                                    thresh = r.get('rhs_val', 0.0) or 0.0
                                    desc = f"{lbl1}.{p1}-{lbl2}.{p2}: {d_val:.1f}px {comp_op} {thresh:.1f}px"
                                elif op in ('INSIDE', 'OUTSIDE', 'OVERLAP') or r.get('is_spatial'):
                                    desc = f"{lbl1} {op} {lbl2}"
                                else:
                                    v1 = r.get('lhs_val')
                                    v2 = r.get('rhs_val')
                                    if v1 is not None and v2 is not None:
                                        desc = f"{lbl1}.{p1} {op} {lbl2}.{p2} ({v1:.1f}px vs {v2:.1f}px)"
                                    else:
                                        desc = f"{lbl1}.{p1} {op} {lbl2}.{p2}"

                                fail_labels.add(f"* Task: {t_name} [{desc}]")
                        else:
                            fail_labels.add(f"* Task: {t_name} (Vi phạm)")
                    else:
                        fail_labels.add(f"Task: {t_name} (OK)")

        except Exception as e:
            print("Error in evaluate_task_calculator (v8):", e)

        return image_rgb, flag, list_register
