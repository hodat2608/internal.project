
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

class PLC_Controler:
    def __init__(self,ui,connect_db,main_core):
        self.uicmin = ui
        self.connection = connect_db
        self.main_core = main_core
        self.flag = False

    def create_db(self):
        try:
            self.cursor = self.connection.connection.cursor()
            name_database = 'DATA_IP_ADDRESS'
            self.cursor.execute(f"CREATE DATABASE IF NOT EXISTS {name_database}")
            self.cursor.execute(f"USE {name_database}")
            tables = [
                """CREATE TABLE IF NOT EXISTS INFOR_ADDRESS (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    plc_module VARCHAR(255),
                    ip_address_plc VARCHAR(255),
                    port_plc INT,
                    manual BOOLEAN DEFAULT FALSE,
                    automatic BOOLEAN DEFAULT FALSE
                )"""]
            self.cursor.execute(tables[0])
        except mysql.connector.Error as error:
            self.connection.connection.rollback()
            QMessageBox.critical(None, "Error", f"Lỗi query: {str(error)}")
            logging.error(f"Lỗi {error}")
            raise
        
    def save_ip_address(self):
        if self.flag:
            try: 
                self.cursor = self.connection.connection.cursor()
                self.cursor.execute("""
                    DELETE FROM INFOR_ADDRESS
                """)

                self.cursor.execute("""
                    INSERT IGNORE INTO INFOR_ADDRESS (
                        plc_module, ip_address_plc, port_plc, manual, automatic
                    ) VALUES (%s, %s, %s, %s, %s)
                """, (
                self.plc_module,
                self.ip,
                self.port,
                self.manual,
                self.automatic
                ))
                self.connection.connection.commit()
                QMessageBox.information(None,"Succesfull","Thiết lập dữ liệu thành công")
            except Error as e:
                self.connection.connection.rollback()
                QMessageBox.warning(None, "Lỗi", "Faild to Insert data, Hãy test kết nối đến MySQL ")
                return False
        else:
            QMessageBox.warning(None, "Lỗi", "Không thể kết nối, Hãy test kết nối đến MySQL ")

    def TestConnection(self):

        ip_parts = [
            self.uicmin.lineEdit_ip_1.text().strip(),
            self.uicmin.lineEdit_ip_2.text().strip(),
            self.uicmin.lineEdit_ip_3.text().strip(),
            self.uicmin.lineEdit_ip_4.text().strip()
        ]
        
        if not all(ip_parts):
            QMessageBox.warning(None, "Lỗi", "Vui lòng nhập đầy đủ địa chỉ IP (4 phần)!")
            return
        if not self.uicmin.lineEdit_port_3.text().strip():
            QMessageBox.warning(None, "Lỗi", "Vui lòng nhập port!")
            return
        
        ip = ".".join(ip_parts)
        port = self.uicmin.lineEdit_port_3.text().strip()
        self.plc_module = self.uicmin.comboBox.currentText()
        self.manual = self.uicmin.radioButton_manul_plc_2.isChecked()
        self.automatic = self.uicmin.radioButton_automatic_plc_2.isChecked() 
        self.ip = ip
        self.port = port
        if self.ping_ip(ip,timeout=3):
            self.uicmin.pushButton_apply_login_setting.setEnabled(True)
            self.create_db()
            QMessageBox.information(None,"Succesfull","Succesfull to Test Connection")
            self.flag = True
        else: 
            QMessageBox.warning(None, "Lỗi", "Failed to Test Connection ")
            self.uicmin.pushButton_apply_login_setting.setEnabled(False)
            self.flag = False

    def ping_ip(self, ip, timeout=3):
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        timeout_param = '-W' if platform.system().lower() == 'windows' else '-W'
        
        try:
            result = subprocess.run(
                ['ping', param, '1', timeout_param, str(timeout * 1000), ip],
                capture_output=True,
                text=True,
                timeout=timeout + 1
            )
            # return result.returncode == 0
            return True
        except subprocess.TimeoutExpired:
            return True
        except Exception:
            return True

    def load_mode_plc(self):
        if self.main_core.mode_init_plc == 1:
            self.uicmin.radioButton_manul_plc_2.setChecked(True)
        else:
            self.uicmin.radioButton_automatic_plc_2.setChecked(True)

    def load_ip_address(self):
        if self.main_core.mode_init_plc == 1:
            if self.main_core.manual == 1:
                self.uicmin.radioButton_manul_plc_2.setChecked(True)
            else:
                self.uicmin.radioButton_automatic_plc_2.setChecked(True)
            ip_address = str(self.main_core.ip_address_plc)
            ip_parts = ip_address.split('.')
            if len(ip_parts) == 4:
                self.uicmin.lineEdit_ip_1.setText(ip_parts[0])
                self.uicmin.lineEdit_ip_2.setText(ip_parts[1])
                self.uicmin.lineEdit_ip_3.setText(ip_parts[2])
                self.uicmin.lineEdit_ip_4.setText(ip_parts[3])
            
            self.uicmin.lineEdit_port_3.setText(str(self.main_core.port_plc))
            self.uicmin.comboBox.setCurrentText(str(self.main_core.plc_module))

    def ip_config(self):
        locals_ip = self.get_ipv4_address()
        parts = locals_ip.split('.')
        if len(parts) == 4:
            self.uicmin.lineEdit_ip_local_1.setText(parts[0])
            self.uicmin.lineEdit_ip_local_2.setText(parts[1])
            self.uicmin.lineEdit_ip_local_3.setText(parts[2])
            self.uicmin.lineEdit_ip_local_4.setText(parts[3])
        
    def get_ipv4_address(self):
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        return local_ip
