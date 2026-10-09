import os
import sys

ultralytics_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'ultralytics'))
if ultralytics_path not in sys.path:
    sys.path.insert(0, ultralytics_path)

from ultralytics import YOLO
import numpy as np
import cv2,time

from _source.v5.v5 import v5s, _read_model_config, COLOR_OK, COLOR_NG, draw_detections
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
        list_register = []
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
                list_register.append(cfg['register'])

            if cfg['ng'] and label in valid_names:
                flag = False
                fail_labels.add(f'* {label}')
                list_register.append(cfg['register'])

        # ── Colour failing boxes red ──────────────────────────────────────────
        for d in draw_candidates:
            if d['label'] in fail_labels:
                d['color'] = COLOR_NG

        result_image_rgb = draw_detections(image, draw_candidates, fail_labels)

        return result_image_rgb, flag, list_register,LOGO_WATERMARK
