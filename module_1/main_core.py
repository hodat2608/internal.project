
from module_1.layout_cameratab import Ui_MainWindow as Ui_CameraTab
from module_1.layout_modeltab import Ui_MainWindow as Ui_ModelTab
from PyQt5.QtWidgets import QMessageBox
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QLineEdit, 
                             QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, 
                             QFrame, QComboBox, QScrollArea, QMessageBox, QSpinBox,
                             QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
                             QGroupBox)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap
from module_1.mysql_connector import Ui_MainWindow as Ui_MySQLConnector
import mysql.connector
from mysql.connector import Error
from module_1.database import Connect2Mysql
from module_1.confirm_dataset import Ui_MainWindow as FormConfirmTable
from module_1.config_editor import ItemCodeConfigEditor
from module_1.add_itemcode_dialog import AddItemCodeDialog
from module_3.main_thread import intermediate_layer
import sys,datetime
import queue
from PyQt5.QtCore import QTimer
from PyQt5 import QtCore, QtGui, QtWidgets
from app_logger.app_logger import get_logger as _get_logger, open_log_window
from module_1.root_path import resource_path

_log = _get_logger('module_1.main_core')
class core: 
    def __init__(self,connect,ui_db,ui,main_core):
        self.dict_list_line = {}
        self.connect = connect
        self.ui_db = ui_db
        self.main_core = main_core
        self.ui = ui
        self.mode_init = 0

    def update_menu(self):
        if self.connect.connection is None:
            _log.warning('[core.update_menu] Database connection is not connected')
            return
        db_submenu = QtWidgets.QMenu()
        self.cursor = self.connect.connection.cursor()
        self.cursor.execute("SHOW DATABASES") 
        databases = self.cursor.fetchall()
        for db_name in databases:
            db_name_str = db_name[0]
            QtWidgets.QAction(db_name_str, db_submenu)
            self.cursor.execute(f"USE {db_name_str}")
            self.cursor.execute(f"SHOW TABLES")
            tables = self.cursor.fetchall()
            for table in tables:
                if 'items_code' == table[0]:
                    self.cursor.execute(f"SELECT name_line_code FROM ITEMS_CODE")
                    item_codes = self.cursor.fetchall()
                    item_code_submenu = QtWidgets.QMenu(f"{db_name_str.upper()}", db_submenu)
                    item_code_submenu.setIcon(QtGui.QIcon(QtGui.QPixmap(resource_path("module_3/assert/icon/server.png"))))
                    delete_db_action = QtWidgets.QAction(f"Delete", item_code_submenu)
                    delete_db_action.setIcon(QtGui.QIcon(QtGui.QPixmap(resource_path("module_3/assert/icon/garbage.png"))))
                    delete_db_action.triggered.connect(lambda checked=False, db=db_name_str: self.delete_database(db))
                    add_itemcode_db_action = QtWidgets.QAction(f"Add Item", item_code_submenu)
                    add_itemcode_db_action.setIcon(QtGui.QIcon(QtGui.QPixmap(resource_path("module_3/assert/icon/add_database.png"))))
                    add_itemcode_db_action.triggered.connect(lambda checked=False, db=db_name_str: self.add_itemcode(db))
                    item_code_submenu.addAction(delete_db_action)
                    item_code_submenu.addAction(add_itemcode_db_action)
                    item_code_submenu.addSeparator()
                    for item_code in item_codes:
                        item_menu = QtWidgets.QMenu(f"{item_code[0]}", item_code_submenu)
                        item_menu.setIcon(QtGui.QIcon(QtGui.QPixmap(resource_path("module_3/assert/icon/label.png"))))
                        open_action = QtWidgets.QAction("Open", item_menu)
                        open_action.setIcon(QtGui.QIcon(QtGui.QPixmap(resource_path("module_3/assert/icon/check.png"))))
                        open_action.triggered.connect(lambda checked=False, code=item_code[0],db=db_name_str: self.open_pyuic6(code,db))
                        item_menu.addAction(open_action)
                        edit_action = QtWidgets.QAction("Edit Configuration", item_menu)
                        edit_action.setIcon(QtGui.QIcon(QtGui.QPixmap(resource_path("module_3/assert/icon/edit.png"))))
                        edit_action.triggered.connect(lambda checked=False, code=item_code[0],db=db_name_str: self.open_config_editor(code,db))
                        item_menu.addAction(edit_action)
                        delete_action = QtWidgets.QAction("Delete", item_menu)
                        delete_action.setIcon(QtGui.QIcon(QtGui.QPixmap(resource_path("module_3/assert/icon/garbage.png"))))
                        delete_action.triggered.connect(lambda checked=False, code=item_code[0],db=db_name_str: self.delete_item_code(code,db))
                        item_menu.addAction(delete_action)
                        item_code_submenu.addMenu(item_menu)
                    db_submenu.addMenu(item_code_submenu)
        self.ui_db.actionDevice_Name.setMenu(db_submenu) 

    def query_device(self, event=None):
        self.update_menu()
        if event is not None:
            if hasattr(event, 'close'):
                event.close()
            elif hasattr(event, 'accept'):
                event.accept()

    def delete_database(self, db):
        confirm = QtWidgets.QMessageBox.warning(None, "CẢNH BÁO NGUY HIỂM", 
            f"Bạn đang yêu cầu XÓA TOÀN BỘ Database '{db}'.\nTất cả dữ liệu, các bảng và mã hàng trong Database này sẽ bị XÓA VĨNH VIỄN!\n\nBạn có CHẮC CHẮN muốn xóa không?", 
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        
        if confirm == QtWidgets.QMessageBox.Yes:
            try:
                cursor = self.connect.connection.cursor()
                cursor.execute(f"DROP DATABASE {db}")
                self.connect.connection.commit()
                QtWidgets.QMessageBox.information(None, "Thành công", f"Đã xóa hoàn toàn Database '{db}'.")
                self.update_menu()
            except Exception as e:
                QtWidgets.QMessageBox.critical(None, "Lỗi", f"Không thể xóa Database: {e}")

    def delete_item_code(self, code, db):
        confirm = QtWidgets.QMessageBox.question(None, "Xác nhận xóa", 
            f"Bạn có chắc chắn muốn xóa mã hàng '{code}' khỏi Database '{db}' không?\nLưu ý: Thao tác này sẽ xóa vĩnh viễn trong CSDL!", 
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        
        if confirm == QtWidgets.QMessageBox.Yes:
            try:
                cursor = self.connect.connection.cursor()
                cursor.execute(f"USE {db}")
                cursor.execute("DELETE FROM ITEMS_CODE WHERE name_line_code = %s", (code,))
                self.connect.connection.commit()
                QtWidgets.QMessageBox.information(None, "Thành công", f"Đã xóa thành công mã hàng '{code}'.")
                self.update_menu()
            except Exception as e:
                QtWidgets.QMessageBox.critical(None, "Lỗi", f"Không thể xóa mã hàng: {e}")

    def open_pyuic6(self,i_code,db):
        from app_utils.progress_bar import AppProgressBar
        
        progress = AppProgressBar(message="Đang khởi tạo giao diện...")
            
        date_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.main_core.write_data_save_default(date_time,i_code,db)
        self.pyuic6_instance = intermediate_layer(i_code,db,self.connect,self.mode_init, progress_callback=progress.update_progress)
        
        progress.close()

    def open_config_editor(self, item_code: str, db_name: str):
        """Mở cửa sổ chỉnh sửa cấu hình cho item_code đã chọn."""
        try:
            # Giữ reference để tránh garbage collect
            if not hasattr(self, '_config_editor_windows'):
                self._config_editor_windows = []

            editor = ItemCodeConfigEditor(
                connection=self.connect.connection,
                db_name=db_name,
                item_code=item_code,
            )
            editor.show()
            self._config_editor_windows.append(editor)

            # Xóa instance khỏi list khi cửa sổ đóng để tránh memory leak
            editor.destroyed.connect(
                lambda: self._config_editor_windows.remove(editor)
                if editor in self._config_editor_windows else None
            )
        except Exception as e:
            _log.error("Error opening config editor: %s", e)
            QtWidgets.QMessageBox.critical(None, "Lỗi", f"Không thể mở cửa sổ chỉnh sửa:\n{e}")

    def add_itemcode(self, db_name: str):
        """Mở dialog thêm mã hàng mới (Custom hoặc Copy)."""
        try:
            dlg = AddItemCodeDialog(
                connection=self.connect.connection,
                db_name=db_name,
                parent=None,
            )

            # Sau khi thêm thành công → refresh menu và (nếu Custom) mở config editor
            def _on_added(name: str, item_id: int, mode: str):
                self.update_menu()
                if mode == 'custom':
                    self.open_config_editor(name, db_name)

            dlg.item_added.connect(_on_added)
            dlg.exec_()

        except Exception as e:
            _log.error("Error opening add-itemcode dialog: %s", e)
            QtWidgets.QMessageBox.critical(None, "Lỗi", f"Không thể mở dialog thêm mã hàng:\n{e}")