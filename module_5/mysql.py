
import mysql.connector
from mysql.connector import Error
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QLineEdit, 
                             QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, 
                             QFrame, QComboBox, QScrollArea, QMessageBox, QSpinBox,
                             QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
                             QGroupBox)
import logging
import socket
from PyQt5.QtCore import Qt, QSize
from PyQt5 import QtCore, QtGui, QtWidgets
from module_1.table_db import *
from module_2.main_core import core
from app_logger.app_logger import get_logger as _get_logger
_log = _get_logger('module_5.mysql')
class MySQL_Core:

    def __init__(self,ui,main_core):
        self.ui_connection_sql = ui
        self.connection = main_core.connection
        self.main_core = main_core
        self.auto_mysql()

    def show_connection_success(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("MySQL Workbench")
        msg.setText("Successfully made the MySQL connection")
        msg.setInformativeText(
            "Information related to this connection:\n\n"
            "Host: 127.0.0.1\n"
            "Port: 3306\n"
            "User: root\n"
            "SSL: enabled with TLS_AES_128_GCM_SHA256\n\n"
            "A successful MySQL connection was made with\n"
            "the parameters defined for this connection."
        )
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
        
    def save_data_login(self):
        layer = self.ui_connection_sql
        self.hostname    = layer.lineEdit_Host_name.text()
        self.username    = layer.lineEdit_UserName.text()
        self.password    = layer.lineEdit_password.text() or '123456789'
        self.port        = layer.lineEdit_port.text()
        self.manual      = layer.radioButton_manual_login.isChecked()
        self.automatic   = layer.radioButton_automatic_login.isChecked()
        if self.flag:
            self.cursor = self.connection.cursor()
            self.cursor.execute("""
                SELECT * FROM `DATA_AUTO_LOGIN`.`INFOR` 
                WHERE hostname = %s
            """, (self.hostname,))
            results = self.cursor.fetchall()
            if results:
                self.cursor.execute("""
                    DELETE FROM `DATA_AUTO_LOGIN`.`INFOR` """)
                
            self.cursor.execute("""
                    INSERT IGNORE INTO `DATA_AUTO_LOGIN`.`INFOR` (
                        hostname, username, password, port, manual, automatic
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    self.hostname,
                    self.username,
                    self.password,
                    self.port,
                    self.manual,
                    self.automatic
                ))
            self.connection.commit()
            core.write_mysql_config(self,host=self.hostname,user=self.username,password=self.password,port=self.port,database='DATA_AUTO_LOGIN',)
            QMessageBox.information(None,"Succesfull","Thiết lập dữ liệu thành công")
        else:
            self.connection.rollback()
            QMessageBox.warning(None, "Lỗi", "Không thể kết nối, Hãy test kết nối đến MySQL ")
        
    def connect_to_mysql(self):

        if not self.ui_connection_sql.lineEdit_Host_name.text():
            QMessageBox.warning(None, "Lỗi", "Vui lòng nhập hostname!")
            return
        if not self.ui_connection_sql.lineEdit_UserName.text():
            QMessageBox.warning(None, "Lỗi", "Vui lòng nhập username!")
            return
        if not self.ui_connection_sql.lineEdit_port.text():
            QMessageBox.warning(None, "Lỗi", "Vui lòng nhập port!")
            return
            
        layer = self.ui_connection_sql
        self.hostname    = layer.lineEdit_Host_name.text()
        self.username    = layer.lineEdit_UserName.text()
        self.password    = layer.lineEdit_password.text() or '123456789'
        self.port        = layer.lineEdit_port.text()
        self.manual      = layer.radioButton_manual_login.isChecked()
        self.automatic   = layer.radioButton_automatic_login.isChecked()

        try:
            self.connection = mysql.connector.connect(
                host=self.hostname,
                user=self.username,
                password=self.password,
                port=int(self.port) if self.port else 3306,
                use_pure=True
            )
            if self.connection.is_connected():
                self.show_connection_success()
                self.flag = True
                # layer.groupBox_plc_connection.setEnabled(True)
                layer.pushButton_apply_login_setting.setEnabled(True)
                self.update_mysql_badges(True)
            else:
                self.flag = False
                # layer.groupBox_plc_connection.setEnabled(True)
                layer.pushButton_apply_login_setting.setEnabled(True)
                self.update_mysql_badges(False)
                QMessageBox.warning(None, "Lỗi", "Không thể kết nối đến MySQL.")
        except Error as e:
            self.update_mysql_badges(False)
            QMessageBox.critical(None, "Lỗi kết nối", f"Lỗi: {str(e)}")

    def auto_mysql(self):
        if self.connection is not None:
            self.flag = True
        else:
            self.flag = False
            self.ui_connection_sql.lineEdit_Host_name.setEnabled(True)
            self.ui_connection_sql.lineEdit_UserName.setEnabled(True)
            self.ui_connection_sql.lineEdit_password.setEnabled(True)
            self.ui_connection_sql.lineEdit_port.setEnabled(True)
            self.ui_connection_sql.pushButton_test_connection.setEnabled(True)

    @staticmethod
    def _update_badge(label, is_connected: bool, online_text: str, offline_text: str, online_state: str, offline_state: str, online_bg: str = "#DCFCE7", online_color: str = "#115E59", online_border: str = "#86EFAC"):
        """Cập nhật giao diện badge trạng thái kết nối MySQL chuẩn đẹp, tương phản cao."""
        if not label:
            return
        state = online_state if is_connected else offline_state
        text = online_text if is_connected else offline_text
        label.setText(text)
        label.setProperty("state", state)
        label.setStyleSheet(f"""
            QLabel {{
                background-color: #FEF2F2;
                color: #991B1B;
                border: 1px solid #FCA5A5;
                border-radius: 11px;
                padding: 4px 14px;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 8pt;
                font-weight: 700;
            }}
            QLabel[state="{online_state}"] {{
                background-color: {online_bg};
                color: {online_color};
                border: 1px solid {online_border};
            }}
        """)
        label.style().unpolish(label)
        label.style().polish(label)

    def update_mysql_badges(self, is_connected: bool):
        """Cập nhật trạng thái cho cả 2 badge: label_status_mysql (Header) và label_mysql_state (Tab)"""
        # 1. Badge trạng thái trên thanh Header chính (label_status_mysql)
        if hasattr(self.ui_connection_sql, 'label_status_mysql'):
            self._update_badge(
                label=self.ui_connection_sql.label_status_mysql,
                is_connected=is_connected,
                online_text="●  MYSQL  ONLINE",
                offline_text="●  MYSQL  OFFLINE",
                online_state="mysql_online",
                offline_state="mysql_offline",
                online_bg="#F0FDF4",
                online_color="#166534",
                online_border="#DCFCE7"
            )

        # 2. Badge trạng thái trong Tab Database Login (label_mysql_state)
        if hasattr(self.ui_connection_sql, 'label_mysql_state'):
            self._update_badge(
                label=self.ui_connection_sql.label_mysql_state,
                is_connected=is_connected,
                online_text="●  CONNECTED",
                offline_text="●  DISCONNECTED",
                online_state="connected",
                offline_state="disconnected",
                online_bg="#DCFCE7",
                online_color="#115E59",
                online_border="#86EFAC"
            )

    def load_mode_login(self):
        # 1. Tự động nạp thông tin kết nối thực tế (Host, User, Password, Port) lên các ô nhập liệu giao diện
        loaded_cfg = False
        is_auto = True
        try:
            conn = getattr(self.main_core, 'connection', None) or self.connection
            if conn and conn.is_connected():
                cursor = conn.cursor()
                cursor.execute("SELECT hostname, username, password, port, manual, automatic FROM `DATA_AUTO_LOGIN`.`INFOR` LIMIT 1")
                row = cursor.fetchone()
                cursor.close()
                if row:
                    h, u, p, port, manual, automatic = row[0], row[1], row[2], row[3], bool(row[4]), bool(row[5])
                    if h: self.ui_connection_sql.lineEdit_Host_name.setText(str(h))
                    if u: self.ui_connection_sql.lineEdit_UserName.setText(str(u))
                    if p is not None: self.ui_connection_sql.lineEdit_password.setText(str(p))
                    if port: self.ui_connection_sql.lineEdit_port.setText(str(port))
                    is_auto = (not manual and automatic)
                    loaded_cfg = True
        except Exception as e:
            _log.debug("Lỗi đọc cấu hình từ DB INFOR: %s", e)

        # Nếu chưa nạp được từ DB (hoặc chưa kết nối), nạp trực tiếp từ file mysql_config.log / .bak
        if not loaded_cfg:
            try:
                cfg = None
                if hasattr(self.main_core, 'read_mysql_config'):
                    cfg = self.main_core.read_mysql_config()
                if not cfg:
                    from module_2.main_core import core as CoreClass
                    cfg = CoreClass.read_mysql_config(self.main_core if self.main_core else None)
                if cfg:
                    if cfg.get('host'):
                        self.ui_connection_sql.lineEdit_Host_name.setText(str(cfg['host']))
                    if cfg.get('user'):
                        self.ui_connection_sql.lineEdit_UserName.setText(str(cfg['user']))
                    if 'password' in cfg and cfg['password'] is not None:
                        self.ui_connection_sql.lineEdit_password.setText(str(cfg['password']))
                    if cfg.get('port'):
                        self.ui_connection_sql.lineEdit_port.setText(str(cfg['port']))
            except Exception as e:
                _log.debug("Lỗi đọc cấu hình từ file log: %s", e)

        if not self.ui_connection_sql.lineEdit_password.text():
            self.ui_connection_sql.lineEdit_password.setText('123456789')

        if is_auto:
            self.ui_connection_sql.radioButton_automatic_login.setChecked(True)
            self.ui_connection_sql.radioButton_manual_login.setChecked(False)
        else:
            self.ui_connection_sql.radioButton_automatic_login.setChecked(False)
            self.ui_connection_sql.radioButton_manual_login.setChecked(True)

        # Cập nhật trạng thái 2 label: label_mysql_state và label_status_mysql
        is_connected = bool(self.connection and hasattr(self.connection, 'is_connected') and self.connection.is_connected())
        self.update_mysql_badges(is_connected)

    def disconnect_mysql(self):
        try:
            conn = getattr(self.main_core, 'connection', None) or self.connection
            if conn and conn.is_connected():
                conn.close()
                self.main_core.mode_init = False
                self.main_core.connection = None
                self.connection = None
                self.update_mysql_badges(False)
                QMessageBox.information(None, "Succesfull", "Ngắt kết nối thành công MySQL")
        except:
            self.update_mysql_badges(False)
            QMessageBox.information(None, "Something Wrong!!", "Đang ngắt kết nối với MySQL") 
            return
