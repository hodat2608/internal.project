import math
import os
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image, ImageEnhance

# Hệ số quy đổi Pixel sang Millimeter (mm/pixel)
PX_VALUE_DEFAULT = 0.00877

# Bảng màu công nghiệp theo không gian RGB (tương thích trực tiếp với QImage.Format_RGB888)
COLOR_OK = (34, 197, 94)          # Xanh lá Emerald (OK / Pass)
COLOR_NG = (239, 68, 68)          # Đỏ Crimson (NG / Fail)
COLOR_WARN = (245, 158, 11)       # Vàng Hổ Phách (Warning / Iris limit)
COLOR_INFO = (56, 189, 248)       # Xanh Sky Cyan (Reference Circle)
COLOR_TEXT_MAIN = (248, 250, 252) # Trắng sáng Slate
COLOR_TEXT_MUTED = (148, 163, 184)# Xám nhạt Slate
COLOR_PANEL_BG = (15, 23, 42)     # Nền tối Slate-900 (cho HUD Card)
COLOR_PANEL_BORDER = (51, 65, 85) # Viền thẻ Slate-700


def _parse_val(v: Any, default: float = 0.0) -> float:
    """Chuyển đổi an toàn giá trị chuỗi/số/None sang float, tránh lỗi crash do ký tự rỗng '-'."""
    if v is None or v == "-" or v == "":
        return float(default)
    try:
        return float(v)
    except (ValueError, TypeError):
        return float(default)


def _parse_range(data_dict: dict, key: str, def_min: float = 0.0, def_max: float = 999999.0) -> Tuple[float, float]:
    """Trích xuất ngưỡng [min, max] an toàn từ từ điển cấu hình."""
    if not isinstance(data_dict, dict):
        return def_min, def_max
    raw = data_dict.get(key, [def_min, def_max])
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        return def_min, def_max
    return _parse_val(raw[0], def_min), _parse_val(raw[1], def_max)


def _draw_transparent_rect(
    img: np.ndarray,
    pt1: Tuple[int, int],
    pt2: Tuple[int, int],
    color: Tuple[int, int, int],
    alpha: float = 0.4
) -> None:
    """Vẽ hình chữ nhật bán trong suốt trên ảnh để làm nổi bật vùng quan sát hoặc tạo thẻ HUD."""
    x1, y1 = max(0, min(pt1[0], pt2[0])), max(0, min(pt1[1], pt2[1]))
    x2, y2 = min(img.shape[1], max(pt1[0], pt2[0])), min(img.shape[0], max(pt1[1], pt2[1]))
    if x2 <= x1 or y2 <= y1:
        return
    sub = img[y1:y2, x1:x2]
    overlay = np.full(sub.shape, color, dtype=np.uint8)
    img[y1:y2, x1:x2] = cv2.addWeighted(sub, 1.0 - alpha, overlay, alpha, 0)


def _draw_text_with_shadow(
    img: np.ndarray,
    text: str,
    pos: Tuple[int, int],
    font_scale: float,
    color: Tuple[int, int, int],
    thickness: int = 2,
    shadow_color: Tuple[int, int, int] = (0, 0, 0)
) -> None:
    """Vẽ chữ có bóng đen đổ viền chống lóa giúp đọc rõ trên mọi nền ảnh sáng/tối."""
    x, y = pos
    cv2.putText(img, text, (x + 2, y + 2), cv2.FONT_HERSHEY_SIMPLEX, font_scale, shadow_color, thickness + 2, cv2.LINE_AA)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness, cv2.LINE_AA)


def _draw_roi_badge(
    img: np.ndarray,
    title: str,
    sub: str,
    x: int,
    y: int,
    is_ok: bool,
    scale: float
) -> None:
    """Vẽ nhãn thẻ nhỏ (badge pill) gắn liền với từng vùng chữ nhật ROI với font to, viền dày."""
    h, w = img.shape[:2]
    color = COLOR_OK if is_ok else COLOR_NG
    fs_t = max(0.48, 0.62 * scale)
    fs_s = max(0.42, 0.52 * scale)
    th = max(2, int(1.8 * scale))

    (tw, th_t), _ = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, fs_t, th)
    (sw, th_s), _ = cv2.getTextSize(sub, cv2.FONT_HERSHEY_SIMPLEX, fs_s, 1)

    bw = max(tw, sw) + int(20 * scale)
    bh = th_t + th_s + int(18 * scale)

    bx = max(5, min(w - bw - 5, x))
    by = max(5, min(h - bh - 5, y))

    # Khung nền tối mờ
    _draw_transparent_rect(img, (bx, by), (bx + bw, by + bh), COLOR_PANEL_BG, alpha=0.84)
    cv2.rectangle(img, (bx, by), (bx + bw, by + bh), color, max(2, int(2.0 * scale)), cv2.LINE_AA)

    # In tiêu đề và thông số con
    t_y = by + th_t + int(6 * scale)
    s_y = t_y + th_s + int(7 * scale)
    _draw_text_with_shadow(img, title, (bx + int(10 * scale), t_y), fs_t, color, th)
    _draw_text_with_shadow(img, sub, (bx + int(10 * scale), s_y), fs_s, COLOR_TEXT_MAIN, max(1, int(1.3 * scale)))


class KiemGuong:
    """
    Bộ xử lý Kiểm tra Gương chuyên dụng trong môi trường công nghiệp (Mirror Inspection Engine).
    Đánh giá toàn diện:
    1. Vị trí tâm gương (Centroid X, Y)
    2. Bán kính đường tròn gương (Radius mm & px)
    3. Độ sáng (Iris / Brightness) trên 4 vùng mép (ROI 1..4)
    4. Độ nét / Tiêu cự (Focus / Sharpness) trên 4 vùng mép (ROI 1..4)
    Trực quan hóa trực tiếp lên ảnh với đường tròn, tâm, các ROI chữ nhật và Bảng điều khiển HUD.
    """

    def __init__(self, MIRROR_DATA: Dict[str, Any], CONFIG_RADIUS: Dict[str, Any]):
        self.MIRROR_DATA = MIRROR_DATA or {}
        self.CONFIG_RADIUS = CONFIG_RADIUS or {}

        # 1. Ngưỡng Tâm và Bán kính
        self.center_x_min, self.center_x_max = _parse_range(self.MIRROR_DATA, 'Center X', 0.0, 999999.0)
        self.center_y_min, self.center_y_max = _parse_range(self.MIRROR_DATA, 'Center Y', 0.0, 999999.0)
        self.radius_min, self.radius_max = _parse_range(self.MIRROR_DATA, 'Circle Radius', 0.0, 999999.0)

        # 2. Cấu hình quét mép
        self.radius_ref = _parse_val(self.CONFIG_RADIUS.get('radius_ref'), 350.0)
        self.delta = _parse_val(self.CONFIG_RADIUS.get('delta'), 40.0)
        self.px_value = _parse_val(self.CONFIG_RADIUS.get('px_value'), PX_VALUE_DEFAULT)

        # 3. Ngưỡng Iris & Focus cho 4 ROI
        self.iris_ranges: Dict[int, Tuple[float, float]] = {}
        self.focus_ranges: Dict[int, Tuple[float, float]] = {}
        for i in range(1, 5):
            self.iris_ranges[i] = _parse_range(self.MIRROR_DATA, f'Iris {i}', 0.0, 255.0)
            self.focus_ranges[i] = _parse_range(self.MIRROR_DATA, f'Focus {i}', 0.0, 999999.0)

        self.roi_coords: List[Tuple[int, int, int, int]] = []

    def inSideCircle(self, point: Tuple[int, int], center: Tuple[int, int], radius: float) -> bool:
        """Kiểm tra điểm có nằm trong hình tròn hay không."""
        return (point[0] - center[0])**2 + (point[1] - center[1])**2 < radius**2

    def measure_light_rectangle(self, img: np.ndarray) -> float:
        """Đo độ sáng trung bình vùng chữ nhật."""
        if img is None or img.size == 0:
            return 0.0
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
        return float(gray.mean())

    def measure_light_circle(self, img: np.ndarray, center: Tuple[int, int], radius: int) -> float:
        """Đo độ sáng trung bình bên trong vùng hình tròn."""
        if img is None or img.size == 0 or radius <= 0:
            return 0.0
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
        mask = np.zeros(gray.shape[:2], np.uint8)
        cv2.circle(mask, center, int(radius), 255, cv2.FILLED)
        vals = gray[mask == 255]
        return float(vals.mean()) if len(vals) > 0 else 0.0

    def shapenessLaplacian(self, img: np.ndarray) -> float:
        """Alias cho hàm đo độ nét Laplacian."""
        return self.sharpnessLaplacian(img)

    def sharpnessLaplacian(self, img: np.ndarray) -> float:
        """Đo độ nét theo phương sai toán tử Laplacian (phương pháp chuẩn công nghiệp)."""
        if img is None or img.size == 0:
            return 0.0
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        return float(np.var(laplacian))

    def sharpnessTenengrad(self, img: np.ndarray) -> float:
        """Đo độ nét theo Tenengrad gradient squared."""
        if img is None or img.size == 0:
            return 0.0
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
        gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        return float(np.sum(gx**2 + gy**2))

    def sharpnessSobel(self, img: np.ndarray) -> float:
        """Đo độ nét theo tổng độ dốc Sobel tuyệt đối."""
        if img is None or img.size == 0:
            return 0.0
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
        gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        return float(np.mean(cv2.convertScaleAbs(gx)) + np.mean(cv2.convertScaleAbs(gy)))

    def frequency_based_sharpness(self, img: np.ndarray) -> float:
        """Đo độ nét trong miền tần số FFT."""
        if img is None or img.size == 0:
            return 0.0
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
        f = np.fft.fft2(gray)
        fshift = np.fft.fftshift(f)
        magnitude = np.log(1 + np.abs(fshift))
        return float(np.mean(magnitude))

    def convert_to_binary(self, img: np.ndarray, threshold: int) -> np.ndarray:
        """Nhị phân hóa ảnh."""
        _, binary = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY)
        return binary

    def shift_image(self, img: np.ndarray, shift_x: float, shift_y: float) -> np.ndarray:
        """Dịch chuyển ảnh theo ma trận affine."""
        h, w = img.shape[:2]
        mat = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
        return cv2.warpAffine(img, mat, (w, h))

    def blur(self, img: np.ndarray, blur_amount: int) -> np.ndarray:
        """Làm mờ ảnh bằng Gaussian Blur."""
        k = max(1, blur_amount | 1)
        return cv2.GaussianBlur(img, (k, k), 0)

    def calculate_distance(self, x1: float, y1: float, x2: float, y2: float) -> float:
        """Tính khoảng cách Euclid giữa 2 điểm."""
        return math.hypot(x2 - x1, y2 - y1)

    def location(self, img: np.ndarray) -> Tuple[int, int, int]:
        """Phương pháp dự phòng phát hiện vị trí vòng tròn qua HoughCircles."""
        a, b, r = 0, 0, 0
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            binary = ~self.convert_to_binary(blurred, 170)
            circles = cv2.HoughCircles(
                binary, cv2.HOUGH_GRADIENT, 0.3, 1,
                param1=1, param2=50, minRadius=int(self.radius_ref - 50), maxRadius=int(self.radius_ref + 50)
            )
            if circles is not None:
                circles = np.uint16(np.around(circles))
                for pt in circles[0, :]:
                    a, b, r = int(pt[0]), int(pt[1]), int(pt[2])
                    break
        except Exception as error:
            print("[KiemGuong.location] Error:", error)
        return a, b, r

    def select_ROI(self, img: np.ndarray, radius: float, delta: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Cắt 4 vùng chữ nhật (ROI 1: Top, ROI 2: Right, ROI 3: Bottom, ROI 4: Left).
        Đảm bảo an toàn không bị tràn biên kích thước ảnh.
        """
        h, w = img.shape[:2]
        cx, cy = w // 2, h // 2
        r, d = int(round(radius)), int(round(delta))

        coords = [
            # ROI 1: Top
            (max(0, cx - d), max(0, cy - (r + d)), min(w, cx + d), min(h, cy - (r - d))),
            # ROI 2: Right
            (max(0, cx + (r - d)), max(0, cy - d), min(w, cx + (r + d)), min(h, cy + d)),
            # ROI 3: Bottom
            (max(0, cx - d), max(0, cy + (r - d)), min(w, cx + d), min(h, cy + (r + d))),
            # ROI 4: Left
            (max(0, cx - (r + d)), max(0, cy - d), min(w, cx - (r - d)), min(h, cy + d)),
        ]
        self.roi_coords = coords

        crops = []
        for x1, y1, x2, y2 in coords:
            if x2 > x1 and y2 > y1:
                crops.append(img[y1:y2, x1:x2].copy())
            else:
                crops.append(np.zeros((10, 10, 3), dtype=np.uint8))
        return tuple(crops)

    def scan_edge_position(self, img: np.ndarray, roi: int = 1) -> Tuple[np.ndarray, list, list]:
        """
        Quét tọa độ điểm biên trên từng ROI.
        Đã sửa lỗi copy-paste ep12 -> ep11 từ phiên bản cũ.
        """
        h, w = img.shape[:2]
        ep1, ep2 = [], []
        if h <= 0 or w <= 0:
            return img, ep1, ep2

        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
        _, binary = cv2.threshold(gray, 225, 255, cv2.THRESH_BINARY)

        if roi == 1:  # Top (quét từ trên xuống)
            x1, x2 = w // 4, w - w // 4
            for y in range(h):
                if binary[y, x1] == 0:
                    ep1.append((x1, y))
                    break
            for y in range(h):
                if binary[y, x2] == 0:
                    ep2.append((x2, y))
                    break
        elif roi == 2:  # Right (quét từ phải sang trái)
            y1, y2 = h // 4, h - h // 4
            for x in range(w - 1, -1, -1):
                if binary[y1, x] == 0:
                    ep1.append((x, y1))
                    break
            for x in range(w - 1, -1, -1):
                if binary[y2, x] == 0:
                    ep2.append((x, y2))
                    break
        elif roi == 3:  # Bottom (quét từ dưới lên)
            x1, x2 = w // 4, w - w // 4
            for y in range(h - 1, -1, -1):
                if binary[y, x1] == 0:
                    ep1.append((x1, y))
                    break
            for y in range(h - 1, -1, -1):
                if binary[y, x2] == 0:
                    ep2.append((x2, y))
                    break
        elif roi == 4:  # Left (quét từ trái sang phải)
            y1, y2 = h // 4, h - h // 4
            for x in range(w):
                if binary[y1, x] == 0:
                    ep1.append((x, y1))
                    break
            for x in range(w):
                if binary[y2, x] == 0:
                    ep2.append((x, y2))
                    break

        return img, ep1, ep2

    def detect_circle(self, img: np.ndarray, radius: float, delta: float) -> Tuple[int, int, list]:
        """
        Dò tìm bán kính và tâm hình tròn qua 4 ROI biên.
        Trả về (center_x, center_y, danh sách bán kính thu thập).
        """
        h, w = img.shape[:2]
        centroid = (w // 2, h // 2)
        crops = self.select_ROI(img, radius, delta)
        coords = getattr(self, 'roi_coords', [])
        radius_filter = []

        for i, crop in enumerate(crops, start=1):
            if crop.size == 0 or i > len(coords):
                continue
            x1_min, y1_min, _, _ = coords[i - 1]
            _, ep1, ep2 = self.scan_edge_position(crop, roi=i)
            if ep1:
                pt1 = (ep1[0][0] + x1_min, ep1[0][1] + y1_min)
                radius_filter.append(self.calculate_distance(pt1[0], pt1[1], centroid[0], centroid[1]))
            if ep2:
                pt2 = (ep2[0][0] + x1_min, ep2[0][1] + y1_min)
                radius_filter.append(self.calculate_distance(pt2[0], pt2[1], centroid[0], centroid[1]))

        return centroid[0], centroid[1], radius_filter

    def run(self, img: np.ndarray) -> Tuple[np.ndarray, bool, Dict[str, Any]]:
        """
        QUY TRÌNH KIỂM TRA GƯƠNG TOÀN DIỆN (Comprehensive Mirror Inspection).
        1. Kiểm tra vị trí tâm gương (Centroid X, Y).
        2. Kiểm tra bán kính vòng tròn (Circle Radius).
        3. Kiểm tra độ sáng (Iris / Brightness) trên 4 ROI.
        4. Kiểm tra độ nét (Focus / Sharpness) trên 4 ROI.
        5. Trực quan hóa hình vẽ với viền dày dặn, font chữ to rõ, bảng HUD mở rộng dễ nhìn.
        
        Trả về: (img_draw, results_flag, dict_data)
        """
        if img is None or img.size == 0:
            empty_draw = np.zeros((400, 600, 3), dtype=np.uint8)
            return empty_draw, False, {}

        self.img = img
        self.img_draw = img.copy()
        h, w = img.shape[:2]

        # Tỷ lệ co giãn trực quan: cỡ to, chữ đậm, viền dày
        scale = max(0.60, min(w / 1920.0, h / 1080.0))
        font_scale = max(0.55, 0.72 * scale)          # Font thông số to rõ
        font_scale_title = max(0.72, 0.96 * scale)    # Tiêu đề nổi bật
        thickness = max(2, int(2.2 * scale))          # Nét chữ đậm đà
        line_spacing = int(34 * scale)                # Giãn dòng rộng rãi

        # -------------------------------------------------------------------
        # BƯỚC 1: DÒ TÌM & ĐÁNH GIÁ TÂM + BÁN KÍNH
        # -------------------------------------------------------------------
        center_x, center_y, radius_filter = self.detect_circle(img, self.radius_ref, self.delta)

        if radius_filter:
            detected_radius = float(np.median(radius_filter))
        else:
            detected_radius = 0.0

        center_x_ok = (self.center_x_min <= center_x <= self.center_x_max)
        center_y_ok = (self.center_y_min <= center_y <= self.center_y_max)
        center_ok = center_x_ok and center_y_ok

        radius_has_points = (len(radius_filter) >= 4)
        radius_in_range = (self.radius_min <= detected_radius <= self.radius_max)
        radius_ok = radius_has_points and radius_in_range

        # -------------------------------------------------------------------
        # BƯỚC 2: CẮT 4 VÙNG ROI & ĐO IRIS + FOCUS
        # -------------------------------------------------------------------
        crops = self.select_ROI(img, self.radius_ref, self.delta)
        roi_coords = getattr(self, 'roi_coords', [])
        roi_names = ["ROI 1 (Top)", "ROI 2 (Right)", "ROI 3 (Bottom)", "ROI 4 (Left)"]

        iris_vals: Dict[int, int] = {}
        focus_vals: Dict[int, float] = {}
        iris_ok_map: Dict[int, bool] = {}
        focus_ok_map: Dict[int, bool] = {}
        roi_ok_map: Dict[int, bool] = {}

        for i, crop in enumerate(crops, start=1):
            # Đo độ sáng
            b_val = math.ceil(self.measure_light_rectangle(crop))
            iris_min, iris_max = self.iris_ranges[i]
            b_ok = (iris_min <= b_val <= iris_max)

            # Đo độ nét
            f_val = round(self.sharpnessLaplacian(crop), 1)
            f_min, f_max = self.focus_ranges[i]
            f_ok = (f_val >= f_min)
            if f_max < 999000.0:
                f_ok = f_ok and (f_val <= f_max)

            iris_vals[i] = b_val
            focus_vals[i] = f_val
            iris_ok_map[i] = b_ok
            focus_ok_map[i] = f_ok
            roi_ok_map[i] = b_ok and f_ok

        # Kết quả tổng thể: ĐẠT khi TẤT CẢ các tiêu chí đều đạt
        overall_ok = center_ok and radius_ok and all(roi_ok_map.values())

        # -------------------------------------------------------------------
        # BƯỚC 3: TRỰC QUAN HÓA CÁC ĐỐI TƯỢNG HÌNH HỌC LÊN ẢNH (VIỀN DÀY RÕ RỆT)
        # -------------------------------------------------------------------

        # (A) Vẽ chữ thập tâm và chấm tâm to rõ
        center_color = COLOR_OK if center_ok else COLOR_NG
        circle_color = COLOR_OK if radius_ok else COLOR_NG
        cross_len = int(35 * scale)
        cross_thick = max(3, int(4.0 * scale))

        cv2.line(
            self.img_draw,
            (center_x - cross_len, center_y), (center_x + cross_len, center_y),
            center_color, cross_thick, cv2.LINE_AA
        )
        cv2.line(
            self.img_draw,
            (center_x, center_y - cross_len), (center_x, center_y + cross_len),
            center_color, cross_thick, cv2.LINE_AA
        )
        cv2.circle(self.img_draw, (center_x, center_y), max(7, int(8 * scale)), center_color, -1, cv2.LINE_AA)

        # (B) Vẽ vòng tròn gương: Viền dày 5px nổi bật
        if detected_radius > 0:
            circle_thick = max(4, int(5.0 * scale))
            cv2.circle(
                self.img_draw,
                (center_x, center_y), int(round(detected_radius)),
                circle_color, circle_thick, cv2.LINE_AA
            )
            # Đường tròn tham chiếu
            if self.radius_ref > 0 and abs(self.radius_ref - detected_radius) > 3:
                cv2.circle(
                    self.img_draw,
                    (center_x, center_y), int(round(self.radius_ref)),
                    COLOR_INFO, max(2, int(2.5 * scale)), cv2.LINE_AA
                )

        # (C) Vẽ 4 Vùng Chữ Nhật ROI: Viền dày 4.5px + Thẻ nhãn to rõ
        for i, coords in enumerate(roi_coords, start=1):
            x1, y1, x2, y2 = coords
            is_ok = roi_ok_map[i]
            rect_color = COLOR_OK if is_ok else COLOR_NG
            rect_thick = max(3, int(4.5 * scale))

            # Nếu lỗi NG: tô lớp màu đỏ mờ cảnh báo bên trong vùng ROI
            if not is_ok:
                _draw_transparent_rect(self.img_draw, (x1, y1), (x2, y2), COLOR_NG, alpha=0.30)

            # Vẽ viền hình chữ nhật dày
            cv2.rectangle(self.img_draw, (x1, y1), (x2, y2), rect_color, rect_thick, cv2.LINE_AA)

            # Nhãn thẻ hiển thị trên/dưới ROI
            status_txt = "OK" if is_ok else "NG"
            badge_title = f"{roi_names[i-1]} [{status_txt}]"
            badge_sub = f"B:{iris_vals[i]} | F:{int(focus_vals[i])}"

            if i == 1:   # Top -> đặt phía trên box
                bx, by = x1 - int(15 * scale), y1 - int(64 * scale)
            elif i == 3: # Bottom -> đặt phía dưới box
                bx, by = x1 - int(15 * scale), y2 + int(14 * scale)
            elif i == 2: # Right -> đặt bên phải box
                bx, by = x2 + int(14 * scale), y1 - int(15 * scale)
            else:        # Left -> đặt bên trái box
                bx, by = x1 - int(210 * scale), y1 - int(15 * scale)

            _draw_roi_badge(self.img_draw, badge_title, badge_sub, bx, by, is_ok, scale)

        # -------------------------------------------------------------------
        # BƯỚC 4: BẢNG HUD DASHBOARD TỔNG HỢP: MỞ RỘNG TO RÕ, DỄ NHÌN
        # -------------------------------------------------------------------
        panel_w = int(620 * scale)  # Mở rộng kích thước ngang
        panel_h = int(420 * scale)  # Mở rộng kích thước dọc
        panel_x = int(25 * scale)
        panel_y = int(25 * scale)

        # Khung nền bán trong suốt chống chói
        _draw_transparent_rect(
            self.img_draw,
            (panel_x, panel_y), (panel_x + panel_w, panel_y + panel_h),
            COLOR_PANEL_BG, alpha=0.88
        )
        panel_border_color = COLOR_OK if overall_ok else COLOR_NG
        panel_border_thick = max(3, int(4.0 * scale))
        cv2.rectangle(
            self.img_draw,
            (panel_x, panel_y), (panel_x + panel_w, panel_y + panel_h),
            panel_border_color, panel_border_thick, cv2.LINE_AA
        )

        cur_y = panel_y + int(42 * scale)
        left_pad = panel_x + int(22 * scale)

        # Tiêu đề kết quả chung font to đậm
        if overall_ok:
            _draw_text_with_shadow(
                self.img_draw,
                "[ PASS / OK ] - KIEM GUONG DAT",
                (left_pad, cur_y), font_scale_title, COLOR_OK, thickness + 1
            )
        else:
            _draw_text_with_shadow(
                self.img_draw,
                "[ FAIL / NG ] - PHAT HIEN LOI",
                (left_pad, cur_y), font_scale_title, COLOR_NG, thickness + 1
            )

        # Đường kẻ phân cách dày
        cur_y += int(16 * scale)
        cv2.line(self.img_draw, (panel_x + 14, cur_y), (panel_x + panel_w - 14, cur_y), COLOR_PANEL_BORDER, max(2, int(2.0 * scale)), cv2.LINE_AA)
        cur_y += int(30 * scale)

        # Dòng 1: Kiểm tra Tâm gương
        c_status_txt = "OK" if center_ok else "NG"
        c_status_col = COLOR_OK if center_ok else COLOR_NG
        _draw_text_with_shadow(self.img_draw, "Tam Guong (X, Y):", (left_pad, cur_y), font_scale, COLOR_TEXT_MUTED, thickness)
        _draw_text_with_shadow(self.img_draw, f"({center_x}, {center_y})", (left_pad + int(225 * scale), cur_y), font_scale, COLOR_TEXT_MAIN, thickness)
        _draw_text_with_shadow(self.img_draw, f"[{c_status_txt}]", (panel_x + panel_w - int(75 * scale), cur_y), font_scale, c_status_col, thickness + 1)
        cur_y += line_spacing

        # Dòng 2: Kiểm tra Bán kính
        r_status_txt = "OK" if radius_ok else "NG"
        r_status_col = COLOR_OK if radius_ok else COLOR_NG
        radius_mm = round(detected_radius * self.px_value, 2)
        _draw_text_with_shadow(self.img_draw, "Ban Kinh (Radius):", (left_pad, cur_y), font_scale, COLOR_TEXT_MUTED, thickness)
        _draw_text_with_shadow(self.img_draw, f"{round(detected_radius)} px (~{radius_mm}mm)", (left_pad + int(225 * scale), cur_y), font_scale, COLOR_TEXT_MAIN, thickness)
        _draw_text_with_shadow(self.img_draw, f"[{r_status_txt}]", (panel_x + panel_w - int(75 * scale), cur_y), font_scale, r_status_col, thickness + 1)
        cur_y += line_spacing

        # Đường phân cách phụ trước danh sách ROI
        cur_y += int(6 * scale)
        cv2.line(self.img_draw, (panel_x + 14, cur_y), (panel_x + panel_w - 14, cur_y), COLOR_PANEL_BORDER, max(2, int(2.0 * scale)), cv2.LINE_AA)
        cur_y += int(26 * scale)

        # Dòng 3-6: Chi tiết 4 ROI (Giá trị đạt chữ XANH, lỗi chữ ĐỎ)
        for i in range(1, 5):
            roi_ok = roi_ok_map[i]
            roi_status_txt = "OK" if roi_ok else "NG"
            roi_status_col = COLOR_OK if roi_ok else COLOR_NG

            b_col = COLOR_OK if iris_ok_map[i] else COLOR_NG
            f_col = COLOR_OK if focus_ok_map[i] else COLOR_NG

            _draw_text_with_shadow(self.img_draw, f"ROI {i}:", (left_pad, cur_y), font_scale, COLOR_TEXT_MUTED, thickness)
            _draw_text_with_shadow(self.img_draw, f"Iris: {iris_vals[i]}", (left_pad + int(100 * scale), cur_y), font_scale, b_col, thickness)
            _draw_text_with_shadow(self.img_draw, f"Focus: {int(focus_vals[i])}", (left_pad + int(290 * scale), cur_y), font_scale, f_col, thickness)
            _draw_text_with_shadow(self.img_draw, f"[{roi_status_txt}]", (panel_x + panel_w - int(75 * scale), cur_y), font_scale, roi_status_col, thickness + 1)

            cur_y += line_spacing

        # -------------------------------------------------------------------
        # BƯỚC 5: ĐÓNG GÓI DICT DATA TƯƠNG THÍCH HOÀN TOÀN HỆ THỐNG
        # -------------------------------------------------------------------
        dict_data = {
            'center_x': int(round(center_x)),
            'center_y': int(round(center_y)),
            'radius': int(round(detected_radius)),
            'delta': int(round(self.delta)),
            'brightness_roi1': int(iris_vals[1]),
            'brightness_roi2': int(iris_vals[2]),
            'brightness_roi3': int(iris_vals[3]),
            'brightness_roi4': int(iris_vals[4]),
            'sharpness_roi1': int(round(focus_vals[1])),
            'sharpness_roi2': int(round(focus_vals[2])),
            'sharpness_roi3': int(round(focus_vals[3])),
            'sharpness_roi4': int(round(focus_vals[4])),
            'status_center': center_ok,
            'status_radius': radius_ok,
            'status_roi1': roi_ok_map[1],
            'status_roi2': roi_ok_map[2],
            'status_roi3': roi_ok_map[3],
            'status_roi4': roi_ok_map[4],
            'overall_result': overall_ok,
        }

        return self.img_draw, overall_ok, dict_data


def display_images(image1: np.ndarray, image2: np.ndarray) -> None:
    """Hiển thị 2 ảnh cạnh nhau trên cùng một cửa sổ để so sánh trực quan."""
    height = 700
    h1, w1 = image1.shape[:2]
    h2, w2 = image2.shape[:2]
    img1_res = cv2.resize(image1, (int(w1 * height / h1), height))
    img2_res = cv2.resize(image2, (int(w2 * height / h2), height))

    combined = cv2.hconcat([img1_res, img2_res])
    cv2.namedWindow("Images", cv2.WINDOW_NORMAL)
    cv2.imshow('Images', combined)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def adjust_brightness(image_path: str, brightness_factor: float) -> None:
    """Điều chỉnh độ sáng ảnh và lưu ra tệp."""
    if not os.path.exists(image_path):
        return
    image = Image.open(image_path)
    enhancer = ImageEnhance.Brightness(image)
    adjusted_image = enhancer.enhance(brightness_factor)
    out_dir = os.path.join("..", "images", "brightness")
    os.makedirs(out_dir, exist_ok=True)
    adjusted_image.save(os.path.join(out_dir, f"{brightness_factor}.jpg"), quality=100)
