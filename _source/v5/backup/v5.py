
import torch
import cv2
import numpy as np
from PyQt5.QtCore import Qt
from module_3.layout_option_model import COLUMN_MAPPING

import cv2
import numpy as np
import torch
from PyQt5.QtCore import Qt

COLOR_OK = (0, 255, 0)   
COLOR_NG = (255, 0, 0)   
 
def draw_detections(image_rgb: np.ndarray, draw_list: list, fail_labels) -> np.ndarray:
    out = image_rgb.copy()

    # ── Bounding boxes ───────────────────────────────────────────────────
    for d in draw_list:
        x1, y1, x2, y2, color = d['x1'], d['y1'], d['x2'], d['y2'], d['color']
        text = f"{d['label']} {d['conf']:.2f} {x2-x1} {y2-y1}"

        cv2.rectangle(out, (x1, y1), (x2, y2), color, 5)

        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 2, 5)
        ty = max(y1 - 5, th + 2)
        cv2.rectangle(out, (x1, ty - th - 2), (x1 + tw + 2, ty + 2), color, -1)
        cv2.putText(out, text, (x1 + 1, ty), cv2.FONT_HERSHEY_SIMPLEX, 2, (0,0,0), 5, cv2.LINE_AA)

    # ── Fail labels (bottom-left, stacked upward) ────────────────────────
    if not fail_labels:
        return out

    img_h, img_w = out.shape[:2]
    font       = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(1.0, img_w / 1000)
    thickness  = max(2, int(font_scale * 2))
    pad        = int(img_w * 0.015)
    (_, lh), bl = cv2.getTextSize("A", font, font_scale, thickness)
    step       = lh + bl + pad

    for i, label in enumerate(sorted(fail_labels)):
        color = COLOR_OK if 'OK' in label else COLOR_NG
        (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)
        y = img_h - pad - i * step
        cv2.rectangle(out, (pad - 4, y - th - 4), (pad + tw + 4, y + bl + 2), color, -1)
        cv2.putText(out, label, (pad, y), font, font_scale, (0,0,0), thickness, cv2.LINE_AA)

    return out

def _read_model_config(model, model_column: list, keys_mapping: list) -> list:

    def text(row, key):
        item = model.item(row, model_column.index(key))
        return item.text().strip() if item else ""
 
    def checked(row, key):
        item = model.item(row, model_column.index(key))
        return item.checkState() == Qt.Checked if item else False
 
    def to_int(row, key, default=0):
        try:
            return int(text(row, key))
        except ValueError:
            return default
 
    rows = []
    for i in range(model.rowCount()):
        rows.append({
            'label'    : text(i,    keys_mapping[0]),
            'join'     : checked(i, keys_mapping[1]),
            'ok'       : checked(i, keys_mapping[2]),
            'ng'       : checked(i, keys_mapping[3]),
            'quantity' : to_int(i,  keys_mapping[4]),
            'wmin'     : to_int(i,  keys_mapping[5]),
            'wmax'     : to_int(i,  keys_mapping[6]),
            'hmin'     : to_int(i,  keys_mapping[7]),
            'hmax'     : to_int(i,  keys_mapping[8]),
            'conf_thr' : to_int(i,  keys_mapping[-1]) / 100,
            'register' : text(i,    keys_mapping[9]),
        })
    return rows
 

class v5s:
 
    def __init__(self, path_pt: str, device: str = 'cpu'):
        self.keys_mapping = list(COLUMN_MAPPING.keys())
        self.source_model = (
            torch.hub.load(
                './_source/v5', 'custom',
                path=path_pt, source='local', force_reload=True
            ).to(device=torch.device(device.split('-')[0]))
        )

        self.list_jumper = [] 
        self.list_can_dien_cuc = []
        self.positive_jumper = {}
        self.params = ['xmax','xmin','ymax','ymin']

    def run_model(self, image: np.ndarray, model_loader, pyuic,camera,key_model,current_count,mode_load_jumper=False):
        """
        Chạy inference, lọc detection, vẽ kết quả và đánh giá pass/fail.
 
        Logic vẽ box:
          - join = False              → KHÔNG vẽ
          - join = True, không thỏa mãn width/height/conf → KHÔNG vẽ
          - join = True, thỏa mãn    → vẽ xanh (OK) hoặc đỏ (NG/fail)
 
        Trả về:
            result_image_bgr : np.ndarray – ảnh BGR đã vẽ box
            flag             : bool       – True = PASS, False = FAIL
            list_register    : list       – các register item bị fail
        """
        # image    = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        result_model = model_loader(
            image,
            size=int(pyuic.comboBox_3.currentText()),
            conf=int(pyuic.spinBox.value()) / 100,
        )
        detections = result_model.pandas().xyxy[0]  
 
        cfg_rows = _read_model_config(pyuic.model, pyuic.model_column, self.keys_mapping)
 
        label_cfg: dict[str, dict] = {}
        for cfg in cfg_rows:
            if cfg['label'] and cfg['label'] not in label_cfg:
                label_cfg[cfg['label']] = cfg
 
        valid_names: list[str] = []
        draw_candidates: list[dict] = []   

        for _, det in detections.iterrows():
            label_name = det['name']
            cfg = label_cfg.get(label_name)
 
            if cfg is None or not cfg['join']:
                continue
 
            width      = det['xmax'] - det['xmin']
            height     = det['ymax'] - det['ymin']
            confidence = det['confidence']
 
            out_of_conf = confidence < cfg['conf_thr']
            out_of_size = (width  < cfg['wmin'] or width  > cfg['wmax'] or
                           height < cfg['hmin'] or height > cfg['hmax'])
 
            if out_of_conf or out_of_size:
                continue

            if self.check_out_position(key_model, "camera-2", "model-2",det['xmin']):
                continue
            
            if not mode_load_jumper:
                self.set_dict_positive(key_model, "camera-3", "model-1", 'positive_jumper', label_name,'chan_comi',det)
                self.set_dict_positive(key_model, "camera-3", "model-1", 'positive_jumper', label_name,'day_jumper',det)
                self.append_labelname_to_init_list(key_model,"camera-2", "model-2", "list_jumper", label_name, "jumper")

            self.append_labelname_to_init_list(key_model,"camera-2","model-2","list_can_dien_cuc",label_name,"can_dien_cuc")

            valid_names.append(label_name)
            draw_candidates.append({
                'x1'   : int(det['xmin']),
                'y1'   : int(det['ymin']),
                'x2'   : int(det['xmax']),
                'y2'   : int(det['ymax']),
                'label': label_name,
                'conf' : confidence,
                'color': COLOR_OK,   
            })

        flag          = True
        list_register = []
        fail_labels   = set() 

        for cfg in cfg_rows:
            if not cfg['join']:
                continue

            label    = cfg['label']
            ok_count = valid_names.count(label)

            if cfg['ok']:
                if ok_count != cfg['quantity']:
                    flag = False
                    fail_labels.add(label)
                    list_register.append(cfg['register'])

            if cfg['ng']:
                if label in valid_names:
                    flag = False
                    fail_labels.add(label)
                    list_register.append(cfg['register'])

        if not mode_load_jumper:
            flag, fail_labels,list_register = self.set_dict_positive_calculator(key_model,"camera-3","model-1",'positive_jumper','chan_comi','day_jumper','minus','xmax',flag,list_register,fail_labels,'DM1910',num_task=1)
            flag, fail_labels,list_register = self.set_dict_positive_calculator(key_model,"camera-3","model-1",'positive_jumper','chan_comi','day_jumper','minus','ymax',flag,list_register,fail_labels,'DM1911',num_task=2)
            flag, fail_labels,list_register = self.set_dict_positive_calculator(key_model,"camera-3","model-1",'positive_jumper','chan_comi','day_jumper','minus','xmax',flag,list_register,fail_labels,'DM1912',num_task=3)
            flag, fail_labels,list_register = self.processing_returned_quantity_intit_list(key_model, "camera-2", "model-2",current_count, 12,'list_jumper',3,flag, list_register, fail_labels,'DM1608')
        
        flag, fail_labels,list_register = self.processing_returned_quantity_intit_list(key_model, "camera-2", "model-2",current_count, 12,'list_can_dien_cuc',1, flag, list_register,fail_labels, 'DM1601')    

        for d in draw_candidates:
            if d['label'] in fail_labels:
                d['color'] = COLOR_NG
 
        result_image_rgb = draw_detections(image,draw_candidates,fail_labels)
        # result_image_rgb = cv2.cvtColor(result_image_rgb, cv2.COLOR_RGB2BGR)
        return result_image_rgb, flag, list_register
    


    def append_labelname_to_init_list(self, key_model, num_camera, num_model, attr_name, label_name, compare_labelname):
            if key_model == (num_camera, num_model):
                if label_name == compare_labelname:
                    if not hasattr(self, attr_name):
                        setattr(self, attr_name, [])
                    current_list = getattr(self, attr_name)
                    current_list.append(label_name)

    def processing_returned_quantity_intit_list(
        self, key_model, num_camera, num_model,
        current_count, num_count,
        attr_name, 
        num_condition, flag, list_register, fail_labels, to_register):
        if key_model == (num_camera, num_model):
            if current_count == num_count:
                name_list = getattr(self, attr_name, [])
                if len(name_list) != num_condition:
                    print(f'NG {attr_name}: {len(name_list)}')
                    fail_labels.add(f'NG {attr_name}: so luong :{len(name_list)}')
                    flag = False
                    list_register.append(to_register)
                else:
                    fail_labels.add(f'OK {attr_name}: so luong :{len(name_list)}')
                setattr(self, attr_name, [])
        return flag, fail_labels,list_register
    
    def set_dict_positive(self,key_model,num_camera,num_model,attr_name,label_name,compare_labelname,det,):
        if key_model == (num_camera, num_model):
            if label_name == compare_labelname:
                if not hasattr(self, attr_name):
                    setattr(self, attr_name, {})
                current_dict = getattr(self, attr_name)
                if label_name not in current_dict:
                    current_dict[label_name] = {}
                for param in self.params:
                    current_dict[label_name][param] = int(det[param])

    def set_dict_positive_calculator(self,key_model,num_camera,num_model,attr_name,labelname_parent,labelname_child,calculator,param,flag,list_register,fail_labels,to_register,num_task=1):
        if key_model == (num_camera, num_model):
            positive_dict = getattr(self, attr_name, [])
            if labelname_parent in positive_dict and labelname_child in positive_dict:
                parent = positive_dict[labelname_parent][param]
                child = positive_dict[labelname_child][param]
                if num_task == 1:
                    width_parent = positive_dict[labelname_parent]['xmax'] - positive_dict[labelname_parent]['xmin']
                    num_condition = width_parent/2
                    if calculator == 'minus':
                        if parent > child:
                            total = parent - child
                            if total > num_condition:
                                flag = False
                                list_register.append(to_register)
                                fail_labels.add(f'NG {attr_name}: {total} > {num_condition}')
                            else :
                                flag = True
                                fail_labels.add(f'OK {attr_name}: {total} < {num_condition}')

                elif num_task == 3:
                    width_parent = positive_dict[labelname_parent]['xmax'] - positive_dict[labelname_parent]['xmin']
                    num_condition = width_parent/2
                    if calculator == 'minus':
                        if parent < child:
                            total = child - parent 
                            if total > num_condition:
                                flag = False
                                list_register.append(to_register)
                                fail_labels.add(f'NG {attr_name}: {total} > {num_condition}')
                            else :
                                flag = True
                                fail_labels.add(f'OK {attr_name}: {total} < {num_condition}')

                elif num_task == 2:
                    if child > parent:
                        flag = False
                        list_register.append(to_register)
                        fail_labels.add(f'NG {attr_name}: {child} > {parent}')
                    else :
                        flag = True
                        fail_labels.add(f'OK {attr_name}: {child} < {parent}')
                        
            if num_task == 3:
                setattr(self, attr_name, {})
        return flag, fail_labels, list_register 

    
    def check_out_position(self,key_model,num_camera,num_model,x_min):
        if key_model == (num_camera, num_model):
            return x_min < 1700
