
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
import subprocess
import platform
from module_1.root_path import resource_path, get_mysql_config_path
from app_logger.app_logger import get_logger as _get_logger, open_log_window
_log = _get_logger('module_1.database')

class Connect2Mysql:

    def __init__(self,ui_connection_sql,ui_mainwindow,uicmin,connection):
        self.ui_mainwindow = ui_mainwindow
        self.ui_connection_sql = ui_connection_sql
        self.uicmin = uicmin
        self.connection = connection
        self.cursor = None
        self.driver_loader = None
        self._translate = QtCore.QCoreApplication.translate
        self.flag = False
    
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

    def make_sql_in4_login(self):
        try:
            self.cursor = self.connection.cursor()
            name_database = 'DATA_AUTO_LOGIN'
            self.cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{name_database}`")
            self.cursor.execute(f"""CREATE TABLE IF NOT EXISTS `{name_database}`.INFOR (
                id INT AUTO_INCREMENT PRIMARY KEY,
                hostname VARCHAR(255),
                username VARCHAR(255),
                password VARCHAR(255),
                port VARCHAR(255),
                manual BOOLEAN DEFAULT FALSE,
                automatic BOOLEAN DEFAULT FALSE,
                credential BOOLEAN DEFAULT FALSE,
                retry_attemps INT NOT NULL
            )""")
        except mysql.connector.Error as error:
            self.connection.rollback()
            QMessageBox.critical(None, "Error", f"Lỗi query: {str(error)}")
            logging.error(f"Lỗi {error}")
            _log.warning(f"Error: {str(error)}")
            raise
        
    def save_data_login(self):
        if self.ui_connection_sql.checkBox_save_infor_login.isChecked():
            if self.flag:
                self.cursor.execute("""
                    SELECT * FROM `DATA_AUTO_LOGIN`.`INFOR` 
                    WHERE hostname = %s
                """, (self.hostname,))
                
                results = self.cursor.fetchall()
                if results:
                    self.cursor.execute("""
                        DELETE FROM `DATA_AUTO_LOGIN`.`INFOR` WHERE hostname = %s
                    """, (self.hostname,))

                    self.cursor.execute("""
                            INSERT IGNORE INTO `DATA_AUTO_LOGIN`.`INFOR` (
                                hostname, username, password, port
                            ) VALUES (%s, %s, %s, %s)
                        """, (
                            self.hostname,
                            self.username,
                            self.password,
                            self.port,
                        ))
                    self.connection.commit()
                else:
                    self.cursor.execute("""
                            INSERT IGNORE INTO `DATA_AUTO_LOGIN`.`INFOR` (
                                hostname, username, password, port
                            ) VALUES (%s, %s, %s, %s)
                        """, (
                            self.hostname,
                            self.username,
                            self.password,
                            self.port,
                        ))
                    self.connection.commit()
            else:
                self.connection.rollback()
                QMessageBox.warning(None, "Lỗi", "Không thể kết nối đến MySQL.")
                _log.warning(f"Error: Không thể kết nối đến MySQL")

    def connect_to_mysql(self):

        if not self.ui_connection_sql.lineEdit_hostname.text():
            QMessageBox.warning(None, "Lỗi", "Vui lòng nhập hostname!")
            return
        if not self.ui_connection_sql.lineEdit_username.text():
            QMessageBox.warning(None, "Lỗi", "Vui lòng nhập username!")
            return
        if not self.ui_connection_sql.lineEdit_password.text():
            QMessageBox.warning(None, "Lỗi", "Vui lòng nhập password!")
            return
        if not self.ui_connection_sql.lineEdit_port.text():
            QMessageBox.warning(None, "Lỗi", "Vui lòng nhập port!")
            return
        layer = self.ui_connection_sql
        self.hostname = layer.lineEdit_hostname.text()
        self.username = layer.lineEdit_username.text()
        self.password = layer.lineEdit_password.text()
        self.port     = layer.lineEdit_port.text()

        if self.connection:
            self.connection.close()
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
                self.make_sql_in4_login()
                self.write_mysql_config(self.hostname, self.username, self.password, self.port, database='DATA_AUTO_LOGIN')
                self.uicmin.btnExecute.setEnabled(True)
                self.flag = True
            else:
                QMessageBox.warning(None, "Lỗi", "Không thể kết nối đến MySQL.")
        except Error as e:
            QMessageBox.critical(None, "Lỗi kết nối", f"Lỗi: {str(e)}")

    def write_mysql_config(self, host, user, password, port, database, filepath=None):
        if filepath is None:
            filepath = get_mysql_config_path(for_writing=True)
        try:
            with open(filepath, 'w') as f:
                f.write(f"host={host}\n")
                f.write(f"user={user}\n")
                f.write(f"password={password}\n")
                f.write(f"port={port}\n")
                f.write(f"database={database}\n")
            _log.info('Success to write mysql config to %s', filepath)
            return True
        except Exception as e:
            _log.warning('Failed to write mysql config: %s', e)
            return False

    def create_item_code_device(self):
        if not self.uicmin.lineEdit_name_devic.text():
            QMessageBox.warning(None, "Lỗi", "Vui lòng nhập tên thiết bị!")
            return
        reply = QMessageBox.question(
            None, "Xác nhận", f"Xác nhận tên thiết bị: {self.uicmin.lineEdit_name_devic.text()}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if not self.connection or not self.connection.is_connected():
                QMessageBox.critical(None, "Error", "Chưa có kết nối đến cơ sở dữ liệu (MySQL). Vui lòng kiểm tra lại kết nối!")
                return
                
            try:
                db_name = self.uicmin.lineEdit_name_devic.text().strip()
                self.cursor = self.connection.cursor()
                self.cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
                for table in TABLES:
                    table_sql = table.replace("CREATE TABLE IF NOT EXISTS ", f"CREATE TABLE IF NOT EXISTS `{db_name}`.")
                    self.cursor.execute(table_sql)
                QMessageBox.information(None, "Thành công", "Thiết lập cơ sở dữ liệu thành công")
                self.uicmin.pushButton_2.setEnabled(True)
            except Exception as error:
                if self.connection and self.connection.is_connected():
                    self.connection.rollback()
                QMessageBox.critical(None, "Error", f"Lỗi khởi tạo DB: {str(error)}, Login vào MySQL Workbench, sau đó kết nối lại.")
                logging.error(f"Lỗi: {error}")

    def insert_item_code(self, item_code):
        try:
            db_name = self.uicmin.lineEdit_name_devic.text().strip()
            self.cursor.execute(f"""
                INSERT IGNORE INTO `{db_name}`.ITEMS_CODE (name_line_code)
                VALUES (%s)
            """, (item_code,))
            self.connection.commit()
            
            self.cursor.execute(f"""
                SELECT id FROM `{db_name}`.ITEMS_CODE 
                WHERE name_line_code = %s
            """, (item_code,))
            
            result = self.cursor.fetchone()
            return result[0] if result else None
        except Error as e:
            self.connection.rollback()
            return None

    def insert_camera_data(self, camera_data, item_code_id):
        try:
            db_name = self.uicmin.lineEdit_name_devic.text().strip()
            for index, camera in enumerate(camera_data.get("camera_tabs", []), 1):
                self.cursor.execute(f"""
                    INSERT IGNORE INTO `{db_name}`.NUMS_CAMERA (
                        nums_camera, device_type, device_serial, 
                        connection_type, ip_address, item_code_id
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    index,
                    camera.get("camera_type", "Unknown"),
                    camera.get("serial", "0"),
                    camera.get("port", "Unknown"),
                    camera.get("ip_address", "Unknown"),
                    item_code_id
                ))

                self.cursor.execute(f"""
                    SELECT id FROM `{db_name}`.NUMS_CAMERA 
                    WHERE nums_camera = %s AND item_code_id = %s
                """, (index, item_code_id))
                
                camera_result = self.cursor.fetchone()
                if camera_result:
                    camera_id = camera_result[0]
                    for model_index in range(1, int(camera.get("model_count", "0")) + 1):
                        self.cursor.execute(f"""
                            INSERT IGNORE INTO `{db_name}`.NUMS_MODEL (nums_model, camera_id)
                            VALUES (%s, %s)
                        """, (model_index, camera_id))
            
            self.connection.commit()
            return True
        except Error as e:
            self.connection.rollback()
            return False
        
    def is_valid_ip(self, ip):
        if ip == 'N/A':
            return True
        ip_parts = ip.split('.')
        if len(ip_parts) != 4:
            return False
        for part in ip_parts:
            if not part.isdigit():
                return False
            part_int = int(part)
            if not (0 <= part_int <= 255):
                return False
        if ip_parts[0] == '127':
            return False
        if ip_parts[0] == '0' or (224 <= part_int <= 239):
            return False
        
        return True

    def commitment(self):
        try:
            list_device_data = []
            list_num_models = []
            for item_code, device_data in self.ui_mainwindow.list_item_code.items():
                for index, camera in enumerate(device_data.get("camera_tabs", []), 1):
                    list_num_models.append(int(camera.get("model_count", 0)))
            # if sum(list_num_models) > 8:
            #     QMessageBox.critical(None, "Error", "Tổng số lượng model nhiều hơn 8, vui lòng kiểm tra lại")
            #     return
                
            for item_code, device_data in self.ui_mainwindow.list_item_code.items():
                for index, camera in enumerate(device_data.get("camera_tabs", []), 1):
                    if camera.get("serial", "0") != '' or (camera.get("ip_address", "") != '' and camera.get("ip_address", "") != 'N/A' and self.is_valid_ip(camera.get("ip_address", ""))):
                            if list_device_data == []:
                                list_device_data.append(device_data)
                if len(list_device_data) == 1 :
                    item_code_id = self.insert_item_code(item_code)
                    if item_code_id is not None:
                        if not self.insert_camera_data(list_device_data[0], item_code_id):
                            QMessageBox.critical(None, "Error", f"Không thể chèn dữ liệu cho {item_code}")
                            return
                elif len(list_device_data) > 1:
                    QMessageBox.critical(None, "Error", f"Vui lòng xem lại cấu hình mã hàng với số lượng nhiều hơn 1")
                    return
                else:
                    QMessageBox.critical(None, "Error", f"Vui lòng xem lại cấu hình mã hàng với số lượng bằng 0")
                    return
                    
            if self.connection and self.connection.is_connected():
                QMessageBox.information(None,"Succesfull",f"Thiết lập Line Code {device_data.get('device_name','')} thành công")
                
        except Error as e:
            QMessageBox.critical(None, "Error", f"Lỗi kết nối MySQL: {e}")