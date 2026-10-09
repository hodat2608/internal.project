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

class main_thread():
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
        self.controller = PLC_Controler(self.ui_sub,self.core,self.main_core)
        self.core.load_mode_login()
        self.controller.load_mode_plc()
        self.controller.load_ip_address()
        self.ui_sub.pushButton_test_connection.clicked.connect(lambda _ , u=self.core: u.connect_to_mysql())
        self.ui_sub.pushButton_apply_login_setting.clicked.connect(lambda _ , u=self.core: u.save_data_login())
        self.ui_sub.pushButton_test_connection_3.clicked.connect(lambda _ , u=self.controller: u.TestConnection())
        self.ui_sub.pushButton_apply_ip_add_setting_2.clicked.connect(lambda _ , u=self.controller: u.save_ip_address())
        self.ui_sub.pushButton.clicked.connect(lambda _ , u=self: u.open_modify_ip_address())
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


    def setup_home_screen(self, graphicsView):
        from PyQt5.QtWidgets import QGraphicsScene, QGraphicsTextItem, QGraphicsDropShadowEffect, QGraphicsEllipseItem, QGraphicsLineItem
        from PyQt5.QtGui import QFont, QColor, QPen, QPainter
        from PyQt5.QtCore import Qt, QTimer
        
        scene = QGraphicsScene()
        graphicsView.setStyleSheet("""
            QGraphicsView {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0F172A, stop:1 #020617);
                border: none;
            }
        """)
        graphicsView.setRenderHint(QPainter.Antialiasing)
        graphicsView.setScene(scene)

        pen_solid = QPen(QColor("#1E293B"))
        pen_solid.setWidth(2)
        circle1 = QGraphicsEllipseItem(-200, -200, 400, 400)
        circle1.setPen(pen_solid)
        scene.addItem(circle1)

        pen_dash = QPen(QColor("#334155"))
        pen_dash.setWidth(2)
        pen_dash.setStyle(Qt.DashLine)
        self.radar_circle = QGraphicsEllipseItem(-350, -350, 700, 700)
        self.radar_circle.setPen(pen_dash)
        scene.addItem(self.radar_circle)
        
        self.radar_line = QGraphicsLineItem(0, 0, 0, -350)
        pen_sweep = QPen(QColor("#0284C7"))
        pen_sweep.setWidth(3)
        self.radar_line.setPen(pen_sweep)
        scene.addItem(self.radar_line)

        text_item = QGraphicsTextItem("MBC VISION INSPECTOR")
        font = QFont("Segoe UI", 56, QFont.Bold)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 5)
        text_item.setFont(font)
        text_item.setDefaultTextColor(QColor("#38BDF8"))
        
        self.title_glow = QGraphicsDropShadowEffect()
        self.title_glow.setBlurRadius(30)
        self.title_glow.setColor(QColor("#0284C7"))
        self.title_glow.setOffset(0, 0)
        text_item.setGraphicsEffect(self.title_glow)
        
        text_width = text_item.boundingRect().width()
        text_item.setPos(-text_width / 2, -130)  # Nâng title chính lên cao
        scene.addItem(text_item)

        # Dòng 2: AI VISION FOR MANUFACTURING
        text_item_2 = QGraphicsTextItem("AI VISION FOR MANUFACTURING")
        font_2 = QFont("Segoe UI", 20, QFont.Bold)
        font_2.setLetterSpacing(QFont.AbsoluteSpacing, 5)
        text_item_2.setFont(font_2)
        text_item_2.setDefaultTextColor(QColor("#38BDF8"))
        
        self.title_glow_2 = QGraphicsDropShadowEffect()
        self.title_glow_2.setBlurRadius(30)
        self.title_glow_2.setColor(QColor("#0284C7"))
        self.title_glow_2.setOffset(0, 0)
        text_item_2.setGraphicsEffect(self.title_glow_2)
        
        text_width_2 = text_item_2.boundingRect().width()
        text_item_2.setPos(-text_width_2 / 2, -30)  # Đặt ở giữa
        scene.addItem(text_item_2)

        # Dòng 3: SUBTITLE
        subtitle = QGraphicsTextItem("ADVANCED MACHINE VISION SYSTEM")
        sub_font = QFont("Segoe UI", 16)
        sub_font.setLetterSpacing(QFont.AbsoluteSpacing, 10)
        subtitle.setFont(sub_font)
        subtitle.setDefaultTextColor(QColor("#94A3B8"))
        
        sub_width = subtitle.boundingRect().width()
        subtitle.setPos(-sub_width / 2, 20)  # Đặt thấp xuống
        scene.addItem(subtitle)

        self.anim_angle = 0
        self.glow_increasing = True

        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(30)

    def update_animation(self):
        self.anim_angle = (self.anim_angle + 2) % 360
        self.radar_line.setRotation(self.anim_angle)
        
        self.radar_circle.setRotation(-self.anim_angle * 0.5)
        
        radius = self.title_glow.blurRadius()
        if self.glow_increasing:
            radius += 1.5
            if radius >= 60:
                self.glow_increasing = False
        else:
            radius -= 1.5
            if radius <= 15:
                self.glow_increasing = True
                
        # Update cả 2 glow
        self.title_glow.setBlurRadius(radius)
        self.title_glow_2.setBlurRadius(radius)

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