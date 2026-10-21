from module_4.basler_pylon import PyUICWidgets
import torch
import cv2
import numpy as np
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional
from PyQt5.QtCore import Qt
import os,datetime
from module_1.root_path import resource_path
from module_3.handle_option_models import COLUMN_MAPPING
LOGO_WATERMARK = "Detected by YOLO V5 Architecture"


COLOR_OK = (0, 255, 0)   
COLOR_NG = (255, 0, 0)   

def _normalize_key_model(k):
    """Chuẩn hoá key_model về tuple dạng ('camera-X', 'model-Y')."""
    if not isinstance(k, (tuple, list)) or len(k) < 2:
        return None
    cam_str = str(k[0]).removeprefix("built-in-").removeprefix("camera-")
    mod_str = str(k[1]).removeprefix("model-")
    return (f"camera-{cam_str}", f"model-{mod_str}")
 

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
                    if reg and reg not in list_register:
                        list_register.append(reg)
        except Exception as e:
            print("Error in evaluate_task_calculator (v5):", e)

        return image_rgb, flag, list_register

 
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
