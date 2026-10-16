from module_4.basler_pylon import PyUICWidgets
import torch
import cv2
import numpy as np
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional
from PyQt5.QtCore import Qt
from module_3.handle_option_models import COLUMN_MAPPING
import os,datetime
from module_1.root_path import resource_path

LOGO_WATERMARK = "Detected by YOLO V5 Architecture"

# ── Config dataclasses (declared at module level for type-checker clarity) ──

@dataclass(frozen=True)
class _PosTrackCfg:
    """Describes one set_dict_positive call: which label to capture into which dict."""
    camera:     str
    model:      str
    attr:       str   # instance attribute that holds the bbox dict
    compare:    str   # label name whose bbox should be stored

@dataclass(frozen=True)
class _SpatialCheckCfg:
    """Describes one set_dict_positive_calculator call."""
    camera:     str
    model:      str
    attr:       str
    parent:     str          # key in bbox dict for the reference label
    child:      str          # key in bbox dict for the measured label
    calculator: str
    param:      str          # 'xmax' / 'xmin' / 'ymax' / 'ymin'
    register:   str          # PLC register to flag on failure
    task:       'v5s.CheckTask'

@dataclass(frozen=True)
class _CountCheckCfg:
    """Describes one processing_returned_quantity_intit_list call."""
    camera:       str
    model:        str
    attr:         str    # accumulator list attribute
    num_count:    int    # frame count at which the check fires
    num_condition: int   # expected length of the accumulator
    register:     str


COLOR_OK = (0, 255, 0)   
COLOR_NG = (255, 0, 0)   
 
# def draw_detections(image_rgb: np.ndarray, draw_list: list, fail_labels) -> np.ndarray:
#     out = image_rgb.copy()

#     # ── Bounding boxes ───────────────────────────────────────────────────
#     for d in draw_list:
#         x1, y1, x2, y2, color = d['x1'], d['y1'], d['x2'], d['y2'], d['color']
#         text = f"{d['label']} {d['conf']:.2f} {x2-x1} {y2-y1}"

#         cv2.rectangle(out, (x1, y1), (x2, y2), color, 5)

#         (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 2, 5)
#         ty = max(y1 - 5, th + 2)
#         cv2.rectangle(out, (x1, ty - th - 2), (x1 + tw + 2, ty + 2), color, -1)
#         cv2.putText(out, text, (x1 + 1, ty), cv2.FONT_HERSHEY_SIMPLEX, 2, (0,0,0), 5, cv2.LINE_AA)

#     # ── Fail labels (bottom-left, stacked upward) ────────────────────────
#     if not fail_labels:
#         return out

#     img_h, img_w = out.shape[:2]
#     font       = cv2.FONT_HERSHEY_SIMPLEX
#     font_scale = max(1.0, img_w / 1000)
#     thickness  = max(2, int(font_scale * 2))
#     pad        = int(img_w * 0.015)
#     (_, lh), bl = cv2.getTextSize("A", font, font_scale, thickness)
#     step       = lh + bl + pad

#     for i, label in enumerate(sorted(fail_labels)):
#         color        = COLOR_NG if 'LECH' in label else COLOR_OK
#         display_text = f'{i+1}. {label}'
#         (tw, th), bl = cv2.getTextSize(display_text, font, font_scale, thickness)
#         y = img_h - pad - i * step
#         cv2.rectangle(out, (pad - 4, y - th - 4), (pad + tw + 4, y + bl + 2), color, -1)
#         cv2.putText(out, display_text, (pad, y), font, font_scale, (0,0,0), thickness, cv2.LINE_AA)

#     return out



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

    # ── Fail labels HUD (Heads-Up Display) ────────────────────────────────
    if not fail_labels and not draw_list:
        return out

    img_h, img_w = out.shape[:2]

    # Dynamic scaling based on image width
    scale = max(0.6, img_w / 1200.0)
    font = cv2.FONT_HERSHEY_SIMPLEX

    font_scale_title = scale * 0.85
    font_scale_body = scale * 0.65
    thick_title = max(2, int(scale * 2.2))
    thick_body = max(1, int(scale * 1.8))

    pad = int(14 * scale)
    line_spacing = int(10 * scale)

    # Process items and classification
    processed_items = []
    ng_count = 0
    ok_count = 0

    if fail_labels:
        for label in sorted(fail_labels):
            lbl_str = str(label).strip()
            is_ng = '*' in lbl_str.upper()

            clean_text = lbl_str
            if clean_text.startswith('NG: '):
                clean_text = clean_text[4:]
            elif clean_text.startswith('OK: '):
                clean_text = clean_text[4:]

            if is_ng:
                ng_count += 1
                status_str = "NG"
            else:
                ok_count += 1
                status_str = "OK"

            processed_items.append({
                'status': status_str,
                'is_ng': is_ng,
                'text': clean_text
            })

    is_overall_ng = ng_count > 0
    overall_status_text = "NG" if is_overall_ng else "OK"
    overall_color = COLOR_NG if is_overall_ng else COLOR_OK

    # Calculate text sizes for HUD layout
    title_text = "INSPECTION HUD"
    status_badge_text = f" STATUS: {overall_status_text} "

    (tw_title, th_title), _ = cv2.getTextSize(title_text, font, font_scale_title, thick_title)
    (tw_badge, th_badge), _ = cv2.getTextSize(status_badge_text, font, font_scale_title, thick_title)

    header_w = tw_title + pad * 2 + tw_badge
    header_h = max(th_title, th_badge)

    det_count = len(draw_list)
    stats_text = f"Objects: {det_count}  |  Passed: {ok_count}  |  Failed: {ng_count}"
    (tw_stats, th_stats), _ = cv2.getTextSize(stats_text, font, font_scale_body, thick_body)

    max_item_w = 0
    item_heights = []
    for item in processed_items:
        tag_str = f"[{item['status']}] "
        full_line = tag_str + item['text']
        (tw_i, th_i), _ = cv2.getTextSize(full_line, font, font_scale_body, thick_body)
        if tw_i > max_item_w:
            max_item_w = tw_i
        item_heights.append(th_i)

    hud_w = max(header_w, tw_stats, max_item_w) + pad * 3

    total_item_h = sum(item_heights) + len(item_heights) * line_spacing if item_heights else 0
    hud_h = pad * 2 + header_h + line_spacing + th_stats + (line_spacing * 2 if processed_items else 0) + total_item_h + pad

    # Position HUD at Bottom-Left with padding
    hud_x1 = pad
    hud_y2 = img_h - pad
    hud_y1 = max(pad, hud_y2 - hud_h)
    hud_x2 = min(img_w - pad, hud_x1 + hud_w)

    # Draw semi-transparent dark HUD background card (ROI-only blend)
    roi = out[hud_y1:hud_y2, hud_x1:hud_x2]
    roi_overlay = roi.copy()
    roi_overlay[:] = (18, 22, 30)
    cv2.addWeighted(roi_overlay, 0.78, roi, 0.22, 0, roi)
    out[hud_y1:hud_y2, hud_x1:hud_x2] = roi

    # Draw HUD outer border box with status color accent
    cv2.rectangle(out, (hud_x1, hud_y1), (hud_x2, hud_y2), overall_color, max(2, int(scale * 2)))

    # Current Y drawing cursor inside HUD
    curr_y = hud_y1 + pad + th_title

    # 1. Render Title Text
    cv2.putText(out, title_text, (hud_x1 + pad, curr_y), font, font_scale_title, (255, 255, 255), thick_title, cv2.LINE_AA)

    # Render Status Badge on the right of title
    badge_x1 = hud_x2 - pad - tw_badge
    badge_y1 = curr_y - th_badge - 2
    badge_y2 = curr_y + 4
    cv2.rectangle(out, (badge_x1, badge_y1), (badge_x1 + tw_badge, badge_y2), overall_color, -1)
    cv2.putText(out, status_badge_text, (badge_x1, curr_y), font, font_scale_title, (0, 0, 0), thick_title, cv2.LINE_AA)

    # Separator Line
    curr_y += line_spacing + 4
    cv2.line(out, (hud_x1 + pad, curr_y), (hud_x2 - pad, curr_y), (80, 90, 110), max(1, int(scale)))

    # 2. Render Statistics Line
    curr_y += line_spacing + th_stats
    cv2.putText(out, stats_text, (hud_x1 + pad, curr_y), font, font_scale_body, (200, 220, 240), thick_body, cv2.LINE_AA)

    # 3. Render Detailed Items
    if processed_items:
        curr_y += line_spacing + 4
        cv2.line(out, (hud_x1 + pad, curr_y), (hud_x2 - pad, curr_y), (50, 60, 80), max(1, int(scale)))

        for item, th_i in zip(processed_items, item_heights):
            curr_y += line_spacing + th_i

            # Draw Tag "[ OK ]" or "[ NG ]"
            tag_text = f"[{item['status']}]"
            tag_color = COLOR_NG if item['is_ng'] else COLOR_OK

            (tw_tag, _), _ = cv2.getTextSize(tag_text, font, font_scale_body, thick_body + 1)
            cv2.putText(out, tag_text, (hud_x1 + pad, curr_y), font, font_scale_body, tag_color, thick_body + 1, cv2.LINE_AA)

            # Draw Item Description & Stats
            text_x = hud_x1 + pad + tw_tag + int(8 * scale)
            cv2.putText(out, item['text'], (text_x, curr_y), font, font_scale_body, (230, 235, 240), thick_body, cv2.LINE_AA)

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

    # ── Class-level check configuration tables ─────────────────────────────
    # Edit these tables to add / remove spatial checks or count checks.
    # Do NOT touch run_model logic for routine configuration changes.

    # Labels whose bounding boxes are tracked per-detection (jumper mode only)
    _JUMPER_TRACK_CFG: tuple[_PosTrackCfg, ...] = (
        _PosTrackCfg(camera='camera-3', model='model-1', attr='positive_jumper', compare='chan_comi'),
        _PosTrackCfg(camera='camera-3', model='model-1', attr='positive_jumper', compare='day_jumper'),
        _PosTrackCfg(camera='camera-3', model='model-1', attr='positive_jumper', compare='dap_day_jumper'),
    )

    # Spatial relationship checks executed after all detections are processed
    # (jumper mode only — ordered, SHIFT_RIGHT always last to reset the dict)
    _SPATIAL_CHECK_CFG: tuple[_SpatialCheckCfg, ...] = ()
    # Populated in __init_subclass__ or lazily on first access to allow
    # forward-referencing CheckTask. See _build_spatial_cfg().

    # Count-consistency checks (some jumper-only, some always active)
    _COUNT_CHECK_CFG: tuple[_CountCheckCfg, ...] = (
        # jumper_only=True  → checked only when mode_load_jumper is False
        _CountCheckCfg(camera='camera-2', model='model-2', attr='list_jumper',       num_count=12, num_condition=3, register='DM1608'),
        # jumper_only=False → always checked
        _CountCheckCfg(camera='camera-2', model='model-2', attr='list_can_dien_cuc', num_count=12, num_condition=1, register='DM1601'),
    )
    # Which entries in _COUNT_CHECK_CFG are jumper-only (by index)
    _COUNT_JUMPER_ONLY_INDICES: frozenset[int] = frozenset({0})

    @classmethod
    def _build_spatial_cfg(cls) -> tuple:
        """Build _SPATIAL_CHECK_CFG once, after CheckTask is defined."""
        T = cls.CheckTask
        return (
            # ── chan_comi vs day_jumper ──────────────────────────────────────
            _SpatialCheckCfg('camera-3','model-1','positive_jumper','chan_comi','day_jumper',    'minus','xmax','DM1910', T.SHIFT_LEFT),
            _SpatialCheckCfg('camera-3','model-1','positive_jumper','chan_comi','day_jumper',    'minus','ymax','DM1911', T.SHIFT_BELOW),
            _SpatialCheckCfg('camera-3','model-1','positive_jumper','chan_comi','day_jumper',    'minus','xmax','DM1912', T.SHIFT_RIGHT),
            # ── chan_comi vs dap_day_jumper ──────────────────────────────────
            _SpatialCheckCfg('camera-3','model-1','positive_jumper','chan_comi','dap_day_jumper','minus','xmax','DM1912', T.CHILD_UNDER_XMAX),
            _SpatialCheckCfg('camera-3','model-1','positive_jumper','chan_comi','dap_day_jumper','minus','xmin','DM1910', T.CHILD_OVER_XMIN),
            _SpatialCheckCfg('camera-3','model-1','positive_jumper','chan_comi','dap_day_jumper','minus','ymax','DM1911', T.CHILD_OVER_YMAX),
            _SpatialCheckCfg('camera-3','model-1','positive_jumper','chan_comi','dap_day_jumper','minus','ymin','DM1911', T.CHILD_RIGHT_HALF),
        )

    # ── Initialiser ────────────────────────────────────────────────────────

    def __init__(self, path_pt: str, device: str = 'cpu'):
        self.keys_mapping = list(COLUMN_MAPPING.keys())
        self.source_model = (
            torch.hub.load(
                resource_path('_source/v5'), 'custom',
                path=path_pt, source='local', force_reload=True
            ).to(device=torch.device(device.split('-')[0]))
        )

        self.list_jumper      = []
        self.list_can_dien_cuc = []
        self.positive_jumper  = {}
        self.params           = ['xmax', 'xmin', 'ymax', 'ymin']

        self.list_image_array :list[np.ndarray] = []

        # Finalise spatial config now that CheckTask is available
        if not v5s._SPATIAL_CHECK_CFG:
            v5s._SPATIAL_CHECK_CFG = v5s._build_spatial_cfg()

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
        if camera:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) 
        self.add_image_array(image_array=image,key_model=key_model, num_camera="camera-2", num_model= "model-2",)
        result_model = model_loader(
            image,
            size=int(pyuic.comboBox_imgsz.currentText()),
            conf=int(pyuic.spinBox_confidenc_score.value()) / 100,
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

        # ── Hàm riêng biệt kiểm tra Task Calculator đa nhãn hình học ──────────
        print("flag",flag)
        result_image_rgb, flag, list_register = self.evaluate_task_calculator(
            result_image_rgb, draw_candidates, pyuic, flag, list_register
        )

        return result_image_rgb, flag, list_register,LOGO_WATERMARK

    def evaluate_task_calculator(
        self,
        image_rgb: np.ndarray,
        draw_candidates: list,
        pyuic,
        flag: bool,
        list_register: list
    ):
        """
        Hàm riêng biệt thực hiện kiểm tra các Task quan hệ tọa độ & kích thước hình học đa nhãn.
        - draw_candidates: danh sách các box hợp lệ (đã qua lọc conf & size ở Bước 1)
        - pyuic: UI object chứa danh sách active_tasks
        - flag: cờ phán định hiện tại (từ lọc nhãn thông thường)
        - list_register: danh sách thanh ghi PLC cần gửi
        """
        processor = getattr(pyuic, 'processor', None)
        active_tasks = getattr(processor, 'active_tasks', []) if processor else []
        if not active_tasks:
            print("flag",flag)
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
                tasks_config=active_tasks,
                draw_overlay=True
            )

            if res_img is not None:
                image_rgb = res_img

            if not task_all_pass:
                flag = False
                for reg, val in plc_to_send:
                    if reg and reg not in list_register:
                        list_register.append(reg)
        except Exception as e:
            print("Error in evaluate_task_calculator (v5):", e)

        return image_rgb, flag, list_register

    # ── Per-detection hooks ──────────────────────────────────────────────────

    def _run_per_detection_hooks(
        self,
        key_model,
        label_name: str,
        det,
        mode_load_jumper: bool,
    ) -> None:
        """Update accumulator dicts / lists for a single accepted detection."""
        if not mode_load_jumper:
            for cfg in self._JUMPER_TRACK_CFG:
                self.set_dict_positive(
                    key_model, cfg.camera, cfg.model,
                    cfg.attr, label_name, cfg.compare, det,
                )
            self.append_labelname_to_init_list(
                key_model, "camera-2", "model-2",
                "list_jumper", label_name, "jumper",
            )

        self.append_labelname_to_init_list(
            key_model, "camera-2", "model-2",
            "list_can_dien_cuc", label_name, "can_dien_cuc",
        )

    # ── Post-detection spatial & count checks ────────────────────────────────

    def _run_spatial_checks(
        self,
        key_model,
        current_count: int,
        flag: bool,
        fail_labels: set,
        list_register: list,
        mode_load_jumper: bool,
        pyuic,
    ) -> bool:
        """Execute all spatial-relationship and count-consistency checks
        defined in the class-level config tables.
        """
        if not mode_load_jumper:
            for sc in self._SPATIAL_CHECK_CFG:
                flag = self.set_dict_positive_calculator(
                    key_model, sc.camera, sc.model,
                    sc.attr, sc.parent, sc.child,
                    sc.calculator, sc.param,
                    flag, list_register, fail_labels,
                    sc.register, task=sc.task,
                )

        for i, cc in enumerate(self._COUNT_CHECK_CFG):
            if i in self._COUNT_JUMPER_ONLY_INDICES and mode_load_jumper:
                continue
            flag = self.processing_returned_quantity_intit_list(
                key_model, cc.camera, cc.model,
                current_count, cc.num_count,
                cc.attr, cc.num_condition,
                flag, list_register, fail_labels, cc.register,
                pyuic,
            )
        return flag

    def append_labelname_to_init_list(
        self,
        key_model: tuple,
        num_camera: str,
        num_model: str,
        attr_name: str,
        label_name: str,
        compare_labelname: str,
    ) -> None:
        if key_model != (num_camera, num_model):
            return
            
        if label_name != compare_labelname:
            return
            
        if not hasattr(self, attr_name):
            setattr(self, attr_name, [])
            
        current_list = getattr(self, attr_name)
        current_list.append(label_name)

    def processing_returned_quantity_intit_list(
        self,
        key_model: tuple,
        num_camera: str,
        num_model: str,
        current_count: int,
        num_count: int,
        attr_name: str,
        num_condition: int,
        flag: bool,
        list_register: list,
        fail_labels: set,
        to_register: str,
        pyuic,
    ) -> bool:
        if key_model != (num_camera, num_model):
            return flag
            
        if current_count != num_count:
            return flag
            
        name_list = getattr(self, attr_name, [])
        list_len = len(name_list)
        
        if list_len != num_condition:
            fail_labels.add(f'* NG: {attr_name} | nums item: {list_len}')
            flag = False
            list_register.append(to_register)
            self.check_and_save_image_array(pyuic)
        else:
            fail_labels.add(f'OK: {attr_name} | nums item: {list_len}')
            self.clear_image_array()
            
        setattr(self, attr_name, [])
        return flag
    
    def set_dict_positive(
        self,
        key_model: tuple,
        num_camera: str,
        num_model: str,
        attr_name: str,
        label_name: str,
        compare_labelname: str,
        det,
    ) -> None:
       
        if key_model != (num_camera, num_model):
            return
            
        if label_name != compare_labelname:
            return
            
        if not hasattr(self, attr_name):
            setattr(self, attr_name, {})
            
        current_dict = getattr(self, attr_name)
        
        if label_name not in current_dict:
            current_dict[label_name] = {}
            
        for param in self.params:
            current_dict[label_name][param] = int(det[param])

    # ──────────────────────────────────────────────────────────────────────
    # Spatial-check dispatcher
    # ──────────────────────────────────────────────────────────────────────

    class CheckTask(Enum):
        """Describes *which* spatial relationship to validate between
        a parent bbox coordinate and a child bbox coordinate."""
        SHIFT_LEFT        = 1   # child is to the LEFT  of centre (x-axis)
        SHIFT_BELOW       = 2   # child is BELOW parent (y-axis)
        SHIFT_RIGHT       = 3   # child is to the RIGHT of centre (x-axis, resets dict)
        CHILD_UNDER_XMAX  = 4   # child.x must not exceed parent.xmax
        CHILD_OVER_XMIN   = 5   # child.x must not fall below parent.xmin
        CHILD_OVER_YMAX   = 6   # child.y must not exceed parent.ymax - offset
        CHILD_RIGHT_HALF  = 7   # child.x must be in the right half of parent (height-derived)

    # -- internal helpers --------------------------------------------------

    @staticmethod
    def _record_fail(
        flag: bool,
        list_register: list,
        fail_labels: set,
        register: str,
        message: str,
    ) -> bool:
        """Mark a failure: append register, add NG label, set flag=False."""
        list_register.append(register)
        fail_labels.add(message)
        return False

    def _check_shift_left(
        self, pbox: dict, parent: int, child: int,
        calculator: str, attr_name: str,
        flag: bool, list_register: list, fail_labels: set, to_register: str,
    ) -> bool:
        """Task SHIFT_LEFT — child is shifted left of parent centre."""
        width     = pbox['xmax'] - pbox['xmin']
        threshold = width / 2
        if calculator == 'minus' and parent > child:
            total = parent - child
            if total > threshold:
                return self._record_fail(
                    flag, list_register, fail_labels, to_register,
                    f'* LECH DAY JUMPER TRAI: {total} > {threshold}',
                )
            fail_labels.add(f'DAY JUMPER TRAI: {total} < {threshold}')
        else:
            fail_labels.add(f'DAY JUMPER TRAI: N/A')
        return flag

    def _check_shift_below(
        self, parent: int, child: int, attr_name: str,
        flag: bool, list_register: list, fail_labels: set, to_register: str,
    ) -> bool:
        """Task SHIFT_BELOW — child.y must not exceed parent.y."""
        if child > parent:
            return self._record_fail(
                flag, list_register, fail_labels, to_register,
                f'* LECH DAY JUMPER PHIA DUOI: {child} > {parent}',
            )
        fail_labels.add(f'DAY JUMPER PHIA DUOI: {child} < {parent}')
        return flag

    def _check_shift_right(
        self, pbox: dict, parent: int, child: int,
        calculator: str, attr_name: str,
        flag: bool, list_register: list, fail_labels: set, to_register: str,
    ) -> bool:
        """Task SHIFT_RIGHT — child is shifted right of parent centre (resets dict after)."""
        width     = pbox['xmax'] - pbox['xmin']
        threshold = width / 2
        if calculator == 'minus' and parent < child:
            total = child - parent
            if total > threshold:
                return self._record_fail(
                    flag, list_register, fail_labels, to_register,
                    f'* LECH DAY JUMPER PHAI: {total} > {threshold}',
                )
            fail_labels.add(f'DAY JUMPER PHAI: {total} < {threshold}')
        else:
            fail_labels.add(f'DAY JUMPER PHAI: N/A')
        return flag

    def _check_child_under_xmax(
        self, parent: int, child: int, attr_name: str,
        flag: bool, list_register: list, fail_labels: set, to_register: str,
    ) -> bool:
        """Task CHILD_UNDER_XMAX — child.x must not be less than parent.x."""
        if child > parent+100:
            return self._record_fail(
                flag, list_register, fail_labels, to_register,
                f'* LECH PHAN DAP DAY JUMPER PHAI: {child} > {parent+100}',
            )
        fail_labels.add(f'PHAN DAP DAY JUMPER PHAI: {child} < {parent+100}')
        return flag

    def _check_child_over_xmin(
        self, parent: int, child: int, attr_name: str,
        flag: bool, list_register: list, fail_labels: set, to_register: str,
    ) -> bool:
        """Task CHILD_OVER_XMIN — child.x must not exceed parent.x."""
        if child < parent-100:
            return self._record_fail(
                flag, list_register, fail_labels, to_register,
                f'* LECH PHAN DAP DAY JUMPER TRAI: {child} < {parent-100}',
            )
        fail_labels.add(f'PHAN DAP DAY JUMPER TRAI: {child} > {parent-100}')
        return flag

    def _check_child_over_ymax(
        self, parent: int, child: int, attr_name: str,
        flag: bool, list_register: list, fail_labels: set, to_register: str,
        offset: int = 30,
    ) -> bool:
        """Task CHILD_OVER_YMAX — child.y must not exceed parent.y minus `offset`."""
        adjusted = parent - offset
        if child > adjusted:
            return self._record_fail(
                flag, list_register, fail_labels, to_register,
                f'* LECH PHAN DAP DAY JUMPER DUOI: {child} > {adjusted}',
            )
        fail_labels.add(f'PHAN DAP DAY JUMPER DUOI: {child} < {adjusted}')
        return flag

    def _check_child_right_half(
        self, pbox: dict, child: int, attr_name: str,
        flag: bool, list_register: list, fail_labels: set, to_register: str,
    ) -> bool:
        """Task CHILD_RIGHT_HALF — child.x must lie in parent's right half
        (centre derived from parent height, anchored at xmin)."""
        height    = pbox['ymax'] - pbox['ymin']
        threshold = pbox['ymin'] + height / 2
        if child < threshold:
            return self._record_fail(
                flag, list_register, fail_labels, to_register,
                f'* LECH PHAN DAP DAY JUMPER TREN: {child} < {threshold}',
            )
        fail_labels.add(f'PHAN DAP DAY JUMPER TREN: {child} > {threshold}')
        return flag

    # -- public interface --------------------------------------------------

    def set_dict_positive_calculator(
        self,
        key_model,
        num_camera,
        num_model,
        attr_name: str,
        labelname_parent: str,
        labelname_child: str,
        calculator: str,
        param: str,
        flag: bool,
        list_register: list,
        fail_labels: set,
        to_register: str,
        task: 'v5s.CheckTask' = None,   # replaces num_task
        num_task: int = 1,              # legacy fallback
    ) -> bool:
        """
        Evaluate a spatial relationship between two detected bounding boxes
        and update the pass/fail state accordingly.

        Parameters
        ----------
        task          : CheckTask  – preferred; describes which check to run.
        num_task      : int        – legacy integer alias (1-7), used when
                                    `task` is None for backwards compatibility.
        """
        if task is None:
            task = v5s.CheckTask(num_task)   # convert legacy int → Enum

        if key_model != (num_camera, num_model):
            return flag

        positive_dict: dict = getattr(self, attr_name, {})

        if labelname_parent in positive_dict and labelname_child in positive_dict:
            parent = positive_dict[labelname_parent][param]
            child  = positive_dict[labelname_child][param]
            pbox   = positive_dict[labelname_parent]   # parent bounding-box dict

            dispatch = {
                v5s.CheckTask.SHIFT_LEFT: lambda: self._check_shift_left(
                    pbox, parent, child, calculator, attr_name,
                    flag, list_register, fail_labels, to_register,
                ),
                v5s.CheckTask.SHIFT_BELOW: lambda: self._check_shift_below(
                    parent, child, attr_name,
                    flag, list_register, fail_labels, to_register,
                ),
                v5s.CheckTask.SHIFT_RIGHT: lambda: self._check_shift_right(
                    pbox, parent, child, calculator, attr_name,
                    flag, list_register, fail_labels, to_register,
                ),
                v5s.CheckTask.CHILD_UNDER_XMAX: lambda: self._check_child_under_xmax(
                    parent, child, attr_name,
                    flag, list_register, fail_labels, to_register,
                ),
                v5s.CheckTask.CHILD_OVER_XMIN: lambda: self._check_child_over_xmin(
                    parent, child, attr_name,
                    flag, list_register, fail_labels, to_register,
                ),
                v5s.CheckTask.CHILD_OVER_YMAX: lambda: self._check_child_over_ymax(
                    parent, child, attr_name,
                    flag, list_register, fail_labels, to_register,
                ),
                v5s.CheckTask.CHILD_RIGHT_HALF: lambda: self._check_child_right_half(
                    pbox, child, attr_name,
                    flag, list_register, fail_labels, to_register,
                ),
            }

            flag = dispatch[task]()

        # Task SHIFT_RIGHT must clear the dict after evaluation
        if task == v5s.CheckTask.CHILD_RIGHT_HALF:
            setattr(self, attr_name, {})

        return flag

    # ──────────────────────────────────────────────────────────────────────

    def check_out_position(self, key_model, num_camera, num_model, x_min: int) -> bool:
        if key_model == (num_camera, num_model):
            return x_min < 1700

    def check_item_option(self,image_array,pyuic,list_item):
        if 'day_jumper' not in list_item or 'dap_day_jumper' not in list_item:
            path_save_image = pyuic.lineEdit_4.text().strip()
            self._save_ng_image(image_array, path_save_image, state="NG")

    def time_to_name_file_image(self):
        return str(datetime.datetime.now()).replace(':', '-').replace(' ', '_').replace('.', '-')

    def _save_ng_image(self, image: np.ndarray, path_save_image: str,state: str) -> None:
        if not path_save_image:
            return

        try:
            today                = datetime.datetime.now().strftime('%Y-%m-%d')
            folder               = os.path.join(path_save_image, state, today)
            os.makedirs(folder,              exist_ok=True)
            name_file            = self.time_to_name_file_image()
            filename             = f'{name_file}_can_dien_cuc_or_day_jumper.jpg'
            filepath             = os.path.join(folder, filename)
            bgr        = cv2.cvtColor(image,        cv2.COLOR_RGB2BGR)
            cv2.imwrite(filepath,        bgr)

        except Exception:
            pass

    def add_image_array(self, image_array : np.ndarray,
        key_model: tuple,
        num_camera: str,
        num_model: str,):
        if key_model != (num_camera, num_model):
            return
        self.list_image_array.append(image_array)

    def clear_image_array(self):
        self.list_image_array.clear()
    
    def check_and_save_image_array(self,pyuic) -> bool:
        path_save_image = pyuic.lineEdit_4.text().strip()
        for i, image_array in enumerate(self.list_image_array):
            self._save_ng_image(image_array, path_save_image, state="NG")
        self.clear_image_array()
            
#!/usr/bin/env python3

# ════════════════════════════════════════════════════════════
#   DETECT VIEWER — Duyệt folder ảnh + chạy YOLOv5 detect
# ════════════════════════════════════════════════════════════
#   - Nút "Load .pt"    : chọn file model .pt
#   - Nút "Load Folder" : chọn folder chứa ảnh
#   - Nút "<< Prev / Next >>" : duyệt qua từng ảnh, tự động detect

#   Cài đặt (nếu chưa có):
#       pip install pillow opencv-python

#   Chạy:
#       python3 detect_viewer.py


# import os
# import cv2
# import torch
# import tkinter as tk
# from tkinter import filedialog, messagebox
# from PIL import Image, ImageTk

# YOLOV5_LOCAL_REPO = "./_source/v5"

# IMG_EXTS = (".jpg", ".jpeg", ".png", ".bmp")


# class DetectViewerApp:
#     def __init__(self, root):
#         self.root = root
#         root.title("YOLOv5 Detect Viewer")
#         root.geometry("1000x750")

#         self.image_paths = []
#         self.current_index = -1
#         self.dev = None            # instance v5s
#         self.source_model = None   # model từ torch.hub.load
#         self.pt_path = None
#         self.cuda_device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

#         # ── Thanh điều khiển trên cùng ─────────────────────
#         top = tk.Frame(root)
#         top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

#         tk.Button(top, text="Load .pt", width=12, command=self.load_pt).pack(side=tk.LEFT, padx=4)
#         tk.Button(top, text="Load Folder", width=12, command=self.load_folder).pack(side=tk.LEFT, padx=4)

#         self.status_label = tk.Label(top, text="Chưa load model", fg="red")
#         self.status_label.pack(side=tk.LEFT, padx=12)

#         # ── Khung hiển thị ảnh ─────────────────────────────
#         self.canvas = tk.Label(root, bg="black")
#         self.canvas.pack(side=tk.TOP, padx=8, pady=8, fill=tk.BOTH, expand=True)

#         # ── Thanh điều hướng Prev / Next ───────────────────
#         nav = tk.Frame(root)
#         nav.pack(side=tk.TOP, fill=tk.X, pady=6)

#         self.prev_btn = tk.Button(nav, text="<< Prev", width=12,
#                                    command=self.prev_image, state=tk.DISABLED)
#         self.prev_btn.pack(side=tk.LEFT, padx=20)

#         self.index_label = tk.Label(nav, text="0 / 0")
#         self.index_label.pack(side=tk.LEFT, padx=20)

#         self.next_btn = tk.Button(nav, text="Next >>", width=12,
#                                    command=self.next_image, state=tk.DISABLED)
#         self.next_btn.pack(side=tk.LEFT, padx=20)

#         # Bàn phím: mũi tên trái/phải để chuyển ảnh
#         root.bind("<Left>", lambda e: self.prev_image())
#         root.bind("<Right>", lambda e: self.next_image())

#         # ── Thông tin kết quả detect ────────────────────────
#         self.info_label = tk.Label(root, text="", justify=tk.LEFT, anchor="w",
#                                     font=("Consolas", 10))
#         self.info_label.pack(side=tk.TOP, fill=tk.X, padx=8, pady=6)

#     # ─────────────────────────────────────────────────────
#     # LOAD MODEL
#     # ─────────────────────────────────────────────────────
#     def load_pt(self):
#         path_pt = filedialog.askopenfilename(
#             title="Chọn file model .pt",
#             filetypes=[("PyTorch model", "*.pt")]
#         )
#         if not path_pt:
#             return

#         self.status_label.config(text="Đang load model ...", fg="orange")
#         self.root.update_idletasks()

#         try:
#             self.dev = v5s(path_pt=path_pt, device="cpu")
#             self.source_model = torch.hub.load(
#                 YOLOV5_LOCAL_REPO, "custom", path=path_pt,
#                 source="local", force_reload=True
#             ).to(device=self.cuda_device)

#             self.pt_path = path_pt
#             self.status_label.config(text=f"Model: {os.path.basename(path_pt)}", fg="green")

#             if self.image_paths:
#                 self.show_current()

#         except Exception as e:
#             self.status_label.config(text="Load model thất bại", fg="red")
#             messagebox.showerror("Lỗi load model", str(e))

#     # ─────────────────────────────────────────────────────
#     # LOAD FOLDER ẢNH
#     # ─────────────────────────────────────────────────────
#     def load_folder(self):
#         folder = filedialog.askdirectory(title="Chọn folder chứa ảnh")
#         if not folder:
#             return

#         self.image_paths = sorted([
#             os.path.join(folder, f) for f in os.listdir(folder)
#             if f.lower().endswith(IMG_EXTS)
#         ])

#         if not self.image_paths:
#             messagebox.showwarning("Không có ảnh", "Folder này không có ảnh hợp lệ (.jpg/.png/.bmp)")
#             return

#         self.current_index = 0
#         self.prev_btn.config(state=tk.NORMAL)
#         self.next_btn.config(state=tk.NORMAL)
#         self.show_current()

#     # ─────────────────────────────────────────────────────
#     # HIỂN THỊ ẢNH HIỆN TẠI (chạy detect nếu đã có model)
#     # ─────────────────────────────────────────────────────
#     def show_current(self):
#         if self.current_index < 0 or self.current_index >= len(self.image_paths):
#             return

#         path = self.image_paths[self.current_index]
#         image = cv2.imread(path)
#         current_index = self.current_index 

#         if image is None:
#             self.info_label.config(text=f"✗ Không đọc được ảnh: {path}")
#             return

#         flag, list_register = None, None

#         if self.dev is None or self.source_model is None:
#             # Chưa load model -> chỉ hiện ảnh gốc
#             display = image
#         else:
#             # try:
#                 display, flag, list_register = self.dev.run_model(
#                     image, self.source_model, None, None,
#                     ("camera-2", "model-2"),current_index, False
#                 )
#             # except Exception as e:
#             #     messagebox.showerror("Lỗi detect", str(e))
#             #     display = image

#         self._render(display)

#         self.index_label.config(text=f"{self.current_index + 1} / {len(self.image_paths)}")
#         self.info_label.config(
#             text=f"File : {os.path.basename(path)}\n"
#                  f"flag : {flag}\n"
#                  f"list_register : {list_register}"
#         )


#     def _render(self, image_bgr):
#         max_w, max_h = 900, 550
#         h, w = image_bgr.shape[:2]
#         scale = min(max_w / w, max_h / h, 1.0)
#         if scale < 1.0:
#             image_bgr = cv2.resize(image_bgr, (int(w * scale), int(h * scale)),
#                                     interpolation=cv2.INTER_AREA)

#         image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
#         img_pil = Image.fromarray(image_rgb)
#         img_tk = ImageTk.PhotoImage(img_pil)

#         self.canvas.imgtk = img_tk  # giữ reference tránh bị garbage collect
#         self.canvas.config(image=img_tk)

#     # ─────────────────────────────────────────────────────
#     # ĐIỀU HƯỚNG
#     # ─────────────────────────────────────────────────────
#     def prev_image(self):
#         if self.current_index > 0:
#             self.current_index -= 1
#             self.show_current()

#     def next_image(self):
#         if self.current_index < len(self.image_paths) - 1:
#             self.current_index += 1
#             self.show_current()


# if __name__ == "__main__":
#     root = tk.Tk()
#     app = DetectViewerApp(root)
#     root.mainloop()

# ════════════════════════════════════════════════════════════
