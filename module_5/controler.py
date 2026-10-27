
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
import os
from module_1.root_path import get_trigger_file_path

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
        self.manual = True
        self.soc = getattr(main_core, 'driver_loader', None)

    def create_db(self):
        try:
            self.cursor = self.main_core.connection.cursor()
            name_database = 'DATA_IP_ADDRESS'
            self.cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{name_database}`")
            tables = [
                f"""CREATE TABLE IF NOT EXISTS `{name_database}`.INFOR_ADDRESS (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    plc_module VARCHAR(255),
                    connection_port VARCHAR(255),
                    ip_address_plc VARCHAR(255),
                    port_plc INT,
                    manual BOOLEAN DEFAULT FALSE,
                    automatic BOOLEAN DEFAULT FALSE,
                    local_ip VARCHAR(255),
                    retry_attempts INT NOT NULL DEFAULT 0,
                    auto_reconnect_on_disconnect BOOLEAN DEFAULT FALSE,
                    direct_to_plc BOOLEAN DEFAULT FALSE,
                    indirect_from_log BOOLEAN DEFAULT FALSE
                )"""]
            self.cursor.execute(tables[0])
            
            # Tự động kiểm tra và thêm các cột mới nếu bảng cũ đã tồn tại trong MySQL
            columns_to_add = [
                ("connection_port", "VARCHAR(255) DEFAULT 'Enthernet' AFTER plc_module"),
                ("local_ip", "VARCHAR(255) DEFAULT '' AFTER automatic"),
                ("retry_attempts", "INT NOT NULL DEFAULT 0 AFTER local_ip"),
                ("auto_reconnect_on_disconnect", "BOOLEAN DEFAULT FALSE AFTER retry_attempts"),
                ("direct_to_plc", "BOOLEAN DEFAULT TRUE AFTER auto_reconnect_on_disconnect"),
                ("indirect_from_log", "BOOLEAN DEFAULT FALSE AFTER direct_to_plc"),
            ]
            for col_name, col_def in columns_to_add:
                try:
                    self.cursor.execute(f"SHOW COLUMNS FROM `{name_database}`.INFOR_ADDRESS LIKE '{col_name}'")
                    if not self.cursor.fetchone():
                        self.cursor.execute(f"ALTER TABLE `{name_database}`.INFOR_ADDRESS ADD COLUMN {col_name} {col_def}")
                except Exception as col_err:
                    logging.warning(f"Could not add column {col_name} to INFOR_ADDRESS: {col_err}")
            self.main_core.connection.commit()
        except mysql.connector.Error as error:
            self.main_core.connection.rollback()
            QMessageBox.critical(None, "Error", f"Lỗi query: {str(error)}")
            logging.error(f"Lỗi {error}")
            raise
        
    def save_ip_address(self):
        try: 
            plc_module = self.uicmin.comboBox.currentText()
            connection_port = self.uicmin.comboBox_connection_type_2.currentText() if hasattr(self.uicmin, 'comboBox_connection_type_2') else 'Enthernet'
            ip = self.uicmin.lineEdit_ip_address_2.text().strip()
            port = self.uicmin.lineEdit_port_3.text().strip()
            manual = self.uicmin.radioButton_manul_plc_2.isChecked()
            automatic = self.uicmin.radioButton_automatic_plc_2.isChecked() 
            local_ip = self.uicmin.lineEdit_local_ip_2.text().strip() if hasattr(self.uicmin, 'lineEdit_local_ip_2') else ''
            retry_attempts = self.uicmin.spinBox_2.value() if hasattr(self.uicmin, 'spinBox_2') else 0
            auto_reconnect = self.uicmin.checkBox_2.isChecked() if hasattr(self.uicmin, 'checkBox_2') else False
            direct_to_plc = (self.uicmin.direct_to_plc.isChecked() if hasattr(self.uicmin, 'direct_to_plc')
                             else (self.uicmin.radioButton.isChecked() if hasattr(self.uicmin, 'radioButton') else True))
            indirect_from_log = (self.uicmin.indirect_from_log.isChecked() if hasattr(self.uicmin, 'indirect_from_log')
                                 else (self.uicmin.radioButton_2.isChecked() if hasattr(self.uicmin, 'radioButton_2') else False))

            self.cursor = self.main_core.connection.cursor()
            self.cursor.execute("""
                DELETE FROM DATA_IP_ADDRESS.INFOR_ADDRESS
            """)

            self.cursor.execute("""
                INSERT IGNORE INTO DATA_IP_ADDRESS.INFOR_ADDRESS (
                    plc_module, connection_port, ip_address_plc, port_plc,
                    manual, automatic, local_ip, retry_attempts,
                    auto_reconnect_on_disconnect, direct_to_plc, indirect_from_log
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                plc_module,
                connection_port,
                ip,
                port,
                manual,
                automatic,
                local_ip,
                retry_attempts,
                auto_reconnect,
                direct_to_plc,
                indirect_from_log
            ))
            self.main_core.connection.commit()

            # Đồng bộ trực tiếp vào main_core để các module khác nhận được ngay lập tức
            self.main_core.plc_module = plc_module
            self.main_core.connection_port = connection_port
            self.main_core.ip_address_plc = ip
            self.main_core.port_plc = port
            self.main_core.manual = manual
            self.main_core.automatic = automatic
            self.main_core.local_ip = local_ip
            self.main_core.retry_attempts = retry_attempts
            self.main_core.auto_reconnect_on_disconnect = auto_reconnect
            self.main_core.direct_to_plc = direct_to_plc
            self.main_core.indirect_from_log = indirect_from_log

            QMessageBox.information(None, "Successful", "Thiết lập dữ liệu kết nối PLC thành công")
            return True
        except Error as e:
            self.main_core.connection.rollback()
            QMessageBox.warning(None, "Lỗi", f"Failed to Insert data, Hãy test kết nối đến MySQL, {e}")
            return False

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

        # Nếu người dùng đang chọn chế độ mô phỏng qua LOG (Indirect from Log)
        if self.is_indirect_log_mode():
            self.flag = True
            try:
                self.soc = PLC_COLLECT.get(self.plc_module, Keyence_Socket_Client)(ip, port)
            except Exception:
                pass
            if apply_btn:
                apply_btn.setEnabled(True)
            QMessageBox.information(None, "Succesfull", "Chế độ mô phỏng (Log): Kết nối thành công!")

            # 1. Badge trạng thái trên thanh Header chính của ứng dụng (label_status_plc)
            if hasattr(self.uicmin, 'label_status_plc'):
                self._update_badge(
                    label=self.uicmin.label_status_plc,
                    is_connected=self.flag,
                    online_text="●  PLC  ONLINE (LOG)",
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
                    online_text="●  CONNECTED (LOG)",
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
                    online_text="●  CONNECTED (LOG)",
                    offline_text="●  DISCONNECTED",
                    online_state="connected",
                    offline_state="disconnected",
                    online_bg="#DCFCE7",
                    online_color="#115E59",
                    online_border="#86EFAC"
                )

            # 4. Cập nhật mục tiêu kết nối
            if hasattr(self.uicmin, 'label_plc_conn_target'):
                self.uicmin.label_plc_conn_target.setText(f"{self.plc_module} (Simulation Log) - {ip}:{port}")
            return

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

    # -----------------------------------------------------------------------
    # Helper xác định chế độ Đọc/Ghi PLC (Direct to PLC vs Indirect from Log)
    # -----------------------------------------------------------------------

    def is_indirect_log_mode(self) -> bool:
        """
        Kiểm tra chế độ giao tiếp PLC:
        - True: Chế độ mô phỏng qua LOG (indirect_from_log = True hoặc radio button indirect_from_log được check)
        - False: Chế độ kết nối trực tiếp thiết bị PLC (direct_to_plc = True hoặc radio button direct_to_plc được check)
        """
        # 1. Kiểm tra ưu tiên trực tiếp trên UI hiện hành
        radio_indirect = getattr(self.uicmin, 'indirect_from_log', None) or getattr(self.uicmin, 'radioButton_2', None)
        radio_direct = getattr(self.uicmin, 'direct_to_plc', None) or getattr(self.uicmin, 'radioButton', None)
        if radio_indirect and radio_indirect.isChecked():
            return True
        if radio_direct and radio_direct.isChecked():
            return False

        # 2. Kiểm tra từ thuộc tính main_core
        if self.main_core is not None:
            if bool(getattr(self.main_core, 'indirect_from_log', False)) is True:
                return True
            if hasattr(self.main_core, 'direct_to_plc') and bool(getattr(self.main_core, 'direct_to_plc')) is False:
                return True
            if bool(getattr(self.main_core, 'direct_to_plc', False)) is True:
                return False

        # 3. Kiểm tra từ CSDL DATA_IP_ADDRESS.INFOR_ADDRESS nếu có
        try:
            conn = getattr(self.main_core, 'connection', None)
            if conn and hasattr(conn, 'cursor') and callable(conn.cursor):
                cursor = conn.cursor()
                cursor.execute("SELECT direct_to_plc, indirect_from_log FROM DATA_IP_ADDRESS.INFOR_ADDRESS LIMIT 1")
                row = cursor.fetchone()
                cursor.close()
                if row:
                    direct_to_plc, indirect_from_log = bool(row[0]), bool(row[1])
                    return indirect_from_log or (not direct_to_plc)
        except Exception:
            pass

        return False

    def _get_trigger_file_path(self, register: str, for_writing: bool = False) -> str:
        """Lấy đường dẫn file trigger_{register}.txt trong AppData bền vững (không bị Access Denied)"""
        return get_trigger_file_path(register, for_writing=for_writing)

    def _read_plc_log(self, register: str):
        """Đọc giá trị PLC từ file log mô phỏng (trigger_{register}.txt)"""
        reg_clean = register.strip().replace(" ", "")
        if reg_clean.lower().startswith("trigger_"):
            reg_clean = reg_clean[8:]
        if reg_clean.lower().endswith(".txt"):
            reg_clean = reg_clean[:-4]

        # 1. Ưu tiên đọc trực tiếp từ file trigger_{register}.txt chuẩn trong AppData / bundle
        file_path = self._get_trigger_file_path(reg_clean, for_writing=False)
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    for line in content.splitlines():
                        line = line.strip()
                        if '=' in line:
                            file_reg, val = line.split('=', 1)
                            if file_reg.strip().upper() == reg_clean.upper():
                                val_str = val.strip()
                                try:
                                    return int(val_str)
                                except ValueError:
                                    try:
                                        return float(val_str)
                                    except ValueError:
                                        return val_str
                            else:
                                val_str = val.strip()
                                try:
                                    return int(val_str)
                                except ValueError:
                                    return val_str
                        elif line:
                            try:
                                return int(line)
                            except ValueError:
                                return line
        except Exception as e:
            logging.error(f"[PLC_Controler] _read_plc_log file read error: {e}")

        # 2. Thử qua self.soc hoặc driver_loader nếu có hàm read_plc_log
        for obj in (getattr(self, 'soc', None), getattr(self.main_core, 'driver_loader', None)):
            if obj is not None and hasattr(obj, 'read_plc_log') and callable(obj.read_plc_log):
                try:
                    return obj.read_plc_log(reg_clean)
                except Exception as e:
                    logging.warning(f"[PLC_Controler] read_plc_log failed via {obj}: {e}")

        return 0

    def _write_plc_log(self, register: str, value) -> bool:
        """Ghi giá trị PLC vào file log mô phỏng (trigger_{register}.txt) trong AppData"""
        reg_clean = register.strip().replace(" ", "")
        if reg_clean.lower().startswith("trigger_"):
            reg_clean = reg_clean[8:]
        if reg_clean.lower().endswith(".txt"):
            reg_clean = reg_clean[:-4]

        file_path = self._get_trigger_file_path(reg_clean, for_writing=True)
        success = False

        # 1. Ghi trực tiếp vào file trong AppData
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"{reg_clean} = {value}\n")
            success = True
        except Exception as e:
            logging.error(f"[PLC_Controler] _write_plc_log file write error: {e}")

        # 2. Đồng thời gọi qua self.soc hoặc driver_loader nếu có hàm write_plc_log
        for obj in (getattr(self, 'soc', None), getattr(self.main_core, 'driver_loader', None)):
            if obj is not None and hasattr(obj, 'write_plc_log') and callable(obj.write_plc_log):
                try:
                    res = obj.write_plc_log(reg_clean, value)
                    if res:
                        success = True
                except Exception as e:
                    logging.warning(f"[PLC_Controler] write_plc_log failed via {obj}: {e}")

        return success

    def read_plc_data(self):
        register = self.uicmin.lineEdit_read_register.text().strip()
        if not register:
            QMessageBox.warning(None, "Lỗi", "Vui lòng nhập tên thanh ghi cần đọc (ví dụ: DM1000)!")
            return False

        # Cơ chế Chuyển Đổi Đọc: Trực tiếp (Direct to PLC) vs Gián tiếp từ Log (Indirect from Log)
        if self.is_indirect_log_mode():
            result = self._read_plc_log(register)
            self.uicmin.lineEdit_read_value.setText(str(result))
            label_read_status = getattr(self.uicmin, 'label_read_status', None)
            if label_read_status:
                label_read_status.setText(f"Read Log Success: {result}")
                label_read_status.setStyleSheet("color: #0284C7; font-weight: bold;")
            return result
        else:
            if not self.flag:
                QMessageBox.warning(None, "Lỗi", "Không thể kết nối, Hãy test kết nối đến PLC hoặc chuyển sang chế độ mô phỏng Log (INDIRECT FROM LOG)!")
                return False

            if not getattr(self, 'soc', None):
                self.soc = getattr(self.main_core, 'driver_loader', None)

            if not self.soc:
                QMessageBox.warning(None, "Lỗi", "Chưa kết nối đến thiết bị PLC!")
                return False

            try:
                result = self.soc.read_plc(register)
                self.uicmin.lineEdit_read_value.setText(str(result))
                label_read_status = getattr(self.uicmin, 'label_read_status', None)
                if label_read_status:
                    label_read_status.setText(f"Read Success: {result}")
                    label_read_status.setStyleSheet("color: #16A34A; font-weight: bold;")
                return result
            except Exception as e:
                logging.error(f"[PLC_Controler] read_plc direct failed: {e}")
                label_read_status = getattr(self.uicmin, 'label_read_status', None)
                if label_read_status:
                    label_read_status.setText("Read Failed")
                    label_read_status.setStyleSheet("color: #DC2626; font-weight: bold;")
                QMessageBox.warning(None, "Lỗi", f"Lỗi đọc PLC: {e}")
                return False

    def write_plc_data(self):
        register = self.uicmin.lineEdit_write_register.text().strip()
        value = self.uicmin.lineEdit_write_value.text().strip()
        if not register:
            QMessageBox.warning(None, "Lỗi", "Vui lòng nhập tên thanh ghi cần ghi (ví dụ: DM1000)!")
            return False

        # Cơ chế Chuyển Đổi Ghi: Trực tiếp (Direct to PLC) vs Gián tiếp từ Log (Indirect from Log)
        if self.is_indirect_log_mode():
            result = self._write_plc_log(register, value)
            label_write_result = getattr(self.uicmin, 'label_write_result', None)
            if label_write_result:
                if result:
                    label_write_result.setText("Write Success (Log)")
                    label_write_result.setStyleSheet("color: green; font-weight: bold;")
                else:
                    label_write_result.setText("Write Failed (Log)")
                    label_write_result.setStyleSheet("color: red; font-weight: bold;")
            return result
        else:
            if not self.flag:
                QMessageBox.warning(None, "Lỗi", "Không thể kết nối, Hãy test kết nối đến PLC hoặc chuyển sang chế độ mô phỏng Log (INDIRECT FROM LOG)!")
                return False

            if not getattr(self, 'soc', None):
                self.soc = getattr(self.main_core, 'driver_loader', None)

            if not self.soc:
                QMessageBox.warning(None, "Lỗi", "Chưa kết nối đến thiết bị PLC!")
                return False

            try:
                result = self.soc.write_plc(register, value)
                label_write_result = getattr(self.uicmin, 'label_write_result', None)
                if label_write_result:
                    if result:
                        label_write_result.setText("Write Success")
                        label_write_result.setStyleSheet("color: green; font-weight: bold;")
                    else:
                        label_write_result.setText("Write Failed")
                        label_write_result.setStyleSheet("color: red; font-weight: bold;")
                return result
            except Exception as e:
                logging.error(f"[PLC_Controler] write_plc direct failed: {e}")
                label_write_result = getattr(self.uicmin, 'label_write_result', None)
                if label_write_result:
                    label_write_result.setText("Write Failed")
                    label_write_result.setStyleSheet("color: red; font-weight: bold;")
                QMessageBox.warning(None, "Lỗi", f"Lỗi ghi PLC: {e}")
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

        if hasattr(self.uicmin, 'comboBox_connection_type_2'):
            self.uicmin.comboBox_connection_type_2.setCurrentText(str(getattr(self.main_core, 'connection_port', 'Enthernet')))
        if hasattr(self.uicmin, 'lineEdit_local_ip_2'):
            self.uicmin.lineEdit_local_ip_2.setText(str(getattr(self.main_core, 'local_ip', '')))
        if hasattr(self.uicmin, 'spinBox_2'):
            self.uicmin.spinBox_2.setValue(int(getattr(self.main_core, 'retry_attempts', 0)))
        if hasattr(self.uicmin, 'checkBox_2'):
            self.uicmin.checkBox_2.setChecked(bool(getattr(self.main_core, 'auto_reconnect_on_disconnect', False)))

        # Chế độ mô phỏng PLC: Direct to PLC vs Indirect from Log
        direct = getattr(self.main_core, 'direct_to_plc', True)
        indirect = getattr(self.main_core, 'indirect_from_log', False)
        radio_indirect = getattr(self.uicmin, 'indirect_from_log', None) or getattr(self.uicmin, 'radioButton_2', None)
        radio_direct = getattr(self.uicmin, 'direct_to_plc', None) or getattr(self.uicmin, 'radioButton', None)
        if radio_indirect and radio_direct:
            if indirect:
                radio_indirect.setChecked(True)
                radio_direct.setChecked(False)
            else:
                radio_direct.setChecked(True)
                radio_indirect.setChecked(False)

        is_connected = bool(getattr(self.main_core, 'driver_loader', None)) or bool(indirect)
        self.flag = is_connected or (getattr(self, 'soc', None) is not None)

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
