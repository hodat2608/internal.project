import os
import sys

ultralytics_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'ultralytics'))
if ultralytics_path not in sys.path:
    sys.path.insert(0, ultralytics_path)

from ultralytics import YOLO
import numpy as np
import cv2,time
import threading
from module_3.task_calculator_engine import evaluate_task_calculator as _eval_engine
import torch
from _source.v5.v5 import v5s, _read_model_config, get_model_config, COLOR_OK, COLOR_NG, draw_detections, _normalize_key_model, InspectionItemList
from module_3.handle_option_models import COLUMN_MAPPING
from app_logger.app_logger import get_logger as _get_logger

_log = _get_logger('source.v8')

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# [HARDCORE TẠM THỜI - ĐỐI ỨNG KHẨN CẤP CAMERA 1 - NHÃN 'mh_klk']
# KHỐI 1: ĐỊNH NGHĨA BIẾN VÀ BỘ THEO DÕI CHU KỲ 5 ẢNH (CAMERA 1)
# -------------------------------------------------------------------------------------------
# Ghi chú cho User/Developer: Khi đã đưa cơ chế đa ảnh liên shot lên giao diện UI, hãy XÓA
# toàn bộ KHỐI 1 này và KHỐI 2, KHỐI 3 trong hàm run_model bên dưới.
#
# Yêu cầu nghiệp vụ:
# - Camera 1 chụp chu kỳ 5 ảnh liên tiếp cho 1 sản phẩm.
# - Nếu trong chu kỳ 5 ảnh chỉ có 1 ảnh bị NG nhãn 'mh_klk' -> Coi như VẪN OK.
# - Nếu có từ 2 ảnh trở lên trong 5 ảnh bị NG nhãn 'mh_klk' -> Phán định NG cho chu kỳ.
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
HARDCORE_TARGET_LABEL = 'mh_klk'
HARDCORE_CYCLE_SHOTS = 5
HARDCORE_NG_MIN_SHOTS = 2
HARDCORE_TIMEOUT_RESET_SEC = 2

_mh_klk_lock = threading.Lock()
_MH_KLK_HARDCORE_STATE = {
    'shot_index': 0,            # Số thứ tự shot hiện tại trong chu kỳ (1 -> 5)
    'ng_shot_indices': set(),   # Tập các shot_index bị NG nhãn mh_klk trong chu kỳ hiện tại
    'last_shot_time': 0.0,      # Timestamp lần gọi shot gần nhất
    'cycle_ng_confirmed': False # Đã chốt NG chu kỳ hay chưa (khi đã có >= 2 shot NG)
}

def _is_hardcore_target_camera(camera, key_model) -> bool:
    """Kiểm tra xem thiết bị hiện tại có phải là Camera 1 hay không."""
    cam_str = str(camera or '').strip().lower()
    km_cam = ""
    if isinstance(key_model, (tuple, list)) and len(key_model) > 0:
        km_cam = str(key_model[0] or '').strip().lower()
    return (
        cam_str in ('camera-1', 'camera_1', 'built-in-camera-1', '1') or
        km_cam in ('camera-1', 'camera_1', 'built-in-camera-1', '1') or
        cam_str.endswith('camera-1') or cam_str.endswith('camera_1') or
        km_cam.endswith('camera-1') or km_cam.endswith('camera_1')
    )
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

LOGO_WATERMARK = "Detected by YOLO V8 Architecture"
class v8s(v5s):
    def __init__(self,model_path,device):
        self.model = YOLO(model_path, task='detect').to(device=device.split('-')[0])
        self.keys_mapping = list(COLUMN_MAPPING.keys())
        self.params           = ['xmax', 'xmin', 'ymax', 'ymin']

    def run_model(self, image: np.ndarray, model_loader, pyuic, camera, key_model, *args, **kwargs):
        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        # [HARDCORE TẠM THỜI - ĐỐI ỨNG KHẨN CẤP CAMERA 1 - NHÃN 'mh_klk']
        # KHỐI 2: CẬP NHẬT TIẾN TRÌNH SHOT (1/5 -> 5/5) CỦA CAMERA 1
        # Ghi chú: Xóa khối này khi đưa tính năng lên giao diện UI.
        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        current_cam_1_shot = 0
        if _is_hardcore_target_camera(camera, key_model):
            with _mh_klk_lock:
                now_ts = time.time()
                # Tự động nhận diện chu kỳ mới: nếu cách shot trước > 4.0s HOẶC shot trước đã là shot 5
                if (now_ts - _MH_KLK_HARDCORE_STATE['last_shot_time'] > HARDCORE_TIMEOUT_RESET_SEC) or \
                   (_MH_KLK_HARDCORE_STATE['shot_index'] >= HARDCORE_CYCLE_SHOTS):
                    _MH_KLK_HARDCORE_STATE['shot_index'] = 1
                    _MH_KLK_HARDCORE_STATE['ng_shot_indices'].clear()
                    _MH_KLK_HARDCORE_STATE['cycle_ng_confirmed'] = False
                    _log.info("[HARDCORE mh_klk] Camera 1: Bắt đầu chu kỳ 5 ảnh mới (Shot 1/%d)", HARDCORE_CYCLE_SHOTS)
                else:
                    _MH_KLK_HARDCORE_STATE['shot_index'] += 1

                _MH_KLK_HARDCORE_STATE['last_shot_time'] = now_ts
                current_cam_1_shot = _MH_KLK_HARDCORE_STATE['shot_index']
                _log.debug("[HARDCORE mh_klk] Camera 1 đang xử lý Shot %d/%d (Đã có %d ảnh NG 'mh_klk')",
                           current_cam_1_shot, HARDCORE_CYCLE_SHOTS, len(_MH_KLK_HARDCORE_STATE['ng_shot_indices']))
        # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

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

        from collections import Counter
        name_counts = Counter(valid_names)

        for cfg in cfg_rows:
            if not cfg.get('join'):
                continue
            if 'quantity' not in cfg:
                continue

            label          = str(cfg.get('label') or '').strip()
            detected_count = name_counts.get(label, 0)
            reg            = str(cfg.get('register') or '').strip()

            try:
                target_qty = int(cfg.get('quantity', 0))
            except (ValueError, TypeError):
                target_qty = 0

            is_ok_rule = bool(cfg.get('ok'))
            is_ng_rule = bool(cfg.get('ng'))

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

            # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            # [HARDCORE TẠM THỜI - ĐỐI ỨNG KHẨN CẤP CAMERA 1 - NHÃN 'mh_klk']
            # KHỐI 3: PHÁN ĐỊNH RIÊNG CHO NHÃN 'mh_klk' TRÊN CAMERA 1 (CẦN >= 2 ẢNH MỚI BỊ NG)
            # Ghi chú: Xóa khối này khi đưa tính năng lên giao diện UI.
            # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
            mh_klk_custom_label = None
            if current_cam_1_shot > 0 and label.strip().lower() == HARDCORE_TARGET_LABEL.lower():
                with _mh_klk_lock:
                    single_shot_violation = is_label_ng

                    if single_shot_violation:
                        _MH_KLK_HARDCORE_STATE['ng_shot_indices'].add(current_cam_1_shot)

                    total_ng_shots = len(_MH_KLK_HARDCORE_STATE['ng_shot_indices'])

                    if total_ng_shots >= HARDCORE_NG_MIN_SHOTS or _MH_KLK_HARDCORE_STATE['cycle_ng_confirmed']:
                        # Đã đạt từ 2 ảnh NG trở lên -> CHÍNH THỨC PHÁN ĐỊNH NG CHU KỲ
                        _MH_KLK_HARDCORE_STATE['cycle_ng_confirmed'] = True
                        is_label_ng = True
                        mh_klk_custom_label = f'{label} - sl: {detected_count} ({total_ng_shots}/{HARDCORE_CYCLE_SHOTS} shot NG -> NG Cycle)'
                        _log.warning("[HARDCORE mh_klk] Camera 1 Shot %d/%d: Phát hiện NG 'mh_klk' (Tổng: %d ảnh NG >= %d) -> CHÍNH THỨC PHÁN ĐỊNH NG!",
                                     current_cam_1_shot, HARDCORE_CYCLE_SHOTS, total_ng_shots, HARDCORE_NG_MIN_SHOTS)
                    else:
                        # Chỉ có 1 ảnh bị NG (hoặc 0 ảnh) -> VẪN PHÁN ĐỊNH LÀ OK!
                        is_label_ng = False
                        if single_shot_violation:
                            mh_klk_custom_label = f'{label} (Shot {current_cam_1_shot}/{HARDCORE_CYCLE_SHOTS} - 1 Shot NG still OK) - sl: {detected_count}'
                            _log.info("[HARDCORE mh_klk] Camera 1 Shot %d/%d: Phát hiện NG 'mh_klk' lần 1 (1/%d ảnh) -> TẠM THỜI GIỮ OK (Cần >= 2 ảnh mới NG)",
                                      current_cam_1_shot, HARDCORE_CYCLE_SHOTS, HARDCORE_CYCLE_SHOTS)
            # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

            if is_label_ng:
                flag = False
                desc_text = mh_klk_custom_label or f"{label} - sl: {detected_count}"
                fail_labels.append({
                    'type': 'LABEL',
                    'label': label,
                    'status': 'NG',
                    'is_ng': True,
                    'count': detected_count,
                    'target': target_qty,
                    'text': desc_text
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
                if mh_klk_custom_label or is_ok_rule or is_ng_rule:
                    desc_text = mh_klk_custom_label or f"{label} - sl: {detected_count}"
                    fail_labels.append({
                        'type': 'LABEL',
                        'label': label,
                        'status': 'OK',
                        'is_ng': False,
                        'count': detected_count,
                        'target': target_qty,
                        'text': desc_text
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

        # ── Trích xuất danh sách các nhãn chính xác bị lỗi NG để đổi màu đỏ ──
        exact_ng_labels = {
            item['label'] for item in fail_labels
            if isinstance(item, dict) and item.get('is_ng') and item.get('type') == 'LABEL' and item.get('label')
        }
        # Hỗ trợ fallback nếu có item dạng chuỗi string legacy
        for x in fail_labels:
            if isinstance(x, str) and ('*' in x or x.startswith('NG')):
                s = str(x).strip()
                if s.startswith('* Task:') or s.startswith('Task:'):
                    continue
                s_clean = s.lstrip('*').strip()
                if s_clean.startswith(('NG :', 'NG:')):
                    s_clean = s_clean.split(':', 1)[1].strip()
                lbl_name = s_clean.split(' - sl:')[0].strip()
                if lbl_name:
                    exact_ng_labels.add(lbl_name)

        for d in draw_candidates:
            if d.get('label') in exact_ng_labels:
                d['color'] = COLOR_NG

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

        enabled_tasks = [t for t in tasks_for_model if t.get('enabled', True) and t.get('rules')]
        if enabled_tasks:
            image, flag, list_register = self.evaluate_task_calculator(
                image, draw_candidates, pyuic, flag, list_register,
                tasks_config=enabled_tasks,
                key_model=key_model,
                fail_labels=fail_labels,
                ng_registers=ng_registers
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
                                'text': f"Task: {t_name} (Vi phạm)"
                            })
                    else:
                        fail_labels.append({
                            'type': 'TASK',
                            'label': t_name,
                            'status': 'OK',
                            'is_ng': False,
                            'text': f"Task: {t_name} (OK)"
                        })

        except Exception as e:
            print("Error in evaluate_task_calculator (v8):", e)

        return image_rgb, flag, list_register
