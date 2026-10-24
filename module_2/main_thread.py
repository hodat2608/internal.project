from Administrator.user_db import ensure_admin_tables
import sys,os
import sys,os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import mysql.connector
from mysql.connector import Error
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QLineEdit, 
                             QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, 
                             QFrame, QComboBox, QScrollArea, QMessageBox, QSpinBox,
                             QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
                             QGroupBox)
from PyQt5 import QtCore, QtGui, QtWidgets
from module_1.main_thread import Pyuic5
from module_5.auto_init_ import Ui_MainWindow as Auto_Config
from module_5.mysql import MySQL_Core as MySQL_Core
from module_5.controler import PLC_Controler as PLC_Controler
from module_2.main_core import core
from PyQt5 import QtCore, QtWidgets
import os
from module_2.StyleSheet import *
from app_logger.app_logger import get_logger as _get_logger, open_log_window
from Administrator.admin_config import open_admin_config
from Administrator.create_user import open_create_user
from Administrator.remove_user import open_remove_user
from Administrator.hardware_key import open_hardware_key
from Administrator.database.DataExport import Ui_DataExportDialog as DataExportDialog
from Administrator.database.DataImport import Ui_DataImportDialog as DataImportDialog
from Administrator.database.main_core import DataExport,DataImport
from Administrator.admin_config import AdminPasswordDialog
from Administrator.modify_ip_address_by_admin import MainWindow, QSS

import math
import random

from PyQt5.QtCore import QElapsedTimer, QRectF, Qt, QTimer
from PyQt5.QtGui import (QBrush, QColor, QConicalGradient, QFont,
                         QLinearGradient, QPainter, QPainterPath, QPen,
                         QRadialGradient)
from PyQt5.QtWidgets import (QGraphicsDropShadowEffect, QGraphicsEllipseItem,
                             QGraphicsLineItem, QGraphicsPathItem,
                             QGraphicsRectItem, QGraphicsScene,
                             QGraphicsSimpleTextItem, QGraphicsView)

# ----------------------------------------------------------------- bảng màu
ACCENT = "#38BDF8"       # xanh sky - màu nhấn chính
ACCENT_DARK = "#0284C7"
MUTED = "#94A3B8"
OK_COLOR = "#34D399"     # xanh lá - sản phẩm đạt
WARN_COLOR = "#FBBF24"   # vàng - cảnh báo / NG
BG_DEEP = "#020617"

RADAR_R = 350            # bán kính vòng ngoài của radar
SWEEP_SPEED = 72.0       # độ/giây (1 vòng = 5 giây)


# ------------------------------------------------------------------ helpers
def _c(hex_color, alpha=255):
    col = QColor(hex_color)
    col.setAlpha(alpha)
    return col


def _mix(h1, h2, k):
    a, b = QColor(h1), QColor(h2)
    return QColor(int(a.red() + (b.red() - a.red()) * k),
                  int(a.green() + (b.green() - a.green()) * k),
                  int(a.blue() + (b.blue() - a.blue()) * k))


def _clamp01(v):
    return max(0.0, min(1.0, v))


def _ease_out(p):
    return 1 - (1 - p) ** 3


def _glow(color, blur):
    fx = QGraphicsDropShadowEffect()
    fx.setBlurRadius(blur)
    fx.setColor(QColor(color))
    fx.setOffset(0, 0)
    return fx


class HomeScreenMixin:
    _default_instance = None

    # ------------------------------------------------------------------ setup
    def setup_home_screen(self, graphicsView=None):
        if graphicsView is None:
            if HomeScreenMixin._default_instance is None:
                HomeScreenMixin._default_instance = HomeScreenMixin()
            return HomeScreenMixin._default_instance.setup_home_screen(self)

        self.stop_home_animation()          # an toàn nếu gọi lại nhiều lần

        scene = QGraphicsScene()
        scene.setSceneRect(-1600, -1000, 3200, 2000)

        graphicsView.setStyleSheet("""
            QGraphicsView {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                            stop:0 #0F172A, stop:1 #020617);
                border: none;
            }
        """)
        graphicsView.setRenderHints(QPainter.Antialiasing
                                    | QPainter.TextAntialiasing
                                    | QPainter.SmoothPixmapTransform)
        graphicsView.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        graphicsView.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        graphicsView.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        graphicsView.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        graphicsView.setScene(scene)
        graphicsView.centerOn(0, 0)
        QTimer.singleShot(0, lambda: graphicsView.centerOn(0, 0))

        self._build_background(scene)
        self._build_radar(scene)
        self._build_overlay(scene)
        self._build_text_block(scene)

        # ---- trạng thái animation
        self.anim_angle = 0.0
        self.glow_increasing = True          # giữ lại cho tương thích code cũ
        self._clock = QElapsedTimer()
        self._clock.start()
        self._last_t = 0.0

        self.anim_timer = QTimer(graphicsView)
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(16)            # ~60 FPS (đổi 33 nếu máy yếu)

    # ------------------------------------------------------------ nền + lưới
    def _build_background(self, scene):
        # Lưới kỹ thuật (blueprint) rất mờ
        grid = QPainterPath()
        step = 60
        for x in range(-1500, 1501, step):
            grid.moveTo(x, -1000)
            grid.lineTo(x, 1000)
        for y in range(-960, 961, step):
            grid.moveTo(-1600, y)
            grid.lineTo(1600, y)
        grid_item = QGraphicsPathItem(grid)
        pen = QPen(_c(ACCENT, 14))
        pen.setWidth(1)
        pen.setCosmetic(True)
        grid_item.setPen(pen)
        grid_item.setZValue(0)
        scene.addItem(grid_item)

        # Quầng sáng tâm
        g = QRadialGradient(0, 0, 430)
        g.setColorAt(0, _c(ACCENT_DARK, 75))
        g.setColorAt(1, _c(ACCENT_DARK, 0))
        halo = scene.addEllipse(-430, -430, 860, 860, QPen(Qt.NoPen), QBrush(g))
        halo.setZValue(1)

    # ------------------------------------------------------------------ radar
    def _build_radar(self, scene):
        R = RADAR_R

        # Vòng trong (nét liền)
        ring1 = QGraphicsEllipseItem(-200, -200, 400, 400)
        pen1 = QPen(_c(ACCENT, 60))
        pen1.setWidth(2)
        ring1.setPen(pen1)
        ring1.setZValue(2)
        scene.addItem(ring1)

        # Vòng ngoài (nét đứt, xoay ngược)
        pen_dash = QPen(_c(ACCENT, 70))
        pen_dash.setWidth(2)
        pen_dash.setStyle(Qt.DashLine)
        self.radar_circle = QGraphicsEllipseItem(-R, -R, 2 * R, 2 * R)
        self.radar_circle.setPen(pen_dash)
        self.radar_circle.setZValue(2)
        scene.addItem(self.radar_circle)

        # Vòng vạch chia (như thước đo), xoay chậm
        ticks = QPainterPath()
        for deg in range(0, 360, 3):
            long_tick = deg % 15 == 0
            r_out = 300
            r_in = r_out - (14 if long_tick else 7)
            a = math.radians(deg)
            ticks.moveTo(r_in * math.cos(a), r_in * math.sin(a))
            ticks.lineTo(r_out * math.cos(a), r_out * math.sin(a))
        self.radar_ticks = QGraphicsPathItem(ticks)
        pen_t = QPen(_c(ACCENT, 95))
        pen_t.setWidth(2)
        self.radar_ticks.setPen(pen_t)
        self.radar_ticks.setZValue(2)
        scene.addItem(self.radar_ticks)

        # Vòng "ping" lan toả định kỳ
        self.radar_ping = QGraphicsEllipseItem(-100, -100, 200, 200)
        pen_p = QPen(_c(ACCENT, 255))
        pen_p.setWidth(2)
        pen_p.setCosmetic(True)
        self.radar_ping.setPen(pen_p)
        self.radar_ping.setZValue(2)
        scene.addItem(self.radar_ping)

        # Vệt quét mờ dần phía sau tia radar
        wedge = QPainterPath()
        wedge.moveTo(0, 0)
        wedge.arcTo(QRectF(-R, -R, 2 * R, 2 * R), 90, 70)
        wedge.closeSubpath()
        cg = QConicalGradient(0, 0, 90)
        cg.setColorAt(0.0, _c(ACCENT, 120))
        cg.setColorAt(0.19, _c(ACCENT, 0))
        cg.setColorAt(1.0, _c(ACCENT, 0))
        self.radar_sweep = QGraphicsPathItem(wedge)
        self.radar_sweep.setPen(QPen(Qt.NoPen))
        self.radar_sweep.setBrush(QBrush(cg))
        self.radar_sweep.setZValue(3)
        scene.addItem(self.radar_sweep)

        # Tia radar
        self.radar_line = QGraphicsLineItem(0, 0, 0, -R)
        pen_sweep = QPen(_c(ACCENT, 235))
        pen_sweep.setWidth(2)
        self.radar_line.setPen(pen_sweep)
        self.radar_line.setGraphicsEffect(_glow(ACCENT, 14))
        self.radar_line.setZValue(3)
        scene.addItem(self.radar_line)

        # Các điểm phát hiện (blip) - sáng lên khi tia quét đi qua
        rnd = random.Random(7)
        self.blips = []
        for _ in range(14):
            ang = rnd.uniform(0, 360)
            rad = rnd.uniform(90, 330)
            x = rad * math.sin(math.radians(ang))
            y = -rad * math.cos(math.radians(ang))
            col = rnd.choice([ACCENT, ACCENT, OK_COLOR, OK_COLOR, WARN_COLOR])
            dot = scene.addEllipse(-4, -4, 8, 8, QPen(Qt.NoPen), QBrush(QColor(col)))
            dot.setPos(x, y)
            dot.setZValue(4)
            dot.setOpacity(0.0)
            halo = QGraphicsEllipseItem(-11, -11, 22, 22, dot)
            halo.setPen(QPen(_c(col, 160), 1.5))
            halo.setBrush(QBrush(Qt.NoBrush))
            self.blips.append((ang, dot))

    # ------------------------------------------------------- vignette + brackets
    def _build_overlay(self, scene):
        # Vignette: tối dần ra mép để tập trung vào trung tâm
        vg = QRadialGradient(0, 0, 1100)
        vg.setColorAt(0.0, _c(BG_DEEP, 0))
        vg.setColorAt(0.45, _c(BG_DEEP, 0))
        vg.setColorAt(1.0, _c(BG_DEEP, 235))
        vignette = QGraphicsRectItem(-1600, -1000, 3200, 2000)
        vignette.setPen(QPen(Qt.NoPen))
        vignette.setBrush(QBrush(vg))
        vignette.setZValue(5)
        scene.addItem(vignette)

    # ----------------------------------------------------------------- chữ
    def _build_text_block(self, scene):
        # --- tiêu đề chính
        title = QGraphicsSimpleTextItem("MBC VISION INSPECTOR")
        f1 = QFont("Segoe UI", 44, QFont.Bold)
        f1.setLetterSpacing(QFont.AbsoluteSpacing, 6)
        title.setFont(f1)
        title.setBrush(QBrush(QColor(ACCENT)))
        self.title_glow = _glow(ACCENT_DARK, 30)
        title.setGraphicsEffect(self.title_glow)
        tw = title.boundingRect().width()
        th = title.boundingRect().height()
        self._title_w = tw
        self.title_item = title

        # --- tagline
        tag = QGraphicsSimpleTextItem("AI VISION FOR MANUFACTURING")
        f2 = QFont("Segoe UI", 18, QFont.DemiBold)
        f2.setLetterSpacing(QFont.AbsoluteSpacing, 8)
        tag.setFont(f2)
        tag.setBrush(QBrush(QColor(ACCENT)))
        self.title_glow_2 = _glow(ACCENT_DARK, 18)
        tag.setGraphicsEffect(self.title_glow_2)
        tagw, tagh = tag.boundingRect().width(), tag.boundingRect().height()

        # --- phụ đề
        sub = QGraphicsSimpleTextItem("ADVANCED MACHINE VISION SYSTEM")
        f3 = QFont("Segoe UI", 12)
        f3.setLetterSpacing(QFont.AbsoluteSpacing, 10)
        sub.setFont(f3)
        sub.setBrush(QBrush(QColor(MUTED)))
        subw, subh = sub.boundingRect().width(), sub.boundingRect().height()

        # --- trạng thái hệ thống
        status = QGraphicsSimpleTextItem("SYSTEM READY")
        f4 = QFont("Segoe UI", 10, QFont.DemiBold)
        f4.setLetterSpacing(QFont.AbsoluteSpacing, 4)
        status.setFont(f4)
        status.setBrush(QBrush(QColor(OK_COLOR)))
        stw, sth = status.boundingRect().width(), status.boundingRect().height()

        # --- xếp dọc theo chiều cao thật của từng dòng, rồi căn giữa cả khối
        y = 0
        title_y = y;  y += th + 8
        div_y = y;    y += 2 + 18
        tag_y = y;    y += tagh + 6
        sub_y = y;    y += subh + 34
        st_y = y;     y += sth
        off = -y / 2

        title.setPos(-tw / 2, title_y + off)
        tag.setPos(-tagw / 2, tag_y + off)
        sub.setPos(-subw / 2, sub_y + off)

        # đường kẻ phân cách có gradient mờ hai đầu
        lg = QLinearGradient(0, 0, tw, 0)
        lg.setColorAt(0.0, _c(ACCENT, 0))
        lg.setColorAt(0.5, _c(ACCENT, 255))
        lg.setColorAt(1.0, _c(ACCENT, 0))
        divider = QGraphicsRectItem(0, 0, tw, 2)
        divider.setPen(QPen(Qt.NoPen))
        divider.setBrush(QBrush(lg))
        divider.setPos(-tw / 2, div_y + off)

        # chấm sáng chạy dọc đường kẻ
        self.div_dot = QGraphicsEllipseItem(-4, -4, 8, 8)
        self.div_dot.setPen(QPen(Qt.NoPen))
        self.div_dot.setBrush(QBrush(QColor("#E0F2FE")))
        self.div_dot.setGraphicsEffect(_glow(ACCENT, 18))
        self.div_dot.setPos(0, div_y + off + 1)

        # trạng thái: chấm xanh nhấp nháy + chữ
        total = 18 + stw
        status.setPos(-total / 2 + 18, st_y + off)
        self.status_dot = QGraphicsEllipseItem(-4, -4, 8, 8)
        self.status_dot.setPen(QPen(Qt.NoPen))
        self.status_dot.setBrush(QBrush(QColor(OK_COLOR)))
        self.status_dot.setGraphicsEffect(_glow(OK_COLOR, 14))
        self.status_dot.setPos(-total / 2 + 4, st_y + off + sth / 2)

        for it in (title, divider, tag, sub, status,
                   self.div_dot, self.status_dot):
            it.setZValue(10)
            scene.addItem(it)

        # (item, y gốc, độ trễ xuất hiện) -> hiệu ứng fade-in + trượt lên lần lượt
        self._intro_items = [
            (title, title.y(), 0.0),
            (divider, divider.y(), 0.45),
            (tag, tag.y(), 0.7),
            (sub, sub.y(), 1.0),
            (status, status.y(), 1.35),
        ]
        self._status_delay = 1.35
        self._div_delay = 0.45

        # --- khung ngắm 4 góc (viewfinder)
        left, right = -tw / 2 - 50, tw / 2 + 50
        top, bottom = off - 34, off + y + 34
        size = 30
        pen_b = QPen(QColor(ACCENT))
        pen_b.setWidth(3)
        pen_b.setCapStyle(Qt.SquareCap)
        pen_b.setJoinStyle(Qt.MiterJoin)
        self._brackets = []
        for (cx, cy, dx, dy) in ((left, top, 1, 1), (right, top, -1, 1),
                                 (left, bottom, 1, -1), (right, bottom, -1, -1)):
            p = QPainterPath()
            p.moveTo(cx + dx * size, cy)
            p.lineTo(cx, cy)
            p.lineTo(cx, cy + dy * size)
            br = QGraphicsPathItem(p)
            br.setPen(pen_b)
            br.setZValue(10)
            br.setOpacity(0.0)
            scene.addItem(br)
            self._brackets.append(br)

    # -------------------------------------------------------------- animation
    def update_animation(self):
        t = self._clock.elapsed() / 1000.0
        dt = min(t - self._last_t, 0.1)
        self._last_t = t

        # ---- radar
        self.anim_angle = (self.anim_angle + SWEEP_SPEED * dt) % 360
        a = self.anim_angle
        self.radar_line.setRotation(a)
        self.radar_sweep.setRotation(a)
        self.radar_circle.setRotation(-a * 0.5)
        self.radar_ticks.setRotation(t * 4.0)

        # vòng ping lan toả mỗi 3.2 giây
        p = (t % 3.2) / 3.2
        self.radar_ping.setScale(0.02 + p * 3.5)
        self.radar_ping.setOpacity((1 - p) ** 1.5 * 0.55)

        # blip: bật sáng khi tia quét đi qua rồi mờ dần
        window = SWEEP_SPEED * dt * 1.5 + 1.0
        for ang, dot in self.blips:
            op = max(0.0, dot.opacity() - dt * 0.45)
            if (a - ang) % 360 < window:
                op = 1.0
            dot.setOpacity(op)

        # ---- fade-in lần lượt khi mở màn hình
        for item, base_y, delay in self._intro_items:
            e = _ease_out(_clamp01((t - delay) / 0.9))
            item.setOpacity(e)
            item.setY(base_y + (1 - e) * 14)

        # chấm chạy trên đường kẻ (mờ dần ở hai đầu)
        e_div = _ease_out(_clamp01((t - self._div_delay) / 0.9))
        s = math.sin(t * 0.9)
        self.div_dot.setX(s * self._title_w * 0.5)
        self.div_dot.setOpacity(e_div * (1 - abs(s) ** 3))

        # chấm trạng thái nhấp nháy nhẹ
        e_st = _ease_out(_clamp01((t - self._status_delay) / 0.9))
        self.status_dot.setOpacity(e_st * (0.45 + 0.55 * (0.5 + 0.5 * math.sin(t * 3.0))))

        # khung ngắm: hiện ra rồi "thở" nhẹ
        e_br = _ease_out(_clamp01((t - 0.2) / 0.9))
        pulse = 0.75 + 0.25 * math.sin(t * 2.0)
        for br in self._brackets:
            br.setOpacity(e_br * pulse)

        # ---- ánh sáng "thở" quanh chữ
        breathe = 0.5 + 0.5 * math.sin(t * 1.6)
        self.title_glow.setBlurRadius(22 + 20 * breathe)
        self.title_glow_2.setBlurRadius(12 + 10 * breathe)

        # ---- hiệu ứng ánh sáng lướt qua tiêu đề (mỗi 6 giây)
        self._update_title_shimmer(t)

    def _update_title_shimmer(self, t):
        left_c, right_c = "#E0F2FE", ACCENT
        grad = QLinearGradient(0, 0, self._title_w, 0)
        grad.setColorAt(0.0, _mix(left_c, right_c, 0.0))
        grad.setColorAt(1.0, _mix(left_c, right_c, 1.0))

        cycle = t % 6.0
        if cycle < 3.0 and t > 1.0:
            center = -0.2 + 1.4 * (cycle / 3.0)
            width = 0.12
            for pos, col in ((center - width, _mix(left_c, right_c, center - width)),
                             (center, QColor("#FFFFFF")),
                             (center + width, _mix(left_c, right_c, center + width))):
                if 0.0 < pos < 1.0:
                    grad.setColorAt(pos, col)
        self.title_item.setBrush(QBrush(grad))

    # ------------------------------------------------------------ điều khiển
    def stop_home_animation(self=None):
        if self is None or not isinstance(self, HomeScreenMixin):
            if HomeScreenMixin._default_instance is not None:
                return HomeScreenMixin._default_instance.stop_home_animation()
            return
        timer = getattr(self, "anim_timer", None)
        if timer is not None:
            timer.stop()

    def start_home_animation(self=None):
        if self is None or not isinstance(self, HomeScreenMixin):
            if HomeScreenMixin._default_instance is not None:
                return HomeScreenMixin._default_instance.start_home_animation()
            return
        timer = getattr(self, "anim_timer", None)
        if timer is not None and not timer.isActive():
            self._last_t = self._clock.elapsed() / 1000.0
            timer.start(16)


class main_thread(HomeScreenMixin):
    def __init__(self,ui,main_core_connection,main_core):
        self.ui = ui
        self.main_core_connection = main_core_connection
        self.main_core = main_core
        self.ui.pyuic5_window = Pyuic5(self.ui,self.main_core_connection,self.main_core)

    def open_pyuic5(self):
        self.ui.pyuic5_window.MainWindow.show()

    def init_Pyuic5(self):
        if not self.main_core.mode_init:
            self.ui.pyuic5_window.core.update_menu()


    def _open_data_export(self):
        from Administrator.user_db import ensure_admin_tables
        ensure_admin_tables(self.main_core_connection)
        auth = AdminPasswordDialog(None)
        if auth.exec_() == QDialog.Accepted and auth.authenticated:
            self.sub_DataExportDialog = QtWidgets.QDialog()
            self.ui_sub_1 = DataExportDialog()
            self.ui_sub_1.setupUi(self.sub_DataExportDialog)
            self.sub_DataExportDialog.show()

            self.data_export_core = DataExport(self.main_core.connection, self.ui_sub_1)
            self.data_export_core.query_all_table()

            self.ui_sub_1.treeSchemas.itemClicked.connect(self.data_export_core.on_schema_clicked)
            self.ui_sub_1.btnSelectViews.clicked.connect(self.data_export_core.select_view)
            self.ui_sub_1.btnRefresh.clicked.connect(self.data_export_core.query_all_table)
            self.ui_sub_1.btnSelectTables.clicked.connect(self.data_export_core.select_tables)
            self.ui_sub_1.btnUnselectAll.clicked.connect(self.data_export_core.unselect_all)
            self.ui_sub_1.btnBrowseProjectFolder.clicked.connect(self.data_export_core.browser_folder_export_data)
            self.ui_sub_1.btnStartExport.clicked.connect(self.data_export_core.export_data)
            self.ui_sub_1.btnCloseProgress.clicked.connect(self.data_export_core.close_window)
    
    def _open_data_import(self):
        from Administrator.user_db import ensure_admin_tables
        ensure_admin_tables(self.main_core_connection)
        auth = AdminPasswordDialog(None)
        if auth.exec_() == QDialog.Accepted and auth.authenticated:
            self.sub_DataImportDialog = QtWidgets.QDialog()
            self.ui_sub_2 = DataImportDialog()
            self.ui_sub_2.setupUi(self.sub_DataImportDialog)
            self.sub_DataImportDialog.show()
            self.data_import_core = DataImport(self.main_core.connection, self.ui_sub_2)
            query_all_table = self.data_import_core.query_all_table()
            self.ui_sub_2.btnBrowseProjectFolder.clicked.connect(self.data_import_core.browser_folder_import_data)
            self.ui_sub_2.treeSchemas.itemClicked.connect(self.data_import_core.on_schema_clicked)
            self.ui_sub_2.btnLoadFolderContents.clicked.connect(self.data_import_core.load_folder_contents) 
            self.ui_sub_2.btnSelectViews.clicked.connect(self.data_import_core.select_view)
            self.ui_sub_2.btnSelectTables.clicked.connect(self.data_import_core.select_tables)
            self.ui_sub_2.btnUnselectAll.clicked.connect(self.data_import_core.unselect_all)
            self.ui_sub_2.btnStartImport.clicked.connect(self.data_import_core.import_data)
            self.ui_sub_2.btnCloseProgress.clicked.connect(self.data_import_core.close_window)
            
    def auto_mysql(self):
        self.sub = QtWidgets.QMainWindow()
        self.ui_sub = Auto_Config()
        self.ui_sub.setupUi(self.sub)
        self.core = MySQL_Core(self.ui_sub,self.main_core)
        self.controller = PLC_Controler(self.ui_sub,self.main_core)
        self.core.load_mode_login()
        self.controller.load_mode_plc()
        self.controller.load_ip_address_status()
        self.ui_sub.pushButton_test_connection.clicked.connect(lambda _ , u=self.core: u.connect_to_mysql())
        self.ui_sub.pushButton_apply_login_setting.clicked.connect(lambda _ , u=self.core: u.save_data_login())
        self.ui_sub.pushButton_test_connection_3.clicked.connect(lambda _ , u=self.controller: u.TestConnection())
        self.ui_sub.pushButton_apply_ip_add_setting_2.clicked.connect(lambda _ , u=self.controller: u.save_ip_address())
        self.ui_sub.pushButton_get_local_ip_2.clicked.connect(lambda _ , u=self.controller: u.ip_config())
        self.ui_sub.network_setting_advanced.clicked.connect(lambda _ , u=self: u.open_modify_ip_address())
        self.ui_sub.pushButton_plc_receive.clicked.connect(lambda _ , u=self.controller: u.read_plc_data())
        self.ui_sub.pushButton_plc_send.clicked.connect(lambda _ , u=self.controller: u.write_plc_data())
        self.sub.show()

    def open_modify_ip_address(self):
        from app_utils.progress_bar import AppProgressBar
        
        progress = AppProgressBar(message="Đang lấy danh sách card mạng...", parent=self.sub)
        
        self._modify_ip_address_window = MainWindow(progress_callback=progress.update_progress)
        self._modify_ip_address_window.setStyleSheet(QSS)
        
        progress.close()
        self._modify_ip_address_window.show()

    def _get_db_cursor(self):
        """Lấy cursor và connect_db từ main_core connection"""
        if self.main_core.connection and self.main_core.connection.is_connected():
            cursor = self.main_core.connection.cursor()
            return cursor, self.main_core.connection
        else:
            QMessageBox.warning(None, "Lỗi", "Chưa kết nối đến MySQL!\nVui lòng cấu hình Auto Configuration trước.")
            return None, None

    def _open_admin_config(self):
        cursor, db = self._get_db_cursor()
        if cursor:
            open_admin_config(cursor, db, self.main_core.connection)

    def _open_create_user(self):
        cursor, db = self._get_db_cursor()
        if cursor:
            open_create_user(cursor, db, self.main_core.connection)

    def _open_remove_user(self):
        cursor, db = self._get_db_cursor()
        if cursor:
            open_remove_user(cursor, db, self.main_core.connection)

    def _open_hardware_key(self):
        cursor, db = self._get_db_cursor()
        if cursor:
            open_hardware_key(cursor, db, self.main_core.connection)

    def _open_scripts(self):
        cursor, db = self._get_db_cursor()
        if cursor:
            from Administrator.scripts_editor import open_scripts_editor
            self._scripts_window = open_scripts_editor(cursor, db, self.main_core.connection)



    def closeEvent(self, event, main_core_ref=None):
        if QtWidgets.QApplication.instance().property("is_exiting"):
            event.accept()
            return

        reply = QMessageBox.question(
            None,
            "Xác nhận thoát",
            "Bạn có chắc chắn muốn thoát?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            print("Đang thoát chương trình...")
            QtWidgets.QApplication.instance().setProperty("is_exiting", True)
            if main_core_ref is not None:
                try:
                    main_core_ref.stop_monitoring()
                except Exception as e:
                    print(f"Lỗi khi dừng CoreWorker: {e}")
            event.accept()
            try:
                QtWidgets.QApplication.closeAllWindows()
            except:
                pass
            os._exit(0)
        else:
            event.ignore()

    def close_application(self, event=None, main_core_ref=None):
        reply = QMessageBox.question(
            None,
            "Xác nhận thoát",
            "Bạn có chắc chắn muốn đóng toàn bộ ứng dụng và kết thúc terminal?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            print("Đang đóng toàn bộ các cửa sổ và terminal...")
            QtWidgets.QApplication.instance().setProperty("is_exiting", True)
            if main_core_ref is not None:
                try:
                    main_core_ref.stop_monitoring()
                except Exception as e:
                    print(f"Lỗi khi dừng CoreWorker: {e}")
            if event is not None:
                try:
                    event.accept()
                except:
                    pass
            try:
                QtWidgets.QApplication.closeAllWindows()
            except:
                pass
            os._exit(0)

    def restart_application(self):
        reply = QMessageBox.question(
            None,
            "Xác nhận Reset",
            "Bạn có chắc chắn muốn khởi động lại ứng dụng?\n"
            "Hãy lưu thông số cài đặt trước khi khởi động lại ứng dụng.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        try:
            python_exe = sys.executable
            os.execv(python_exe, [python_exe] + sys.argv)
        except Exception as e:
            QMessageBox.critical(
                None, "Lỗi Reset",
                "Không thể khởi động lại ứng dụng:\n{}".format(str(e))
            )
