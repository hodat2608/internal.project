"""
YOLOv11 GUI - Detect / Training / Auto Label
=============================================
3 tab:
  1) Detect      : load model .pt, load folder ảnh, chỉnh thông số filter theo
                    từng class (conf/width/height), phán định OK/NG.
  2) Training     : chọn folder dataset (images + labels dạng YOLO txt), tool
                    tự động chia train/valid, tự tạo data.yaml, rồi train
                    bằng ultralytics YOLO với imgsz/batch/epochs tuỳ chỉnh,
                    lưu weight cuối vào nơi + tên do người dùng chỉ định.
  3) Auto Label   : load model .pt + folder ảnh (chưa có nhãn), tool tự chạy
                    detect và sinh file nhãn .txt (định dạng YOLO) + classes.txt
                    cho từng ảnh để phục vụ gán nhãn / chỉnh sửa lại sau.

Cài đặt:
    pip install -r requirements.txt

Chạy:
    python main.py
"""

import os
import sys
import glob
import random
import shutil
import threading
import colorsys
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk, ImageDraw, ImageFont

try:
    import yaml
except ImportError:
    yaml = None

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff")

# Confidence "nền" dùng khi chạy model ở tab Detect - phải thấp hơn hoặc bằng
# conf nhỏ nhất mà người dùng có thể set trên GUI, để không phải chạy lại
# model mỗi khi người dùng kéo thanh confidence (chỉ cần lọc lại kết quả cache).
BASE_INFER_CONF = 0.01


# ========================================================================== #
# Helper chung
# ========================================================================== #

def gen_color(idx, total):
    """Sinh màu RGB khác nhau cho từng class id."""
    hue = (idx * 0.61803398875) % 1.0  # golden ratio để màu tách biệt
    r, g, b = colorsys.hsv_to_rgb(hue, 0.65, 0.95)
    return int(r * 255), int(g * 255), int(b * 255)


class ClassSetting:
    """Thông số filter + phán định OK/NG cho 1 class (dùng ở tab Detect)."""

    def __init__(self):
        self.conf = tk.DoubleVar(value=0.25)
        self.w_min = tk.DoubleVar(value=0)
        self.w_max = tk.DoubleVar(value=99999)
        self.h_min = tk.DoubleVar(value=0)
        self.h_max = tk.DoubleVar(value=99999)
        self.enabled = tk.BooleanVar(value=True)

        # ok=True: nhãn bắt buộc xuất hiện đúng "count" lần -> OK, sai -> NG
        # ng=True: nhãn hễ xuất hiện (>=1) là NG, không xuất hiện thì OK
        self.ok = tk.BooleanVar(value=False)
        self.ng = tk.BooleanVar(value=False)
        self.count = tk.IntVar(value=1)


class TextRedirector:
    """Redirect stdout/stderr vào 1 callback (dùng để log training ra Text widget)."""

    def __init__(self, callback):
        self.callback = callback

    def write(self, s):
        s = s.strip("\n")
        if s:
            self.callback(s)

    def flush(self):
        pass


# ========================================================================== #
# App chính
# ========================================================================== #

class YoloGuiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YOLOv11 GUI - Detect / Training / Auto Label")
        self.root.geometry("1450x880")

        # ---- state cho tab Detect ----
        self.model = None
        self.class_names = {}
        self.class_settings = {}
        self.class_colors = {}
        self.image_paths = []
        self.current_index = -1
        self.current_pil_image = None
        self.current_detections = []
        self.tk_image = None

        # ---- state cho tab Auto Label ----
        self.al_model = None
        self.al_model_path = None
        self.al_folder = None
        self.al_class_names = {}
        self.al_class_settings = {}
        self.al_class_colors = {}

        # ---- Notebook 4 tab ----
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.tab_detect = ttk.Frame(self.notebook)
        self.tab_train = ttk.Frame(self.notebook)
        self.tab_autolabel = ttk.Frame(self.notebook)
        self.tab_crop = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_detect, text="1. Detect")
        self.notebook.add(self.tab_train, text="2. Training")
        self.notebook.add(self.tab_autolabel, text="3. Auto Label")
        self.notebook.add(self.tab_crop, text="4. Crop Image & Label")

        self._build_detect_tab(self.tab_detect)
        self._build_train_tab(self.tab_train)
        self._build_autolabel_tab(self.tab_autolabel)
        self._build_crop_tab(self.tab_crop)

        # ---- Status bar chung ----
        self.status_var = tk.StringVar(value="Sẵn sàng.")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w").pack(
            side=tk.BOTTOM, fill=tk.X
        )

    # ====================================================================== #
    # TAB 1: DETECT
    # ====================================================================== #
    def _build_detect_tab(self, parent):
        toolbar = ttk.Frame(parent, padding=6)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(toolbar, text="Load model (.pt)", command=self.load_model).pack(
            side=tk.LEFT, padx=4
        )
        self.model_label = ttk.Label(toolbar, text="Chưa load model", foreground="red")
        self.model_label.pack(side=tk.LEFT, padx=10)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Button(toolbar, text="Load folder ảnh", command=self.load_folder).pack(
            side=tk.LEFT, padx=4
        )
        self.folder_label = ttk.Label(toolbar, text="Chưa chọn folder")
        self.folder_label.pack(side=tk.LEFT, padx=10)

        main_pane = ttk.Panedwindow(parent, orient=tk.HORIZONTAL)
        main_pane.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # --- Trái: ảnh + điều hướng ---
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=3)

        self.canvas = tk.Canvas(left_frame, bg="#222222")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda e: self._redraw())

        nav_frame = ttk.Frame(left_frame, padding=6)
        nav_frame.pack(side=tk.BOTTOM, fill=tk.X)

        ttk.Button(nav_frame, text="<< Prev", command=self.prev_image).pack(side=tk.LEFT, padx=4)
        ttk.Button(nav_frame, text="Next >>", command=self.next_image).pack(side=tk.LEFT, padx=4)
        self.index_label = ttk.Label(nav_frame, text="0 / 0")
        self.index_label.pack(side=tk.LEFT, padx=15)

        ttk.Label(nav_frame, text="Đến ảnh số:").pack(side=tk.LEFT, padx=(15, 4))
        self.goto_index_var = tk.StringVar()
        goto_entry = ttk.Entry(nav_frame, textvariable=self.goto_index_var, width=6)
        goto_entry.pack(side=tk.LEFT)
        goto_entry.bind("<Return>", lambda e: self.goto_image())
        ttk.Button(nav_frame, text="Go", command=self.goto_image).pack(side=tk.LEFT, padx=4)

        self.filename_label = ttk.Label(nav_frame, text="")
        self.filename_label.pack(side=tk.LEFT, padx=15)

        # --- Phải: bảng thông số class ---
        right_frame = ttk.Frame(main_pane, padding=6)
        main_pane.add(right_frame, weight=2)

        ttk.Label(right_frame, text="Thông số theo từng class", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", pady=(0, 6)
        )

        header = ttk.Frame(right_frame)
        header.pack(fill=tk.X)
        headers = ["Hiện", "Class", "Conf", "W min", "W max", "H min", "H max", "OK", "NG", "Count"]
        widths = [4, 14, 6, 6, 6, 6, 6, 4, 4, 6]
        for h, w in zip(headers, widths):
            ttk.Label(header, text=h, width=w, font=("Segoe UI", 9, "bold")).pack(
                side=tk.LEFT, padx=1
            )

        table_container = ttk.Frame(right_frame)
        table_container.pack(fill=tk.BOTH, expand=True)

        self.table_canvas = tk.Canvas(table_container, highlightthickness=0)
        vscroll = ttk.Scrollbar(table_container, orient=tk.VERTICAL, command=self.table_canvas.yview)
        self.table_inner = ttk.Frame(self.table_canvas)

        self.table_inner.bind(
            "<Configure>",
            lambda e: self.table_canvas.configure(scrollregion=self.table_canvas.bbox("all")),
        )
        self.table_canvas.create_window((0, 0), window=self.table_inner, anchor="nw")
        self.table_canvas.configure(yscrollcommand=vscroll.set)

        self.table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.table_canvas.bind_all(
            "<MouseWheel>",
            lambda e: self.table_canvas.yview_scroll(int(-e.delta / 120), "units"),
        )

        bottom_btns = ttk.Frame(right_frame)
        bottom_btns.pack(fill=tk.X, pady=6)
        ttk.Button(bottom_btns, text="Áp dụng cho tất cả", command=self.open_apply_all_dialog).pack(
            side=tk.LEFT
        )

        judge_frame = ttk.LabelFrame(right_frame, text="Kết quả phán định OK/NG", padding=6)
        judge_frame.pack(fill=tk.BOTH, pady=(4, 0))

        self.overall_judge_label = ttk.Label(
            judge_frame, text="Chưa có rule nào", font=("Segoe UI", 14, "bold")
        )
        self.overall_judge_label.pack(anchor="w")

        self.judge_detail_text = tk.Text(judge_frame, height=8, wrap="word", state="disabled")
        self.judge_detail_text.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

    # ---- load model ----
    def load_model(self):
        if YOLO is None:
            messagebox.showerror("Thiếu thư viện", "Chưa cài ultralytics. Chạy: pip install ultralytics")
            return

        path = filedialog.askopenfilename(
            title="Chọn file .pt", filetypes=[("YOLO weights", "*.pt"), ("All files", "*.*")]
        )
        if not path:
            return

        self.status_var.set(f"Đang load model: {path} ...")
        self.root.update_idletasks()

        def worker():
            try:
                model = YOLO(path)
                names = model.names
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Lỗi load model", str(e)))
                self.root.after(0, lambda: self.status_var.set("Load model thất bại."))
                return

            def apply():
                self.model = model
                self.class_names = dict(names)
                self._build_class_table()
                self.model_label.config(
                    text=f"Model: {os.path.basename(path)} ({len(self.class_names)} class)",
                    foreground="green",
                )
                self.status_var.set("Load model thành công.")
                if self.current_index >= 0:
                    self._detect_current_image()

            self.root.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def _build_class_table(self):
        for w in self.table_inner.winfo_children():
            w.destroy()
        self.class_settings.clear()
        self.class_colors.clear()

        n = len(self.class_names)
        for i, (cls_id, name) in enumerate(sorted(self.class_names.items())):
            setting = ClassSetting()
            self.class_settings[cls_id] = setting
            self.class_colors[cls_id] = gen_color(cls_id, n)

            row = ttk.Frame(self.table_inner)
            row.pack(fill=tk.X, pady=1)

            color_hex = "#%02x%02x%02x" % self.class_colors[cls_id]
            tk.Label(row, text="  ", bg=color_hex, width=2).pack(side=tk.LEFT, padx=1)

            ttk.Checkbutton(row, variable=setting.enabled, command=self._redraw).pack(
                side=tk.LEFT, padx=1
            )
            ttk.Label(row, text=name, width=14).pack(side=tk.LEFT, padx=1)

            self._add_spin(row, setting.conf, 0, 1, 0.01, width=6)
            self._add_spin(row, setting.w_min, 0, 100000, 1, width=6)
            self._add_spin(row, setting.w_max, 0, 100000, 1, width=6)
            self._add_spin(row, setting.h_min, 0, 100000, 1, width=6)
            self._add_spin(row, setting.h_max, 0, 100000, 1, width=6)

            def make_ok_cb(s=setting):
                def cb():
                    if s.ok.get():
                        s.ng.set(False)
                    self._redraw()
                return cb

            def make_ng_cb(s=setting):
                def cb():
                    if s.ng.get():
                        s.ok.set(False)
                    self._redraw()
                return cb

            ttk.Checkbutton(row, variable=setting.ok, command=make_ok_cb()).pack(
                side=tk.LEFT, padx=(6, 1)
            )
            ttk.Checkbutton(row, variable=setting.ng, command=make_ng_cb()).pack(side=tk.LEFT, padx=1)
            self._add_spin(row, setting.count, 0, 100000, 1, width=6)

    def _add_spin(self, parent, var, lo, hi, step, width):
        sb = ttk.Spinbox(
            parent, from_=lo, to=hi, increment=step, textvariable=var, width=width, command=self._redraw
        )
        sb.pack(side=tk.LEFT, padx=1)
        sb.bind("<Return>", lambda e: self._redraw())
        sb.bind("<FocusOut>", lambda e: self._redraw())
        return sb

    def open_apply_all_dialog(self):
        if not self.class_settings:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Áp dụng cho tất cả class")
        dialog.geometry("260x220")

        conf = tk.DoubleVar(value=0.25)
        w_min = tk.DoubleVar(value=0)
        w_max = tk.DoubleVar(value=99999)
        h_min = tk.DoubleVar(value=0)
        h_max = tk.DoubleVar(value=99999)

        for label, var in [
            ("Conf", conf), ("W min", w_min), ("W max", w_max), ("H min", h_min), ("H max", h_max)
        ]:
            f = ttk.Frame(dialog, padding=4)
            f.pack(fill=tk.X)
            ttk.Label(f, text=label, width=8).pack(side=tk.LEFT)
            ttk.Entry(f, textvariable=var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        def apply_all():
            for s in self.class_settings.values():
                s.conf.set(conf.get())
                s.w_min.set(w_min.get())
                s.w_max.set(w_max.get())
                s.h_min.set(h_min.get())
                s.h_max.set(h_max.get())
            self._redraw()
            dialog.destroy()

        ttk.Button(dialog, text="Áp dụng", command=apply_all).pack(pady=10)

    # ---- load folder / điều hướng ảnh ----
    def load_folder(self):
        folder = filedialog.askdirectory(title="Chọn folder ảnh")
        if not folder:
            return
        paths = []
        for ext in IMAGE_EXTS:
            paths.extend(glob.glob(os.path.join(folder, f"*{ext}")))
            paths.extend(glob.glob(os.path.join(folder, f"*{ext.upper()}")))
        paths = sorted(set(paths))

        if not paths:
            messagebox.showwarning("Không có ảnh", "Folder này không có ảnh nào.")
            return

        self.image_paths = paths
        self.current_index = 0
        self.folder_label.config(text=f"{folder} ({len(paths)} ảnh)")
        self._load_current_image()

    def prev_image(self):
        if not self.image_paths:
            return
        if self.current_index > 0:
            self.current_index -= 1
            self._load_current_image()

    def next_image(self):
        if not self.image_paths:
            return
        if self.current_index < len(self.image_paths) - 1:
            self.current_index += 1
            self._load_current_image()

    def goto_image(self):
        if not self.image_paths:
            messagebox.showwarning("Chưa có ảnh", "Vui lòng load folder ảnh trước.")
            return

        raw = self.goto_index_var.get().strip()
        try:
            n = int(raw)
        except ValueError:
            messagebox.showerror("Lỗi", "Vui lòng nhập số thứ tự ảnh (số nguyên).")
            return

        total = len(self.image_paths)
        if n < 1 or n > total:
            messagebox.showerror("Lỗi", f"Số thứ tự ảnh phải trong khoảng 1 - {total}.")
            return

        self.current_index = n - 1
        self._load_current_image()

    def _load_current_image(self):
        path = self.image_paths[self.current_index]
        try:
            self.current_pil_image = Image.open(path).convert("RGB")
        except Exception as e:
            messagebox.showerror("Lỗi mở ảnh", str(e))
            return

        self.index_label.config(text=f"{self.current_index + 1} / {len(self.image_paths)}")
        self.filename_label.config(text=os.path.basename(path))
        self._detect_current_image()

    # ---- detect ----
    def _detect_current_image(self):
        if self.current_pil_image is None:
            return

        if self.model is None:
            self.current_detections = []
            self._redraw()
            self.status_var.set("Chưa load model - chỉ hiển thị ảnh gốc.")
            return

        self.status_var.set("Đang detect...")
        self.root.update_idletasks()

        def worker():
            try:
                results = self.model.predict(source=self.current_pil_image, conf=BASE_INFER_CONF, verbose=False)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Lỗi detect", str(e)))
                return

            dets = []
            if results:
                r = results[0]
                if r.boxes is not None:
                    for box in r.boxes:
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        conf = float(box.conf[0].item())
                        cls_id = int(box.cls[0].item())
                        dets.append({
                            "cls_id": cls_id,
                            "cls_name": self.class_names.get(cls_id, str(cls_id)),
                            "conf": conf,
                            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                            "w": x2 - x1, "h": y2 - y1,
                        })

            def apply():
                self.current_detections = dets
                self._redraw()
                self.status_var.set(f"Detect xong: {len(dets)} box (trước khi lọc).")

            self.root.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def _filter_detections(self):
        visible = []
        for d in self.current_detections:
            setting = self.class_settings.get(d["cls_id"])
            if setting is None:
                continue
            if not setting.enabled.get():
                continue
            if d["conf"] < setting.conf.get():
                continue
            if not (setting.w_min.get() < d["w"] < setting.w_max.get()):
                continue
            if not (setting.h_min.get() < d["h"] < setting.h_max.get()):
                continue
            visible.append(d)
        return visible

    def _evaluate_judgment(self, visible_detections):
        counts = {}
        for d in visible_detections:
            counts[d["cls_id"]] = counts.get(d["cls_id"], 0) + 1

        details = []
        for cls_id, setting in self.class_settings.items():
            cls_name = self.class_names.get(cls_id, str(cls_id))
            detected_count = counts.get(cls_id, 0)

            if setting.ok.get():
                required = setting.count.get()
                result = "OK" if detected_count == required else "NG"
                details.append({
                    "class": cls_name, "rule": f"OK nếu count == {required}",
                    "detected_count": detected_count, "result": result,
                })
            elif setting.ng.get():
                result = "NG" if detected_count > 0 else "OK"
                details.append({
                    "class": cls_name, "rule": "NG nếu xuất hiện",
                    "detected_count": detected_count, "result": result,
                })

        if not details:
            return None, details

        overall = "OK" if all(d["result"] == "OK" for d in details) else "NG"
        return overall, details

    def _update_judge_panel(self, overall, details):
        if overall is None:
            self.overall_judge_label.config(text="Chưa có rule nào", foreground="black")
        elif overall == "OK":
            self.overall_judge_label.config(text="TỔNG: OK", foreground="green")
        else:
            self.overall_judge_label.config(text="TỔNG: NG", foreground="red")

        self.judge_detail_text.config(state="normal")
        self.judge_detail_text.delete("1.0", tk.END)
        for d in details:
            line = f"[{d['result']}] {d['class']}  -  {d['rule']}  (detect: {d['detected_count']})\n"
            self.judge_detail_text.insert(tk.END, line)
        self.judge_detail_text.config(state="disabled")

    def _redraw(self):
        if self.current_pil_image is None:
            self.canvas.delete("all")
            return

        img = self.current_pil_image.copy()
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except Exception:
            font = ImageFont.load_default()

        visible = self._filter_detections()

        for d in visible:
            color = self.class_colors.get(d["cls_id"], (255, 0, 0))
            x1, y1, x2, y2 = d["x1"], d["y1"], d["x2"], d["y2"]
            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
            label = f"{d['cls_name']} {d['conf']:.2f}"
            tb = draw.textbbox((0, 0), label, font=font)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
            draw.rectangle([x1, max(0, y1 - th - 4), x1 + tw + 6, y1], fill=color)
            draw.text((x1 + 3, max(0, y1 - th - 4)), label, fill=(0, 0, 0), font=font)

        overall, details = self._evaluate_judgment(visible)
        self._update_judge_panel(overall, details)

        if overall is not None:
            try:
                big_font = ImageFont.truetype("arial.ttf", 48)
            except Exception:
                big_font = font
            text = overall
            bg_color = (0, 170, 0) if overall == "OK" else (200, 0, 0)
            tb = draw.textbbox((0, 0), text, font=big_font)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
            pad = 10
            draw.rectangle([10, 10, 10 + tw + pad * 2, 10 + th + pad * 2], fill=bg_color)
            draw.text((10 + pad, 10 + pad), text, fill=(255, 255, 255), font=big_font)

        canvas_w = max(self.canvas.winfo_width(), 10)
        canvas_h = max(self.canvas.winfo_height(), 10)
        img_w, img_h = img.size
        scale = min(canvas_w / img_w, canvas_h / img_h)
        new_size = (max(1, int(img_w * scale)), max(1, int(img_h * scale)))
        img_resized = img.resize(new_size, Image.LANCZOS)

        self.tk_image = ImageTk.PhotoImage(img_resized)
        self.canvas.delete("all")
        self.canvas.create_image(canvas_w // 2, canvas_h // 2, image=self.tk_image, anchor="center")

    # ====================================================================== #
    # TAB 2: TRAINING
    # ====================================================================== #
    def _build_train_tab(self, parent):
        pad = dict(padx=6, pady=4)

        form = ttk.Frame(parent, padding=10)
        form.pack(side=tk.TOP, fill=tk.X)

        # dataset dir
        self.train_dataset_var = tk.StringVar()
        r = 0
        ttk.Label(form, text="Folder dataset (chứa images/ + labels/):").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(form, textvariable=self.train_dataset_var, width=60).grid(row=r, column=1, **pad)
        ttk.Button(form, text="Chọn...", command=self._browse_train_dataset).grid(row=r, column=2, **pad)

        # Chế độ khởi tạo model
        r += 1
        self.train_mode_var = tk.StringVar(value="Config (.yaml)")
        ttk.Label(form, text="Chế độ khởi tạo model:").grid(row=r, column=0, sticky="w", **pad)
        self.train_mode_combobox = ttk.Combobox(
            form, textvariable=self.train_mode_var, values=["Config (.yaml)", "Pretrained (.pt)"],
            width=20, state="readonly"
        )
        self.train_mode_combobox.grid(row=r, column=1, sticky="w", **pad)
        self.train_mode_combobox.bind("<<ComboboxSelected>>", self._on_train_mode_change)

        # config kiến trúc model (yaml) - train from scratch
        r += 1
        self.train_config_yaml_var = tk.StringVar(value="yolo11.yaml")
        self.yaml_label = ttk.Label(form, text="Config kiến trúc (.yaml):")
        self.yaml_label.grid(row=r, column=0, sticky="w", **pad)
        self.yaml_entry = ttk.Entry(form, textvariable=self.train_config_yaml_var, width=60)
        self.yaml_entry.grid(row=r, column=1, **pad)
        self.yaml_btn = ttk.Button(form, text="Chọn...", command=self._browse_config_yaml)
        self.yaml_btn.grid(row=r, column=2, **pad)

        # pretrained weights (pt) - fine-tune
        r += 1
        self.train_base_model_var = tk.StringVar(value="yolo11s.pt")
        self.pt_label = ttk.Label(form, text="Model weights (.pt):")
        self.pt_label.grid(row=r, column=0, sticky="w", **pad)
        self.pt_entry = ttk.Entry(form, textvariable=self.train_base_model_var, width=60)
        self.pt_entry.grid(row=r, column=1, **pad)
        self.pt_btn = ttk.Button(form, text="Chọn...", command=self._browse_base_model)
        self.pt_btn.grid(row=r, column=2, **pad)

        # model scale
        r += 1
        self.train_scale_var = tk.StringVar(value="n")
        self.scale_label = ttk.Label(form, text="Model scale (n/s/m/l/x):")
        self.scale_label.grid(row=r, column=0, sticky="w", **pad)
        self.scale_combo = ttk.Combobox(
            form, textvariable=self.train_scale_var, values=["n", "s", "m", "l", "x"],
            width=6, state="readonly",
        )
        self.scale_combo.grid(row=r, column=1, sticky="w", **pad)
        self.scale_info_label = ttk.Label(
            form,
            text="(chỉ dùng cho .yaml - file .yaml gốc có nhiều scale, mặc định n = nhỏ/nhanh nhất)",
            foreground="gray",
        )
        self.scale_info_label.grid(row=r, column=2, sticky="w", **pad)

        # imgsz / batch / epochs / train ratio / device / workers / patience / seed
        r += 1
        self.train_imgsz_var = tk.IntVar(value=960)
        self.train_batch_var = tk.IntVar(value=16)
        self.train_epochs_var = tk.IntVar(value=500)
        self.train_ratio_var = tk.DoubleVar(value=0.8)

        # Tự động phát hiện GPU khả dụng (mặc định chọn GPU đơn 0 trên Windows để tránh overhead DDP)
        default_device = "0"
        try:
            import torch
            if torch.cuda.is_available():
                default_device = "0"
            else:
                default_device = "cpu"
        except Exception:
            pass

        self.train_device_var = tk.StringVar(value=default_device)
        self.train_workers_var = tk.IntVar(value=2)
        self.train_patience_var = tk.IntVar(value=45)
        self.train_seed_var = tk.IntVar(value=42)

        param_frame = ttk.LabelFrame(form, text="Thông số cơ bản", padding=6)
        param_frame.grid(row=r, column=0, columnspan=3, sticky="we", **pad)

        ttk.Label(param_frame, text="Image size:").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(param_frame, textvariable=self.train_imgsz_var, width=8).grid(row=0, column=1, sticky="w", padx=2, pady=2)

        ttk.Label(param_frame, text="Batch:").grid(row=0, column=2, sticky="w", padx=10, pady=2)
        ttk.Entry(param_frame, textvariable=self.train_batch_var, width=8).grid(row=0, column=3, sticky="w", padx=2, pady=2)

        ttk.Label(param_frame, text="Epochs:").grid(row=0, column=4, sticky="w", padx=10, pady=2)
        ttk.Entry(param_frame, textvariable=self.train_epochs_var, width=8).grid(row=0, column=5, sticky="w", padx=2, pady=2)

        ttk.Label(param_frame, text="Tỷ lệ train (0-1):").grid(row=0, column=6, sticky="w", padx=10, pady=2)
        ttk.Entry(param_frame, textvariable=self.train_ratio_var, width=8).grid(row=0, column=7, sticky="w", padx=2, pady=2)

        ttk.Label(param_frame, text="Device GPU (vd: 0,1 hoặc 0 hoặc cpu):").grid(row=1, column=0, columnspan=2, sticky="w", padx=2, pady=2)
        ttk.Entry(param_frame, textvariable=self.train_device_var, width=12).grid(row=1, column=2, sticky="w", padx=2, pady=2)

        ttk.Label(param_frame, text="Workers:").grid(row=1, column=3, sticky="w", padx=10, pady=2)
        ttk.Entry(param_frame, textvariable=self.train_workers_var, width=8).grid(row=1, column=4, sticky="w", padx=2, pady=2)

        ttk.Label(param_frame, text="Patience:").grid(row=1, column=5, sticky="w", padx=10, pady=2)
        ttk.Entry(param_frame, textvariable=self.train_patience_var, width=8).grid(row=1, column=6, sticky="w", padx=2, pady=2)

        ttk.Label(param_frame, text="Seed:").grid(row=1, column=7, sticky="w", padx=10, pady=2)
        ttk.Entry(param_frame, textvariable=self.train_seed_var, width=8).grid(row=1, column=8, sticky="w", padx=2, pady=2)

        # Augmentation hyperparameters
        r += 1
        self.train_hsv_h_var = tk.DoubleVar(value=0.01)
        self.train_hsv_s_var = tk.DoubleVar(value=0.1)
        self.train_hsv_v_var = tk.DoubleVar(value=0.1)
        self.train_scale_aug_var = tk.DoubleVar(value=0.1)
        self.train_fliplr_var = tk.DoubleVar(value=0.1)
        self.train_mosaic_var = tk.DoubleVar(value=0.0)
        self.train_erasing_var = tk.DoubleVar(value=0.0)

        aug_frame = ttk.LabelFrame(form, text="Thông số Augmentation (Tăng cường dữ liệu)", padding=6)
        aug_frame.grid(row=r, column=0, columnspan=3, sticky="we", **pad)

        ttk.Label(aug_frame, text="hsv_h:").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(aug_frame, textvariable=self.train_hsv_h_var, width=8).grid(row=0, column=1, sticky="w", padx=2, pady=2)

        ttk.Label(aug_frame, text="hsv_s:").grid(row=0, column=2, sticky="w", padx=10, pady=2)
        ttk.Entry(aug_frame, textvariable=self.train_hsv_s_var, width=8).grid(row=0, column=3, sticky="w", padx=2, pady=2)

        ttk.Label(aug_frame, text="hsv_v:").grid(row=0, column=4, sticky="w", padx=10, pady=2)
        ttk.Entry(aug_frame, textvariable=self.train_hsv_v_var, width=8).grid(row=0, column=5, sticky="w", padx=2, pady=2)

        ttk.Label(aug_frame, text="scale:").grid(row=0, column=6, sticky="w", padx=10, pady=2)
        ttk.Entry(aug_frame, textvariable=self.train_scale_aug_var, width=8).grid(row=0, column=7, sticky="w", padx=2, pady=2)

        ttk.Label(aug_frame, text="fliplr:").grid(row=0, column=8, sticky="w", padx=10, pady=2)
        ttk.Entry(aug_frame, textvariable=self.train_fliplr_var, width=8).grid(row=0, column=9, sticky="w", padx=2, pady=2)

        ttk.Label(aug_frame, text="mosaic:").grid(row=1, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(aug_frame, textvariable=self.train_mosaic_var, width=8).grid(row=1, column=1, sticky="w", padx=2, pady=2)

        ttk.Label(aug_frame, text="erasing:").grid(row=1, column=2, sticky="w", padx=10, pady=2)
        ttk.Entry(aug_frame, textvariable=self.train_erasing_var, width=8).grid(row=1, column=3, sticky="w", padx=2, pady=2)

        # save dir + name
        r += 1
        self.train_savedir_var = tk.StringVar()
        ttk.Label(form, text="Nơi lưu file .pt sau khi train:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(form, textvariable=self.train_savedir_var, width=60).grid(row=r, column=1, **pad)
        ttk.Button(form, text="Chọn...", command=self._browse_train_savedir).grid(row=r, column=2, **pad)

        r += 1
        self.train_savename_var = tk.StringVar(value="my_model")
        ttk.Label(form, text="Tên file (không cần .pt):").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(form, textvariable=self.train_savename_var, width=30).grid(row=r, column=1, sticky="w", **pad)

        # start button
        r += 1
        btn_frame = ttk.Frame(form)
        btn_frame.grid(row=r, column=0, columnspan=3, sticky="w", pady=10)
        self.train_start_btn = ttk.Button(btn_frame, text="Bắt đầu chia dataset + Training", command=self.start_training)
        self.train_start_btn.pack(side=tk.LEFT)
        self.train_status_label = ttk.Label(btn_frame, text="")
        self.train_status_label.pack(side=tk.LEFT, padx=15)

        # log
        log_frame = ttk.LabelFrame(parent, text="Log training", padding=6)
        log_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.train_log_text = tk.Text(log_frame, state="disabled", wrap="word")
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.train_log_text.yview)
        self.train_log_text.configure(yscrollcommand=log_scroll.set)
        self.train_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._on_train_mode_change()

    def _on_train_mode_change(self, event=None):
        mode = self.train_mode_var.get()
        if "yaml" in mode.lower():
            self.yaml_label.config(state="normal")
            self.yaml_entry.config(state="normal")
            self.yaml_btn.config(state="normal")
            self.scale_label.config(state="normal")
            self.scale_combo.config(state="readonly")
            self.scale_info_label.config(state="normal")
            
            self.pt_label.config(state="disabled")
            self.pt_entry.config(state="disabled")
            self.pt_btn.config(state="disabled")
        else:
            self.yaml_label.config(state="disabled")
            self.yaml_entry.config(state="disabled")
            self.yaml_btn.config(state="disabled")
            self.scale_label.config(state="disabled")
            self.scale_combo.config(state="disabled")
            self.scale_info_label.config(state="disabled")
            
            self.pt_label.config(state="normal")
            self.pt_entry.config(state="normal")
            self.pt_btn.config(state="normal")

    def _browse_train_dataset(self):
        d = filedialog.askdirectory(title="Chọn folder dataset")
        if d:
            self.train_dataset_var.set(d)

    def _browse_config_yaml(self):
        f = filedialog.askopenfilename(
            title="Chọn config kiến trúc model (.yaml)", filetypes=[("YAML config", "*.yaml *.yml")]
        )
        if f:
            self.train_config_yaml_var.set(f)

    def _browse_base_model(self):
        f = filedialog.askopenfilename(
            title="Chọn model weights (.pt)", filetypes=[("YOLO weights", "*.pt")]
        )
        if f:
            self.train_base_model_var.set(f)

    def _browse_train_savedir(self):
        d = filedialog.askdirectory(title="Chọn nơi lưu model sau khi train")
        if d:
            self.train_savedir_var.set(d)

    def _train_log(self, msg):
        def append():
            self.train_log_text.config(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self.train_log_text.insert(tk.END, f"[{ts}] {msg}\n")
            self.train_log_text.see(tk.END)
            self.train_log_text.config(state="disabled")

        self.root.after(0, append)

    def start_training(self):
        if YOLO is None:
            messagebox.showerror("Thiếu thư viện", "Chưa cài ultralytics. Chạy: pip install ultralytics")
            return

        dataset_dir = self.train_dataset_var.get().strip()
        if not dataset_dir or not os.path.isdir(dataset_dir):
            messagebox.showerror("Lỗi", "Vui lòng chọn folder dataset hợp lệ.")
            return

        save_dir = self.train_savedir_var.get().strip()
        if not save_dir:
            messagebox.showerror("Lỗi", "Vui lòng chọn nơi lưu model sau khi train.")
            return

        save_name = self.train_savename_var.get().strip() or "my_model"

        try:
            imgsz = int(self.train_imgsz_var.get())
            batch = int(self.train_batch_var.get())
            epochs = int(self.train_epochs_var.get())
            ratio = float(self.train_ratio_var.get())
            assert 0 < ratio < 1

            # device parse
            device_str = self.train_device_var.get().strip()
            # If comma in device_str, parse it as list of ints, e.g. [0, 1]
            if ',' in device_str:
                device = [int(x.strip()) for x in device_str.split(',') if x.strip().isdigit()]
            elif device_str.isdigit():
                device = int(device_str)
            else:
                device = device_str  # e.g., 'cpu'

            hsv_h = float(self.train_hsv_h_var.get())
            hsv_s = float(self.train_hsv_s_var.get())
            hsv_v = float(self.train_hsv_v_var.get())
            scale_aug = float(self.train_scale_aug_var.get())
            fliplr = float(self.train_fliplr_var.get())
            mosaic = float(self.train_mosaic_var.get())
            erasing = float(self.train_erasing_var.get())
            workers = int(self.train_workers_var.get())
            patience = int(self.train_patience_var.get())
            seed = int(self.train_seed_var.get())

        except Exception as e:
            messagebox.showerror("Lỗi", f"Thông số nhập vào không hợp lệ: {e}")
            return

        mode = self.train_mode_var.get()
        config_yaml = self.train_config_yaml_var.get().strip() or "yolo11.yaml"
        scale = self.train_scale_var.get().strip() or "n"
        base_model = self.train_base_model_var.get().strip() or "yolo11s.pt"

        self.train_start_btn.config(state="disabled")
        self.train_status_label.config(text="Đang xử lý...")
        self.train_log_text.config(state="normal")
        self.train_log_text.delete("1.0", tk.END)
        self.train_log_text.config(state="disabled")

        threading.Thread(
            target=self._train_worker,
            args=(
                mode, dataset_dir, config_yaml, scale, base_model, imgsz, batch, epochs, ratio,
                device, hsv_h, hsv_s, hsv_v, scale_aug, fliplr, mosaic, erasing, workers, patience, seed,
                save_dir, save_name
            ),
            daemon=True,
        ).start()

    def _train_worker(self, mode, dataset_dir, config_yaml, scale, base_model, imgsz, batch, epochs, ratio,
                      device, hsv_h, hsv_s, hsv_v, scale_aug, fliplr, mosaic, erasing, workers, patience, seed,
                      save_dir, save_name):
        try:
            self._train_log("Bắt đầu chia dataset train/valid ...")
            split_root, names = self._split_dataset(dataset_dir, ratio)
            self._train_log(f"Đã chia xong dataset tại: {split_root}")
            self._train_log(f"Danh sách class ({len(names)}): {names}")

            data_yaml_path = self._write_data_yaml(split_root, names)
            self._train_log(f"Đã tạo data.yaml: {data_yaml_path}")

            if "yaml" in mode.lower():
                # Bắt buộc build model từ config kiến trúc (.yaml) - train from scratch,
                # KHÔNG load weight .pt pretrained. Dùng config dạng detect (box thường),
                # không phải seg/obb/pose/cls.
                #
                # File config gốc (kiểu yolov8.yaml) thường KHÔNG có sẵn "nc" (số class)
                # và có nhiều "scale" (n/s/m/l/x) nhưng không chỉ định scale nào -> nếu
                # build thẳng sẽ lỗi "unsupported operand type(s) for +: 'NoneType' and 'int'"
                # vì nc/scale bị None. Nên phải tự chèn nc + scale vào 1 bản copy trước khi build.
                resolved_yaml = self._prepare_model_yaml(config_yaml, len(names), scale, split_root)
                self._train_log(
                    f"Build model từ config kiến trúc: {resolved_yaml} "
                    f"(train from scratch, nc={len(names)}, scale={scale})"
                )
                model = YOLO(resolved_yaml)
            else:
                self._train_log(f"Load base weights model: {base_model}")
                model = YOLO(base_model)

            project_dir = save_dir
            run_name = f"{save_name}_run"

            self._train_log(
                f"Bắt đầu training: imgsz={imgsz}, batch={batch}, epochs={epochs} ..."
            )

            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout = TextRedirector(self._train_log)
            sys.stderr = TextRedirector(self._train_log)
            try:
                model.train(
                    data=data_yaml_path,
                    imgsz=imgsz,
                    batch=batch,
                    epochs=epochs,
                    project=project_dir,
                    name=run_name,
                    exist_ok=True,
                    device=device,
                    hsv_h=hsv_h,
                    hsv_s=hsv_s,
                    hsv_v=hsv_v,
                    scale=scale_aug,
                    fliplr=fliplr,
                    mosaic=mosaic,
                    erasing=erasing,
                    workers=workers,
                    patience=patience,
                    seed=seed,
                )
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

            best_pt = os.path.join(project_dir, run_name, "weights", "best.pt")
            final_name = save_name if save_name.endswith(".pt") else save_name + ".pt"
            final_path = os.path.join(save_dir, final_name)

            if os.path.isfile(best_pt):
                shutil.copy2(best_pt, final_path)
                self._train_log(f"Training xong! Đã lưu model tốt nhất tại: {final_path}")
            else:
                self._train_log(
                    f"Training xong nhưng không tìm thấy best.pt tại {best_pt}. "
                    f"Kiểm tra thư mục {os.path.join(project_dir, run_name, 'weights')}."
                )

            self.root.after(0, lambda: self.train_status_label.config(text="Hoàn tất!"))

        except Exception as e:
            self._train_log(f"LỖI: {e}")
            self.root.after(0, lambda: self.train_status_label.config(text="Lỗi - xem log."))
            self.root.after(0, lambda: messagebox.showerror("Lỗi training", str(e)))
        finally:
            self.root.after(0, lambda: self.train_start_btn.config(state="normal"))

    def _split_dataset(self, dataset_dir, ratio):
        """
        Hỗ trợ 2 kiểu cấu trúc dataset đầu vào:
          A) dataset_dir/images/*.jpg  + dataset_dir/labels/*.txt
          B) dataset_dir/*.jpg         + dataset_dir/*.txt  (ảnh và label cùng 1 folder)

        Tự tạo folder split tại: dataset_dir/../<ten_dataset>_split/
            train/images, train/labels, valid/images, valid/labels
        Trả về (split_root, class_names_list)
        """
        images_sub = os.path.join(dataset_dir, "images")
        labels_sub = os.path.join(dataset_dir, "labels")

        if os.path.isdir(images_sub):
            img_dir = images_sub
            lbl_dir = labels_sub if os.path.isdir(labels_sub) else images_sub
        else:
            img_dir = dataset_dir
            lbl_dir = dataset_dir

        image_files = []
        for ext in IMAGE_EXTS:
            image_files.extend(glob.glob(os.path.join(img_dir, f"*{ext}")))
            image_files.extend(glob.glob(os.path.join(img_dir, f"*{ext.upper()}")))
        image_files = sorted(set(image_files))

        if not image_files:
            raise RuntimeError(f"Không tìm thấy ảnh nào trong {img_dir}")

        # đọc classes.txt nếu có (chuẩn labelImg / labelme export YOLO)
        names = None
        for candidate in [
            os.path.join(dataset_dir, "classes.txt"),
            os.path.join(lbl_dir, "classes.txt"),
            os.path.join(img_dir, "classes.txt"),
        ]:
            if os.path.isfile(candidate):
                with open(candidate, "r", encoding="utf-8") as f:
                    names = [line.strip() for line in f if line.strip()]
                break

        if names is None:
            # tự dò class id lớn nhất từ các file label
            max_id = -1
            for img_path in image_files:
                base = os.path.splitext(os.path.basename(img_path))[0]
                lbl_path = os.path.join(lbl_dir, base + ".txt")
                if os.path.isfile(lbl_path):
                    with open(lbl_path, "r", encoding="utf-8") as f:
                        for line in f:
                            parts = line.strip().split()
                            if parts:
                                max_id = max(max_id, int(float(parts[0])))
            if max_id < 0:
                raise RuntimeError("Không tìm thấy file label .txt nào và cũng không có classes.txt.")
            names = [f"class{i}" for i in range(max_id + 1)]

        random.shuffle(image_files)
        split_idx = int(len(image_files) * ratio)
        train_files = image_files[:split_idx]
        valid_files = image_files[split_idx:]
        if not valid_files:  # dataset quá nhỏ, đảm bảo có ít nhất 1 ảnh valid
            valid_files = train_files[-1:]
            train_files = train_files[:-1]

        dataset_name = os.path.basename(os.path.normpath(dataset_dir))
        split_root = os.path.join(os.path.dirname(os.path.normpath(dataset_dir)), f"{dataset_name}_split")

        for sub in ["train/images", "train/labels", "valid/images", "valid/labels"]:
            os.makedirs(os.path.join(split_root, sub), exist_ok=True)

        def copy_set(files, subset):
            for img_path in files:
                base = os.path.splitext(os.path.basename(img_path))[0]
                ext = os.path.splitext(img_path)[1]
                lbl_path = os.path.join(lbl_dir, base + ".txt")

                shutil.copy2(img_path, os.path.join(split_root, subset, "images", base + ext))
                if os.path.isfile(lbl_path):
                    shutil.copy2(lbl_path, os.path.join(split_root, subset, "labels", base + ".txt"))
                else:
                    # không có label -> tạo file rỗng (ảnh background, không có object)
                    open(os.path.join(split_root, subset, "labels", base + ".txt"), "w").close()

        copy_set(train_files, "train")
        copy_set(valid_files, "valid")

        self._train_log(f"Train: {len(train_files)} ảnh - Valid: {len(valid_files)} ảnh")
        return split_root, names

    def _write_data_yaml(self, split_root, names):
        yaml_path = os.path.join(split_root, "data.yaml")
        names_lines = "\n".join(f"  {i}: {name}" for i, name in enumerate(names))
        content = (
            f"path: {split_root}\n"
            f"train: train/images\n"
            f"val: valid/images\n"
            f"nc: {len(names)}\n"
            f"names:\n{names_lines}\n"
        )
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(content)
        return yaml_path

    def _prepare_model_yaml(self, config_yaml_path, nc, scale, split_root):
        """
        Đọc file config kiến trúc (kiểu yolov8.yaml), chèn/ghi đè "nc" (số class)
        và "scale" (n/s/m/l/x) rồi ghi ra 1 bản copy tạm để build model.

        Bắt buộc phải làm bước này vì file config gốc dạng yolov8.yaml thường:
          - không có sẵn "nc" (số lớp) -> nc=None khi build model
          - có nhiều scale (n/s/m/l/x) nhưng không có "scale" -> scale=None
        Cả 2 trường hợp trên đều khiến ultralytics build model lỗi dạng
        "unsupported operand type(s) for +: 'NoneType' and 'int'".
        """
        if not os.path.isfile(config_yaml_path):
            raise FileNotFoundError(f"Không tìm thấy file config kiến trúc: {config_yaml_path}")

        out_path = os.path.join(split_root, "model_arch.yaml")

        if yaml is not None:
            with open(config_yaml_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            if not isinstance(cfg, dict):
                raise ValueError(f"File config kiến trúc không hợp lệ: {config_yaml_path}")

            cfg["nc"] = nc
            if cfg.get("scales"):
                cfg["scale"] = scale

            with open(out_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
        else:
            # Không có PyYAML: fallback ghép thủ công (ít an toàn hơn nhưng vẫn chạy được)
            with open(config_yaml_path, "r", encoding="utf-8") as f:
                original_content = f.read()
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(f"nc: {nc}\n")
                f.write(f"scale: {scale}\n")
                f.write(original_content)

        return out_path

    # ====================================================================== #
    # TAB 3: AUTO LABEL
    # ====================================================================== #
    def _build_autolabel_tab(self, parent):
        pad = dict(padx=6, pady=4)

        # ---- Panedwindow: trái = điều khiển + log, phải = bảng thông số class ----
        main_pane = ttk.Panedwindow(parent, orient=tk.HORIZONTAL)
        main_pane.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=3)

        form = ttk.Frame(left_frame, padding=10)
        form.pack(side=tk.TOP, fill=tk.X)

        r = 0
        self.al_model_var = tk.StringVar(value="Chưa load model")
        ttk.Label(form, text="Model (.pt):").grid(row=r, column=0, sticky="w", **pad)
        ttk.Label(form, textvariable=self.al_model_var, foreground="red").grid(row=r, column=1, sticky="w", **pad)
        ttk.Button(form, text="Load model...", command=self._al_load_model).grid(row=r, column=2, **pad)

        r += 1
        self.al_folder_var = tk.StringVar(value="Chưa chọn folder")
        ttk.Label(form, text="Folder ảnh cần auto label:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Label(form, textvariable=self.al_folder_var).grid(row=r, column=1, sticky="w", **pad)
        ttk.Button(form, text="Chọn folder...", command=self._al_load_folder).grid(row=r, column=2, **pad)

        r += 1
        self.al_base_conf_var = tk.DoubleVar(value=0.01)
        ttk.Label(form, text="Conf nền khi chạy model (nên để thấp):").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(form, textvariable=self.al_base_conf_var, width=10).grid(row=r, column=1, sticky="w", **pad)
        ttk.Label(
            form,
            text="(box giữ lại cuối cùng do bảng thông số bên phải quyết định)",
            foreground="gray",
        ).grid(row=r, column=2, sticky="w", **pad)

        r += 1
        btn_frame = ttk.Frame(form)
        btn_frame.grid(row=r, column=0, columnspan=3, sticky="w", pady=10)
        self.al_start_btn = ttk.Button(btn_frame, text="Bắt đầu Auto Label", command=self.start_autolabel)
        self.al_start_btn.pack(side=tk.LEFT)

        self.al_progress = ttk.Progressbar(left_frame, mode="determinate")
        self.al_progress.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 6))

        log_frame = ttk.LabelFrame(left_frame, text="Log auto label", padding=6)
        log_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.al_log_text = tk.Text(log_frame, state="disabled", wrap="word")
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.al_log_text.yview)
        self.al_log_text.configure(yscrollcommand=log_scroll.set)
        self.al_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Phải: bảng thông số điều chỉnh theo từng class (giống tab Detect) ----
        right_frame = ttk.Frame(main_pane, padding=6)
        main_pane.add(right_frame, weight=2)

        ttk.Label(
            right_frame, text="Thông số tạo nhãn theo từng class", font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 6))
        ttk.Label(
            right_frame,
            text="Chỉ box thỏa Conf/W/H dưới đây mới được ghi vào file nhãn .txt.",
            foreground="gray",
            wraplength=320,
            justify="left",
        ).pack(anchor="w", pady=(0, 6))

        al_header = ttk.Frame(right_frame)
        al_header.pack(fill=tk.X)
        al_headers = ["Tạo nhãn", "Class", "Conf", "W min", "W max", "H min", "H max"]
        al_widths = [7, 14, 6, 6, 6, 6, 6]
        for h, w in zip(al_headers, al_widths):
            ttk.Label(al_header, text=h, width=w, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=1)

        al_table_container = ttk.Frame(right_frame)
        al_table_container.pack(fill=tk.BOTH, expand=True)

        self.al_table_canvas = tk.Canvas(al_table_container, highlightthickness=0)
        al_vscroll = ttk.Scrollbar(al_table_container, orient=tk.VERTICAL, command=self.al_table_canvas.yview)
        self.al_table_inner = ttk.Frame(self.al_table_canvas)

        self.al_table_inner.bind(
            "<Configure>",
            lambda e: self.al_table_canvas.configure(scrollregion=self.al_table_canvas.bbox("all")),
        )
        self.al_table_canvas.create_window((0, 0), window=self.al_table_inner, anchor="nw")
        self.al_table_canvas.configure(yscrollcommand=al_vscroll.set)

        self.al_table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        al_vscroll.pack(side=tk.RIGHT, fill=tk.Y)

        al_bottom_btns = ttk.Frame(right_frame)
        al_bottom_btns.pack(fill=tk.X, pady=6)
        ttk.Button(al_bottom_btns, text="Áp dụng cho tất cả", command=self._al_open_apply_all_dialog).pack(
            side=tk.LEFT
        )

    def _al_log(self, msg):
        def append():
            self.al_log_text.config(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self.al_log_text.insert(tk.END, f"[{ts}] {msg}\n")
            self.al_log_text.see(tk.END)
            self.al_log_text.config(state="disabled")

        self.root.after(0, append)

    def _al_load_model(self):
        if YOLO is None:
            messagebox.showerror("Thiếu thư viện", "Chưa cài ultralytics. Chạy: pip install ultralytics")
            return
        path = filedialog.askopenfilename(title="Chọn file .pt", filetypes=[("YOLO weights", "*.pt")])
        if not path:
            return

        self.al_model_var.set(f"Đang load {os.path.basename(path)} ...")

        def worker():
            try:
                model = YOLO(path)
                names = model.names
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Lỗi load model", str(e)))
                return

            def apply():
                self.al_model = model
                self.al_model_path = path
                self.al_class_names = dict(names)
                self._al_build_class_table()
                self.al_model_var.set(f"{os.path.basename(path)} ({len(names)} class)")
            self.root.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def _al_build_class_table(self):
        """Dựng bảng thông số Conf/W/H theo từng class cho tab Auto Label."""
        for w in self.al_table_inner.winfo_children():
            w.destroy()
        self.al_class_settings.clear()
        self.al_class_colors.clear()

        n = len(self.al_class_names)
        for cls_id, name in sorted(self.al_class_names.items()):
            setting = ClassSetting()
            self.al_class_settings[cls_id] = setting
            self.al_class_colors[cls_id] = gen_color(cls_id, n)

            row = ttk.Frame(self.al_table_inner)
            row.pack(fill=tk.X, pady=1)

            color_hex = "#%02x%02x%02x" % self.al_class_colors[cls_id]
            tk.Label(row, text="  ", bg=color_hex, width=2).pack(side=tk.LEFT, padx=1)

            ttk.Checkbutton(row, variable=setting.enabled).pack(side=tk.LEFT, padx=(6, 1))
            ttk.Label(row, text=name, width=14).pack(side=tk.LEFT, padx=1)

            self._al_add_spin(row, setting.conf, 0, 1, 0.01, width=6)
            self._al_add_spin(row, setting.w_min, 0, 100000, 1, width=6)
            self._al_add_spin(row, setting.w_max, 0, 100000, 1, width=6)
            self._al_add_spin(row, setting.h_min, 0, 100000, 1, width=6)
            self._al_add_spin(row, setting.h_max, 0, 100000, 1, width=6)

    def _al_add_spin(self, parent, var, lo, hi, step, width):
        sb = ttk.Spinbox(parent, from_=lo, to=hi, increment=step, textvariable=var, width=width)
        sb.pack(side=tk.LEFT, padx=1)
        return sb

    def _al_open_apply_all_dialog(self):
        if not self.al_class_settings:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Áp dụng cho tất cả class")
        dialog.geometry("260x220")

        conf = tk.DoubleVar(value=0.25)
        w_min = tk.DoubleVar(value=0)
        w_max = tk.DoubleVar(value=99999)
        h_min = tk.DoubleVar(value=0)
        h_max = tk.DoubleVar(value=99999)

        for label, var in [
            ("Conf", conf), ("W min", w_min), ("W max", w_max), ("H min", h_min), ("H max", h_max)
        ]:
            f = ttk.Frame(dialog, padding=4)
            f.pack(fill=tk.X)
            ttk.Label(f, text=label, width=8).pack(side=tk.LEFT)
            ttk.Entry(f, textvariable=var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        def apply_all():
            for s in self.al_class_settings.values():
                s.conf.set(conf.get())
                s.w_min.set(w_min.get())
                s.w_max.set(w_max.get())
                s.h_min.set(h_min.get())
                s.h_max.set(h_max.get())
            dialog.destroy()

        ttk.Button(dialog, text="Áp dụng", command=apply_all).pack(pady=10)

    def _al_load_folder(self):
        folder = filedialog.askdirectory(title="Chọn folder ảnh cần auto label")
        if not folder:
            return
        self.al_folder = folder
        self.al_folder_var.set(f"{folder}")

    def start_autolabel(self):
        if self.al_model is None:
            messagebox.showerror("Lỗi", "Vui lòng load model .pt trước.")
            return
        if not self.al_folder or not os.path.isdir(self.al_folder):
            messagebox.showerror("Lỗi", "Vui lòng chọn folder ảnh hợp lệ.")
            return
        try:
            base_conf = float(self.al_base_conf_var.get())
        except Exception:
            messagebox.showerror("Lỗi", "Conf nền phải là số.")
            return

        self.al_start_btn.config(state="disabled")
        self.al_log_text.config(state="normal")
        self.al_log_text.delete("1.0", tk.END)
        self.al_log_text.config(state="disabled")

        threading.Thread(target=self._autolabel_worker, args=(self.al_folder, base_conf), daemon=True).start()

    def _al_filter_box(self, cls_id, conf, w, h):
        """Lọc 1 box theo thông số class ở bảng tab Auto Label. Trả về True nếu được giữ lại."""
        setting = self.al_class_settings.get(cls_id)
        if setting is None:
            return False
        if not setting.enabled.get():
            return False
        if conf < setting.conf.get():
            return False
        if not (setting.w_min.get() < w < setting.w_max.get()):
            return False
        if not (setting.h_min.get() < h < setting.h_max.get()):
            return False
        return True

    def _autolabel_worker(self, folder, base_conf):
        try:
            image_files = []
            for ext in IMAGE_EXTS:
                image_files.extend(glob.glob(os.path.join(folder, f"*{ext}")))
                image_files.extend(glob.glob(os.path.join(folder, f"*{ext.upper()}")))
            image_files = sorted(set(image_files))

            if not image_files:
                self._al_log("Không tìm thấy ảnh nào trong folder này.")
                return

            names = self.al_model.names
            classes_txt_path = os.path.join(folder, "classes.txt")
            with open(classes_txt_path, "w", encoding="utf-8") as f:
                for i in sorted(names.keys()):
                    f.write(f"{names[i]}\n")
            self._al_log(f"Đã tạo classes.txt ({len(names)} class) tại: {classes_txt_path}")

            total = len(image_files)
            self.root.after(0, lambda: self.al_progress.config(maximum=total, value=0))

            for idx, img_path in enumerate(image_files, start=1):
                base = os.path.splitext(os.path.basename(img_path))[0]
                label_path = os.path.join(folder, base + ".txt")

                try:
                    results = self.al_model.predict(source=img_path, conf=base_conf, verbose=False)
                except Exception as e:
                    self._al_log(f"[{idx}/{total}] Lỗi detect {os.path.basename(img_path)}: {e}")
                    continue

                lines = []
                kept, total_raw = 0, 0
                if results:
                    r = results[0]
                    if r.boxes is not None and len(r.boxes) > 0:
                        xyxy = r.boxes.xyxy       # pixel, để lọc theo width/height
                        xywhn = r.boxes.xywhn     # normalize sẵn, để ghi ra file
                        confs = r.boxes.conf
                        cls_ids = r.boxes.cls
                        total_raw = len(r.boxes)

                        for j in range(len(r.boxes)):
                            x1, y1, x2, y2 = [float(v) for v in xyxy[j].tolist()]
                            box_conf = float(confs[j].item())
                            cid = int(cls_ids[j].item())
                            w_px, h_px = x2 - x1, y2 - y1

                            if not self._al_filter_box(cid, box_conf, w_px, h_px):
                                continue

                            cx, cy, w, h = [float(v) for v in xywhn[j].tolist()]
                            lines.append(f"{cid} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
                            kept += 1

                with open(label_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))

                self._al_log(
                    f"[{idx}/{total}] {os.path.basename(img_path)} -> giữ {kept}/{total_raw} object"
                )
                self.root.after(0, lambda v=idx: self.al_progress.config(value=v))

            self._al_log("Auto label hoàn tất cho toàn bộ folder.")

        except Exception as e:
            self._al_log(f"LỖI: {e}")
            self.root.after(0, lambda: messagebox.showerror("Lỗi auto label", str(e)))
        finally:
            self.root.after(0, lambda: self.al_start_btn.config(state="normal"))

    def _build_crop_tab(self, parent):
        pad = dict(padx=6, pady=4)

        form = ttk.Frame(parent, padding=10)
        form.pack(side=tk.TOP, fill=tk.X)

        # Input folder
        self.crop_input_var = tk.StringVar()
        r = 0
        ttk.Label(form, text="Folder ảnh đầu vào:").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(form, textvariable=self.crop_input_var, width=60).grid(row=r, column=1, **pad)
        ttk.Button(form, text="Chọn...", command=self._browse_crop_input).grid(row=r, column=2, **pad)

        # Output folder
        r += 1
        self.crop_output_var = tk.StringVar()
        ttk.Label(form, text="Folder đầu ra (Lưu kết quả):").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(form, textvariable=self.crop_output_var, width=60).grid(row=r, column=1, **pad)
        ttk.Button(form, text="Chọn...", command=self._browse_crop_output).grid(row=r, column=2, **pad)

        # Parameters (Target Width, Target Height, Top Offset Shift)
        r += 1
        self.crop_width_var = tk.IntVar(value=1045)
        self.crop_height_var = tk.IntVar(value=739)
        self.crop_offset_var = tk.IntVar(value=50)

        param_frame = ttk.LabelFrame(form, text="Thông số Cắt (Crop Parameters)", padding=6)
        param_frame.grid(row=r, column=0, columnspan=3, sticky="we", **pad)

        ttk.Label(param_frame, text="Target Width:").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(param_frame, textvariable=self.crop_width_var, width=8).grid(row=0, column=1, sticky="w", padx=2, pady=2)

        ttk.Label(param_frame, text="Target Height:").grid(row=0, column=2, sticky="w", padx=10, pady=2)
        ttk.Entry(param_frame, textvariable=self.crop_height_var, width=8).grid(row=0, column=3, sticky="w", padx=2, pady=2)

        ttk.Label(param_frame, text="Top Offset Shift (offset Y):").grid(row=0, column=4, sticky="w", padx=10, pady=2)
        ttk.Entry(param_frame, textvariable=self.crop_offset_var, width=8).grid(row=0, column=5, sticky="w", padx=2, pady=2)

        # Action & Progress
        r += 1
        action_frame = ttk.Frame(form)
        action_frame.grid(row=r, column=0, columnspan=3, sticky="we", pady=10)

        self.crop_start_btn = ttk.Button(action_frame, text="Bắt đầu cắt ảnh & label", command=self.start_cropping)
        self.crop_start_btn.pack(side=tk.LEFT)

        self.crop_progress = ttk.Progressbar(action_frame, orient=tk.HORIZONTAL, length=300, mode="determinate")
        self.crop_progress.pack(side=tk.LEFT, padx=15)

        self.crop_status_label = ttk.Label(action_frame, text="Sẵn sàng")
        self.crop_status_label.pack(side=tk.LEFT, padx=10)

        # Log frame
        log_frame = ttk.LabelFrame(parent, text="Log xử lý", padding=6)
        log_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.crop_log_text = tk.Text(log_frame, state="disabled", wrap="word")
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.crop_log_text.yview)
        self.crop_log_text.configure(yscrollcommand=log_scroll.set)
        self.crop_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _browse_crop_input(self):
        d = filedialog.askdirectory(title="Chọn folder ảnh đầu vào")
        if d:
            self.crop_input_var.set(d)

    def _browse_crop_output(self):
        d = filedialog.askdirectory(title="Chọn folder đầu ra")
        if d:
            self.crop_output_var.set(d)

    def _crop_log(self, msg):
        def append():
            self.crop_log_text.config(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self.crop_log_text.insert(tk.END, f"[{ts}] {msg}\n")
            self.crop_log_text.see(tk.END)
            self.crop_log_text.config(state="disabled")
        self.root.after(0, append)

    def start_cropping(self):
        input_folder = self.crop_input_var.get().strip()
        output_folder = self.crop_output_var.get().strip()

        if not input_folder or not os.path.isdir(input_folder):
            messagebox.showerror("Lỗi", "Vui lòng chọn folder đầu vào hợp lệ.")
            return

        if not output_folder:
            messagebox.showerror("Lỗi", "Vui lòng chọn folder đầu ra hợp lệ.")
            return

        try:
            target_w = int(self.crop_width_var.get())
            target_h = int(self.crop_height_var.get())
            offset_y = int(self.crop_offset_var.get())
        except Exception:
            messagebox.showerror("Lỗi", "Width, Height và Offset Y phải là các số nguyên.")
            return

        self.crop_start_btn.config(state="disabled")
        self.crop_status_label.config(text="Đang xử lý...")
        self.crop_log_text.config(state="normal")
        self.crop_log_text.delete("1.0", tk.END)
        self.crop_log_text.config(state="disabled")

        threading.Thread(
            target=self._crop_worker,
            args=(input_folder, output_folder, target_w, target_h, offset_y),
            daemon=True
        ).start()

    def _crop_worker(self, input_folder, output_folder, target_w, target_h, offset_y):
        try:
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)

            supported_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
            all_files = os.listdir(input_folder)
            image_files = [f for f in all_files if f.lower().endswith(supported_exts)]

            total = len(image_files)
            if total == 0:
                self._crop_log("Không tìm thấy file ảnh nào trong folder đầu vào.")
                self.root.after(0, lambda: self.crop_status_label.config(text="Không có ảnh."))
                return

            self.root.after(0, lambda: self.crop_progress.config(maximum=total, value=0))
            self._crop_log(f"Bắt đầu cắt {total} ảnh và label (Target: {target_w}x{target_h}, Offset Y: {offset_y})...")

            for idx, filename in enumerate(image_files, start=1):
                img_path = os.path.join(input_folder, filename)
                base_name = os.path.splitext(filename)[0]
                txt_filename = base_name + ".txt"
                txt_path = os.path.join(input_folder, txt_filename)

                try:
                    with Image.open(img_path) as img:
                        orig_w, orig_h = img.size

                        # Tính toán tọa độ cắt
                        left = (orig_w - target_w) // 2
                        top = ((orig_h - target_h) // 2) + offset_y

                        top = max(0, top)
                        right = left + target_w
                        bottom = top + target_h

                        if bottom > orig_h:
                            bottom = orig_h
                            top = bottom - target_h

                        # Xử lý file nhãn YOLO
                        new_labels = []
                        if os.path.exists(txt_path):
                            with open(txt_path, 'r', encoding="utf-8") as f:
                                lines = f.readlines()

                            for line in lines:
                                parts = line.strip().split()
                                if len(parts) != 5:
                                    continue

                                class_id, x_center_rel, y_center_rel, w_rel, h_rel = parts
                                class_id = int(class_id)

                                # Chuyển đổi sang pixel tuyệt đối
                                x_center_abs = float(x_center_rel) * orig_w
                                y_center_abs = float(y_center_rel) * orig_h
                                w_abs = float(w_rel) * orig_w
                                h_abs = float(h_rel) * orig_h

                                # Tọa độ góc tuyệt đối
                                x1_abs = x_center_abs - w_abs / 2
                                y1_abs = y_center_abs - h_abs / 2
                                x2_abs = x_center_abs + w_abs / 2
                                y2_abs = y_center_abs + h_abs / 2

                                # Tọa độ mới sau khi dịch chuyển
                                x1_new = x1_abs - left
                                y1_new = y1_abs - top
                                x2_new = x2_abs - left
                                y2_new = y2_abs - top

                                # Clip trong khoảng ảnh mới
                                x1_new = max(0.0, min(target_w, x1_new))
                                y1_new = max(0.0, min(target_h, y1_new))
                                x2_new = max(0.0, min(target_w, x2_new))
                                y2_new = max(0.0, min(target_h, y2_new))

                                new_w_abs = x2_new - x1_new
                                new_h_abs = y2_new - y1_new
                                new_x_center_abs = x1_new + new_w_abs / 2
                                new_y_center_abs = y1_new + new_h_abs / 2

                                if new_w_abs > 1 and new_h_abs > 1:
                                    new_x_center_rel = new_x_center_abs / target_w
                                    new_y_center_rel = new_y_center_abs / target_h
                                    new_w_rel = new_w_abs / target_w
                                    new_h_rel = new_h_abs / target_h

                                    new_labels.append(f"{class_id} {new_x_center_rel:.6f} {new_y_center_rel:.6f} {new_w_rel:.6f} {new_h_rel:.6f}\n")

                            output_txt_path = os.path.join(output_folder, txt_filename)
                            with open(output_txt_path, 'w', encoding="utf-8") as f:
                                f.writelines(new_labels)

                        # Cắt và lưu ảnh mới
                        cropped_img = img.crop((left, top, right, bottom))
                        output_img_path = os.path.join(output_folder, filename)
                        cropped_img.save(output_img_path)

                    self._crop_log(f"[{idx}/{total}] Đã xử lý: {filename}")
                except Exception as img_err:
                    self._crop_log(f"[{idx}/{total}] Lỗi xử lý {filename}: {img_err}")

                self.root.after(0, lambda v=idx: self.crop_progress.config(value=v))

            self._crop_log("--- HOÀN THÀNH BIẾN ĐỔI ẢNH VÀ LABEL ---")
            self.root.after(0, lambda: self.crop_status_label.config(text="Hoàn tất!"))

        except Exception as e:
            self._crop_log(f"LỖI: {e}")
            self.root.after(0, lambda: self.crop_status_label.config(text="Lỗi - xem log."))
            self.root.after(0, lambda: messagebox.showerror("Lỗi", str(e)))
        finally:
            self.root.after(0, lambda: self.crop_start_btn.config(state="normal"))

def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        style.theme_use("clam")
    except Exception:
        pass
    app = YoloGuiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()