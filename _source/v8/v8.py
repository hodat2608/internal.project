import os
import sys

ultralytics_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'ultralytics'))
if ultralytics_path not in sys.path:
    sys.path.insert(0, ultralytics_path)

from ultralytics import YOLO
import numpy as np
import cv2,time

from _source.v5.v5 import v5s, _read_model_config, COLOR_OK, COLOR_NG, draw_detections, _normalize_key_model
from module_3.handle_option_models import COLUMN_MAPPING

LOGO_WATERMARK = "Detected by YOLO V8 Architecture"
class v8s(v5s):
    def __init__(self,model_path,device):
        self.model = YOLO(model_path, task='detect').to(device=device.split('-')[0])
        self.keys_mapping = list(COLUMN_MAPPING.keys())
        self.params           = ['xmax', 'xmin', 'ymax', 'ymin']

    def run_model(self, image: np.ndarray, model_loader, pyuic,camera,key_model,current_count,mode_load_jumper=False):
        if camera:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) 
        
        results = model_loader(
            image,
            imgsz=int(pyuic.comboBox_imgsz.currentText()),
            conf=int(pyuic.spinBox_confidenc_score.value()) / 100,
        )
        
        boxes_dict = results[0].boxes.cpu().numpy()
        # YOLOv8 provides xyxy format directly: [xmin, ymin, xmax, ymax]
        xyxy_list = boxes_dict.xyxy.tolist()
        cls_list = boxes_dict.cls.tolist()
        conf_list = boxes_dict.conf.tolist()
        names = results[0].names
        
        cfg_rows = _read_model_config(pyuic.model, pyuic.model_column, self.keys_mapping)
 
        label_cfg: dict[str, dict] = {}
        for cfg in cfg_rows:
            if cfg['label'] and cfg['label'] not in label_cfg:
                label_cfg[cfg['label']] = cfg
 
        valid_names: list[str] = []
        draw_candidates: list[dict] = []   

        for xyxy, cls, conf in zip(xyxy_list, cls_list, conf_list):
            label_name = names[int(cls)]
            cfg = label_cfg.get(label_name)
 
            if cfg is None or not cfg['join']:
                continue
 
            xmin, ymin, xmax, ymax = xyxy
            width      = xmax - xmin
            height     = ymax - ymin
            confidence = conf
 
            out_of_conf = confidence < cfg['conf_thr']
            out_of_size = (width  < cfg['wmin'] or width  > cfg['wmax'] or
                           height < cfg['hmin'] or height > cfg['hmax'])

            if out_of_conf or out_of_size:
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

        # ── Per-label OK / NG quantity check (from UI config table) ──────────
        for cfg in cfg_rows:
            if not cfg['join']:
                continue

            label    = cfg['label']
            ok_count = valid_names.count(label)

            if cfg['ok'] and ok_count != cfg['quantity']:
                flag = False
                fail_labels.add(f'* {label}')
                reg = str(cfg.get('register') or '').strip()
                if reg:
                    list_register[reg] = cfg.get('value', 1)

            if cfg['ng'] and label in valid_names:
                flag = False
                fail_labels.add(f'* {label}')
                reg = str(cfg.get('register') or '').strip()
                if reg:
                    list_register[reg] = cfg.get('value', 1)

        # ── Colour failing boxes red ──────────────────────────────────────────
        for d in draw_candidates:
            if d['label'] in fail_labels:
                d['color'] = COLOR_NG

        result_image_rgb = draw_detections(image, draw_candidates, fail_labels)

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

        # Chỉ khi trùng key_model và có task cấu hình thì mới thực thi evaluate_task_calculator
        if tasks_for_model:
            result_image_rgb, flag, list_register = self.evaluate_task_calculator(
                result_image_rgb, draw_candidates, pyuic, flag, list_register,
                tasks_config=tasks_for_model,
                key_model=key_model
            )

        return result_image_rgb, flag, list_register,LOGO_WATERMARK

    def evaluate_task_calculator(
        self,
        image_rgb: np.ndarray,
        draw_candidates: list,
        pyuic,
        flag: bool,
        list_register: list,
        tasks_config: list = None,
        key_model: tuple = None,
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

        try:
            from module_3.task_calculator_engine import evaluate_task_calculator as _eval_engine
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
                for reg, val in plc_to_send:
                    reg_str = str(reg or '').strip()
                    if reg_str and reg_str not in list_register:
                        list_register[reg_str] = val
        except Exception as e:
            print("Error in evaluate_task_calculator (v8):", e)

        return image_rgb, flag, list_register
