
from app_logger.app_logger import get_logger as _get_logger
_log = _get_logger('module_3.signal_process')

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import (QMessageBox)
from PyQt5 import QtCore, QtGui, QtWidgets
from mysql.connector import Error
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSpinBox, QTableWidget,
    QTableWidgetItem, QComboBox
)

import mysql.connector
from mysql.connector import Error
from module_3.animation import PLCSignalScene
from module_1.root_path import resource_path
import re
from module_3.config_status_logger import PLCConfigStatusLogger
class SignalTableHelper:
    def __init__(self, table_widget):
        self.table = table_widget
        self.rows = {}
        self.update_rows_mapping()
        self.columns = {
            'address': 0,
            'read_register': 1,
            'read_value_on': 2,
            'read_value_off': 3,
            'write_register': 4,
            'write_value_on': 5,
            'write_value_off': 6
        }
        
    def update_rows_mapping(self):
        self.rows = {}
        for row in range(self.table.rowCount()):
            item = self.table.verticalHeaderItem(row)
            if item:
                self.rows[item.text().lower()] = row

    def get_value(self, signal_name, column_name):
        row = self.rows.get(signal_name.lower())
        col = self.columns.get(column_name.lower())
        if row is not None and col is not None:
            if col == 0:
                widget = self.table.cellWidget(row, col)
                return widget.currentText() if widget else ''
            item = self.table.item(row, col)
            return item.text() if item else ''
        return None

    def set_value(self, signal_name, column_name, value):
        row = self.rows.get(signal_name.lower())
        col = self.columns.get(column_name.lower())
        if row is not None and col is not None:
            if col == 0:
                widget = self.table.cellWidget(row, col)
                if widget:
                    widget.setCurrentText(str(value) if value is not None else "")
            else:
                item = QtWidgets.QTableWidgetItem(str(value) if value is not None else "")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(row, col, item)


class DataProcessSignal:

    def __init__(self,uic):
        self.uic = uic
        self.signal_table = SignalTableHelper(self.uic.tableWidget)
        self.mode_auto_id = None
        self.dict_mode_params = {}
        self.check_connect_plc = False
        self.is_connected_plc = None
        
        # Thiết lập Context Menu cho bảng
        self.uic.tableWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.uic.tableWidget.customContextMenuRequested.connect(self.setup_context_menu)

        # # PLC Signal Communication animation
        # self._plc_scene = PLCSignalScene(self.uic.graphicsView)
        # self.uic.graphicsView.setScene(self._plc_scene)
        # self.uic.graphicsView.setRenderHint(QtGui.QPainter.Antialiasing)
        # self.uic.graphicsView.setStyleSheet("border: 1px solid #21262d; border-radius: 6px;")
        # self.uic.graphicsView.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        # self.uic.graphicsView.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        # self.uic.graphicsView.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

        # Thêm ComboBox DMA cho các hàng có sẵn
        for row in range(self.uic.tableWidget.rowCount()):
            self._add_dma_combobox_to_row(row)

        self.generate_table()
        self.table_signal_up_to_selected_trigger_signals()
        self.is_unlocked = False
        self.set_ui_enabled(False)
        self._setup_config_status_log_ui()

    def _setup_config_status_log_ui(self):
        """Khởi tạo textBrowser_status_log động bên trong self.uic.groupBox_5
        để không bị mất khi biên dịch lại file giao diện .ui."""
        if not hasattr(self.uic, 'groupBox_5'):
            return

        self.uic.groupBox_5.setTitle("PLC Configuration Status")

        # Xóa các item / spacer cũ trong gridLayout_4 nếu có
        if hasattr(self.uic, 'gridLayout_4') and self.uic.gridLayout_4:
            while self.uic.gridLayout_4.count():
                item = self.uic.gridLayout_4.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        # Tạo textBrowser_status_log động
        self.uic.textBrowser_status_log = QtWidgets.QTextBrowser(self.uic.groupBox_5)
        font = QtGui.QFont()
        font.setFamily("Segoe UI")
        font.setPointSize(10)
        self.uic.textBrowser_status_log.setFont(font)
        self.uic.textBrowser_status_log.setStyleSheet("""
            QTextBrowser {
                background-color: #FFFFFF;
                border: 1px solid #000000;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        self.uic.textBrowser_status_log.setObjectName("textBrowser_status_log")
        self.uic.gridLayout_4.addWidget(self.uic.textBrowser_status_log, 0, 0, 1, 1)

        # Gắn logger vào self.uic
        self.uic.config_logger = PLCConfigStatusLogger(self.uic.textBrowser_status_log)

    def _add_dma_combobox_to_row(self, row_index):
        combo = QtWidgets.QComboBox()
        combo.addItems(["DM", "MR", "R", "T", "C"])
        
        # 1. Thiết lập StyleSheet gộp toàn bộ cấu hình (Font Segoe UI, Size 10pt, Nền trắng, Chữ đen)
        combo.setStyleSheet("""
            QComboBox { 
                background-color: #F7FFFA; 
                color: black; 
                font-family: 'Segoe UI'; 
                font-size: 10pt; 
            }
            QComboBox QAbstractItemView {
                text-align: center;
            }
        """)
        
        # 2. Bắt buộc thêm các dòng này để ép chữ trên khung chính phải căn giữa hoàn toàn
        combo.setEditable(True)
        combo.lineEdit().setAlignment(QtCore.Qt.AlignCenter)
        combo.lineEdit().setReadOnly(True)
        
        self.uic.tableWidget.setCellWidget(row_index, 0, combo)

    def setup_context_menu(self, pos):
        menu = QtWidgets.QMenu()
        add_action = menu.addAction("Add Row")
        add_action.setIcon(QtGui.QIcon(QtGui.QPixmap(resource_path("module_3/assert/icon/add_row.png"))))
        delete_action = menu.addAction("Delete Row")
        delete_action.setIcon(QtGui.QIcon(QtGui.QPixmap(resource_path("module_3/assert/icon/x-button.png"))))
        refresh_action = menu.addAction("Refresh Table")
        refresh_action.setIcon(QtGui.QIcon(QtGui.QPixmap(resource_path("module_3/assert/icon/arrow_tble.png"))))
        
        action = menu.exec_(self.uic.tableWidget.mapToGlobal(pos))
        
        if action == add_action:
            self.add_row()
        elif action == delete_action:
            self.delete_row()
        elif action == refresh_action:
            self.refresh_table()

    def refresh_table(self):
        self.generate_table()
        self.table_signal_up_to_selected_trigger_signals()

    def add_row(self):
        signal_name, ok = QtWidgets.QInputDialog.getText(None, "Add Row", "Enter new row name:")
        if ok and signal_name:
            if signal_name.lower() in self.signal_table.rows:
                QMessageBox.warning(None, "Warning", "Signal already exists!")
                return
            #nếu trong signal_name có khoảng cách giữa các chữ, báo lỗi
            if " " in signal_name:
                QMessageBox.warning(None, "Warning", "Signal name cannot contain spaces!")
                return
            # trong signal_name chỉ có số hoặc chữ và ký tự '_', ngoài ra sẽ báo lỗi:
            if not re.match(r"^[a-zA-Z0-9_]*$", signal_name):
                QMessageBox.warning(None, "Warning", "Signal name can only contain letters, numbers, and underscores!")
                return
                
            row_count = self.uic.tableWidget.rowCount()
            self.uic.tableWidget.insertRow(row_count)
            item = QtWidgets.QTableWidgetItem(signal_name)
            self.uic.tableWidget.setVerticalHeaderItem(row_count, item)
            
            self._add_dma_combobox_to_row(row_count)
            for col in range(1, self.uic.tableWidget.columnCount()):
                empty_item = QtWidgets.QTableWidgetItem("")
                empty_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.uic.tableWidget.setItem(row_count, col, empty_item)
                
            self.signal_table.update_rows_mapping()
            self.table_signal_up_to_selected_trigger_signals()

    def delete_row(self):
        current_row = self.uic.tableWidget.currentRow()
        if current_row >= 0:
            reply = QMessageBox.question(None, "Xóa Hàng", "Bạn có chắc chắn muốn xóa hàng này không?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.uic.tableWidget.removeRow(current_row)
                self.signal_table.update_rows_mapping()
                self.table_signal_up_to_selected_trigger_signals()
        else:
            QMessageBox.warning(None, "Cảnh báo", "Vui lòng chọn một hàng để xóa!")

    def load_register_name_line_code(self,cursor):
        Itemcode = self.uic.comboBox_Itemcode.currentText()
        try:
            cursor.execute("""
                    SELECT assign_register, value_bit_on, value_bit_off FROM ITEMS_CODE 
                    WHERE name_line_code = %s 
                """, (Itemcode,))
            if result := cursor.fetchone():
                register = result[0]
                value_bit_on = result[1]
                value_bit_off = result[2]
                self.uic.lineEdit_assign_itemcode_plc.setText(register)
                self.uic.comboBox_value_register_bit_on.setCurrentText(str(value_bit_on))
                self.uic.comboBox_value_register_bit_off.setCurrentText(str(value_bit_off))
            
        except mysql.connector.Error as error:
            QMessageBox.critical(None, "Error", f"Lỗi Load: {str(error)}")
            raise   

    def save_register_name_line_code(self,cursor,connect_db):
        Itemcode = self.uic.comboBox_Itemcode.currentText()
        assign_register = self.uic.lineEdit_assign_itemcode_plc.text()
        value_bit_on = self.uic.comboBox_value_register_bit_on.currentText()
        value_bit_off = self.uic.comboBox_value_register_bit_off.currentText()
        if not assign_register or assign_register == '':
            QMessageBox.warning(None, "Cảnh báo", f"Vui lòng nhập thanh ghi cho Mã hàng {Itemcode}")
            return
        try:
            cursor.execute("""
                    SELECT id FROM ITEMS_CODE 
                    WHERE name_line_code = %s 
                """, (Itemcode,))
            if result := cursor.fetchone():
                cursor.execute("""
                            UPDATE ITEMS_CODE 
                            SET assign_register = %s, value_bit_on = %s, value_bit_off = %s 
                            WHERE name_line_code = %s 
                """, (assign_register, value_bit_on, value_bit_off, Itemcode))
                connect_db.connection.commit()
                if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                    self.uic.config_logger.set_status('item_code', 'success', f"Đã lưu thành công mã hàng '{Itemcode}' (Reg: {assign_register})")
                QMessageBox.information(None, "Thành công", f"Lưu thành công Ma hang {Itemcode}!")
            else:
                if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                    self.uic.config_logger.set_status('item_code', 'error', f"Không tìm thấy mã hàng '{Itemcode}'")
                QMessageBox.critical(None, "Error", f"Khong tim thay Ma hang {Itemcode}")
        except mysql.connector.Error as error:
            connect_db.connection.rollback()
            if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                self.uic.config_logger.set_status('item_code', 'error', f"Lỗi lưu mã hàng: {str(error)}")
            QMessageBox.critical(None, "Error", f"Lỗi Update: {str(error)}")
            raise    

    def save_default_mode(self, cursor, connect_db, result_camera_id):
        if (camera_id := result_camera_id[0] if result_camera_id else None):
            mode_name = self.uic.comboBox_default_mode.currentText()
            cursor.execute("""
                SELECT id FROM DEFAULT_MODE_AUTO 
                WHERE camera_id = %s 
            """, (camera_id,))
            result = cursor.fetchone()
            if not result:
                cursor.execute("""
                    INSERT INTO DEFAULT_MODE_AUTO (mode_name, camera_id)
                    VALUES (%s, %s)
                """, (mode_name, camera_id))
                connect_db.connection.commit()
            else:
                cursor.execute("""
                    UPDATE DEFAULT_MODE_AUTO 
                    SET mode_name = %s 
                    WHERE camera_id = %s 
                """, (mode_name,camera_id))
                connect_db.connection.commit()

    def save_mode_auto(self, cursor, connect_db, item_code_id):
        try:
            camera_name = self.uic.comboBox_camera.currentText()
            register_mode = self.uic.lineEdit_register_mode.text()
            value_bit_on = self.uic.comboBox_value_mode_selector_bit_on.currentText()
            value_bit_off = self.uic.comboBox_value_mode_selector_bit_off.currentText()
            mode_name = self.uic.comboBox_mode_auto.currentText()

            if not register_mode or register_mode == '':
                QMessageBox.warning(None, "Cảnh báo", f"Vui lòng nhập thanh ghi cho chế độ {mode_name}")
                return

            cursor.execute("""
                        SELECT id FROM NUMS_CAMERA 
                        WHERE item_code_id = %s AND nums_camera = %s
                    """, (item_code_id, camera_name))
                
            result_camera_id = cursor.fetchone() 
            self.save_default_mode( cursor, connect_db,result_camera_id)
            if (camera_id := result_camera_id[0] if result_camera_id else None):
                cursor.execute("""
                    SELECT id FROM MODE_AUTO 
                    WHERE mode_name = %s AND camera_id = %s 
                """, (mode_name,camera_id))
                result = cursor.fetchone()
                if not result:
                    cursor.execute("""
                        INSERT INTO MODE_AUTO (mode_name, camera_id,assign_register,value_bit_on,value_bit_off)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (mode_name, camera_id,register_mode,value_bit_on,value_bit_off))
                    cursor.execute("""
                        SELECT id FROM MODE_AUTO 
                        WHERE mode_name = %s AND camera_id = %s 
                        """, (mode_name,camera_id))
                    result = cursor.fetchone()
                else: 
                    cursor.execute("""
                    UPDATE MODE_AUTO 
                    SET assign_register = %s,value_bit_on = %s,value_bit_off = %s
                    WHERE  mode_name = %s AND camera_id = %s 
                """, (register_mode,value_bit_on,value_bit_off,mode_name,camera_id))

            self.mode_auto_id = result[0] if result else None
            connect_db.connection.commit()
            if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                self.uic.config_logger.set_status('mode_auto', 'success', f"Đã lưu thành công Mode '{mode_name}'")
            QMessageBox.information(None, "Thành công", "Lưu thành công mode auto!")

        except mysql.connector.Error as error:
                connect_db.connection.rollback()
                if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                    self.uic.config_logger.set_status('mode_auto', 'error', f"Lỗi lưu mode: {str(error)}")
                QMessageBox.critical(None, "Error", f"Lỗi Insert: {str(error)}")
                raise    
        
    def produce_mode_auto_id(self,cursor,connect_db,item_code_id):
        camera_name = self.uic.comboBox_camera.currentText()
        mode_name = self.uic.comboBox_mode_auto.currentText()
        cursor.execute("""
                    SELECT id FROM NUMS_CAMERA 
                    WHERE item_code_id = %s AND nums_camera = %s
                """, (item_code_id, camera_name))
            
        result_camera_id = cursor.fetchone() 
        if (camera_id := result_camera_id[0] if result_camera_id else None):
            cursor.execute("""
                SELECT id FROM MODE_AUTO 
                WHERE mode_name = %s AND camera_id = %s
            """, (mode_name, camera_id))
            result = cursor.fetchone()
            if not result:
                QMessageBox.information(None, "Information", f"Mode {mode_name} is not exists ")
                return
            
        return result[0] if result else None

    def save_values_signal_to_db_from_gui(self, cursor,connect_db,item_code_id):
        mode_auto_id = self.produce_mode_auto_id(cursor,connect_db,item_code_id)
        if mode_auto_id:
            try:
                cursor.execute("""
                    DELETE FROM MODE_AUTO_SIGNAL WHERE mode_id = %s
                """, (mode_auto_id,))
                for signal_name in self.signal_table.rows.keys():
                    address = self.signal_table.get_value(signal_name, 'address')
                    read_register = self.signal_table.get_value(signal_name, 'read_register')
                    read_value_on = self.signal_table.get_value(signal_name, 'read_value_on')
                    read_value_off = self.signal_table.get_value(signal_name, 'read_value_off')
                    write_register = self.signal_table.get_value(signal_name, 'write_register')
                    write_value_on = self.signal_table.get_value(signal_name, 'write_value_on')
                    write_value_off = self.signal_table.get_value(signal_name, 'write_value_off')

                    cursor.execute("""
                        INSERT INTO MODE_AUTO_SIGNAL (
                            signal_name, address, read_register, 
                            read_value_on, read_value_off, write_register, write_value_on, write_value_off, mode_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        signal_name,
                        address if address else None,
                        read_register if read_register else None,
                        read_value_on if read_value_on else None,
                        read_value_off if read_value_off else None,
                        write_register if write_register else None,
                        write_value_on if write_value_on else None,
                        write_value_off if write_value_off else None,
                        mode_auto_id
                    ))
                connect_db.connection.commit()
                if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                    self.uic.config_logger.set_status('signal_table', 'success', "Đã lưu thành công bảng tín hiệu PLC")
                QMessageBox.information(None, "Thành công", "Lưu thành công mode auto!")

            except Error as e:
                connect_db.connection.rollback()
                if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                    self.uic.config_logger.set_status('signal_table', 'error', f"Lỗi MySQL: {e}")
                QMessageBox.critical(None, "Lỗi", f"MySQL Error: {e}")

            except Exception as e:
                connect_db.connection.rollback()
                if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                    self.uic.config_logger.set_status('signal_table', 'error', f"Lỗi: {e}")
                QMessageBox.critical(None, "Lỗi không xác định", str(e))

        else:
            if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                self.uic.config_logger.set_status('signal_table', 'error', "Chưa lưu Mode Auto trước khi lưu tín hiệu")
            QMessageBox.critical(None, "Lỗi", f"Please Save Mode Auto Before Save Sinals Parameters")

    def load_values_signal_default_mode_from_db_up_to_gui(self,cursor,camera_id):
        
        cursor.execute("""
            SELECT mode_name FROM DEFAULT_MODE_AUTO
            WHERE camera_id = %s
        """, (camera_id,))
        result = cursor.fetchone()
        if result:
            mode_name = result[0]
            self.uic.comboBox_default_mode.setCurrentText(str(mode_name))
            self.uic.comboBox_mode_auto.setCurrentText(str(mode_name))

            cursor.execute("""
                SELECT id, assign_register FROM MODE_AUTO
                WHERE mode_name = %s AND camera_id = %s
            """, (mode_name, camera_id))

            result = cursor.fetchone()
            if result:
                self.uic.lineEdit_register_mode.setText(str(result[1]))
                mode_auto_id = result[0]
                cursor.execute("""
                    SELECT signal_name, address, read_register, 
                    read_value_on, read_value_off, write_register, write_value_on, write_value_off
                    FROM MODE_AUTO_SIGNAL
                    WHERE mode_id = %s
                """, (mode_auto_id,))
                rows = cursor.fetchall()
                for row in rows:
                    signal_name = row[0].lower()
                    if signal_name not in self.signal_table.rows:
                        row_count = self.uic.tableWidget.rowCount()
                        self.uic.tableWidget.insertRow(row_count)
                        item = QtWidgets.QTableWidgetItem(signal_name)
                        self.uic.tableWidget.setVerticalHeaderItem(row_count, item)
                        
                        self._add_dma_combobox_to_row(row_count)
                        for col in range(1, self.uic.tableWidget.columnCount()):
                            empty_item = QtWidgets.QTableWidgetItem("")
                            empty_item.setTextAlignment(QtCore.Qt.AlignCenter)
                            self.uic.tableWidget.setItem(row_count, col, empty_item)
                        self.signal_table.update_rows_mapping()
                        self.table_signal_up_to_selected_trigger_signals()
                        
                for row in rows:
                    signal_name = row[0].lower()
                    for i, column_name in enumerate(self.signal_table.columns.keys()):
                        value = row[i + 1]
                        if value is not None:
                            self.signal_table.set_value(signal_name, column_name, value)
                
                return mode_auto_id
            
    def load_params_signals_from_gui_mapping_db(self, cursor, camera_id, mode_name=None, show_message=True):
        if mode_name is None:
            mode_name = self.uic.comboBox_mode_auto.currentText()
        else:
            index = self.uic.comboBox_mode_auto.findText(str(mode_name))
            if index >= 0:
                self.uic.comboBox_mode_auto.blockSignals(True)
                self.uic.comboBox_mode_auto.setCurrentIndex(index)
                self.uic.comboBox_mode_auto.blockSignals(False)
            else:
                self.uic.comboBox_mode_auto.setCurrentText(str(mode_name))

        cursor.execute("""
                SELECT id, assign_register,value_bit_on,value_bit_off FROM MODE_AUTO
                WHERE mode_name = %s AND camera_id = %s
            """, (mode_name, camera_id))

        if result := cursor.fetchone():
            self.uic.lineEdit_register_mode.setText(str(result[1]))
            self.uic.comboBox_value_mode_selector_bit_on.setCurrentText(str(result[2]))
            self.uic.comboBox_value_mode_selector_bit_off.setCurrentText(str(result[3]))
            mode_auto_id = result[0]
            cursor.execute("""
                SELECT signal_name, address, read_register, 
                read_value_on, read_value_off, write_register, write_value_on, write_value_off
                FROM MODE_AUTO_SIGNAL
                WHERE mode_id = %s
            """, (mode_auto_id,))
            rows = cursor.fetchall()
            for row in range(self.uic.tableWidget.rowCount()):
                combo = self.uic.tableWidget.cellWidget(row, 0)
                if combo:
                    combo.setCurrentIndex(0)
                else:
                    self._add_dma_combobox_to_row(row)
                for col in range(1, self.uic.tableWidget.columnCount()):
                    self.uic.tableWidget.setItem(row,col,QtWidgets.QTableWidgetItem(""))
                    
            for row in rows:
                signal_name = row[0].lower()
                if signal_name not in self.signal_table.rows:
                    row_count = self.uic.tableWidget.rowCount()
                    self.uic.tableWidget.insertRow(row_count)
                    item = QtWidgets.QTableWidgetItem(signal_name)
                    self.uic.tableWidget.setVerticalHeaderItem(row_count, item)
                    
                    self._add_dma_combobox_to_row(row_count)
                    for col in range(1, self.uic.tableWidget.columnCount()):
                        empty_item = QtWidgets.QTableWidgetItem("")
                        empty_item.setTextAlignment(QtCore.Qt.AlignCenter)
                        self.uic.tableWidget.setItem(row_count, col, empty_item)
                    self.signal_table.update_rows_mapping()
                    self.table_signal_up_to_selected_trigger_signals()

            for row in rows:
                signal_name = row[0].lower()
                for i, column_name in enumerate(self.signal_table.columns.keys()):
                    value = row[i + 1]
                    if value is not None:
                        self.signal_table.set_value(signal_name, column_name, value)

            return mode_auto_id if result else None
        else: 
            if show_message:
                QMessageBox.information(None, "Information", f"Mode {mode_name} is not exists ")
            else:
                _log.warning("Mode %s does not exist in MODE_AUTO for camera %s", mode_name, camera_id)
            return
        

    def get_dict_mode_params(self,cursor,camera_id):
        cursor.execute("""
                SELECT mode_name FROM MODE_AUTO
                WHERE camera_id = %s
            """, (camera_id,))

        if results := cursor.fetchall():
            for result in results:
                mode_name = result[0]
                cursor.execute("""
                    SELECT id, assign_register,value_bit_on,value_bit_off FROM MODE_AUTO
                    WHERE mode_name = %s AND camera_id = %s
                """, (mode_name, camera_id))

                if result := cursor.fetchone():
                    self.uic.lineEdit_register_mode.setText(str(result[1]))
                    self.uic.comboBox_value_mode_selector_bit_on.setCurrentText(str(result[2]))
                    self.uic.comboBox_value_mode_selector_bit_off.setCurrentText(str(result[3]))
                    mode_auto_id = result[0]
                    cursor.execute("""
                        SELECT signal_name, address, read_register, 
                        read_value_on, read_value_off, write_register, write_value_on, write_value_off
                        FROM MODE_AUTO_SIGNAL
                        WHERE mode_id = %s
                    """, (mode_auto_id,))
                    rows = cursor.fetchall()
                    for row in range(self.uic.tableWidget.rowCount()):
                        combo = self.uic.tableWidget.cellWidget(row, 0)
                        if combo:
                            combo.setCurrentIndex(0)
                        else:
                            self._add_dma_combobox_to_row(row)
                        for col in range(1, self.uic.tableWidget.columnCount()):
                            self.uic.tableWidget.setItem(row,col,QtWidgets.QTableWidgetItem(""))
                            
                    for row in rows:
                        signal_name = row[0].lower()
                        if signal_name not in self.signal_table.rows:
                            row_count = self.uic.tableWidget.rowCount()
                            self.uic.tableWidget.insertRow(row_count)
                            item = QtWidgets.QTableWidgetItem(signal_name)
                            self.uic.tableWidget.setVerticalHeaderItem(row_count, item)
                            
                            self._add_dma_combobox_to_row(row_count)
                            for col in range(1, self.uic.tableWidget.columnCount()):
                                empty_item = QtWidgets.QTableWidgetItem("")
                                empty_item.setTextAlignment(QtCore.Qt.AlignCenter)
                                self.uic.tableWidget.setItem(row_count, col, empty_item)
                            self.signal_table.update_rows_mapping()
                            self.table_signal_up_to_selected_trigger_signals()
                            
                    for row in rows:
                        signal_name = row[0].lower()
                        for i, column_name in enumerate(self.signal_table.columns.keys()):
                            value = row[i + 1]
                            if value is not None:
                                self.signal_table.set_value(signal_name, column_name, value)
                dict_params = self.get_db_params()
                self.dict_mode_params[mode_name] = {}
                self.dict_mode_params[mode_name]['values_signals'] = dict_params
                self.dict_mode_params[mode_name]['register_on'] = result[1]
            return self.dict_mode_params
        else: 
            # QMessageBox.warning(None, "Warning", f"No mode found for camera {camera_id}\n Please setup mode in camera setting!")
            _log.warning(f"No mode found for camera {camera_id}")
            return
    
        
    def get_table_params(self):
        dict_params = {}
        for signal_name in self.signal_table.rows.keys():
            dict_params[signal_name] = {}
            for column_name in self.signal_table.columns.keys():
                dict_params[signal_name][column_name] = self.signal_table.get_value(signal_name, column_name)
        return dict_params
    

    def get_db_params(self):
        dict_params = {}
        for signal_name in self.signal_table.rows.keys():
            dict_params[signal_name] = {}
            for column_name in self.signal_table.columns.keys():
                dict_params[signal_name][column_name] = self.signal_table.get_value(signal_name, column_name)
        return dict_params
    
    
    def save_shotxmodel_to_db(self,cursor,connect_db,item_code_id):
        mode_auto_id = self.produce_mode_auto_id(cursor,connect_db,item_code_id)
        if mode_auto_id:
            try: 
                cursor.execute("""
                    DELETE FROM SHOTXMODEL WHERE mode_id = %s
                """, (mode_auto_id,))

                row_count = self.uic.tableWidget_shotxmodel.rowCount()
                col_count = self.uic.tableWidget_shotxmodel.columnCount()
                list_insert = []

                for row in range(row_count):
                    row_data = {}
                    for col in range(col_count):
                        item = self.uic.tableWidget_shotxmodel.item(row, col)
                        if item is not None:
                            row_data[col] = item.text()
                        else:
                            widget = self.uic.tableWidget_shotxmodel.cellWidget(row, col)
                            if isinstance(widget, QComboBox):
                                row_data[col] = widget.currentText()
                    if row_data:
                        list_insert.append(row_data)
                _log.debug('list_insert: %s', list_insert)
                if list_insert:
                    insert_query = """
                        INSERT INTO SHOTXMODEL (shot, no_of_model, mode_id)
                        VALUES (%s, %s, %s)
                    """
                    for row in list_insert:
                        shot = int(row.get(0, 0)) 
                        no_of_model = int(row.get(1, 0))  
                        cursor.execute(insert_query, (shot, no_of_model,mode_auto_id))
                    connect_db.connection.commit()
                    if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                        self.uic.config_logger.set_status('shot_model', 'success', f"Đã lưu thành công bảng Shot x Model ({len(list_insert)} dòng)")
                    QMessageBox.information(None, "Thành công", "Lưu thành công shot link model!")

            except Error as e:
                connect_db.connection.rollback()
                if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                    self.uic.config_logger.set_status('shot_model', 'error', f"Lỗi lưu Shot x Model: {e}")
                QMessageBox.critical(None, "Lỗi", f"MySQL Error: {e}")

            except Exception as e:
                connect_db.connection.rollback()
                if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                    self.uic.config_logger.set_status('shot_model', 'error', f"Lỗi lưu Shot x Model: {e}")
                QMessageBox.critical(None, "Lỗi không xác định", str(e))

        else:
            if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                self.uic.config_logger.set_status('shot_model', 'error', "Chưa lưu Mode Auto trước khi lưu Shot x Model")
            QMessageBox.critical(None, "Lỗi", f"Please Save Mode Auto Before Save Sinals Parameters")

    def load_shotxmodel_from_db(self,cursor,connect_db,mode_auto_id,num_models):
        try: 
            query = """
                SELECT shot,no_of_model
                FROM SHOTXMODEL
                WHERE mode_id = %s
                ORDER BY shot ASC
            """
            cursor.execute(query, (mode_auto_id,))
            if results:=cursor.fetchall():
                self.uic.tableWidget_shotxmodel.setRowCount(len(results))
                self.uic.spinBox_num_shot.setValue(len(results))
                for row_index, (shot, no_of_model) in enumerate(results):
                    shot_item = QTableWidgetItem(f'{str(shot)}')
                    shot_item.setTextAlignment(QtCore.Qt.AlignCenter)
                    self.uic.tableWidget_shotxmodel.setItem(row_index,0,shot_item)
                    combo = QComboBox()
                    combo.addItems([str(i+1) for i in range(int(num_models))])
                    combo.setCurrentText(str(no_of_model))
                    combo.setEditable(True)
                    combo.lineEdit().setReadOnly(True)
                    combo.lineEdit().setAlignment(QtCore.Qt.AlignCenter)
                    self.uic.tableWidget_shotxmodel.setCellWidget(row_index, 1, combo)
        except Error as e:
            connect_db.connection.rollback()
            QMessageBox.critical(None, "Lỗi", f"MySQL Error: {e}")

        except Exception as e:
            connect_db.connection.rollback()
            QMessageBox.critical(None, "Lỗi không xác định", str(e))

    def dict_shotxmodel(self):
        row_count = self.uic.tableWidget_shotxmodel.rowCount()
        row_data = {}
        for row in range(row_count):
            item = self.uic.tableWidget_shotxmodel.item(row,0)
            shot = item.text()
            widget_model = self.uic.tableWidget_shotxmodel.cellWidget(row, 1)
            if isinstance(widget_model, QComboBox):
                model = widget_model.currentText()
            row_data[shot] = model

        return row_count,row_data
    

    def collect_dict_from_mode_auto(self,cursor,camera_id):
        a = {}
        cursor.execute("""
                SELECT id,mode_name,assign_register,value_bit_on,value_bit_off FROM MODE_AUTO
                WHERE camera_id = %s
            """, (camera_id,))
    
        results = cursor.fetchall()
        if results:
            for result in results:
                b={}
                mode_id = result[0]
                mode_name = result[1]
                a[mode_name] = {}
                assign = result[2]
                value_bit_on = result[3]
                value_bit_off = result[4]
                cursor.execute("""
                    SELECT index_user_selector,user_set_selector FROM USER_SET_CAMERA
                    WHERE mode_id = %s
                """, (mode_id,))
                results = cursor.fetchone()
                if results:
                    index_userset = results[0]
                    usersetselector = results[1]
                    b['register']=assign
                    b['value_bit_on']=value_bit_on
                    b['value_bit_off']=value_bit_off
                    b['usersetcamera']=usersetselector
                    b['index']=index_userset
                    a[mode_name] = b
                else:
                    index_userset = None
                    usersetselector = None
                    b['register']=assign
                    b['value_bit_on']=value_bit_on
                    b['value_bit_off']=value_bit_off
                    b['usersetcamera']=usersetselector
                    b['index']=index_userset
                    a[mode_name] = b
                    _log.warning(f'Non Initialized index_userset and usersetselector for {mode_name}!')
        else:
            _log.warning(f'Non Initialize mode auto!')
        return a
            
    def connect_plc(self, dict, connect_db=None):
        p1 = self.uic.lineEditIP1.text().strip()
        p2 = self.uic.lineEditIP2.text().strip()
        p3 = self.uic.lineEditIP3.text().strip()
        p4 = self.uic.lineEditIP4.text().strip()
        ipv4 = f"{p1}.{p2}.{p3}.{p4}"
        port = self.uic.lineEdit.text().strip() if hasattr(self.uic, 'lineEdit') else "8051"
        self.is_connected_plc = dict[self.uic.comboBox_type_dev.currentText()](ipv4, port)
        result_conn =  self.is_connected_plc.connect()
        if result_conn:
            self.uic.label_green_red.setStyleSheet("""
                background-color: green;
                border-radius: 15px;
            """)
            self.check_connect_plc = True
            if connect_db is not None:
                connect_db.driver_loader = self.is_connected_plc
        else:
            self.uic.label_green_red.setStyleSheet("""
                background-color: red;
                border-radius: 15px;
            """)

    def save_data_ipV4(self,cursor,connect_db):
        if self.check_connect_plc:
            p1 = self.uic.lineEditIP1.text().strip()
            p2 = self.uic.lineEditIP2.text().strip()
            p3 = self.uic.lineEditIP3.text().strip()
            p4 = self.uic.lineEditIP4.text().strip()
            ipv4 = f"{p1}.{p2}.{p3}.{p4}"
            port = self.uic.lineEdit.text().strip() if hasattr(self.uic, 'lineEdit') else "8051"
            cursor.execute("""DELETE FROM PLC_DATA """)
            cursor.execute("""
                    INSERT IGNORE INTO PLC_DATA (
                        ip_v4, port, type_dev, protocol
                    ) VALUES (%s, %s, %s, %s)
                """, (
                    ipv4,
                    port,
                    self.uic.comboBox_type_dev.currentText(),
                    self.uic.comboBox_protocol.currentText(),
                ))
            connect_db.connection.commit()
            QMessageBox.information(None, "Thành công", "Lưu thành công data PLC!")
        else:
            QMessageBox.critical(None, "Infor", f"Vui lòng test kết nối đến thiết bị PLC")
            return 
        
    def load_data_plc(self,cursor):
        cursor.execute("SELECT * FROM DATA_IP_ADDRESS.INFOR_ADDRESS")
        result = cursor.fetchall()
        if not result:
            _log.warning("No PLC info found in DATA_IP_ADDRESS.INFOR_ADDRESS")
            return

        entry            = result[0]
        plc_module       = entry[1]
        ip_address_plc   = entry[2]
        port_plc         = entry[3]
        manual           = entry[4]
        automatic        = entry[5]
        self.uic.IPV4_PLC.setText(str(ip_address_plc))
        self.uic.comboBox_type_dev.setCurrentText(str(plc_module))
        self.uic.comboBox_protocol.setCurrentText(str(manual))


    def save_all_data(self,cursor,connect_db,camera_id):
        try:
            self.save_signal_transmission_and_reception(cursor,connect_db,camera_id)
            self.save_signal_timing_config(cursor,connect_db,camera_id)
            if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                self.uic.config_logger.set_status('transmission_timing', 'success', "Đã lưu thành công dữ liệu truyền nhận & timing")
        except Exception as e:
            if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                self.uic.config_logger.set_status('transmission_timing', 'error', f"Lỗi lưu truyền nhận & timing: {str(e)}")

    def load_all_data(self,cursor,camera_id):
        self.load_data_signal_transmission_and_reception(cursor,camera_id)
        self.load_signal_timing_config(cursor,camera_id)


    def save_signal_transmission_and_reception(self, cursor, connect_db, camera_id):
        # Cấu hình map (phase, signal) với các UI Widget tương ứng
        configs = [
            ("before", "gate", self.uic.checkBox_join_gate_2, self.uic.spinBox_Ordinal_gate_2, self.uic.comboBox_value_gate_2),
            ("before", "busy", self.uic.checkBox_join_busy_2, self.uic.spinBox_Ordinal_busy_2, self.uic.comboBox_value_busy_2),
            ("before", "ready", self.uic.checkBox_join_ready_2, self.uic.spinBox_Ordinal_ready_2, self.uic.comboBox_value_ready_2),
            ("after", "gate", self.uic.checkBox_join_gate_3, self.uic.spinBox_Ordinal_gate_3, self.uic.comboBox_value_gate_3),
            ("after", "busy", self.uic.checkBox_join_busy_3, self.uic.spinBox_Ordinal_busy_3, self.uic.comboBox_value_busy_3),
            ("after", "ready", self.uic.checkBox_join_ready_3, self.uic.spinBox_Ordinal_ready_3, self.uic.comboBox_value_ready_3),
        ]

        try:
            cursor.execute("DELETE FROM signal_transmission_and_reception WHERE camera_id = %s", (camera_id,))
            
            sql_command = """
                INSERT INTO signal_transmission_and_reception
                    (camera_id, phase, signal_name, is_join, ordinal_number, value_reg)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            for phase, signal, chk_join, sp_ord, cb_val in configs:
                is_join = int(chk_join.isChecked())
                ordinal = sp_ord.value()
                val_text = cb_val.currentText().strip()
                value_reg = val_text if val_text else "0"
                
                cursor.execute(sql_command, (camera_id, phase, signal, is_join, ordinal, value_reg))

            connect_db.connection.commit()
            QMessageBox.information(None, "Thành công", "Lưu thành công data signal transmission and reception!")
        except Exception as e:
            connect_db.connection.rollback()
            QMessageBox.critical(None, "Lỗi", f"Lỗi khi lưu data signal transmission: {e}")


    def load_data_signal_transmission_and_reception(self, cursor, camera_id):
        cursor.execute("""
            SELECT phase, signal_name, is_join, ordinal_number, value_reg
            FROM signal_transmission_and_reception
            WHERE camera_id = %s
        """, (camera_id,))
        rows = cursor.fetchall()
        if not rows:
            # QMessageBox.critical(None, "Notification", "Chưa thiết lập kết nối đến PLC load_data_signal_transmission_and_reception")
            _log.warning("Chưa thiết lập kết nối đến PLC load_data_signal_transmission_and_reception")
            return 

        ui_map = {
            ("before", "gate"): (self.uic.checkBox_join_gate_2, self.uic.spinBox_Ordinal_gate_2, self.uic.comboBox_value_gate_2),
            ("before", "busy"): (self.uic.checkBox_join_busy_2, self.uic.spinBox_Ordinal_busy_2, self.uic.comboBox_value_busy_2),
            ("before", "ready"): (self.uic.checkBox_join_ready_2, self.uic.spinBox_Ordinal_ready_2, self.uic.comboBox_value_ready_2),
            ("after", "gate"): (self.uic.checkBox_join_gate_3, self.uic.spinBox_Ordinal_gate_3, self.uic.comboBox_value_gate_3),
            ("after", "busy"): (self.uic.checkBox_join_busy_3, self.uic.spinBox_Ordinal_busy_3, self.uic.comboBox_value_busy_3),
            ("after", "ready"): (self.uic.checkBox_join_ready_3, self.uic.spinBox_Ordinal_ready_3, self.uic.comboBox_value_ready_3),
        }

        for phase, signal_name, is_join, ordinal_number, value_reg in rows:
            key = (phase, signal_name)
            if key in ui_map:
                chk_join, sp_ord, cb_val = ui_map[key]
                chk_join.setChecked(bool(is_join))
                sp_ord.setValue(int(ordinal_number))
            
                try:
                    val_int = int(value_reg)
                    if 0 <= val_int < cb_val.count():
                        cb_val.setCurrentIndex(val_int)
                except (ValueError, TypeError):
                    pass


    def save_signal_timing_config(self, cursor, connect_db, camera_id):
        configs = [
            ("before", "gate", self.uic.checkBox_before_gate_2, self.uic.checkBox_after_gate_2, self.uic.lineEdit_timer_gate_2),
            ("before", "busy", self.uic.checkBox_before_busy_2, self.uic.checkBox_after_busy_2, self.uic.lineEdit_timer_busy_2),
            ("before", "ready", self.uic.checkBox_before_ready_2, self.uic.checkBox_after_ready_2, self.uic.lineEdit_timer_ready_2),
            ("after", "gate", self.uic.checkBox_before_gate_3, self.uic.checkBox_after_gate_3, self.uic.lineEdit_timer_gate_3),
            ("after", "busy", self.uic.checkBox_before_busy_3, self.uic.checkBox_after_busy_3, self.uic.lineEdit_timer_busy_3),
            ("after", "ready", self.uic.checkBox_before_ready_3, self.uic.checkBox_after_ready_3, self.uic.lineEdit_timer_ready_3),
        ]
        
        def safe_float(text):
            try: return float(text) if text else 0.0
            except ValueError: return 0.0

        try:
            cursor.execute("DELETE FROM signal_timing_config WHERE camera_id = %s", (camera_id,))
            
            sql_command = """
                INSERT INTO signal_timing_config
                    (camera_id, phase, signal_name, delay_before, delay_after, timer_ms)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            for phase, signal, chk_bef, chk_aft, le_timer in configs:
                cursor.execute(sql_command, (
                    camera_id, phase, signal,
                    int(chk_bef.isChecked()),
                    int(chk_aft.isChecked()),
                    safe_float(le_timer.text())
                ))

            connect_db.connection.commit()
            QMessageBox.information(None, "Thành công", "Lưu thành công data signal timing config!")
        except Exception as e:
            connect_db.connection.rollback()
            QMessageBox.critical(None, "Lỗi", f"Lỗi khi lưu data signal timing config: {e}")


    def load_signal_timing_config(self, cursor, camera_id):
        cursor.execute("""
            SELECT phase, signal_name, delay_before, delay_after, timer_ms
            FROM signal_timing_config
            WHERE camera_id = %s
        """, (camera_id,))
        rows = cursor.fetchall()
        
        if not rows:
            # QMessageBox.critical(None, "Notification", "Chưa thiết lập kết nối đến PLC load_data_signal_timing_config")
            _log.warning("Chưa thiết lập kết nối đến PLC load_data_signal_timing_config")
            return 

        ui_map = {
            ("before", "gate"): (self.uic.checkBox_before_gate_2, self.uic.checkBox_after_gate_2, self.uic.lineEdit_timer_gate_2),
            ("before", "busy"): (self.uic.checkBox_before_busy_2, self.uic.checkBox_after_busy_2, self.uic.lineEdit_timer_busy_2),
            ("before", "ready"): (self.uic.checkBox_before_ready_2, self.uic.checkBox_after_ready_2, self.uic.lineEdit_timer_ready_2),
            ("after", "gate"): (self.uic.checkBox_before_gate_3, self.uic.checkBox_after_gate_3, self.uic.lineEdit_timer_gate_3),
            ("after", "busy"): (self.uic.checkBox_before_busy_3, self.uic.checkBox_after_busy_3, self.uic.lineEdit_timer_busy_3),
            ("after", "ready"): (self.uic.checkBox_before_ready_3, self.uic.checkBox_after_ready_3, self.uic.lineEdit_timer_ready_3),
        }

        for phase, signal_name, delay_before, delay_after, time_delay in rows:
            key = (phase, signal_name)
            if key in ui_map:
                chk_bef, chk_aft, le_timer = ui_map[key]
                chk_bef.setChecked(bool(delay_before))
                chk_aft.setChecked(bool(delay_after))
                le_timer.setText(str(time_delay))
        
        

    
    def toggle_lock(self, cursor, connect_db):
        if getattr(self, 'is_unlocked', False):
            self.lock_gui(cursor, connect_db, method=False, boolen=False)
            self.is_unlocked = False
            self.uic.pushButton_admin.setText("ADMIN")
        else:
            if self.lock_gui(cursor, connect_db, method=True, boolen=True):
                self.is_unlocked = True
                self.uic.pushButton_admin.setText("LOCK")

    def set_ui_enabled(self, enabled=False):
        widget_types = (
            QtWidgets.QPushButton, QtWidgets.QLineEdit, QtWidgets.QComboBox,
            QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox, QtWidgets.QCheckBox,
            QtWidgets.QRadioButton, QtWidgets.QSlider, QtWidgets.QListView,
            QtWidgets.QTreeView, QtWidgets.QTableView, QtWidgets.QTableWidget,
            QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit
        )
        for widget in self.uic.centralwidget.findChildren(widget_types):
            if widget != self.uic.pushButton_admin:
                widget.setEnabled(enabled)
        self.uic.pushButton_admin.setEnabled(True)

    def lock_gui(self, cursor, connect_db, method=False, boolen=False):
        try:
            if method:
                dlg = QtWidgets.QDialog()
                dlg.setWindowTitle("User Authentication")
                dlg.setFixedSize(320, 180)
                dlg.setWindowFlags(dlg.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
                layout = QtWidgets.QVBoxLayout()

                user_combo = QtWidgets.QComboBox()
                user_combo.addItem("Administrator (Master)", userData="__ADMIN__")
                
                try:
                    from Administrator.user_db import get_all_users
                    users = get_all_users(cursor)
                    if users:
                        for u in users:
                            user_id, username, role, is_active, *_ = u
                            if is_active:
                                user_combo.addItem(f"{username} (Role: {role})", userData=username)
                except Exception as e:
                    print("Could not load users from DB:", e)

                password_input = QtWidgets.QLineEdit()
                password_input.setEchoMode(QtWidgets.QLineEdit.Password)
                password_input.setPlaceholderText("Enter password")

                button = QtWidgets.QPushButton("Unlock GUI")

                def check_password():
                    selected_user = user_combo.currentData()
                    input_pass = password_input.text()
                    
                    if selected_user == "__ADMIN__":
                        from Administrator.user_db import verify_admin_password
                        if verify_admin_password(input_pass):
                            dlg.accept()
                        else:
                            QtWidgets.QMessageBox.warning(dlg, "Sai mật khẩu", "Mật khẩu Admin không đúng!")
                    else:
                        try:
                            cursor.execute("SELECT password_hash, role FROM ADMINISTRATOR.ADMIN_USERS WHERE username = %s AND is_active = 1", (selected_user,))
                            result = cursor.fetchone()
                            if result:
                                saved_hash, role = result
                                from Administrator.user_db import verify_password
                                if verify_password(input_pass, saved_hash):
                                    dlg.accept()
                                else:
                                    QtWidgets.QMessageBox.warning(dlg, "Sai mật khẩu", "Mật khẩu không đúng!")
                            else:
                                QtWidgets.QMessageBox.warning(dlg, "Lỗi", "Tài khoản không tồn tại hoặc bị vô hiệu hóa!")
                        except Exception as e:
                            QtWidgets.QMessageBox.critical(dlg, "Lỗi CSDL", str(e))

                button.clicked.connect(check_password)
                password_input.returnPressed.connect(check_password)

                layout.addWidget(QtWidgets.QLabel("Select User:"))
                layout.addWidget(user_combo)
                layout.addWidget(password_input)
                layout.addWidget(button)
                dlg.setLayout(layout)

                result = dlg.exec_()
                if result == QtWidgets.QDialog.Accepted:
                    QtCore.QTimer.singleShot(50, lambda: self.set_ui_enabled(enabled=boolen))
                    return True
                else:
                    return False
            else:
                self.set_ui_enabled(enabled=boolen)
                return True
        except Exception as e:
            print("Error in lock_gui:", e)
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(None, "Lỗi khi mở form", str(e))
            return False

    def generate_table(self):
        num_shots = self.uic.spinBox_num_shot.value()
        self.uic.tableWidget_shotxmodel.setRowCount(num_shots)
        for row in range(num_shots):
            shot_item = QTableWidgetItem(f'{str(row+1)}')
            shot_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.uic.tableWidget_shotxmodel.setItem(row,0,shot_item)
            list_model = QComboBox()
            list_model.addItems([str(i+1) for i in range(int(self.uic.comboBox_n_model.currentText()))])
            list_model.setEditable(True)
            list_model.lineEdit().setReadOnly(True)
            list_model.lineEdit().setAlignment(QtCore.Qt.AlignCenter)
            self.uic.tableWidget_shotxmodel.setCellWidget(row,1,list_model)




    def setup_counter_shot(self, cursor, connect_db, camera_id):
        is_check_pc = self.uic.radioButton_counter_pc.isChecked()
        is_check_plc = self.uic.radioButton_counter_plc.isChecked()
        is_check_plc_to_pc = self.uic.radioButton_condition_plc_pc.isChecked()

        is_check = 'PC'
        is_reset = 'RESET'
        if is_check_pc:
            is_check = 'PC'
        elif is_check_plc:
            is_check = 'PLC'
        elif is_check_plc_to_pc:
            is_check = 'PLC_TO_PC'

        is_reset_counter = self.uic.radioButton_reset.isChecked()
        is_none_reset = self.uic.radioButton_none_reset.isChecked()

        is_cycle_shot = self.uic.radioButton_cycle_frame.isChecked()
        is_single_frame = self.uic.radioButton_single_frame.isChecked()

        if is_cycle_shot:
            method_use = 'Cycle'
        elif is_single_frame:
            method_use = 'Single'

        if is_reset_counter:
            is_reset = 'RESET'
        elif is_none_reset:
            is_reset = 'NONE_RESET'

        increment_counter_signal_selected = self.uic.comboBox_increment_counter_signal_selected.currentText()
        reset_counter_signal_selected = self.uic.comboBox_reset_counter_signal_selected.currentText()
        method_use_signal_selected = self.uic.comboBox_method_use_signal_selected.currentText()

        try:
            cursor.execute("DELETE FROM counter_shot_setup WHERE camera_id = %s", (camera_id,))

            sql_command = """
                INSERT INTO counter_shot_setup
                    (camera_id, setup_counter_shot, reset_counter, method_use, increment_counter_signal_selected, reset_counter_signal_selected, method_use_signal_selected)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """

            cursor.execute(sql_command, (camera_id, is_check, is_reset, method_use, increment_counter_signal_selected, reset_counter_signal_selected, method_use_signal_selected))
            connect_db.connection.commit()
            if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                self.uic.config_logger.set_status('counter_shot', 'success', f"Đã lưu thành công thiết lập Counter Shot ({method_use})")
            QtWidgets.QMessageBox.information(None, "Thành công", "Thiết lập counter shot thành công!")
        except Exception as e:
            if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                self.uic.config_logger.set_status('counter_shot', 'error', f"Lỗi thiết lập counter shot: {str(e)}")
            QtWidgets.QMessageBox.critical(None, "Lỗi khi thiết lập counter shot", str(e))

        

    def load_counter_shot(self, cursor, camera_id):
        cursor.execute("SELECT * FROM counter_shot_setup WHERE camera_id = %s", (camera_id,))
        result = cursor.fetchone()
        if result:
            _, _, is_check, is_reset,method_use,increment_counter_signal_selected,reset_counter_signal_selected,method_use_signal_selected = result
            if is_check == 'PC':
                self.uic.radioButton_counter_pc.setChecked(True)
            elif is_check == 'PLC':
                self.uic.radioButton_counter_plc.setChecked(True)
            elif is_check == 'PLC_TO_PC':
                self.uic.radioButton_condition_plc_pc.setChecked(True)
            
            if is_reset == 'RESET':
                self.uic.radioButton_reset.setChecked(True)
            elif is_reset == 'NONE_RESET':
                self.uic.radioButton_none_reset.setChecked(True)

            if method_use == 'Cycle':
                self.uic.radioButton_cycle_frame.setChecked(True)
            elif method_use == 'Single':
                self.uic.radioButton_single_frame.setChecked(True)

            self.uic.comboBox_increment_counter_signal_selected.setCurrentText(increment_counter_signal_selected)
            self.uic.comboBox_reset_counter_signal_selected.setCurrentText(reset_counter_signal_selected)
            self.uic.comboBox_method_use_signal_selected.setCurrentText(method_use_signal_selected)

    def table_signal_up_to_selected_trigger_signals(self):
        current_text = self.uic.comboBox_set_trigger_automatic.currentText()
        self.uic.comboBox_set_trigger_automatic.clear()
        
        for row in range(self.uic.tableWidget.rowCount()):
            item = self.uic.tableWidget.verticalHeaderItem(row)
            if item:
                self.uic.comboBox_set_trigger_automatic.addItem(item.text())
                self.uic.comboBox_set_trigger_mirror.addItem(item.text())
                self.uic.comboBox_set_trigger_logging.addItem(item.text())
                self.uic.comboBox_set_component_automatic.addItem(item.text())
                self.uic.comboBox_set_component_mirror.addItem(item.text())
                self.uic.comboBox_set_component_logging.addItem(item.text())
                self.uic.comboBox_set_completed_automatic.addItem(item.text())
                self.uic.comboBox_set_completed_mirror.addItem(item.text())
                self.uic.comboBox_set_completed_logging.addItem(item.text())
                self.uic.comboBox_increment_counter_signal_selected.addItem(item.text())
                self.uic.comboBox_reset_counter_signal_selected.addItem(item.text())
                self.uic.comboBox_method_use_signal_selected.addItem(item.text())
                
        index = self.uic.comboBox_set_trigger_automatic.findText(current_text)
        if index >= 0:
            self.uic.comboBox_set_trigger_automatic.setCurrentIndex(index)           

    MAPPING_MODE_NAMES = ('automatic', 'mirror', 'logging')

    def _mapping_mode_widgets(self, mode_name):
        return {
            'mapping_mode':     getattr(self.uic, f'comboBox_{mode_name}_mode'),
            'trigger_selected': getattr(self.uic, f'comboBox_set_trigger_{mode_name}'),
            'component':        getattr(self.uic, f'comboBox_set_component_{mode_name}'),
            'completed':        getattr(self.uic, f'comboBox_set_completed_{mode_name}'),
        }

    def save_mapping_mode(self, cursor, connect_db, camera_id):
        try:
            cursor.execute("DELETE FROM setup_mapping_mode WHERE camera_id = %s", (camera_id,))
            sql_command = """
                INSERT INTO setup_mapping_mode
                    (camera_id, mode_name, mapping_mode, trigger_selected, component, completed)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            for mode_name in self.MAPPING_MODE_NAMES:
                w = self._mapping_mode_widgets(mode_name)
                cursor.execute(sql_command, (
                    camera_id,
                    mode_name,
                    w['mapping_mode'].currentText(),
                    w['trigger_selected'].currentText(),
                    w['component'].currentText(),
                    w['completed'].currentText(),
                ))
            connect_db.connection.commit()
            if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                self.uic.config_logger.set_status('mapping_mode', 'success', "Đã lưu thành công thiết lập Mapping Mode")
            QtWidgets.QMessageBox.information(None, "Thành công", "Thiết lập Mapping Mode thành công!")
        except Exception as e:
            if hasattr(self.uic, 'config_logger') and self.uic.config_logger:
                self.uic.config_logger.set_status('mapping_mode', 'error', f"Lỗi Mapping Mode: {str(e)}")
            QtWidgets.QMessageBox.critical(None, "Lỗi khi thiết lập Mapping Mode", str(e))

    def load_mapping_mode(self, cursor, camera_id):
        cursor.execute(
            "SELECT mode_name, mapping_mode, trigger_selected, component, completed "
            "FROM setup_mapping_mode WHERE camera_id = %s", (camera_id,))
        rows = cursor.fetchall()
        list_mode = {
            name: {'mapping_mode': None, 'trigger_selected': None, 'component': None, 'completed': None}
            for name in self.MAPPING_MODE_NAMES
        }

        for mode_name, mapping_mode, trigger_selected, component, completed in rows:
            if mode_name not in list_mode:
                continue
            values = {
                'mapping_mode': mapping_mode,
                'trigger_selected': trigger_selected,
                'component': component,
                'completed': completed,
            }
            widgets = self._mapping_mode_widgets(mode_name)
            for field, value in values.items():
                if value:
                    widgets[field].setCurrentText(value)
            list_mode[mode_name] = values

        return list_mode


        
