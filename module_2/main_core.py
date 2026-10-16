
import mysql.connector
from module_3.main_thread import intermediate_layer
import sys
import threading
import time
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread, Qt
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QLineEdit, 
                             QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, 
                             QFrame, QComboBox, QScrollArea, QMessageBox, QSpinBox,
                             QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
                             QGroupBox)
from module_6.mitsubishi.initial import SocketClient as Mitsubishi_Socket_Client
from module_6.keyence.initial import KeyenceClient as Keyence_Socket_Client
from module_6.omron.initial import OmronClient as Omron_Socket_Client
from datetime import datetime
from app_logger.app_logger import get_logger as _get_logger, open_log_window
import subprocess,re
from module_1.root_path import resource_path
from module_1.table_db import _ADMIN_TABLES_SQL,TABLES_SQL_ITEM_CODE_SAVE,TABLES_SQL_DATA_IP_ADDRESS,TABLES_SQL_DATA_AUTO_LOGIN
_log = _get_logger('module_2.main_core')

PLC_COLLECT = {
    'KEYENCE'     : Keyence_Socket_Client,
    'OMRON'       : Omron_Socket_Client,
    'MITSHUBISHI' : Mitsubishi_Socket_Client,
}


class CoreWorker(QThread):
    trigger_detected = pyqtSignal(str, str)

    def __init__(self, core_instance):
        super().__init__()
        self.core_instance = core_instance
        self.running = True

    def run(self):
        _log.info("[CoreWorker] Running in thread: %s", threading.current_thread().name)
        self.core_instance.startup() 
        while self.running:
            self.core_instance.wait_for_signal()
            time.sleep(0.1)


class core:
    def __init__(self):
        _log.info("[core.__init__] START")
        self.dict_list_line   = {}
        self.mode_init        = 0
        self.mode_init_plc    = 0
        self.is_first_startup = True

        self.item_code    = None
        self.line_code    = None
        self.date_time    = None

        self.connection    = None
        self.driver_loader = None

        # Mặc định thông số PLC (phòng ngừa máy mới tinh chưa có cấu hình trong CSDL)
        self.plc_module     = "KEYENCE"
        self.ip_address_plc = "192.168.0.10"
        self.port_plc       = 5000
        self.manual         = 1
        self.automatic      = 0

        _log.info("[core.__init__] Creating CoreWorker...")
        self.worker_thread = CoreWorker(self)
        _log.info("[core.__init__] CoreWorker created. Connecting to MySQL...")

        connect_result, mode_init = self.connect_to_mysql()
        _log.info("[core.__init__] connect_to_mysql done. connect_result=%s", connect_result)
        self.connection = connect_result
        self.mode_init  = mode_init
        if self.connection is not None:
            self.cursor = self.connection.cursor()
            _log.info('Success to initialize connections')
        else:
            _log.warning('Failed to initialize connections')


        _log.info("[core.__init__] init_plc_data...")
        self.init_plc_data()
        _log.info("[core.__init__] Connecting trigger signal...")
        self.worker_thread.trigger_detected.connect(self.open_pyuic6)

        self.count = 0
        _log.info("[core.__init__] collect_dict_item...")
        self.collect_dict_item()
        _log.info("[core.__init__] DONE")

    def start_monitoring(self):
        self.worker_thread.start()
        _log.info('Success to start monitoring')

    def stop_monitoring(self):
        _log.info('Stopping CoreWorker...')
        self.worker_thread.running = False
        self.worker_thread.quit()
        self.worker_thread.wait()
        if hasattr(self, 'pyuic6_instance') and self.pyuic6_instance:
            _log.info("Reloading program: Closing existing instance for item code: %s", self.item_code)
            self.pyuic6_instance.Close_window()
        else:
            _log.info("No instance of pyuic6_instance found to close")
        _log.info('Success to stop monitoring')

    def read_mysql_config(self, filepath=resource_path("module_2/mysql_config.log")):
        config = {}
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        config[key.strip()] = value.strip()
        except FileNotFoundError:
            _log.warning("Config file not found: %s", filepath)
            return None
        except Exception as e:
            _log.error("Error reading config file: %s", e)
            return None
        return config

    def connect_mysql_from_log(self, filepath=resource_path("module_2/mysql_config.log")):
        _log.info("[connect_mysql_from_log] Reading config from %s", filepath)
        config = self.read_mysql_config(filepath)
        if not config:
            _log.info("[connect_mysql_from_log] No config found")
            return None
        try:
            _log.info("[connect_mysql_from_log] Attempting mysql.connector.connect with host=%s, user=%s, port=%s...", config.get('host'), config.get('user'), config.get('port'))
            connection = mysql.connector.connect(
                host     = config.get('host', 'localhost'),
                user     = config.get('user', 'root'),
                password = config.get('password', ''),
                port     = int(config.get('port', 3306)),
                use_pure = True
            )
            _log.info('[connect_mysql_from_log] Success to connect mysql')
            return connection
        except Exception as err:
            _log.warning('[connect_mysql_from_log] Failed to connect mysql: %s', err)
            return None

    def write_mysql_config(self, host, user, password, port, database,filepath=resource_path("module_2/mysql_config.log")):
        try:
            if password == "":
                with open(filepath, 'w') as f:
                    f.write(f"host={host}\n")
                    f.write(f"user={user}\n")
                    f.write(f"port={port}\n")
                    f.write(f"database={database}\n")
            else:
                with open(filepath, 'w') as f:
                    f.write(f"host={host}\n")
                    f.write(f"user={user}\n")
                    f.write(f"password={password}\n")
                    f.write(f"port={port}\n")
                    f.write(f"database={database}\n")
            _log.info('Success to write mysql config')
            return True
        except Exception as e:
            _log.warning('Failed to write mysql config: %s', e)
            return False

    def create_table_data_save_default(self, connection):
        cursor = connection.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS ITEM_CODE_SAVE")
        cursor.execute("USE ITEM_CODE_SAVE")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS DATA_SAVE_DEFAULT (
                id               INT AUTO_INCREMENT PRIMARY KEY,
                name_item_code   VARCHAR(255),
                name_line        VARCHAR(255),
                mode_name        VARCHAR(255),
                date_time        DATETIME NOT NULL
            )
        """)
        connection.commit()
        cursor.close()

    def connect_to_mysql(self):
        _log.info("[connect_to_mysql] Calling connect_mysql_from_log...")
        connection = self.connect_mysql_from_log()
        _log.info("[connect_to_mysql] connect_mysql_from_log returned: %s", connection)
        if connection is None:
            _log.info("[connect_to_mysql] Showing QMessageBox warning...")
            QMessageBox.warning(None, "Lỗi", "Không thể kết nối đến MySQL, \nVui lòng kiểm tra lại thông tin đăng nhập.")
            _log.info("[connect_to_mysql] QMessageBox closed.")
            return None, 0
    
        _log.info("[connect_to_mysql] Creating default table...")
        try:
            cursor = connection.cursor()
            for sql in _ADMIN_TABLES_SQL:
                cursor.execute(sql)
            for sql in TABLES_SQL_ITEM_CODE_SAVE:
                cursor.execute(sql)
            for sql in TABLES_SQL_DATA_IP_ADDRESS:
                cursor.execute(sql)
            for sql in TABLES_SQL_DATA_AUTO_LOGIN:
                cursor.execute(sql)
            connection.commit()
            cursor.close()
        except Exception as e:
            _log.warning('Failed to create default table: %s', e)

        try:
            cursor = connection.cursor()
            cursor.execute("USE DATA_AUTO_LOGIN")
            cursor.execute("SELECT * FROM INFOR")
            result = cursor.fetchall()
            cursor.close()

            if not result:
                return connection, 0

            manual    = bool(result[0][5])
            automatic = bool(result[0][6])
            
            if not manual and automatic:
                _log.info("[connect_to_mysql] Success to connect MySQL (Auto-login enabled)")
                return connection, 1
            else:
                _log.info("[connect_to_mysql] Success to connect MySQL (Manual mode)")
                return connection, 0

        except Exception as e:
            _log.error("Error in connect_to_mysql: %s", e)
            return connection, 0

        return connection, 0

    def init_plc_data(self):
        if not self.connection:
            _log.info("No connection to MySQL in init_plc_data")
            return
        try:
            cursor = self.connection.cursor()
            cursor.execute("USE DATA_IP_ADDRESS")
            cursor.execute("SELECT * FROM INFOR_ADDRESS")
            result = cursor.fetchall()
            cursor.close()

            if not result:
                _log.warning("No PLC info found in DATA_IP_ADDRESS.INFOR_ADDRESS")
                return

            entry            = result[0]
            plc_module       = entry[1]
            ip_address_plc   = entry[2]
            port_plc         = entry[3]
            manual           = entry[4]
            automatic        = entry[5]

            self.plc_module     = plc_module
            self.ip_address_plc = ip_address_plc
            self.port_plc       = port_plc
            self.manual         = manual
            self.automatic      = automatic

            if not manual and automatic:
                plc_instance = PLC_COLLECT[plc_module](ip_address_plc, port_plc)
                if plc_instance.connect():
                    self.driver_loader = plc_instance
                    self.mode_init_plc = 1
                    _log.info('Success to connect PLC %s at %s:%s', plc_module, ip_address_plc, port_plc)
                else:
                    _log.warning('Failed to connect PLC %s at %s:%s', plc_module, ip_address_plc, port_plc)
            else:
                _log.warning('PLC connection disabled in settings (Manual mode active)')

        except Exception as e:
            _log.error("Error in init_plc_data: %s", e)

    def collect_dict_item(self):
        if self.connection and self.mode_init:
            _log.info('Mode Automatic Login in MySQL (Optimized)')
            try:
                query_find_dbs = "SELECT TABLE_SCHEMA FROM information_schema.TABLES WHERE TABLE_NAME = 'ITEMS_CODE'"
                self.cursor.execute(query_find_dbs)
                databases = [row[0] for row in self.cursor.fetchall()]

                for name_line in databases:
                    query_get_items = f"SELECT name_line_code, assign_register, value_bit_on, value_bit_off FROM {name_line}.ITEMS_CODE"
                    self.cursor.execute(query_get_items)
                    item_codes = self.cursor.fetchall()

                    self.dict_list_line[name_line] = [
                        {'item_code': row[0], 'register': row[1], 'value_bit_on': row[2], 'value_bit_off': row[3]} for row in item_codes
                    ]

                _log.info("Successfully loaded items from %d databases", len(databases))
            except Exception as e:
                _log.error("Error in collect_dict_item: %s", e)
        else:
            _log.warning('Mode Manual Login or No Connection')

    def open_pyuic6(self, item_code, name_line):
        if self.connection:
            from app_utils.progress_bar import AppProgressBar
            
            progress = AppProgressBar(message="Đang khởi tạo giao diện...")

            if hasattr(self, 'pyuic6_instance') and self.pyuic6_instance:
                _log.info("Reloading program: Closing existing instance for item code: %s", self.item_code)
                self.pyuic6_instance.Close_window()
            self.pyuic6_instance = intermediate_layer(item_code, name_line, self, self.mode_init, progress_callback=progress.update_progress)
            
            progress.close()

    def wait_for_signal(self):
        if not self.dict_list_line or self.driver_loader is None:
            return

        for name_line, values in list(self.dict_list_line.items()):
            for entry in values:
                item_code = entry.get('item_code')
                register  = entry.get('register')
                value_bit_on = entry.get('value_bit_on')
                value_bit_off = entry.get('value_bit_off')

                if not register:
                    continue
                try:
                    current_value = self.driver_loader.read_plc(register)
                    if current_value is not None and int(current_value) == value_bit_on:
                        _log.info("PLC Trigger detected: %s = %d (Item: %s)", register, value_bit_on, item_code)
                        self.driver_loader.write_plc_log(register, value_bit_off)

                        date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        self.item_code = item_code
                        self.line_code = name_line
                        self.write_data_save_default(date_time, item_code, name_line)

                        self.worker_thread.trigger_detected.emit(item_code, name_line)
                except Exception as e:
                    _log.error("Error while reading trigger %s: %s", register, e)

    def startup(self):
        if self.connection and self.mode_init:
            if self.is_first_startup:
                self.is_first_startup = False
                result = self.read_data_save_default()
                if result:
                    _log.info(
                        "Auto-restoring from last saved state: %s, %s (saved at %s)",
                        result[0][0], result[0][1], result[0][2]
                    )
                    self.worker_thread.trigger_detected.emit(result[0][0], result[0][1])
                else:
                    _log.warning('No data save default')

    def write_data_save_default(self, date_time, item_code, name_line):
        if not self.connection:
            _log.info("No connection to MySQL in write_data_save_default")
            return
        try:
            cursor = self.connection.cursor()
            cursor.execute("USE ITEM_CODE_SAVE")
            cursor.execute("DELETE FROM DATA_SAVE_DEFAULT")
            self.connection.commit()
            cursor.execute(
                "INSERT INTO DATA_SAVE_DEFAULT (date_time, name_item_code, name_line) VALUES (%s, %s, %s)",
                (date_time, item_code, name_line)
            )
            self.connection.commit()
            cursor.close()
            _log.info('Success to write data save default: %s, %s', item_code, name_line)
        except Exception as e:
            _log.error("Error writing data save default: %s", e)

    def read_data_save_default(self):
        if not self.connection:
            _log.info("No connection to MySQL in read_data_save_default")
            return None
        try:
            cursor = self.connection.cursor()
            cursor.execute("USE ITEM_CODE_SAVE")
            cursor.execute("SELECT name_item_code, name_line, date_time FROM DATA_SAVE_DEFAULT")
            result = cursor.fetchall()
            cursor.close()
            return result
        except Exception as e:
            _log.error("Error reading data save default: %s", e)
            return None

        
    def query_hardware_key(self):
        if not self.connection:
            _log.warning("No database connection. Bypassing hardware key check to allow GUI configuration.")
            return True
        serial_hardware_key = self.get_serial_hardware_key()
        if not serial_hardware_key:
            QMessageBox.warning(
                None,
                "No License found!",
                "No License found! \nPlease insert USB Hardware Key to continue!\n\n"
            )
            return False
        else:
            usb_list = self.get_connected_usb_serials()
            for usb in usb_list:
                for i in range(len(serial_hardware_key)):
                    if usb['serial'] == serial_hardware_key[i][0]:
                        _log.info('Success to check hardware key')
                        return True
            QMessageBox.warning(
                None,
                "No License found!",
                "No License found! \n Please insert USB Hardware Key to continue!\n\n"
            )
            return False


    def get_serial_hardware_key(self):
        if not self.connection:
            print("No database connection")
            return
        try:
            cursor = self.connection.cursor(buffered=True)
            cursor.execute("SELECT hash_code FROM ADMINISTRATOR.HARDWARE_KEY_CONFIG WHERE is_enabled = 1")
            result = cursor.fetchall()
            cursor.close()
            return result
        except Exception as e:
            _log.error("Error reading hardware key: %s", e)
            return None


    def get_connected_usb_serials(self) -> list:
        """
        Quét tất cả USB đang cắm và tạo Hardware ID (HWID) bảo mật.
        Sử dụng PowerShell để lấy danh sách thiết bị.
        """
        import hashlib
        import subprocess

        usb_list = []
        try:
            cmd = (
                'powershell -Command "'
                "Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPDeviceID -match '^USB' } | ForEach-Object { $serial = $_.PNPDeviceID.Split('\')[-1]; [PSCustomObject]@{ 'Device Name' = $_.Name; 'Serial Number' = $serial } } | ConvertTo-Csv -NoTypeInformation"
                '"'
            )
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=10)
            output = result.stdout.strip()
            
            if output:
                lines = output.strip().split('\n')
                for line in lines[1:]:
                    parts = line.strip().strip('"').split('","')
                    if len(parts) >= 2:
                        model = parts[0].strip()
                        pnp_and_serial = parts[1].strip()
                        if pnp_and_serial and "ROOT_HUB" not in pnp_and_serial:
                            raw_hwid = pnp_and_serial
                            salt = "AI_VISION_PRO_SECURE_SALT_"
                            secure_hash = hashlib.sha256((salt + raw_hwid).encode('utf-8')).hexdigest().upper()
                            usb_list.append({
                                "serial": secure_hash,
                                "raw_serial": raw_hwid,
                                "model": model
                            })
        except Exception as e:
            _log.error("Lỗi khi quét USB bảo mật: %s", e)
            
        return usb_list
        

    