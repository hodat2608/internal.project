"""
YOLO Studio - GUI Detect / Training / Auto Label / Crop
======================================================
Được nâng cấp từ detect_model.py (Tkinter cũ) sang PyQt5,
đồng bộ toàn bộ mã xử lý core với giao diện hiện đại từ yolo_studio.ui / yolo_studio.py.

Các tính năng chính:
  1) Detection:
     - Load model .pt, load folder ảnh.
     - Lọc kết quả detect thời gian thực theo từng class (Conf, Width, Height, Enabled).
     - Phán định OK/NG (rule theo count hoặc hễ có là NG), hiển thị badge và chi tiết.
     - Hiển thị ảnh kèm bounding box trực quan, tự co giãn mượt mà theo kích thước cửa sổ.
  2) Training:
     - Tùy chỉnh huấn luyện cho YOLOv8 và YOLOv8 trở lên (YOLOv8, YOLOv9, YOLOv10, YOLO11, YOLOv12, Custom).
     - Hỗ trợ cả 2 chế độ: Config kiến trúc (.yaml) và Pretrained weights (.pt).
     - Tự động gợi ý config/weight và danh sách scale tương ứng cho từng phiên bản YOLO.
     - Tự động chia train/valid, sinh data.yaml và chuẩn bị model architecture yaml.
     - Đầy đủ thông số cơ bản & augmentation, redirect log training thời gian thực.
  3) Auto Label:
     - Tự động gắn nhãn hàng loạt bằng model YOLO.
     - Tự sinh file classes.txt và các file nhãn .txt chuẩn YOLO.
     - Bảng lọc box theo từng class (Conf, W, H) trước khi ghi nhãn.
  4) Convert Image Dimensions & Label (Crop):
     - Cắt ảnh hàng loạt theo kích thước mong muốn kèm Top Offset Shift (Y).
     - Tự động tính toán lại tọa độ bounding box trong file nhãn .txt chuẩn YOLO.
"""

import os
import sys
import glob
import random
import shutil
import colorsys
from datetime import datetime

from PyQt5 import QtCore, QtGui, QtWidgets
from PIL import Image, ImageDraw, ImageFont

try:
    import yaml
except ImportError:
    yaml = None

# Thêm đường dẫn chứa thư viện Ultralytics trong dự án (_source/v8/ultralytics) và thư mục hiện tại
_curr_dir = os.path.dirname(os.path.abspath(__file__))
if _curr_dir not in sys.path:
    sys.path.insert(0, _curr_dir)

_possible_ultra_paths = [
    os.path.abspath(os.path.join(_curr_dir, "..", "v8", "ultralytics")),
    os.path.abspath(os.path.join(_curr_dir, "..", "v8")),
    os.path.abspath(os.path.join(os.getcwd(), "_source", "v8", "ultralytics")),
]
for _p in _possible_ultra_paths:
    if os.path.exists(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

# Import UI generated from Designer
try:
    from yolo_studio import Ui_MainWindow
except ImportError:
    # Nếu chạy từ thư mục khác
    from .yolo_studio import Ui_MainWindow


IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff")
BASE_INFER_CONF = 0.01

# Cấu hình mặc định cho các dòng YOLO từ v8 trở lên
YOLO_FAMILY_CONFIGS = {
    "YOLOv8": {
        "yaml": "yolov8.yaml",
        "weights": "yolov8s.pt",
        "scales": ["n", "s", "m", "l", "x"],
        "default_scale": "s",
        "prefix": "yolov8",
    },
    "YOLOv9": {
        "yaml": "yolov9c.yaml",
        "weights": "yolov9s.pt",
        "scales": ["t", "s", "m", "c", "e"],
        "default_scale": "s",
        "prefix": "yolov9",
    },
    "YOLOv10": {
        "yaml": "yolov10s.yaml",
        "weights": "yolov10s.pt",
        "scales": ["n", "s", "m", "b", "l", "x"],
        "default_scale": "s",
        "prefix": "yolov10",
    },
    "YOLO11": {
        "yaml": "yolo11.yaml",
        "weights": "yolo11s.pt",
        "scales": ["n", "s", "m", "l", "x"],
        "default_scale": "s",
        "prefix": "yolo11",
    },
    "YOLOv12": {
        "yaml": "yolo12.yaml",
        "weights": "yolov12s.pt",
        "scales": ["n", "s", "m", "l", "x"],
        "default_scale": "s",
        "prefix": "yolov12",
    },
    "Tùy chỉnh (Custom)": {
        "yaml": "yolov8.yaml",
        "weights": "yolov8s.pt",
        "scales": ["n", "s", "m", "l", "x"],
        "default_scale": "s",
        "prefix": "",
    },
}


# ========================================================================== #
# Helper Functions & Classes
# ========================================================================== #

def gen_color(idx, total):
    """Sinh màu RGB phân biệt cho từng class bằng Golden Ratio."""
    hue = (idx * 0.61803398875) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.70, 0.95)
    return int(r * 255), int(g * 255), int(b * 255)


def find_model_yaml(name):
    """Tìm đường dẫn file config .yaml (trong thư mục hiện tại hoặc bên trong gói ultralytics)."""
    if os.path.isfile(name):
        return os.path.abspath(name)
    try:
        import ultralytics
        base_cfg = os.path.join(os.path.dirname(ultralytics.__file__), "cfg", "models")
        for root, _, files in os.walk(base_cfg):
            if name in files:
                return os.path.join(root, name)
    except Exception:
        pass
    return None


class ClassSetting:
    """Thông số filter + phán định OK/NG cho 1 class."""
    def __init__(self):
        self.conf = 0.25
        self.w_min = 0.0
        self.w_max = 99999.0
        self.h_min = 0.0
        self.h_max = 99999.0
        self.enabled = True
        self.ok = False
        self.ng = False
        self.count = 1


class StreamToSignal:
    """Redirect stdout/stderr tới 1 callable/signal."""
    def __init__(self, callback):
        self.callback = callback

    def write(self, s):
        if not s:
            return
        lines = s.splitlines()
        for line in lines:
            line = line.strip("\r\n")
            if line:
                self.callback(line)

    def flush(self):
        pass


# ========================================================================== #
# Worker Threads for Asynchronous Processing
# ========================================================================== #

class ModelLoadWorker(QtCore.QThread):
    finished_signal = QtCore.pyqtSignal(bool, object, str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        try:
            model = YOLO(self.path)
            self.finished_signal.emit(True, model, "")
        except Exception as e:
            self.finished_signal.emit(False, None, str(e))


class InferenceWorker(QtCore.QThread):
    finished_signal = QtCore.pyqtSignal(bool, list, str)

    def __init__(self, model, pil_image, class_names):
        super().__init__()
        self.model = model
        self.pil_image = pil_image
        self.class_names = class_names

    def run(self):
        try:
            results = self.model.predict(source=self.pil_image, conf=BASE_INFER_CONF, verbose=False)
            dets = []
            if results and results[0].boxes is not None:
                for box in results[0].boxes:
                    x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
                    conf = float(box.conf[0].item())
                    cid = int(box.cls[0].item())
                    dets.append({
                        "cls_id": cid,
                        "cls_name": self.class_names.get(cid, str(cid)),
                        "conf": conf,
                        "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                        "w": x2 - x1, "h": y2 - y1,
                    })
            self.finished_signal.emit(True, dets, "")
        except Exception as e:
            self.finished_signal.emit(False, [], str(e))


class TrainWorker(QtCore.QThread):
    log_signal = QtCore.pyqtSignal(str)
    status_signal = QtCore.pyqtSignal(str, str)
    finished_signal = QtCore.pyqtSignal(bool, str)

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run(self):
        p = self.params
        try:
            self.log_signal.emit("Bắt đầu chuẩn bị dataset train/valid ...")
            split_root, names = self._split_dataset(p["dataset_dir"], p["ratio"])
            self.log_signal.emit(f"Đã phân chia dataset tại: {split_root}")
            self.log_signal.emit(f"Số lượng class: {len(names)} -> {names}")

            data_yaml_path = self._write_data_yaml(split_root, names)
            self.log_signal.emit(f"Đã tạo file data.yaml: {data_yaml_path}")

            if "yaml" in p["mode"].lower():
                resolved_yaml = self._prepare_model_yaml(
                    p["config_yaml"], len(names), p["scale"], p["version_prefix"], split_root
                )
                self.log_signal.emit(
                    f"Khởi tạo kiến trúc model từ: {resolved_yaml} (nc={len(names)}, scale={p['scale']})"
                )
                model = YOLO(resolved_yaml)
            else:
                self.log_signal.emit(f"Load pretrained weights: {p['base_model']}")
                model = YOLO(p["base_model"])

            project_dir = p["save_dir"]
            run_name = f"{p['save_name']}_run"

            self.log_signal.emit(
                f"Bắt đầu huấn luyện YOLO: imgsz={p['imgsz']}, batch={p['batch']}, epochs={p['epochs']}, device={p['device']} ..."
            )

            old_stdout, old_stderr = sys.stdout, sys.stderr
            redirector = StreamToSignal(self.log_signal.emit)
            sys.stdout = redirector
            sys.stderr = redirector
            try:
                model.train(
                    data=data_yaml_path,
                    imgsz=p["imgsz"],
                    batch=p["batch"],
                    epochs=p["epochs"],
                    project=project_dir,
                    name=run_name,
                    exist_ok=True,
                    device=p["device"],
                    hsv_h=p["hsv_h"],
                    hsv_s=p["hsv_s"],
                    hsv_v=p["hsv_v"],
                    scale=p["scale_aug"],
                    fliplr=p["fliplr"],
                    mosaic=p["mosaic"],
                    erasing=p["erasing"],
                    workers=p["workers"],
                    patience=p["patience"],
                    seed=p["seed"],
                )
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

            best_pt = os.path.join(project_dir, run_name, "weights", "best.pt")
            final_name = p["save_name"] if p["save_name"].endswith(".pt") else p["save_name"] + ".pt"
            final_path = os.path.join(project_dir, final_name)

            if os.path.isfile(best_pt):
                shutil.copy2(best_pt, final_path)
                self.log_signal.emit(f"Đã lưu weights tốt nhất (best.pt) tại: {final_path}")
                self.status_signal.emit("Huấn luyện hoàn tất thành công!", "status-ok")
                self.finished_signal.emit(True, f"Huấn luyện thành công!\nFile weights: {final_path}")
            else:
                self.log_signal.emit(f"Không tìm thấy best.pt tại {best_pt}. Kiểm tra thư mục {run_name}.")
                self.status_signal.emit("Huấn luyện xong (không thấy best.pt)", "status-warn")
                self.finished_signal.emit(True, "Huấn luyện kết thúc nhưng không tìm thấy file best.pt.")

        except Exception as e:
            self.log_signal.emit(f"LỖI HUẤN LUYỆN: {e}")
            self.status_signal.emit("Huấn luyện thất bại!", "status-warn")
            self.finished_signal.emit(False, str(e))

    def _split_dataset(self, dataset_dir, ratio):
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
            raise RuntimeError(f"Không tìm thấy ảnh nào trong: {img_dir}")

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
            max_id = -1
            for img_path in image_files:
                base = os.path.splitext(os.path.basename(img_path))[0]
                lbl_path = os.path.join(lbl_dir, base + ".txt")
                if os.path.isfile(lbl_path):
                    with open(lbl_path, "r", encoding="utf-8") as f:
                        for line in f:
                            parts = line.strip().split()
                            if parts:
                                try:
                                    max_id = max(max_id, int(float(parts[0])))
                                except Exception:
                                    pass
            if max_id < 0:
                raise RuntimeError("Không tìm thấy file nhãn .txt nào và không có classes.txt.")
            names = [f"class{i}" for i in range(max_id + 1)]

        random.shuffle(image_files)
        split_idx = int(len(image_files) * ratio)
        train_files = image_files[:split_idx]
        valid_files = image_files[split_idx:]
        if not valid_files:
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
                    open(os.path.join(split_root, subset, "labels", base + ".txt"), "w").close()

        copy_set(train_files, "train")
        copy_set(valid_files, "valid")

        self.log_signal.emit(f"Phân chia xong: Train = {len(train_files)} ảnh | Valid = {len(valid_files)} ảnh")
        return split_root, names

    def _write_data_yaml(self, split_root, names):
        yaml_path = os.path.join(split_root, "data.yaml")
        names_lines = "\n".join(f"  {i}: {name}" for i, name in enumerate(names))
        content = (
            f"path: {os.path.abspath(split_root)}\n"
            f"train: train/images\n"
            f"val: valid/images\n"
            f"nc: {len(names)}\n"
            f"names:\n{names_lines}\n"
        )
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(content)
        return yaml_path

    def _prepare_model_yaml(self, config_yaml_path, nc, scale, prefix, split_root):
        resolved_path = find_model_yaml(config_yaml_path)
        if not resolved_path or not os.path.isfile(resolved_path):
            raise FileNotFoundError(f"Không tìm thấy file config kiến trúc: {config_yaml_path}")

        # Đặt tên file có chứa scale (ví dụ yolov8s_custom.yaml) để Ultralytics tự đoán scale chính xác
        file_prefix = prefix if prefix else "yolo_model"
        out_name = f"{file_prefix}{scale}_custom.yaml"
        out_path = os.path.join(split_root, out_name)

        if yaml is not None:
            with open(resolved_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            if not isinstance(cfg, dict):
                raise ValueError(f"Nội dung file config không hợp lệ: {resolved_path}")

            cfg["nc"] = nc
            if cfg.get("scales"):
                cfg["scale"] = scale

            with open(out_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
        else:
            with open(resolved_path, "r", encoding="utf-8") as f:
                original = f.read()
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(f"nc: {nc}\nscale: {scale}\n")
                f.write(original)

        return out_path


class AutoLabelWorker(QtCore.QThread):
    log_signal = QtCore.pyqtSignal(str)
    progress_signal = QtCore.pyqtSignal(int, int)
    finished_signal = QtCore.pyqtSignal(bool, str)

    def __init__(self, model, folder, base_conf, class_settings):
        super().__init__()
        self.model = model
        self.folder = folder
        self.base_conf = base_conf
        self.class_settings = class_settings

    def run(self):
        try:
            image_files = []
            for ext in IMAGE_EXTS:
                image_files.extend(glob.glob(os.path.join(self.folder, f"*{ext}")))
                image_files.extend(glob.glob(os.path.join(self.folder, f"*{ext.upper()}")))
            image_files = sorted(set(image_files))

            if not image_files:
                self.finished_signal.emit(False, "Không tìm thấy file ảnh nào trong folder.")
                return

            names = self.model.names
            classes_txt_path = os.path.join(self.folder, "classes.txt")
            with open(classes_txt_path, "w", encoding="utf-8") as f:
                for i in sorted(names.keys()):
                    f.write(f"{names[i]}\n")
            self.log_signal.emit(f"Đã tạo file classes.txt ({len(names)} class)")

            total = len(image_files)
            for idx, img_path in enumerate(image_files, start=1):
                base = os.path.splitext(os.path.basename(img_path))[0]
                label_path = os.path.join(self.folder, base + ".txt")

                try:
                    results = self.model.predict(source=img_path, conf=self.base_conf, verbose=False)
                except Exception as e:
                    self.log_signal.emit(f"[{idx}/{total}] Lỗi detect {os.path.basename(img_path)}: {e}")
                    self.progress_signal.emit(idx, total)
                    continue

                lines = []
                kept = 0
                total_raw = 0
                if results and results[0].boxes is not None:
                    r = results[0]
                    total_raw = len(r.boxes)
                    xyxy = r.boxes.xyxy
                    xywhn = r.boxes.xywhn
                    confs = r.boxes.conf
                    cls_ids = r.boxes.cls

                    for j in range(total_raw):
                        x1, y1, x2, y2 = [float(v) for v in xyxy[j].tolist()]
                        b_conf = float(confs[j].item())
                        cid = int(cls_ids[j].item())
                        w_px, h_px = x2 - x1, y2 - y1

                        s = self.class_settings.get(cid)
                        if s is None or not s.enabled:
                            continue
                        if b_conf < s.conf or not (s.w_min < w_px < s.w_max) or not (s.h_min < h_px < s.h_max):
                            continue

                        cx, cy, w, h = [float(v) for v in xywhn[j].tolist()]
                        lines.append(f"{cid} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
                        kept += 1

                with open(label_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))

                self.log_signal.emit(
                    f"[{idx}/{total}] {os.path.basename(img_path)} -> giữ {kept}/{total_raw} box"
                )
                self.progress_signal.emit(idx, total)

            self.log_signal.emit("--- AUTO LABEL HOÀN TẤT CHO TOÀN BỘ FOLDER ---")
            self.finished_signal.emit(True, f"Đã hoàn thành gắn nhãn cho {total} ảnh.")

        except Exception as e:
            self.log_signal.emit(f"LỖI AUTO LABEL: {e}")
            self.finished_signal.emit(False, str(e))


class CropWorker(QtCore.QThread):
    log_signal = QtCore.pyqtSignal(str)
    progress_signal = QtCore.pyqtSignal(int, int)
    finished_signal = QtCore.pyqtSignal(bool, str)

    def __init__(self, in_dir, out_dir, target_w, target_h, offset_y):
        super().__init__()
        self.in_dir = in_dir
        self.out_dir = out_dir
        self.target_w = target_w
        self.target_h = target_h
        self.offset_y = offset_y

    def run(self):
        try:
            os.makedirs(self.out_dir, exist_ok=True)
            files = [f for f in os.listdir(self.in_dir) if f.lower().endswith(IMAGE_EXTS)]
            total = len(files)
            if total == 0:
                self.finished_signal.emit(False, "Không tìm thấy file ảnh nào trong folder đầu vào.")
                return

            self.log_signal.emit(
                f"Bắt đầu cắt {total} ảnh & nhãn (Target: {self.target_w}x{self.target_h}, Offset Y: {self.offset_y}) ..."
            )

            for idx, fname in enumerate(files, start=1):
                img_path = os.path.join(self.in_dir, fname)
                base = os.path.splitext(fname)[0]
                txt_path = os.path.join(self.in_dir, base + ".txt")

                try:
                    with Image.open(img_path) as img:
                        orig_w, orig_h = img.size
                        left = (orig_w - self.target_w) // 2
                        top = ((orig_h - self.target_h) // 2) + self.offset_y

                        top = max(0, top)
                        right = left + self.target_w
                        bottom = top + self.target_h

                        if bottom > orig_h:
                            bottom = orig_h
                            top = max(0, bottom - self.target_h)

                        # Xử lý nhãn YOLO nếu có
                        if os.path.isfile(txt_path):
                            new_labels = []
                            with open(txt_path, "r", encoding="utf-8") as f:
                                for line in f:
                                    parts = line.strip().split()
                                    if len(parts) != 5:
                                        continue
                                    cid = int(float(parts[0]))
                                    cx_rel, cy_rel, w_rel, h_rel = [float(v) for v in parts[1:]]

                                    cx_abs = cx_rel * orig_w
                                    cy_abs = cy_rel * orig_h
                                    bw_abs = w_rel * orig_w
                                    bh_abs = h_rel * orig_h

                                    x1_abs = cx_abs - bw_abs / 2
                                    y1_abs = cy_abs - bh_abs / 2
                                    x2_abs = cx_abs + bw_abs / 2
                                    y2_abs = cy_abs + bh_abs / 2

                                    x1_new = max(0.0, min(self.target_w, x1_abs - left))
                                    y1_new = max(0.0, min(self.target_h, y1_abs - top))
                                    x2_new = max(0.0, min(self.target_w, x2_abs - left))
                                    y2_new = max(0.0, min(self.target_h, y2_abs - top))

                                    nw = x2_new - x1_new
                                    nh = y2_new - y1_new
                                    if nw > 1.0 and nh > 1.0:
                                        ncx = (x1_new + nw / 2) / self.target_w
                                        ncy = (y1_new + nh / 2) / self.target_h
                                        new_labels.append(
                                            f"{cid} {ncx:.6f} {ncy:.6f} {nw / self.target_w:.6f} {nh / self.target_h:.6f}\n"
                                        )

                            out_txt = os.path.join(self.out_dir, base + ".txt")
                            with open(out_txt, "w", encoding="utf-8") as f:
                                f.writelines(new_labels)

                        cropped = img.crop((left, top, right, bottom))
                        cropped.save(os.path.join(self.out_dir, fname))
                        self.log_signal.emit(f"[{idx}/{total}] Đã xử lý: {fname}")

                except Exception as ex:
                    self.log_signal.emit(f"[{idx}/{total}] Lỗi xử lý {fname}: {ex}")

                self.progress_signal.emit(idx, total)

            self.log_signal.emit("--- HOÀN THÀNH BIẾN ĐỔI KÍCH THƯỚC ẢNH VÀ NHÃN ---")
            self.finished_signal.emit(True, f"Đã cắt và chuyển đổi xong {total} ảnh.")

        except Exception as e:
            self.log_signal.emit(f"LỖI CẮT ẢNH: {e}")
            self.finished_signal.emit(False, str(e))


# ========================================================================== #
# Main Window Application Class
# ========================================================================== #

class YoloStudioApp(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # Trạng thái Tab Detect
        self.model = None
        self.model_path = None
        self.class_names = {}
        self.class_settings = {}
        self.class_colors = {}
        self.image_paths = []
        self.current_index = -1
        self.current_pil_image = None
        self.current_detections = []
        self.rendered_pixmap = None

        # Trạng thái Tab Auto Label
        self.al_model = None
        self.al_model_path = None
        self.al_folder = None
        self.al_class_names = {}
        self.al_class_settings = {}
        self.al_class_colors = {}

        # Worker threads
        self.train_thread = None
        self.al_thread = None
        self.crop_thread = None

        self._setup_connections()
        self._init_defaults()

    def _refresh_style(self, widget):
        """Buộc Qt cập nhật stylesheet khi thay đổi dynamic property 'role'."""
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _setup_connections(self):
        # ---- TAB 1: DETECT ----
        self.btnLoadModel.clicked.connect(self.load_model)
        self.btnLoadFolder.clicked.connect(self.load_folder)
        self.btnPrev.clicked.connect(self.prev_image)
        self.btnNext.clicked.connect(self.next_image)
        self.btnGoto.clicked.connect(self.goto_image)
        self.editGoto.returnPressed.connect(self.goto_image)
        self.btnApplyAll.clicked.connect(self.open_apply_all_dialog)

        # Lắng nghe sự kiện resize của lblImageView để scale ảnh mượt mà
        self.lblImageView.installEventFilter(self)

        # ---- TAB 2: TRAINING ----
        self.btnBrowseDataset.clicked.connect(self._browse_train_dataset)
        self.btnBrowseYaml.clicked.connect(self._browse_config_yaml)
        self.btnBrowsePt.clicked.connect(self._browse_base_model)
        self.btnBrowseSaveDir.clicked.connect(self._browse_train_savedir)
        self.comboTrainMode.currentIndexChanged.connect(self._on_train_mode_changed)

        if hasattr(self, "comboYoloVersion"):
            self.comboYoloVersion.currentIndexChanged.connect(self._on_yolo_version_changed)
        self.comboScale.currentTextChanged.connect(self._on_scale_changed)
        self.btnStartTrain.clicked.connect(self.start_training)

        # ---- TAB 3: AUTO LABEL ----
        self.btnAlLoadModel.clicked.connect(self._al_load_model)
        self.btnAlLoadFolder.clicked.connect(self._al_load_folder)
        self.btnAlApplyAll.clicked.connect(self._al_open_apply_all_dialog)
        self.btnAlStart.clicked.connect(self.start_autolabel)

        # ---- TAB 4: CROP ----
        self.btnBrowseCropInput.clicked.connect(self._browse_crop_input)
        self.btnBrowseCropOutput.clicked.connect(self._browse_crop_output)
        self.btnCropStart.clicked.connect(self.start_cropping)

    def _init_defaults(self):
        # Tự động phát hiện GPU
        try:
            import torch
            if torch.cuda.is_available():
                self.editDevice.setText("0")
            else:
                self.editDevice.setText("cpu")
        except Exception:
            self.editDevice.setText("cpu")

        # Cập nhật giao diện chế độ train ban đầu
        self._on_yolo_version_changed()
        self._on_train_mode_changed()

    def eventFilter(self, source, event):
        if source == self.lblImageView and event.type() == QtCore.QEvent.Resize:
            self._update_image_display()
        return super().eventFilter(source, event)

    # ====================================================================== #
    # TAB 1: DETECT LOGIC
    # ====================================================================== #

    def load_model(self):
        if YOLO is None:
            QtWidgets.QMessageBox.critical(self, "Thiếu thư viện", "Chưa cài đặt ultralytics. Hãy chạy: pip install ultralytics")
            return

        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Chọn file model weights (.pt)", "", "YOLO Weights (*.pt);;All Files (*.*)"
        )
        if not path:
            return

        self.lblModelStatus.setText(f"Đang load: {os.path.basename(path)} ...")
        self.lblModelStatus.setProperty("role", "status-neutral")
        self._refresh_style(self.lblModelStatus)
        self.statusBar().showMessage(f"Đang nạp model: {path} ...")

        self.model_load_thread = ModelLoadWorker(path)
        self.model_load_thread.finished_signal.connect(
            lambda success, mdl, err: self._on_model_loaded(success, mdl, err, path)
        )
        self.model_load_thread.start()

    def _on_model_loaded(self, success, model, err, path):
        if not success:
            self.lblModelStatus.setText("Lỗi load model")
            self.lblModelStatus.setProperty("role", "status-warn")
            self._refresh_style(self.lblModelStatus)
            QtWidgets.QMessageBox.critical(self, "Lỗi load model", err)
            return

        self.model = model
        self.model_path = path
        self.class_names = dict(model.names)
        self.lblModelStatus.setText(f"{os.path.basename(path)} ({len(self.class_names)} class)")
        self.lblModelStatus.setProperty("role", "status-ok")
        self._refresh_style(self.lblModelStatus)
        self.statusBar().showMessage("Load model thành công.")

        self._build_class_table()

        if self.current_index >= 0:
            self._detect_current_image()

    def _build_class_table(self):
        self.tableClasses.setRowCount(0)
        self.class_settings.clear()
        self.class_colors.clear()

        n = len(self.class_names)
        self.tableClasses.setRowCount(n)

        for row, (cls_id, name) in enumerate(sorted(self.class_names.items())):
            setting = ClassSetting()
            self.class_settings[cls_id] = setting
            color = gen_color(cls_id, n)
            self.class_colors[cls_id] = color

            # Col 0: Hiện (Checkable)
            chk_item = QtWidgets.QTableWidgetItem()
            chk_item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            chk_item.setCheckState(QtCore.Qt.Checked)
            chk_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.tableClasses.setItem(row, 0, chk_item)

            # Col 1: Class (Tên + Icon màu)
            pix = QtGui.QPixmap(14, 14)
            pix.fill(QtGui.QColor(*color))
            cls_item = QtWidgets.QTableWidgetItem(QtGui.QIcon(pix), name)
            cls_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            self.tableClasses.setItem(row, 1, cls_item)

            # Col 2: Conf (DoubleSpinBox)
            sp_conf = QtWidgets.QDoubleSpinBox()
            sp_conf.setRange(0.0, 1.0)
            sp_conf.setSingleStep(0.01)
            sp_conf.setValue(0.25)
            sp_conf.setAlignment(QtCore.Qt.AlignCenter)
            sp_conf.valueChanged.connect(lambda val, s=setting: self._on_setting_changed(s, "conf", val))
            self.tableClasses.setCellWidget(row, 2, sp_conf)

            # Col 3: W min
            sp_wmin = QtWidgets.QSpinBox()
            sp_wmin.setRange(0, 100000)
            sp_wmin.setValue(0)
            sp_wmin.setAlignment(QtCore.Qt.AlignCenter)
            sp_wmin.valueChanged.connect(lambda val, s=setting: self._on_setting_changed(s, "w_min", val))
            self.tableClasses.setCellWidget(row, 3, sp_wmin)

            # Col 4: W max
            sp_wmax = QtWidgets.QSpinBox()
            sp_wmax.setRange(0, 100000)
            sp_wmax.setValue(99999)
            sp_wmax.setAlignment(QtCore.Qt.AlignCenter)
            sp_wmax.valueChanged.connect(lambda val, s=setting: self._on_setting_changed(s, "w_max", val))
            self.tableClasses.setCellWidget(row, 4, sp_wmax)

            # Col 5: H min
            sp_hmin = QtWidgets.QSpinBox()
            sp_hmin.setRange(0, 100000)
            sp_hmin.setValue(0)
            sp_hmin.setAlignment(QtCore.Qt.AlignCenter)
            sp_hmin.valueChanged.connect(lambda val, s=setting: self._on_setting_changed(s, "h_min", val))
            self.tableClasses.setCellWidget(row, 5, sp_hmin)

            # Col 6: H max
            sp_hmax = QtWidgets.QSpinBox()
            sp_hmax.setRange(0, 100000)
            sp_hmax.setValue(99999)
            sp_hmax.setAlignment(QtCore.Qt.AlignCenter)
            sp_hmax.valueChanged.connect(lambda val, s=setting: self._on_setting_changed(s, "h_max", val))
            self.tableClasses.setCellWidget(row, 6, sp_hmax)

            # Col 7: OK (Checkable)
            ok_item = QtWidgets.QTableWidgetItem()
            ok_item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            ok_item.setCheckState(QtCore.Qt.Unchecked)
            ok_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.tableClasses.setItem(row, 7, ok_item)

            # Col 8: NG (Checkable)
            ng_item = QtWidgets.QTableWidgetItem()
            ng_item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            ng_item.setCheckState(QtCore.Qt.Unchecked)
            ng_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.tableClasses.setItem(row, 8, ng_item)

            # Col 9: Count
            sp_count = QtWidgets.QSpinBox()
            sp_count.setRange(0, 100000)
            sp_count.setValue(1)
            sp_count.setAlignment(QtCore.Qt.AlignCenter)
            sp_count.valueChanged.connect(lambda val, s=setting: self._on_setting_changed(s, "count", val))
            self.tableClasses.setCellWidget(row, 9, sp_count)

        self.tableClasses.itemChanged.connect(self._on_table_item_changed)

    def _on_setting_changed(self, setting, field, value):
        setattr(setting, field, value)
        self._redraw()

    def _on_table_item_changed(self, item):
        row = item.row()
        col = item.column()
        cls_ids = sorted(self.class_names.keys())
        if row >= len(cls_ids):
            return
        cid = cls_ids[row]
        setting = self.class_settings[cid]

        self.tableClasses.blockSignals(True)
        try:
            if col == 0:  # Hiện
                setting.enabled = (item.checkState() == QtCore.Qt.Checked)
            elif col == 7:  # OK
                setting.ok = (item.checkState() == QtCore.Qt.Checked)
                if setting.ok:
                    setting.ng = False
                    ng_item = self.tableClasses.item(row, 8)
                    if ng_item:
                        ng_item.setCheckState(QtCore.Qt.Unchecked)
            elif col == 8:  # NG
                setting.ng = (item.checkState() == QtCore.Qt.Checked)
                if setting.ng:
                    setting.ok = False
                    ok_item = self.tableClasses.item(row, 7)
                    if ok_item:
                        ok_item.setCheckState(QtCore.Qt.Unchecked)
        finally:
            self.tableClasses.blockSignals(False)

        self._redraw()

    def open_apply_all_dialog(self):
        if not self.class_settings:
            QtWidgets.QMessageBox.information(self, "Thông báo", "Vui lòng load model trước khi áp dụng thông số.")
            return

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Áp dụng cho tất cả class")
        dlg.resize(320, 260)
        layout = QtWidgets.QFormLayout(dlg)

        sp_conf = QtWidgets.QDoubleSpinBox()
        sp_conf.setRange(0.0, 1.0)
        sp_conf.setSingleStep(0.01)
        sp_conf.setValue(0.25)
        layout.addRow("Conf:", sp_conf)

        sp_wmin = QtWidgets.QSpinBox()
        sp_wmin.setRange(0, 100000)
        sp_wmin.setValue(0)
        layout.addRow("W min:", sp_wmin)

        sp_wmax = QtWidgets.QSpinBox()
        sp_wmax.setRange(0, 100000)
        sp_wmax.setValue(99999)
        layout.addRow("W max:", sp_wmax)

        sp_hmin = QtWidgets.QSpinBox()
        sp_hmin.setRange(0, 100000)
        sp_hmin.setValue(0)
        layout.addRow("H min:", sp_hmin)

        sp_hmax = QtWidgets.QSpinBox()
        sp_hmax.setRange(0, 100000)
        sp_hmax.setValue(99999)
        layout.addRow("H max:", sp_hmax)

        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        layout.addRow(btn_box)

        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            conf_val = sp_conf.value()
            wmin_val = sp_wmin.value()
            wmax_val = sp_wmax.value()
            hmin_val = sp_hmin.value()
            hmax_val = sp_hmax.value()

            for row in range(self.tableClasses.rowCount()):
                w_conf = self.tableClasses.cellWidget(row, 2)
                w_wmin = self.tableClasses.cellWidget(row, 3)
                w_wmax = self.tableClasses.cellWidget(row, 4)
                w_hmin = self.tableClasses.cellWidget(row, 5)
                w_hmax = self.tableClasses.cellWidget(row, 6)
                if w_conf: w_conf.setValue(conf_val)
                if w_wmin: w_wmin.setValue(wmin_val)
                if w_wmax: w_wmax.setValue(wmax_val)
                if w_hmin: w_hmin.setValue(hmin_val)
                if w_hmax: w_hmax.setValue(hmax_val)

            for s in self.class_settings.values():
                s.conf = conf_val
                s.w_min = wmin_val
                s.w_max = wmax_val
                s.h_min = hmin_val
                s.h_max = hmax_val

            self._redraw()

    def load_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Chọn folder ảnh")
        if not folder:
            return

        paths = []
        for ext in IMAGE_EXTS:
            paths.extend(glob.glob(os.path.join(folder, f"*{ext}")))
            paths.extend(glob.glob(os.path.join(folder, f"*{ext.upper()}")))
        paths = sorted(set(paths))

        if not paths:
            QtWidgets.QMessageBox.warning(self, "Không có ảnh", "Folder này không chứa file ảnh nào hợp lệ.")
            return

        self.image_paths = paths
        self.current_index = 0
        self.lblFolderStatus.setText(f"{folder} ({len(paths)} ảnh)")
        self.lblFolderStatus.setProperty("role", "status-ok")
        self._refresh_style(self.lblFolderStatus)

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
            QtWidgets.QMessageBox.warning(self, "Chưa có ảnh", "Vui lòng load folder ảnh trước.")
            return

        raw = self.editGoto.text().strip()
        try:
            val = int(raw)
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng nhập số thứ tự ảnh hợp lệ.")
            return

        total = len(self.image_paths)
        if 1 <= val <= total:
            self.current_index = val - 1
            self._load_current_image()
        else:
            QtWidgets.QMessageBox.warning(self, "Lỗi", f"Số thứ tự ảnh phải nằm trong khoảng 1 - {total}.")

    def _load_current_image(self):
        if not self.image_paths or self.current_index < 0:
            return

        path = self.image_paths[self.current_index]
        try:
            self.current_pil_image = Image.open(path).convert("RGB")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi mở ảnh", f"Không thể đọc ảnh: {e}")
            return

        self.lblIndex.setText(f"{self.current_index + 1} / {len(self.image_paths)}")
        self.lblFilename.setText(os.path.basename(path))
        self._detect_current_image()

    def _detect_current_image(self):
        if self.current_pil_image is None:
            return

        if self.model is None:
            self.current_detections = []
            self._redraw()
            self.statusBar().showMessage("Chưa load model - hiển thị ảnh gốc.")
            return

        self.statusBar().showMessage("Đang thực hiện detect ...")
        self.infer_thread = InferenceWorker(self.model, self.current_pil_image, self.class_names)
        self.infer_thread.finished_signal.connect(self._on_inference_finished)
        self.infer_thread.start()

    def _on_inference_finished(self, success, dets, err):
        if not success:
            QtWidgets.QMessageBox.critical(self, "Lỗi detect", err)
            self.statusBar().showMessage("Lỗi khi chạy detect.")
            return

        self.current_detections = dets
        self._redraw()
        self.statusBar().showMessage(f"Detect xong: {len(dets)} box (trước khi lọc).")

    def _filter_detections(self):
        visible = []
        for d in self.current_detections:
            setting = self.class_settings.get(d["cls_id"])
            if setting is None or not setting.enabled:
                continue
            if d["conf"] < setting.conf:
                continue
            if not (setting.w_min < d["w"] < setting.w_max):
                continue
            if not (setting.h_min < d["h"] < setting.h_max):
                continue
            visible.append(d)
        return visible

    def _evaluate_judgment(self, visible_detections):
        counts = {}
        for d in visible_detections:
            counts[d["cls_id"]] = counts.get(d["cls_id"], 0) + 1

        details = []
        for cls_id, setting in self.class_settings.items():
            name = self.class_names.get(cls_id, str(cls_id))
            detected_count = counts.get(cls_id, 0)

            if setting.ok:
                required = setting.count
                res = "OK" if detected_count == required else "NG"
                details.append({
                    "class": name, "rule": f"OK nếu count == {required}",
                    "detected_count": detected_count, "result": res
                })
            elif setting.ng:
                res = "NG" if detected_count > 0 else "OK"
                details.append({
                    "class": name, "rule": "NG nếu xuất hiện",
                    "detected_count": detected_count, "result": res
                })

        if not details:
            return None, details

        overall = "OK" if all(d["result"] == "OK" for d in details) else "NG"
        return overall, details

    def _update_judge_panel(self, overall, details):
        if overall is None:
            self.lblOverallJudge.setText("Chưa có rule nào")
            self.lblOverallJudge.setProperty("role", "judge")
        elif overall == "OK":
            self.lblOverallJudge.setText("TỔNG: OK")
            self.lblOverallJudge.setProperty("role", "judge-ok")
        else:
            self.lblOverallJudge.setText("TỔNG: NG")
            self.lblOverallJudge.setProperty("role", "judge-ng")
        self._refresh_style(self.lblOverallJudge)

        self.txtJudgeDetail.clear()
        for d in details:
            line = f"[{d['result']}] {d['class']}  -  {d['rule']}  (detect: {d['detected_count']})\n"
            self.txtJudgeDetail.appendPlainText(line)

    def _redraw(self):
        if self.current_pil_image is None:
            self.lblImageView.clear()
            self.lblImageView.setText("Chưa có ảnh")
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
                big_font = ImageFont.truetype("arial.ttf", 46)
            except Exception:
                big_font = font
            badge_text = overall
            bg_col = (40, 167, 69) if overall == "OK" else (220, 53, 69)
            tb = draw.textbbox((0, 0), badge_text, font=big_font)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
            pad = 12
            draw.rectangle([12, 12, 12 + tw + pad * 2, 12 + th + pad * 2], fill=bg_col)
            draw.text((12 + pad, 12 + pad), badge_text, fill=(255, 255, 255), font=big_font)

        # Chuyển đổi PIL Image sang QPixmap
        data = img.tobytes("raw", "RGB")
        qimg = QtGui.QImage(data, img.width, img.height, img.width * 3, QtGui.QImage.Format_RGB888)
        self.rendered_pixmap = QtGui.QPixmap.fromImage(qimg)

        self._update_image_display()

    def _update_image_display(self):
        if self.rendered_pixmap is None or self.rendered_pixmap.isNull():
            return
        w = max(self.lblImageView.width(), 10)
        h = max(self.lblImageView.height(), 10)
        scaled = self.rendered_pixmap.scaled(w, h, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.lblImageView.setPixmap(scaled)

    # ====================================================================== #
    # TAB 2: TRAINING LOGIC (Hỗ trợ tùy chỉnh YOLOv8 và YOLOv8 trở lên)
    # ====================================================================== #

    def _on_yolo_version_changed(self):
        """Khi người dùng đổi phiên bản YOLO (YOLOv8, YOLOv9, YOLOv10, YOLO11, YOLOv12, Custom)."""
        if not hasattr(self, "comboYoloVersion"):
            return

        version = self.comboYoloVersion.currentText()
        cfg = YOLO_FAMILY_CONFIGS.get(version, YOLO_FAMILY_CONFIGS["YOLO11"])

        # Cập nhật danh sách scale tương ứng của dòng YOLO đó
        self.comboScale.blockSignals(True)
        self.comboScale.clear()
        self.comboScale.addItems(cfg["scales"])
        idx = self.comboScale.findText(cfg["default_scale"])
        if idx >= 0:
            self.comboScale.setCurrentIndex(idx)
        self.comboScale.blockSignals(False)

        # Cập nhật gợi ý file yaml và pt
        if version != "Tùy chỉnh (Custom)":
            self.editConfigYaml.setText(cfg["yaml"])
            self._update_pt_recommendation()

    def _on_scale_changed(self, scale_text):
        """Tự động cập nhật file weights .pt phù hợp khi thay đổi scale."""
        self._update_pt_recommendation()

    def _update_pt_recommendation(self):
        if not hasattr(self, "comboYoloVersion"):
            return
        version = self.comboYoloVersion.currentText()
        scale = self.comboScale.currentText()
        cfg = YOLO_FAMILY_CONFIGS.get(version)
        if not cfg or not cfg["prefix"]:
            return

        # Ví dụ: yolov8s.pt, yolov9s.pt, yolov10s.pt, yolo11s.pt, yolov12s.pt
        recommended_pt = f"{cfg['prefix']}{scale}.pt"
        self.editBaseModel.setText(recommended_pt)

    def _on_train_mode_changed(self):
        is_yaml = (self.comboTrainMode.currentIndex() == 0)
        self.lblYaml.setEnabled(is_yaml)
        self.editConfigYaml.setEnabled(is_yaml)
        self.btnBrowseYaml.setEnabled(is_yaml)
        self.lblScale.setEnabled(is_yaml)
        self.comboScale.setEnabled(is_yaml)
        self.lblScaleInfo.setEnabled(is_yaml)

        self.lblPt.setEnabled(not is_yaml)
        self.editBaseModel.setEnabled(not is_yaml)
        self.btnBrowsePt.setEnabled(not is_yaml)

    def _browse_train_dataset(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Chọn folder dataset (chứa images/ và labels/)")
        if d:
            self.editTrainDataset.setText(d)

    def _browse_config_yaml(self):
        f, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Chọn config kiến trúc model (.yaml)", "", "YAML config (*.yaml *.yml);;All Files (*.*)"
        )
        if f:
            self.editConfigYaml.setText(f)

    def _browse_base_model(self):
        f, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Chọn model weights (.pt)", "", "YOLO weights (*.pt);;All Files (*.*)"
        )
        if f:
            self.editBaseModel.setText(f)

    def _browse_train_savedir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu model sau khi train")
        if d:
            self.editSaveDir.setText(d)

    def _train_log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.txtTrainLog.appendPlainText(f"[{ts}] {msg}")

    def _set_train_status(self, text, role):
        self.lblTrainStatus.setText(text)
        self.lblTrainStatus.setProperty("role", role)
        self._refresh_style(self.lblTrainStatus)

    def start_training(self):
        if YOLO is None:
            QtWidgets.QMessageBox.critical(self, "Thiếu thư viện", "Chưa cài đặt ultralytics.")
            return

        dataset_dir = self.editTrainDataset.text().strip()
        if not dataset_dir or not os.path.isdir(dataset_dir):
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn thư mục dataset hợp lệ.")
            return

        save_dir = self.editSaveDir.text().strip()
        if not save_dir:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn thư mục lưu model sau khi train.")
            return
        os.makedirs(save_dir, exist_ok=True)

        save_name = self.editSaveName.text().strip() or "my_model"

        try:
            imgsz = self.spinImgsz.value()
            batch = self.spinBatch.value()
            epochs = self.spinEpochs.value()
            ratio = self.dspinRatio.value()
            assert 0.0 < ratio < 1.0

            device_str = self.editDevice.text().strip()
            if "," in device_str:
                device = [int(x.strip()) for x in device_str.split(",") if x.strip().isdigit()]
            elif device_str.isdigit():
                device = int(device_str)
            else:
                device = device_str

            workers = self.spinWorkers.value()
            patience = self.spinPatience.value()
            seed = self.spinSeed.value()

            hsv_h = self.dspinHsvH.value()
            hsv_s = self.dspinHsvS.value()
            hsv_v = self.dspinHsvV.value()
            scale_aug = self.dspinScaleAug.value()
            fliplr = self.dspinFliplr.value()
            mosaic = self.dspinMosaic.value()
            erasing = self.dspinErasing.value()

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi thông số", f"Thông số huấn luyện không hợp lệ: {e}")
            return

        version = self.comboYoloVersion.currentText() if hasattr(self, "comboYoloVersion") else "YOLO11"
        ver_cfg = YOLO_FAMILY_CONFIGS.get(version, {})
        prefix = ver_cfg.get("prefix", "yolo")

        params = {
            "mode": self.comboTrainMode.currentText(),
            "dataset_dir": dataset_dir,
            "config_yaml": self.editConfigYaml.text().strip() or "yolov8.yaml",
            "scale": self.comboScale.currentText().strip() or "n",
            "base_model": self.editBaseModel.text().strip() or "yolov8s.pt",
            "version_prefix": prefix,
            "imgsz": imgsz,
            "batch": batch,
            "epochs": epochs,
            "ratio": ratio,
            "device": device,
            "workers": workers,
            "patience": patience,
            "seed": seed,
            "hsv_h": hsv_h,
            "hsv_s": hsv_s,
            "hsv_v": hsv_v,
            "scale_aug": scale_aug,
            "fliplr": fliplr,
            "mosaic": mosaic,
            "erasing": erasing,
            "save_dir": save_dir,
            "save_name": save_name,
        }

        self.btnStartTrain.setEnabled(False)
        self._set_train_status("Đang huấn luyện ...", "status-warn")
        self.txtTrainLog.clear()

        self.train_thread = TrainWorker(params)
        self.train_thread.log_signal.connect(self._train_log)
        self.train_thread.status_signal.connect(self._set_train_status)
        self.train_thread.finished_signal.connect(self._on_train_finished)
        self.train_thread.start()

    def _on_train_finished(self, success, msg):
        self.btnStartTrain.setEnabled(True)
        if success:
            QtWidgets.QMessageBox.information(self, "Huấn luyện hoàn tất", msg)
        else:
            QtWidgets.QMessageBox.critical(self, "Lỗi huấn luyện", msg)

    # ====================================================================== #
    # TAB 3: AUTO LABEL LOGIC
    # ====================================================================== #

    def _al_load_model(self):
        if YOLO is None:
            QtWidgets.QMessageBox.critical(self, "Thiếu thư viện", "Chưa cài đặt ultralytics.")
            return

        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Chọn file model weights (.pt)", "", "YOLO weights (*.pt);;All Files (*.*)"
        )
        if not path:
            return

        self.lblAlModel.setText(f"Đang load: {os.path.basename(path)} ...")
        self.lblAlModel.setProperty("role", "status-neutral")
        self._refresh_style(self.lblAlModel)

        def worker():
            try:
                mdl = YOLO(path)
                return True, mdl, ""
            except Exception as e:
                return False, None, str(e)

        # Threading load
        self.al_load_thread = ModelLoadWorker(path)
        self.al_load_thread.finished_signal.connect(
            lambda success, mdl, err: self._on_al_model_loaded(success, mdl, err, path)
        )
        self.al_load_thread.start()

    def _on_al_model_loaded(self, success, model, err, path):
        if not success:
            self.lblAlModel.setText("Lỗi load model")
            self.lblAlModel.setProperty("role", "status-warn")
            self._refresh_style(self.lblAlModel)
            QtWidgets.QMessageBox.critical(self, "Lỗi load model", err)
            return

        self.al_model = model
        self.al_model_path = path
        self.al_class_names = dict(model.names)
        self.lblAlModel.setText(f"{os.path.basename(path)} ({len(self.al_class_names)} class)")
        self.lblAlModel.setProperty("role", "status-ok")
        self._refresh_style(self.lblAlModel)

        self._al_build_class_table()

    def _al_build_class_table(self):
        self.tableAlClasses.setRowCount(0)
        self.al_class_settings.clear()
        self.al_class_colors.clear()

        n = len(self.al_class_names)
        self.tableAlClasses.setRowCount(n)

        for row, (cls_id, name) in enumerate(sorted(self.al_class_names.items())):
            setting = ClassSetting()
            self.al_class_settings[cls_id] = setting
            color = gen_color(cls_id, n)
            self.al_class_colors[cls_id] = color

            # Col 0: Color icon
            pix = QtGui.QPixmap(14, 14)
            pix.fill(QtGui.QColor(*color))
            icon_item = QtWidgets.QTableWidgetItem(QtGui.QIcon(pix), "")
            icon_item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.tableAlClasses.setItem(row, 0, icon_item)

            # Col 1: Tạo nhãn (Checkable)
            chk_item = QtWidgets.QTableWidgetItem()
            chk_item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            chk_item.setCheckState(QtCore.Qt.Checked)
            chk_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.tableAlClasses.setItem(row, 1, chk_item)

            # Col 2: Class
            name_item = QtWidgets.QTableWidgetItem(name)
            name_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            self.tableAlClasses.setItem(row, 2, name_item)

            # Col 3: Conf
            sp_conf = QtWidgets.QDoubleSpinBox()
            sp_conf.setRange(0.0, 1.0)
            sp_conf.setSingleStep(0.01)
            sp_conf.setValue(0.25)
            sp_conf.setAlignment(QtCore.Qt.AlignCenter)
            sp_conf.valueChanged.connect(lambda val, s=setting: setattr(s, "conf", val))
            self.tableAlClasses.setCellWidget(row, 3, sp_conf)

            # Col 4: W min
            sp_wmin = QtWidgets.QSpinBox()
            sp_wmin.setRange(0, 100000)
            sp_wmin.setValue(0)
            sp_wmin.setAlignment(QtCore.Qt.AlignCenter)
            sp_wmin.valueChanged.connect(lambda val, s=setting: setattr(s, "w_min", val))
            self.tableAlClasses.setCellWidget(row, 4, sp_wmin)

            # Col 5: W max
            sp_wmax = QtWidgets.QSpinBox()
            sp_wmax.setRange(0, 100000)
            sp_wmax.setValue(99999)
            sp_wmax.setAlignment(QtCore.Qt.AlignCenter)
            sp_wmax.valueChanged.connect(lambda val, s=setting: setattr(s, "w_max", val))
            self.tableAlClasses.setCellWidget(row, 5, sp_wmax)

            # Col 6: H min
            sp_hmin = QtWidgets.QSpinBox()
            sp_hmin.setRange(0, 100000)
            sp_hmin.setValue(0)
            sp_hmin.setAlignment(QtCore.Qt.AlignCenter)
            sp_hmin.valueChanged.connect(lambda val, s=setting: setattr(s, "h_min", val))
            self.tableAlClasses.setCellWidget(row, 6, sp_hmin)

            # Col 7: H max
            sp_hmax = QtWidgets.QSpinBox()
            sp_hmax.setRange(0, 100000)
            sp_hmax.setValue(99999)
            sp_hmax.setAlignment(QtCore.Qt.AlignCenter)
            sp_hmax.valueChanged.connect(lambda val, s=setting: setattr(s, "h_max", val))
            self.tableAlClasses.setCellWidget(row, 7, sp_hmax)

        self.tableAlClasses.itemChanged.connect(self._on_al_table_item_changed)

    def _on_al_table_item_changed(self, item):
        if item.column() == 1:
            row = item.row()
            cls_ids = sorted(self.al_class_names.keys())
            if row < len(cls_ids):
                cid = cls_ids[row]
                self.al_class_settings[cid].enabled = (item.checkState() == QtCore.Qt.Checked)

    def _al_open_apply_all_dialog(self):
        if not self.al_class_settings:
            QtWidgets.QMessageBox.information(self, "Thông báo", "Vui lòng load model Auto Label trước.")
            return

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Áp dụng thông số Auto Label cho tất cả class")
        dlg.resize(320, 260)
        layout = QtWidgets.QFormLayout(dlg)

        sp_conf = QtWidgets.QDoubleSpinBox()
        sp_conf.setRange(0.0, 1.0)
        sp_conf.setSingleStep(0.01)
        sp_conf.setValue(0.25)
        layout.addRow("Conf:", sp_conf)

        sp_wmin = QtWidgets.QSpinBox()
        sp_wmin.setRange(0, 100000)
        sp_wmin.setValue(0)
        layout.addRow("W min:", sp_wmin)

        sp_wmax = QtWidgets.QSpinBox()
        sp_wmax.setRange(0, 100000)
        sp_wmax.setValue(99999)
        layout.addRow("W max:", sp_wmax)

        sp_hmin = QtWidgets.QSpinBox()
        sp_hmin.setRange(0, 100000)
        sp_hmin.setValue(0)
        layout.addRow("H min:", sp_hmin)

        sp_hmax = QtWidgets.QSpinBox()
        sp_hmax.setRange(0, 100000)
        sp_hmax.setValue(99999)
        layout.addRow("H max:", sp_hmax)

        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        layout.addRow(btn_box)

        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            conf_val = sp_conf.value()
            wmin_val = sp_wmin.value()
            wmax_val = sp_wmax.value()
            hmin_val = sp_hmin.value()
            hmax_val = sp_hmax.value()

            for row in range(self.tableAlClasses.rowCount()):
                w_conf = self.tableAlClasses.cellWidget(row, 3)
                w_wmin = self.tableAlClasses.cellWidget(row, 4)
                w_wmax = self.tableAlClasses.cellWidget(row, 5)
                w_hmin = self.tableAlClasses.cellWidget(row, 6)
                w_hmax = self.tableAlClasses.cellWidget(row, 7)
                if w_conf: w_conf.setValue(conf_val)
                if w_wmin: w_wmin.setValue(wmin_val)
                if w_wmax: w_wmax.setValue(wmax_val)
                if w_hmin: w_hmin.setValue(hmin_val)
                if w_hmax: w_hmax.setValue(hmax_val)

            for s in self.al_class_settings.values():
                s.conf = conf_val
                s.w_min = wmin_val
                s.w_max = wmax_val
                s.h_min = hmin_val
                s.h_max = hmax_val

    def _al_load_folder(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Chọn folder ảnh cần Auto Label")
        if d:
            self.al_folder = d
            self.lblAlFolder.setText(d)
            self.lblAlFolder.setProperty("role", "status-ok")
            self._refresh_style(self.lblAlFolder)

    def start_autolabel(self):
        if self.al_model is None:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng load model .pt trước.")
            return

        if not self.al_folder or not os.path.isdir(self.al_folder):
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn folder ảnh hợp lệ.")
            return

        base_conf = self.dspinAlBaseConf.value()
        self.btnAlStart.setEnabled(False)
        self.txtAlLog.clear()
        self.progressAl.setValue(0)

        self.al_thread = AutoLabelWorker(self.al_model, self.al_folder, base_conf, self.al_class_settings)
        self.al_thread.log_signal.connect(self._al_log)
        self.al_thread.progress_signal.connect(lambda cur, tot: self._update_al_progress(cur, tot))
        self.al_thread.finished_signal.connect(self._on_al_finished)
        self.al_thread.start()

    def _al_log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.txtAlLog.appendPlainText(f"[{ts}] {msg}")

    def _update_al_progress(self, current, total):
        self.progressAl.setMaximum(total)
        self.progressAl.setValue(current)

    def _on_al_finished(self, success, msg):
        self.btnAlStart.setEnabled(True)
        if success:
            QtWidgets.QMessageBox.information(self, "Auto Label hoàn tất", msg)
        else:
            QtWidgets.QMessageBox.critical(self, "Lỗi Auto Label", msg)

    # ====================================================================== #
    # TAB 4: CROP IMAGE & LABEL LOGIC
    # ====================================================================== #

    def _browse_crop_input(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Chọn folder ảnh đầu vào")
        if d:
            self.editCropInput.setText(d)

    def _browse_crop_output(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Chọn folder lưu kết quả cắt")
        if d:
            self.editCropOutput.setText(d)

    def _crop_log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.txtCropLog.appendPlainText(f"[{ts}] {msg}")

    def start_cropping(self):
        in_dir = self.editCropInput.text().strip()
        out_dir = self.editCropOutput.text().strip()

        if not in_dir or not os.path.isdir(in_dir):
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn folder đầu vào hợp lệ.")
            return

        if not out_dir:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn folder đầu ra.")
            return

        target_w = self.spinCropWidth.value()
        target_h = self.spinCropHeight.value()
        offset_y = self.spinCropOffset.value()

        self.btnCropStart.setEnabled(False)
        self.lblCropStatus.setText("Đang xử lý ...")
        self.lblCropStatus.setProperty("role", "status-warn")
        self._refresh_style(self.lblCropStatus)
        self.txtCropLog.clear()
        self.progressCrop.setValue(0)

        self.crop_thread = CropWorker(in_dir, out_dir, target_w, target_h, offset_y)
        self.crop_thread.log_signal.connect(self._crop_log)
        self.crop_thread.progress_signal.connect(lambda cur, tot: self._update_crop_progress(cur, tot))
        self.crop_thread.finished_signal.connect(self._on_crop_finished)
        self.crop_thread.start()

    def _update_crop_progress(self, current, total):
        self.progressCrop.setMaximum(total)
        self.progressCrop.setValue(current)

    def _on_crop_finished(self, success, msg):
        self.btnCropStart.setEnabled(True)
        if success:
            self.lblCropStatus.setText("Hoàn tất!")
            self.lblCropStatus.setProperty("role", "status-ok")
            QtWidgets.QMessageBox.information(self, "Cắt ảnh & nhãn hoàn tất", msg)
        else:
            self.lblCropStatus.setText("Lỗi!")
            self.lblCropStatus.setProperty("role", "status-warn")
            QtWidgets.QMessageBox.critical(self, "Lỗi", msg)
        self._refresh_style(self.lblCropStatus)


# ========================================================================== #
# Main Entry Point
# ========================================================================== #

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = YoloStudioApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
