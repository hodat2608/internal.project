# -*- coding: utf-8 -*-
"""
mirror_widget.py
=================
Ban hop nhat: CrosshairLabel ho tro CA 2 yeu cau:
  1) Show Cross / Drag Cross / Show Grid hoat dong duoc KHONG CAN co anh
     (canvas trong khi chua browse file, chua streaming)
  2) Ho tro Live Stream tu camera (driver ghi thang vao QLabel qua setPixmap())

self.ui_mirror_tab.label_display_image o day chinh la instance CrosshairLabel
duoc tao ra va gan de (monkey-patch) vao thay cho QLabel goc trong setupUi.
"""

import cv2
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QRect, QPointF, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QFont
from PyQt5.QtWidgets import QLabel, QSizePolicy, QMessageBox
from module_3.mirror_test import KiemGuong

# Neu cac hang mau/cau hinh nay da khai bao san o noi khac trong project,
# xoa doan duoi day di de tranh dinh nghia trung ten.
COLOR_BG = "#101116"
COLOR_CROSS = "#FF7A1A"
COLOR_CROSS_ACTIVE = "#FFC400"
COLOR_GRID_V = "#E8342E"
COLOR_GRID_H = "#5A5C68"
GRID_COLS = 16
GRID_ROWS = 10

class SignalTable:
    def __init__(self, table_widget):
        self.table_center_mirror = table_widget.tableWidget_center_mirror
        self.table_iris = table_widget.tableWidget_iris
        self.table_focuss = table_widget.tableWidget_focuss

        self.rows_center_mirror = {
            'center_x': 0,
            'center_y': 1,
            'circle_radius':2,
            'radius_ref': 3,
            'delta': 4,
        }
        self.columns_center_mirror = {
            'result_values': 0,
            'min': 1,
            'max': 2,
            'status': 3
        }

        self.rows_iris = {
            'iris_1': 0,
            'iris_2': 1,
            'iris_3': 2,
            'iris_4': 3,
        }
        self.columns_iris = {
            'result_values': 0,
            'min': 1,
            'max': 2,
            'status': 3
        }

        self.rows_focuss = {
            'focus_1': 0,
            'focus_2': 1,
            'focus_3': 2,
            'focus_4': 3,
        }
        self.columns_focuss = {
            'result_values': 0,
            'min': 1,
            'max': 2,
            'status': 3
        }

    def _get_table_and_maps(self, signal_name):
        name_lower = signal_name.lower()
        if name_lower in self.rows_center_mirror:
            return self.table_center_mirror, self.rows_center_mirror, self.columns_center_mirror
        elif name_lower in self.rows_iris:
            return self.table_iris, self.rows_iris, self.columns_iris
        elif name_lower in self.rows_focuss:
            return self.table_focuss, self.rows_focuss, self.columns_focuss
        return None, None, None

    def get_value(self, signal_name, column_name):
        table, rows_map, cols_map = self._get_table_and_maps(signal_name)
        if table is None:
            return None
        row = rows_map.get(signal_name.lower())
        col = cols_map.get(column_name.lower())
        if row is not None and col is not None:
            item = table.item(row, col)
            return item.text() if item else ''
        return None

    def set_value(self, signal_name, column_name, value):
        table, rows_map, cols_map = self._get_table_and_maps(signal_name)
        if table is None:
            return
        row = rows_map.get(signal_name.lower())
        col = cols_map.get(column_name.lower())
        if row is not None and col is not None:
            item = table.item(row, col)
            if not item:
                item = QtWidgets.QTableWidgetItem()
                table.setItem(row, col, item)
            item.setText(str(value))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            if value == "OK":
                item.setBackground(QtGui.QColor(0, 255, 0))
            elif value == "NG":
                item.setBackground(QtGui.QColor(255, 0, 0))
            else:
                item.setBackground(QtGui.QBrush())


    def to_number(self,val):
        if val is None:
            return "-"
        val_str = str(val).strip()
        if val_str == "" or val_str == "-":
            return "-"
        try:
            if '.' in val_str:
                return float(val_str)
            return int(val_str)
        except ValueError:
            return val_str

# --------------------------------------------------------------------------
# OverlayWidget: Native window overlay widget that sits on top of QLabel
# to render crosshair and gridlines, keeping them visible above SDK direct-draw video.
# --------------------------------------------------------------------------
class OverlayWidget(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WA_NativeWindow, True)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        parent = self.parent()
        if parent._show_grid:
            parent._draw_grid(painter, parent._draw_rect.x(), parent._draw_rect.y(),
                              parent._draw_rect.width(), parent._draw_rect.height())

        if parent._show_cross:
            cx = parent._draw_rect.x() + parent._rel_x * parent._draw_rect.width()
            cy = parent._draw_rect.y() + parent._rel_y * parent._draw_rect.height()
            color = QColor(COLOR_CROSS_ACTIVE if parent._move_mode else COLOR_CROSS)
            painter.setPen(QPen(color, 2))
            painter.drawLine(parent._draw_rect.left(), int(round(cy)),
                             parent._draw_rect.right(), int(round(cy)))
            painter.drawLine(int(round(cx)), parent._draw_rect.top(),
                             int(round(cx)), parent._draw_rect.bottom())
            painter.setBrush(color)
            painter.drawEllipse(QPointF(cx, cy), 5, 5)

        painter.end()

    def mousePressEvent(self, event):
        parent = self.parent()
        if parent._move_mode and event.button() == QtCore.Qt.LeftButton:
            parent._dragging = True
            parent._move_cross_to(event.pos())
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        parent = self.parent()
        if parent._move_mode and parent._dragging:
            parent._move_cross_to(event.pos())
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        parent = self.parent()
        if event.button() == QtCore.Qt.LeftButton:
            parent._dragging = False
            event.accept()
        else:
            event.ignore()


# --------------------------------------------------------------------------
# QLabel tuy bien: hien anh (trong/file/camera) + crosshair + grid
# --------------------------------------------------------------------------
class CrosshairLabel(QLabel):
    position_changed = pyqtSignal(int, int)  # toa do tam (pixel anh that hoac canvas)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(1, 1)
        self.setAlignment(Qt.AlignCenter)
        self.setMouseTracking(True)

        self._original_pixmap = None   # anh tu file (browse) hoac stream
        self._live_stream = False      # co the khong can dung nua neu truyen QPixmap truc tiep
        self._show_cross = False
        self._move_mode = False
        self._dragging = False
        self._show_grid = False

        # vi tri tam, luu duoi dang ty le (0.0 - 1.0) so voi vung ve hien tai
        self._rel_x = 0.5
        self._rel_y = 0.5

        # vung ve thuc te tren widget (co tinh letterbox), cap nhat moi lan paint
        self._draw_rect = QRect(0, 0, 640, 480)

    # ------------------------------------------------------------------
    # Nap du lieu anh
    # ------------------------------------------------------------------
    @QtCore.pyqtSlot(QtGui.QPixmap)
    def set_pixmap_image(self, pixmap: QPixmap):
        """Goi khi mo anh tu file (browse) hoac nhan frame tu stream."""
        self._original_pixmap = pixmap
        self.update()
        self._emit_position()

    def set_live_stream(self, enabled: bool):
        """Goi khi bat/tat streaming camera."""
        self._live_stream = enabled
        if enabled:
            # reset pixmap khi bat dau stream de tranh hien thi anh cu
            self._original_pixmap = None
        self.update()
        self._emit_position()

    # ------------------------------------------------------------------
    def has_image(self):
        """True neu dang co du lieu anh THAT."""
        return self._original_pixmap is not None and not self._original_pixmap.isNull()

    def image_size(self):
        if self._original_pixmap is not None and not self._original_pixmap.isNull():
            return self._original_pixmap.width(), self._original_pixmap.height()
        return 0, 0

    # ------------------------------------------------------------------
    # Bat/tat tinh nang - KHONG dieu kien "phai co anh"
    # ------------------------------------------------------------------
    def set_show_cross(self, enabled: bool):
        self._show_cross = enabled
        self.update()

    def set_move_mode(self, enabled: bool):
        self._move_mode = enabled
        self.setCursor(Qt.CrossCursor if enabled else Qt.ArrowCursor)
        self.update()

    def set_show_grid(self, enabled: bool):
        self._show_grid = enabled
        self.update()

    def reset_center(self):
        self._rel_x, self._rel_y = 0.5, 0.5
        self.update()
        self._emit_position()

    # ------------------------------------------------------------------
    # paintEvent
    # ------------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(COLOR_BG))

        source_pixmap = None
        if self._original_pixmap is not None and not self._original_pixmap.isNull():
            source_pixmap = self._original_pixmap

        if source_pixmap is not None:
            scaled = source_pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            x_off = (self.width() - scaled.width()) // 2
            y_off = (self.height() - scaled.height()) // 2
            self._draw_rect = QRect(x_off, y_off, scaled.width(), scaled.height())
            painter.drawPixmap(x_off, y_off, scaled)
        else:
            self._draw_rect = self.rect()
            painter.setPen(QColor("#7A7C8A"))
            painter.setFont(QFont("Segoe UI", 12))
            if self._live_stream:
                msg = "Dang cho khung hinh tu camera..."
            else:
                msg = "Chua co anh\n\nNhan \"Mo anh...\" de bat dau\nhoac bat Streaming tu camera"
            painter.drawText(self.rect(), Qt.AlignCenter, msg)

        # Ve Grid
        if self._show_grid:
            self._draw_grid(painter, self._draw_rect.x(), self._draw_rect.y(),
                            self._draw_rect.width(), self._draw_rect.height())

        # Ve Crosshair
        if self._show_cross:
            cx = self._draw_rect.x() + self._rel_x * self._draw_rect.width()
            cy = self._draw_rect.y() + self._rel_y * self._draw_rect.height()
            color = QColor(COLOR_CROSS_ACTIVE if self._move_mode else COLOR_CROSS)
            painter.setPen(QPen(color, 2))
            painter.drawLine(self._draw_rect.left(), int(round(cy)),
                             self._draw_rect.right(), int(round(cy)))
            painter.drawLine(int(round(cx)), self._draw_rect.top(),
                             int(round(cx)), self._draw_rect.bottom())
            painter.setBrush(color)
            painter.drawEllipse(QPointF(cx, cy), 5, 5)

        painter.end()

    def _draw_grid(self, painter, x_off, y_off, w, h):
        pen_h = QPen(QColor(COLOR_GRID_H), 1)
        painter.setPen(pen_h)
        for i in range(1, GRID_ROWS):
            y = y_off + round(h * i / GRID_ROWS)
            painter.drawLine(x_off, y, x_off + w, y)

        pen_v = QPen(QColor(COLOR_GRID_V), 1)
        painter.setPen(pen_v)
        for i in range(1, GRID_COLS):
            x = x_off + round(w * i / GRID_COLS)
            painter.drawLine(x, y_off, x, y_off + h)

    # ------------------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()

    def mousePressEvent(self, event):
        if self._move_mode and event.button() == Qt.LeftButton:
            self._dragging = True
            self._move_cross_to(event.pos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._move_mode and self._dragging:
            self._move_cross_to(event.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    def _move_cross_to(self, widget_pos):
        if self._draw_rect.width() == 0 or self._draw_rect.height() == 0:
            return
        x = widget_pos.x() - self._draw_rect.x()
        y = widget_pos.y() - self._draw_rect.y()
        x = max(0, min(x, self._draw_rect.width()))
        y = max(0, min(y, self._draw_rect.height()))
        self._rel_x = x / self._draw_rect.width()
        self._rel_y = y / self._draw_rect.height()
        self.update()
        self._emit_position()

    def _emit_position(self):
        w, h = self.image_size()
        if w <= 0 or h <= 0:
            w, h = self._draw_rect.width(), self._draw_rect.height()
        if w <= 0 or h <= 0:
            return
        px = int(round(self._rel_x * w))
        py = int(round(self._rel_y * h))
        self.position_changed.emit(px, py)

    def _emit_position(self):
        w, h = self.image_size()
        if w <= 0 or h <= 0:
            w, h = self._draw_rect.width(), self._draw_rect.height()
        if w <= 0 or h <= 0:
            return
        px = int(round(self._rel_x * w))
        py = int(round(self._rel_y * h))
        self.position_changed.emit(px, py)


# --------------------------------------------------------------------------
# Bo dieu khien - noi UI (nut bam trong a.py) voi CrosshairLabel
# --------------------------------------------------------------------------
class Process_Mirror_Device:
    def __init__(self, ui_mirror_tab,connect_db,cursor):
        self.ui_mirror_tab = ui_mirror_tab
        self.file_path = None
        self.image = None  # anh numpy (RGB) sau khi imread
        self.sinal = SignalTable(ui_mirror_tab)
        self.MIRROR_DATA_CAMERA1 ={}
        self.CONFIG_CAMERA1 = {}
        self.connect_db = connect_db
        self.cursor = cursor
        self.timer_detect = QtCore.QTimer()
        self.timer_detect.timeout.connect(self.streaming_run_check)
        # ------------------------------------------------------------
        # Thay QLabel goc (tu setupUi) bang CrosshairLabel.
        # self.ui_mirror_tab.label_display_image SAU DAY chinh la
        # instance CrosshairLabel - noi hien thi cross/grid.
        # ------------------------------------------------------------
        self._replace_label_with_crosshair()

        # QUAN TRONG: connect signal DUY NHAT 1 LAN tai day (khong connect
        # lai trong on_toggle_drag_cross / reset_center nhu ban truoc,
        # tranh bug nhan tin hieu nhieu lan).
        self.ui_mirror_tab.label_display_image.position_changed.connect(
            self.on_position_changed
        )

    # ------------------------------------------------------------------
    def _replace_label_with_crosshair(self):
        old_label = self.ui_mirror_tab.label_display_image

        # Uu tien lay dung layout/parent dang chua QLabel goc de thay the
        # dung cho, tranh truong hop widget moi khong nam trong layout nao.
        if hasattr(self.ui_mirror_tab, 'splitter_5') and \
           self.ui_mirror_tab.splitter_5.indexOf(old_label) != -1:
            splitter = self.ui_mirror_tab.splitter_5
            index = splitter.indexOf(old_label)
            old_label.hide()
            old_label.deleteLater()

            new_label = CrosshairLabel(splitter)
            new_label.setObjectName("label_display_image")
            splitter.insertWidget(index, new_label)
        else:
            parent_widget = old_label.parentWidget()
            parent_layout = parent_widget.layout() if parent_widget else None

            new_label = CrosshairLabel(parent_widget)
            new_label.setObjectName("label_display_image")

            if parent_layout is not None:
                parent_layout.replaceWidget(old_label, new_label)
            old_label.hide()
            old_label.deleteLater()

        new_label.show()
        self.ui_mirror_tab.label_display_image = new_label

    # ------------------------------------------------------------------
    # pushButton_broswer_file_img
    # ------------------------------------------------------------------
    def browse_file(self):
        options = QtWidgets.QFileDialog.Options()
        self.file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            None,
            "Chọn file",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp)",
            options=options
        )
        if self.file_path:
            self.ui_mirror_tab.lineEdit_input_img_file.setText(self.file_path)
            self.display_img()

    def display_img(self):
        self.image = cv2.imread(self.file_path)
        if self.image is None:
            QMessageBox.warning(None, "Loi", "Khong the doc anh da chon.")
            return
        self.image = cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)

        h, w = self.image.shape[:2]
        qimg = QtGui.QImage(self.image.data, w, h, self.image.strides[0], QtGui.QImage.Format_RGB888)
        pix = QtGui.QPixmap.fromImage(qimg)

        self.ui_mirror_tab.label_display_image.set_pixmap_image(pix)

    def has_image(self):
        return self.ui_mirror_tab.label_display_image.has_image()

    # ------------------------------------------------------------------
    # pushButton_streaming / pushButton_stop_grab
    # ------------------------------------------------------------------
    def set_live_stream(self, enabled: bool):
        """Goi khi bat/tat streaming camera de cross/grid/drag khop dung
        khung hinh camera thay vi anh file."""
        self.ui_mirror_tab.label_display_image.set_live_stream(enabled)

    # ------------------------------------------------------------------
    # pushButton_show_crossline / pushButton_drag_crossline / pushButton_show_gridline
    # ------------------------------------------------------------------
    def on_toggle_show_cross(self, checked):
        # tat Show Cross -> tat luon Drag neu dang bat
        if not checked and self.ui_mirror_tab.pushButton_drag_crossline.isChecked():
            self.ui_mirror_tab.pushButton_drag_crossline.setChecked(False)
        self.ui_mirror_tab.label_display_image.set_show_cross(checked)

    def on_toggle_drag_cross(self, checked):
        # Bat Drag thi tu dong bat luon Show Cross
        if checked and not self.ui_mirror_tab.pushButton_show_crossline.isChecked():
            self.ui_mirror_tab.pushButton_show_crossline.setChecked(True)
        self.ui_mirror_tab.label_display_image.set_move_mode(checked)

    def on_toggle_show_grid(self, checked):
        self.ui_mirror_tab.label_display_image.set_show_grid(checked)

    # ------------------------------------------------------------------
    # pushButton_reset_cross
    # ------------------------------------------------------------------
    def reset_center(self):
        self.ui_mirror_tab.label_display_image.reset_center()

    # ------------------------------------------------------------------
    def on_position_changed(self, x, y):
        self.ui_mirror_tab.label.setText(
            f"Center coordinates: ({x}, {y})"

        )

    def run_check(self,raw_image_rgb):
        if raw_image_rgb is None and self.image is None:
            QMessageBox.warning(None, "Lỗi", "Chưa có ảnh để kiểm gương. Vui lòng chụp ảnh từ camera hoặc tải ảnh từ file trước.")
            return

        if getattr(self.ui_mirror_tab.label_display_image, '_live_stream', False):
            self.toggle_stream_detect()
            return

        if raw_image_rgb is None and self.image is not None:
            raw_image_rgb = self.image

        # try:
        self.get_value_from_table()
        obj        = KiemGuong(self.MIRROR_DATA_CAMERA1, self.CONFIG_CAMERA1)
        img, check, dict_data = obj.run(raw_image_rgb)
        label_size = self.ui_mirror_tab.label_display_image.size()
        h, w = img.shape[:2]
        qimg = QtGui.QImage(img.data, w, h, img.strides[0], QtGui.QImage.Format_RGB888)
        pix = QtGui.QPixmap.fromImage(qimg)
        scaled_pix = pix.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.ui_mirror_tab.label_display_image.set_pixmap_image(scaled_pix)
        self.set_value(dict_data)
        self.check_all_status()
        # except Exception:
        #    print('[handle_result_mode_geji] KiemGuong.run failed')

    def start_stream_detect(self):
        self.timer_detect.start(50)  # Chạy mỗi 50ms (~20 fps) để không quá tải
        self.ui_mirror_tab.label.setText("Đang bật Detect Stream")

    def stop_stream_detect(self):
        if self.timer_detect.isActive:
            self.timer_detect.stop()
            self.ui_mirror_tab.label.setText("Đã tắt Detect Stream")

    def streaming_run_check(self):
        if self.image is None :
            return
            
        try:
            self.get_value_from_table()
            obj        = KiemGuong(self.MIRROR_DATA_CAMERA1, self.CONFIG_CAMERA1)
            img, check, dict_data = obj.run(self.image)
            label_size = self.ui_mirror_tab.label_display_image.size()
            h, w = img.shape[:2]
            qimg = QtGui.QImage(img.data, w, h, img.strides[0], QtGui.QImage.Format_RGB888)
            pix = QtGui.QPixmap.fromImage(qimg)
            scaled_pix = pix.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.ui_mirror_tab.label_display_image.set_pixmap_image(scaled_pix)
            self.set_value(dict_data)
            self.check_all_status()
        except Exception as e:
            print(f"Lỗi trong quá trình detect stream: {e}")


    def get_value_from_table(self):
        self.MIRROR_DATA_CAMERA1['Title1'] = 'XNCD CAMERA 1 - KIEM GUONG'
        self.MIRROR_DATA_CAMERA1['Feature'] = ["Gioi han duoi","Gioi han tren"]

        self.MIRROR_DATA_CAMERA1['Center X'] = [
            self.sinal.to_number(self.sinal.get_value("center_x", "min")),
            self.sinal.to_number(self.sinal.get_value("center_x", "max"))
        ]
        self.MIRROR_DATA_CAMERA1['Center Y'] = [
            self.sinal.to_number(self.sinal.get_value("center_y", "min")),
            self.sinal.to_number(self.sinal.get_value("center_y", "max"))
        ]
        self.MIRROR_DATA_CAMERA1['Circle Radius'] = [
            self.sinal.to_number(self.sinal.get_value("circle_radius", "min")),
            self.sinal.to_number(self.sinal.get_value("circle_radius", "max"))
        ]

        for key in ['iris_1', 'iris_2', 'iris_3', 'iris_4', 'focus_1', 'focus_2', 'focus_3', 'focus_4']:
            dict_key = key.replace('_', ' ').title()
            self.MIRROR_DATA_CAMERA1[dict_key] = [
                self.sinal.to_number(self.sinal.get_value(key, "min")),
                self.sinal.to_number(self.sinal.get_value(key, "max"))
            ]

        # config
        self.CONFIG_CAMERA1['radius_ref'] = self.sinal.to_number(self.sinal.get_value("radius_ref", "result_values"))
        self.CONFIG_CAMERA1['delta'] = self.sinal.to_number(self.sinal.get_value("delta", "result_values"))

        return self.MIRROR_DATA_CAMERA1, self.CONFIG_CAMERA1


    def set_value(self,dict_data):
        self.sinal.set_value("center_x", "result_values", dict_data['center_x'])
        self.sinal.set_value("center_y", "result_values", dict_data['center_y'])
        self.sinal.set_value("circle_radius", "result_values", dict_data['radius'])
        self.sinal.set_value("delta", "result_values", dict_data['delta'])
        self.sinal.set_value("iris_1", "result_values", dict_data['brightness_roi1'])
        self.sinal.set_value("iris_2", "result_values", dict_data['brightness_roi2'])
        self.sinal.set_value("iris_3", "result_values", dict_data['brightness_roi3'])
        self.sinal.set_value("iris_4", "result_values", dict_data['brightness_roi4'])
        self.sinal.set_value("focus_1", "result_values", dict_data['sharpness_roi1'])
        self.sinal.set_value("focus_2", "result_values", dict_data['sharpness_roi2'])
        self.sinal.set_value("focus_3", "result_values", dict_data['sharpness_roi3'])
        self.sinal.set_value("focus_4", "result_values", dict_data['sharpness_roi4'])

    def check_all_status(self):
        any_ng = False
        for rows_dict in [self.sinal.rows_center_mirror, self.sinal.rows_iris, self.sinal.rows_focuss]:
            for i in rows_dict.keys():
                value = self.sinal.to_number(self.sinal.get_value(i, "result_values"))
                min_val = self.sinal.to_number(self.sinal.get_value(i, "min"))
                max_val = self.sinal.to_number(self.sinal.get_value(i, "max"))
                
                if not isinstance(value, (int, float)):
                    continue
                    
                is_ng = False
                if isinstance(min_val, (int, float)) and value < min_val:
                    is_ng = True
                if isinstance(max_val, (int, float)) and value > max_val:
                    is_ng = True
                    
                if is_ng:
                    self.sinal.set_value(i, "status", "NG")
                    any_ng = True
                else:
                    self.sinal.set_value(i, "status", "OK")
                    
        if any_ng:
            self.ui_mirror_tab.label.setText("NG")
        else:
            self.ui_mirror_tab.label.setText("OK")

    def produce_mode_auto_id(self,item_code_id,camera_name):
        self.cursor.execute("""
                    SELECT id FROM NUMS_CAMERA 
                    WHERE item_code_id = %s AND nums_camera = %s
                """, (item_code_id, camera_name))
            
        result_camera_id = self.cursor.fetchone()[0] 
        return  result_camera_id
    
    def save_params(self,item_code_id,camera_name):
        camera_id = self.produce_mode_auto_id(item_code_id,camera_name)
        
        self.cursor.execute("""
            DELETE FROM MIRROR_CONFIG WHERE camera_id = %s
        """, (camera_id,))
        for params in list(self.sinal.rows_center_mirror.keys()) + list(self.sinal.rows_iris.keys()) + list(self.sinal.rows_focuss.keys()):
            result_values = self.sinal.get_value(params, 'result_values')
            min = self.sinal.get_value(params, 'min')
            max = self.sinal.get_value(params, 'max')
            status = self.sinal.get_value(params, 'status')
            self.cursor.execute("""
                INSERT INTO MIRROR_CONFIG (
                    parameter_name, result_value, min_value, max_value, status, camera_id
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                params,
                result_values if result_values else None,
                min if min else None,
                max if max else None,
                status if status else None,
                camera_id
            ))
        self.connect_db.connection.commit()
        self.get_value_from_table()
        QMessageBox.information(None, "Thành công", "Lưu thành công mode auto!")

    def load_params(self,item_code_id,camera_name):
        camera_id = self.produce_mode_auto_id(item_code_id,camera_name)
        self.cursor.execute("""
            SELECT parameter_name,result_value,min_value,max_value,status FROM MIRROR_CONFIG WHERE camera_id = %s
        """, (camera_id,))
        rows = self.cursor.fetchall()
        for row in rows:
            signal_name = str(row[0]).lower()
            for i, column_name in enumerate(self.sinal.columns_center_mirror.keys()):
                value = row[i + 1]
                if value is not None:
                    self.sinal.set_value(signal_name, column_name, value)

        self.connect_db.connection.commit()
        self.get_value_from_table() # Lấy giá trị lưu vào biến Dict trên Main Thread
        # QMessageBox.information(None, "Thành công", "Tải thành công mode auto!")
        