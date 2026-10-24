
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

from module_6.mitsubishi.initial import SocketClient as Mitsubishi_Socket_Client
from module_6.keyence.initial import KeyenceClient as Keyence_Socket_Client
from module_6.omron.initial import OmronClient as Omron_Socket_Client

PLC_COLLECT = {
   'KEYENCE' : Keyence_Socket_Client,
   'OMRON' : Omron_Socket_Client,
   'MITSUBISHI': Mitsubishi_Socket_Client
}

class PLC_Controler:
    def __init__(self,ui,main_core):
        self.uicmin = ui
        self.main_core = main_core
        self.flag = False

    def create_db(self):
        try:
            self.cursor = self.main_core.connection.cursor()
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
            self.main_core.connection.rollback()
            QMessageBox.critical(None, "Error", f"Lỗi query: {str(error)}")
            logging.error(f"Lỗi {error}")
            raise
        
    def save_ip_address(self):
        # if self.flag:
            try: 
                plc_module = self.uicmin.comboBox.currentText()
                manual = self.uicmin.radioButton_manul_plc_2.isChecked()
                automatic = self.uicmin.radioButton_automatic_plc_2.isChecked() 
                ip = self.uicmin.lineEdit_ip_address_2.text().strip()
                port = self.uicmin.lineEdit_port_3.text().strip()
                self.cursor = self.main_core.connection.cursor()
                self.cursor.execute("""
                    DELETE FROM DATA_IP_ADDRESS.INFOR_ADDRESS
                """)

                self.cursor.execute("""
                    INSERT IGNORE INTO DATA_IP_ADDRESS.INFOR_ADDRESS (
                        plc_module, ip_address_plc, port_plc, manual, automatic
                    ) VALUES (%s, %s, %s, %s, %s)
                """, (
                    plc_module,
                    ip,
                    port,
                    manual,
                    automatic
                ))
                self.main_core.connection.commit()
                QMessageBox.information(None,"Succesfull","Thiết lập dữ liệu thành công")
            except Error as e:
                self.main_core.connection.rollback()
                QMessageBox.warning(None, "Lỗi", f"Faild to Insert data, Hãy test kết nối đến MySQL,{e} ")
                return False
        # else:
        #     QMessageBox.warning(None, "Lỗi", "Không thể kết nối, Hãy test kết nối đến MySQL ")

    def TestConnection(self):
        if hasattr(self.uicmin, 'lineEdit_ip_address_2'):
            ip = self.uicmin.lineEdit_ip_address_2.text().strip()
        else:
            ip_parts = [
                getattr(self.uicmin, f'lineEdit_ip_{i}', None) for i in range(1, 5)
            ]
            ip = ".".join(p.text().strip() for p in ip_parts if p)

        if not ip:
            QMessageBox.warning(None, "Lỗi", "Vui lòng nhập địa chỉ IP!")
            return
        port_text = self.uicmin.lineEdit_port_3.text().strip()
        if not port_text:
            QMessageBox.warning(None, "Lỗi", "Vui lòng nhập port!")
            return
        
        try:
            port = int(port_text)
        except ValueError:
            QMessageBox.warning(None, "Lỗi", "Port phải là một số nguyên!")
            return

        self.plc_module = self.uicmin.comboBox.currentText()
        self.manual = self.uicmin.radioButton_manul_plc_2.isChecked()
        self.automatic = self.uicmin.radioButton_automatic_plc_2.isChecked() 
        self.ip = ip
        self.port = port

        apply_btn = getattr(self.uicmin, 'pushButton_apply_ip_add_setting_2', None) or getattr(self.uicmin, 'pushButton_apply_login_setting', None)

        if self.ping_ip(ip, timeout=1):
            if self.socket_connect():
                if apply_btn:
                    apply_btn.setEnabled(True)
                QMessageBox.information(None, "Succesfull", "Succesfull to Connect to PLC")
                self.flag = True
                 # 1. Badge trạng thái trên thanh Header chính của ứng dụng (label_status_plc)
                if hasattr(self.uicmin, 'label_status_plc'):
                    self._update_badge(
                        label=self.uicmin.label_status_plc,
                        is_connected=self.flag,
                        online_text="●  PLC  ONLINE",
                        offline_text="●  PLC  OFFLINE",
                        online_state="plc_online",
                        offline_state="plc_offline",
                        online_bg="#F0FDF4",
                        online_color="#166534",
                        online_border="#DCFCE7"
                    )

                # 2. Badge trạng thái trong Tab Auto Connect PLC (label_plc_state)
                if hasattr(self.uicmin, 'label_plc_state'):
                    self._update_badge(
                        label=self.uicmin.label_plc_state,
                        is_connected=self.flag,
                        online_text="●  CONNECTED",
                        offline_text="●  DISCONNECTED",
                        online_state="connected",
                        offline_state="disconnected",
                        online_bg="#DCFCE7",
                        online_color="#115E59",
                        online_border="#86EFAC"
                    )

                # 3. Badge trạng thái trong Tab PLC Signal Test (label_plc_conn_status)
                if hasattr(self.uicmin, 'label_plc_conn_status'):
                    self._update_badge(
                        label=self.uicmin.label_plc_conn_status,
                        is_connected=self.flag,
                        online_text="●  CONNECTED",
                        offline_text="●  DISCONNECTED",
                        online_state="connected",
                        offline_state="disconnected",
                        online_bg="#DCFCE7",
                        online_color="#115E59",
                        online_border="#86EFAC"
                    )
            else:
                QMessageBox.warning(None, "Lỗi", "Failed to Connect to PLC, Please check Port or PLC is OFF")
                if apply_btn:
                    apply_btn.setEnabled(False)
                self.flag = False
        else: 
            QMessageBox.warning(None, "Lỗi", "Ping Failed, Please check IP/Port or PLC is OFF")
            if apply_btn:
                apply_btn.setEnabled(False)
            self.flag = False
            # 1. Badge trạng thái trên thanh Header chính của ứng dụng (label_status_plc)
            if hasattr(self.uicmin, 'label_status_plc'):
                self._update_badge(
                    label=self.uicmin.label_status_plc,
                    is_connected=self.flag,
                    online_text="●  PLC  ONLINE",
                    offline_text="●  PLC  OFFLINE",
                    online_state="plc_online",
                    offline_state="plc_offline",
                    online_bg="#F0FDF4",
                    online_color="#166534",
                    online_border="#DCFCE7"
                )

            # 2. Badge trạng thái trong Tab Auto Connect PLC (label_plc_state)
            if hasattr(self.uicmin, 'label_plc_state'):
                self._update_badge(
                    label=self.uicmin.label_plc_state,
                    is_connected=self.flag,
                    online_text="●  CONNECTED",
                    offline_text="●  DISCONNECTED",
                    online_state="connected",
                    offline_state="disconnected",
                    online_bg="#DCFCE7",
                    online_color="#115E59",
                    online_border="#86EFAC"
                )

            # 3. Badge trạng thái trong Tab PLC Signal Test (label_plc_conn_status)
            if hasattr(self.uicmin, 'label_plc_conn_status'):
                self._update_badge(
                    label=self.uicmin.label_plc_conn_status,
                    is_connected=self.flag,
                    online_text="●  CONNECTED",
                    offline_text="●  DISCONNECTED",
                    online_state="connected",
                    offline_state="disconnected",
                    online_bg="#DCFCE7",
                    online_color="#115E59",
                    online_border="#86EFAC"
                )
            
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
            return False
        except Exception:
            return False
    
    def socket_connect(self):
        self.soc = PLC_COLLECT[self.plc_module](self.ip, self.port)
        return self.soc.connect()

    def read_plc_data(self):
        if not self.flag:
            QMessageBox.warning(None, "Lỗi", "Không thể kết nối, Hãy test kết nối đến PLC ")
            return False

        if self.manual:
            result = self.soc.read_plc(self.uicmin.lineEdit_read_register.text().strip())
            self.uicmin.lineEdit_read_value.setText(str(result))
            return result
        else:
            self.uicmin.lineEdit_read_value.setText("No Value....")
            return False
             
    def write_plc_data(self):
        if not self.flag:
            QMessageBox.warning(None, "Lỗi", "Không thể kết nối, Hãy test kết nối đến PLC ")
            return False

        if self.manual:
            result = self.soc.write_plc(self.uicmin.lineEdit_write_register.text().strip(),self.uicmin.lineEdit_write_value.text().strip())
            label_write_result = getattr(self.uicmin, 'label_write_result', None)
            if label_write_result:
                if result:
                    label_write_result.setText("Write Success")
                    label_write_result.setStyleSheet("color: green")
                else:
                    label_write_result.setText("Write Failed")
                    label_write_result.setStyleSheet("color: red")
            return result
        else:
            return False   

    def load_mode_plc(self):
        if self.main_core.mode_init_plc == 1:
            self.uicmin.radioButton_manul_plc_2.setChecked(True)
        else:
            self.uicmin.radioButton_automatic_plc_2.setChecked(True)

    @staticmethod
    def _update_badge(label, is_connected: bool, online_text: str, offline_text: str, online_state: str, offline_state: str, online_bg: str = "#DCFCE7", online_color: str = "#115E59", online_border: str = "#86EFAC"):
        """Cập nhật giao diện badge trạng thái kết nối PLC chuẩn đẹp, tương phản cao."""
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

    def load_ip_address_status(self):
        manual = getattr(self.main_core, 'manual', 1)
        automatic = getattr(self.main_core, 'automatic', 0)
        if manual == 1:
            self.uicmin.radioButton_manul_plc_2.setChecked(True)
            self.uicmin.radioButton_automatic_plc_2.setChecked(False)
        elif automatic == 1:
            self.uicmin.radioButton_automatic_plc_2.setChecked(True)
            self.uicmin.radioButton_manul_plc_2.setChecked(False)

        ip_address = str(getattr(self.main_core, 'ip_address_plc', '192.168.0.10'))
        self.uicmin.lineEdit_ip_address_2.setText(ip_address)
        self.uicmin.lineEdit_port_3.setText(str(getattr(self.main_core, 'port_plc', 5000)))
        self.uicmin.comboBox.setCurrentText(str(getattr(self.main_core, 'plc_module', 'KEYENCE')))

        is_connected = bool(getattr(self.main_core, 'driver_loader', None))

        # 1. Badge trạng thái trên thanh Header chính của ứng dụng (label_status_plc)
        if hasattr(self.uicmin, 'label_status_plc'):
            self._update_badge(
                label=self.uicmin.label_status_plc,
                is_connected=is_connected,
                online_text="●  PLC  ONLINE",
                offline_text="●  PLC  OFFLINE",
                online_state="plc_online",
                offline_state="plc_offline",
                online_bg="#F0FDF4",
                online_color="#166534",
                online_border="#DCFCE7"
            )

        # 2. Badge trạng thái trong Tab Auto Connect PLC (label_plc_state)
        if hasattr(self.uicmin, 'label_plc_state'):
            self._update_badge(
                label=self.uicmin.label_plc_state,
                is_connected=is_connected,
                online_text="●  CONNECTED",
                offline_text="●  DISCONNECTED",
                online_state="connected",
                offline_state="disconnected",
                online_bg="#DCFCE7",
                online_color="#115E59",
                online_border="#86EFAC"
            )

        # 3. Badge trạng thái trong Tab PLC Signal Test (label_plc_conn_status)
        if hasattr(self.uicmin, 'label_plc_conn_status'):
            self._update_badge(
                label=self.uicmin.label_plc_conn_status,
                is_connected=is_connected,
                online_text="●  CONNECTED",
                offline_text="●  DISCONNECTED",
                online_state="connected",
                offline_state="disconnected",
                online_bg="#DCFCE7",
                online_color="#115E59",
                online_border="#86EFAC"
            )

        # 4. Dòng thông tin mục tiêu kết nối (label_plc_conn_target)
        if hasattr(self.uicmin, 'label_plc_conn_target'):
            if is_connected:
                self.uicmin.label_plc_conn_target.setText(f"{self.main_core.plc_module} - {ip_address}:{self.main_core.port_plc}")
            else:
                self.uicmin.label_plc_conn_target.setText("Connect a PLC in “Auto Connect Device Control” first")
            

    def ip_config(self):
        locals_ip = self.get_ipv4_address()
        self.uicmin.lineEdit_local_ip_2.setText(locals_ip)
        
    def get_ipv4_address(self):
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        return local_ip
