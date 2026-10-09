
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

    def make_sql_in4_login(self):
        try:
            self.cursor = self.connection.cursor()
            name_database = 'DATA_AUTO_LOGIN'
            self.cursor.execute(f"CREATE DATABASE IF NOT EXISTS {name_database}")
            self.cursor.execute(f"USE {name_database}")
            tables = [
                """CREATE TABLE IF NOT EXISTS INFOR (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    hostname VARCHAR(255),
                    username VARCHAR(255),
                    password VARCHAR(255),
                    port VARCHAR(255),
                    manual BOOLEAN DEFAULT FALSE,
                    automatic BOOLEAN DEFAULT FALSE,
                    credential BOOLEAN DEFAULT FALSE,
                    retry_attemps INT NOT NULL
                )"""]
            
            self.cursor.execute(tables[0])
        except mysql.connector.Error as error:
                self.connection.rollback()
                QMessageBox.critical(None, "Error", f"Lỗi query: {str(error)}")
                logging.error(f"Lỗi {error}")
                raise
        
    def save_data_login(self):
        layer = self.ui_connection_sql
        self.hostname    = layer.lineEdit_Host_name.text()
        self.username    = layer.lineEdit_UserName.text()
        self.password    = '123456789' if layer.lineEdit_password.text() == '' else layer.lineEdit_password.text()
        self.port        = layer.lineEdit_port.text()
        self.manual      = layer.radioButton_manual_login.isChecked()
        self.automatic   = layer.radioButton_automatic_login.isChecked()
        if self.flag:
            self.cursor = self.connection.cursor()
            self.cursor.execute(f"USE DATA_AUTO_LOGIN")
            self.cursor.execute("""
                SELECT * FROM INFOR 
                WHERE hostname = %s
            """, (self.hostname,))
            if results := self.cursor.fetchall():
                self.cursor.execute("""
                    DELETE FROM INFOR """)
                
            self.cursor.execute("""
                    INSERT IGNORE INTO INFOR (
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
        if not self.ui_connection_sql.lineEdit_password.text():
            QMessageBox.warning(None, "Lỗi", "Vui lòng nhập password!")
            return
        if not self.ui_connection_sql.lineEdit_port.text():
            QMessageBox.warning(None, "Lỗi", "Vui lòng nhập port!")
            return
            
        layer = self.ui_connection_sql
        self.hostname    = layer.lineEdit_Host_name.text()
        self.username    = layer.lineEdit_UserName.text()
        self.password    = layer.lineEdit_password.text()
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
                layer.groupBox_plc_connection.setEnabled(True)
                layer.pushButton_apply_login_setting.setEnabled(True)
            else:
                self.flag = False
                layer.groupBox_plc_connection.setEnabled(True)
                layer.pushButton_apply_login_setting.setEnabled(True)
                QMessageBox.warning(None, "Lỗi", "Không thể kết nối đến MySQL.")
        except Error as e:
            QMessageBox.critical(None, "Lỗi kết nối", f"Lỗi: {str(e)}")

    def auto_mysql(self):
        if self.connection is not None:
            self.flag = True
            self.ui_connection_sql.radioButton_user_manual_login.setChecked(False)
        else:
            self.flag = False
            self.ui_connection_sql.radioButton_user_manual_login.setChecked(True)
            self.ui_connection_sql.lineEdit_Host_name.setEnabled(True)
            self.ui_connection_sql.lineEdit_UserName.setEnabled(True)
            self.ui_connection_sql.lineEdit_password.setEnabled(True)
            self.ui_connection_sql.lineEdit_port.setEnabled(True)
            self.ui_connection_sql.pushButton_test_connection.setEnabled(True)
            QMessageBox.warning(None, "Lỗi", "Không thể kết nối đến MySQL.")

    def load_mode_login(self):
        if self.main_core.mode_init:
            self.ui_connection_sql.radioButton_automatic_login.setChecked(True) 
            # self.ui_connection_sql.radioButton_manual_login.setEnabled(False)
        else:
            # self.ui_connection_sql.radioButton_automatic_login.setChecked(False)
            self.ui_connection_sql.radioButton_manual_login.setEnabled(True)

    def disconnect_mysql(self):
        try:
            if self.main_core.connection.is_connected():
                self.main_core.connection.close()
                self.main_core.mode_init = False
                QMessageBox.information(None,"Succesfull","Ngắt kết nối thành công MySQL")
        except:
            QMessageBox.information(None,"Something Wrong!!","Đang ngắt kết nối với MySQL") 
            return
