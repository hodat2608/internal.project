from PyQt5.QtWidgets import QCheckBox
from PyQt5 import QtWidgets
from functools import partial
import glob
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSpinBox, QTableWidget,
    QTableWidgetItem, QComboBox
)
from PyQt5 import QtCore,QtGui
from PyQt5.QtGui import QPixmap
import cv2
from app_logger.app_logger import get_logger as _get_logger, open_log_window
from module_1.root_path import resource_path
from module_2.StyleSheet import *
_log = _get_logger('auto_logging_process')

class AutoLoggingProcess:
    def __init__(self, ui_logging, cursor, process=None, built_in_objects={}, camera_id=None, connection=None):
        self.ui_logging = ui_logging
        self.cursor = cursor
        self.list_size = []
        self.process = process
        self.built_in_objects = built_in_objects
        self.camera_id = camera_id
        self.connection = connection
        self.is_unlocked = False
        self.current_user = None
        self.current_role = None

        # Tích hợp nút Lịch Sử Cấu Hình cho Auto Logging
        if hasattr(self.ui_logging, 'hlayout_item_code'):
            if not hasattr(self.ui_logging, 'pushButton_config_history'):
                self.ui_logging.pushButton_config_history = QtWidgets.QPushButton(getattr(self.ui_logging, 'groupBox_item', None))
                self.ui_logging.pushButton_config_history.setMinimumSize(QtCore.QSize(50, 40))
                self.ui_logging.pushButton_config_history.setMaximumSize(QtCore.QSize(60, 16777215))
                self.ui_logging.pushButton_config_history.setStyleSheet(pushButton_config_history_style)
                self.ui_logging.pushButton_config_history.setToolTip("🕒 Xem Lịch Sử Cấu Hình, So Sánh Diff & Rollback (Auto Logging)")
                icon_h = QtGui.QIcon()
                icon_h.addPixmap(QtGui.QPixmap(resource_path("module_3/assert/icon/history.png")), QtGui.QIcon.Normal, QtGui.QIcon.Off)
                self.ui_logging.pushButton_config_history.setIcon(icon_h)
                self.ui_logging.pushButton_config_history.setIconSize(QtCore.QSize(25, 25))
                self.ui_logging.hlayout_item_code.addWidget(self.ui_logging.pushButton_config_history)
    
    def broswer_folder(self):
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(
            None,
            "Chọn thư mục lưu trữ",
            "",
            QtWidgets.QFileDialog.ShowDirsOnly |
            QtWidgets.QFileDialog.DontResolveSymlinks
        )
        self.ui_logging.lineEdit_folder_path.setText(folder_path)

    def _get_button_row(self, btn, col=9) -> int:
        """Tìm chỉ số dòng hiện tại của một button nằm trong bảng tableWidget."""
        table = getattr(self.ui_logging, 'tableWidget', None)
        if not table:
            return -1
        for r in range(table.rowCount()):
            if table.cellWidget(r, col) is btn:
                return r
        return -1

    def _create_save_button(self, row: int, file_path: str = None) -> QtWidgets.QPushButton:
        """Tạo nút Save cho từng dòng ảnh với giao diện chuyên nghiệp."""
        btn = QtWidgets.QPushButton("💾 Data Save")
        btn.setToolTip("Lưu cấu hình riêng cho dòng ảnh này vào cơ sở dữ liệu")
        btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        btn.setStyleSheet(save_button_btn_setStyleSheet)
        if hasattr(self, 'is_unlocked'):
            btn.setEnabled(self.is_unlocked)
        btn.clicked.connect(lambda _=False, r=row, fp=file_path, b=btn: self.on_save_row_clicked(r, fp, b))
        return btn

    def _create_detect_button(self, file_path: str, combo_cam, combo_key) -> QtWidgets.QPushButton:
        """Tạo nút Detect cho cột View Detection."""
        btn = QtWidgets.QPushButton("Detect")
        btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        btn.setStyleSheet(detect_button_setStyleSheet)
        if hasattr(self, 'is_unlocked'):
            btn.setEnabled(self.is_unlocked)
        from functools import partial
        btn.clicked.connect(partial(self.on_detect_clicked, file_path, combo_cam, combo_key))
        return btn

    def _show_save_success_effect(self, btn: QtWidgets.QPushButton):
        """Hiệu ứng xanh lá '✔ Đã lưu' tạm thời trên nút Save khi lưu thành công."""
        orig_text = btn.text()
        orig_style = btn.styleSheet()
        btn.setText("✔ Đã lưu")
        btn.setStyleSheet(show_save_success_effect)
        QtCore.QTimer.singleShot(2500, lambda: self._reset_save_button_state(btn, orig_text, orig_style))

    def _reset_save_button_state(self, btn: QtWidgets.QPushButton, orig_text: str, orig_style: str):
        try:
            if btn and not btn.isHidden():
                btn.setText(orig_text)
                btn.setStyleSheet(orig_style)
        except RuntimeError:
            pass

    def _adjust_table_columns(self):
        """Cấu hình lại độ rộng và chế độ hiển thị chuẩn cho 10 cột trong tableWidget."""
        table = self.ui_logging.tableWidget
        if table.columnCount() < 10:
            table.setColumnCount(10)
            
        header = table.horizontalHeader()
        header.setCascadingSectionResizes(False)
        for i in range(table.columnCount()):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Interactive)
            
        table.setColumnWidth(0, 75)   # Join State
        table.setColumnWidth(1, 320)  # Image Preview / Path
        table.setColumnWidth(2, 130)  # Description
        table.setColumnWidth(3, 110)  # Select Camera
        table.setColumnWidth(4, 110)  # Select Model
        table.setColumnWidth(5, 85)   # View Detection
        table.setColumnWidth(6, 95)   # Register
        table.setColumnWidth(7, 85)   # Value ON
        table.setColumnWidth(8, 85)   # Value OFF
        table.setColumnWidth(9, 90)   # Action (Save)

    def get_row_data(self, row: int) -> dict:
        """Trích xuất dữ liệu của 1 dòng từ tableWidget."""
        data = {
            'row': row,
            'db_id': None,
            'folder_path': '',
            'join_state': 1,
            'image_path': '',
            'description_image': '',
            'select_camera': '',
            'select_model': '',
            'register': '',
            'value_on': '',
            'value_off': '',
        }
        
        # 1. Folder path
        if hasattr(self.ui_logging, 'lineEdit_folder_path'):
            data['folder_path'] = self.ui_logging.lineEdit_folder_path.text().strip()
            
        # 2. Col 0: Join State
        cell0 = self.ui_logging.tableWidget.cellWidget(row, 0)
        if cell0 is not None:
            chk = cell0.findChild(QtWidgets.QCheckBox)
            if chk is not None:
                data['join_state'] = 1 if chk.isChecked() else 0
            elif isinstance(cell0, QtWidgets.QCheckBox):
                data['join_state'] = 1 if cell0.isChecked() else 0
        else:
            item0 = self.ui_logging.tableWidget.item(row, 0)
            if item0:
                data['join_state'] = 1 if item0.checkState() == QtCore.Qt.Checked else 0

        # 3. Col 1: Image Path & DB ID
        item1 = self.ui_logging.tableWidget.item(row, 1)
        if item1 is not None:
            data['image_path'] = item1.text().strip()
            user_data = item1.data(QtCore.Qt.UserRole)
            if user_data is not None:
                try:
                    data['db_id'] = int(user_data)
                except (ValueError, TypeError):
                    data['db_id'] = None

        # 4. Col 2: Description
        item2 = self.ui_logging.tableWidget.item(row, 2)
        if item2 is not None:
            data['description_image'] = item2.text().strip()

        # 5. Col 3: Select Camera
        cell3 = self.ui_logging.tableWidget.cellWidget(row, 3)
        if isinstance(cell3, QtWidgets.QComboBox):
            data['select_camera'] = cell3.currentText().strip()
        elif self.ui_logging.tableWidget.item(row, 3):
            data['select_camera'] = self.ui_logging.tableWidget.item(row, 3).text().strip()

        # 6. Col 4: Select Model
        cell4 = self.ui_logging.tableWidget.cellWidget(row, 4)
        if isinstance(cell4, QtWidgets.QComboBox):
            data['select_model'] = cell4.currentText().strip()
        elif self.ui_logging.tableWidget.item(row, 4):
            data['select_model'] = self.ui_logging.tableWidget.item(row, 4).text().strip()

        # 7. Col 6: Register
        item6 = self.ui_logging.tableWidget.item(row, 6)
        if item6 is not None:
            data['register'] = item6.text().strip()

        # 8. Col 7: Value ON
        item7 = self.ui_logging.tableWidget.item(row, 7)
        if item7 is not None:
            data['value_on'] = item7.text().strip()

        # 9. Col 8: Value OFF
        item8 = self.ui_logging.tableWidget.item(row, 8)
        if item8 is not None:
            data['value_off'] = item8.text().strip()

        return data

    def on_save_row_clicked(self, row: int, file_path: str = None, btn: QtWidgets.QPushButton = None):
        """Lưu cấu hình riêng cho từng dòng ảnh vào database auto_logging và ghi lịch sử thay đổi."""
        if hasattr(self, 'is_unlocked') and not self.is_unlocked:
            QtWidgets.QMessageBox.warning(
                getattr(self.ui_logging, 'centralwidget', None),
                "Từ chối thao tác",
                "Chức năng Auto Logging đang ở chế độ khóa!\n"
                "Vui lòng nhấn nút ADMIN tại tab PLC Settings để đăng nhập với quyền Quản trị viên (Administrator)."
            )
            return

        actual_row = row
        if btn is not None:
            found = self._get_button_row(btn, col=9)
            if found != -1:
                actual_row = found
                
        row_count = self.ui_logging.tableWidget.rowCount()
        if actual_row < 0 or actual_row >= row_count:
            QtWidgets.QMessageBox.warning(None, "Lỗi", f"Không tìm thấy dòng tương ứng ({actual_row})!")
            return

        row_data = self.get_row_data(actual_row)
        image_path = row_data['image_path']
        if not image_path and file_path:
            image_path = file_path
            row_data['image_path'] = file_path
            
        if not image_path:
            QtWidgets.QMessageBox.warning(None, "Cảnh báo", "Dòng này chưa có đường dẫn hình ảnh!")
            return

        conn = getattr(self, 'connection', None)
        if conn is None and hasattr(self, 'cursor') and self.cursor:
            conn = getattr(self.cursor, 'connection', None)
        if conn is None:
            QtWidgets.QMessageBox.warning(None, "Lỗi kết nối", "Chưa có kết nối cơ sở dữ liệu để lưu dữ liệu!")
            return

        # Xác định camera_id
        camera_id = getattr(self, 'camera_id', None)
        if camera_id is None:
            cam_str = row_data.get('select_camera', '')
            import re
            digits = re.findall(r'\d+', cam_str)
            camera_id = int(digits[0]) if digits else 1
        else:
            try:
                import re
                digits = re.findall(r'\d+', str(camera_id))
                camera_id = int(digits[0]) if digits else int(camera_id)
            except Exception:
                camera_id = 1

        from module_3.change_reason_dialog import ChangeReasonDialog
        from module_3.config_version_manager import save_snapshot

        curr_user = getattr(self, 'current_user', None) or 'Admin'
        curr_role = getattr(self, 'current_role', None) or 'full_control'
        img_name = os.path.basename(image_path)

        reason_dlg = ChangeReasonDialog(
            current_user=curr_user,
            current_role=curr_role,
            context_info=f"Camera {camera_id} - Dòng ảnh: {img_name}",
            parent=getattr(self.ui_logging, 'centralwidget', None)
        )
        if reason_dlg.exec_() != QtWidgets.QDialog.Accepted:
            return

        change_reason, is_golden = reason_dlg.get_reason_and_golden()

        cursor = conn.cursor()
        db_id = row_data.get('db_id')
        
        # Kiểm tra xem bản ghi đã tồn tại trong DB chưa (theo id hoặc theo image_path + camera_id)
        existing_id = None
        if db_id:
            cursor.execute("SELECT id FROM auto_logging WHERE id = %s", (db_id,))
            res = cursor.fetchone()
            if res:
                existing_id = res[0]
        
        if existing_id is None:
            cursor.execute(
                "SELECT id FROM auto_logging WHERE image_path = %s AND camera_id = %s LIMIT 1",
                (image_path, camera_id)
            )
            res = cursor.fetchone()
            if res:
                existing_id = res[0]

        try:
            if existing_id is not None:
                update_sql = """
                    UPDATE auto_logging SET
                        folder_path = %s,
                        join_state = %s,
                        image_path = %s,
                        description_image = %s,
                        select_camera = %s,
                        select_model = %s,
                        register = %s,
                        value_on = %s,
                        value_off = %s,
                        camera_id = %s
                    WHERE id = %s
                """
                cursor.execute(update_sql, (
                    row_data['folder_path'],
                    row_data['join_state'],
                    row_data['image_path'],
                    row_data['description_image'],
                    row_data['select_camera'],
                    row_data['select_model'],
                    row_data['register'],
                    row_data['value_on'],
                    row_data['value_off'],
                    camera_id,
                    existing_id
                ))
                final_id = existing_id
            else:
                insert_sql = """
                    INSERT INTO auto_logging (
                        folder_path, join_state, image_path, description_image,
                        select_camera, select_model, register, value_on, value_off, camera_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_sql, (
                    row_data['folder_path'],
                    row_data['join_state'],
                    row_data['image_path'],
                    row_data['description_image'],
                    row_data['select_camera'],
                    row_data['select_model'],
                    row_data['register'],
                    row_data['value_on'],
                    row_data['value_off'],
                    camera_id
                ))
                final_id = cursor.lastrowid
                
            conn.commit()
            
            # Cập nhật ID vào UserRole của ô image_path trong bảng
            shot_item = self.ui_logging.tableWidget.item(actual_row, 1)
            if shot_item:
                shot_item.setData(QtCore.Qt.UserRole, final_id)

            # Ghi snapshot audit trail
            try:
                conn_raw = getattr(conn, 'connection', conn)
                save_snapshot(
                    cursor=cursor,
                    connection=conn_raw,
                    scope_category='AUTO_LOGGING',
                    change_reason=f"Lưu riêng dòng [{img_name}]: {change_reason}",
                    changed_by=curr_user,
                    camera_id=str(camera_id),
                    user_role=curr_role,
                    is_golden=is_golden
                )
            except Exception as e_snap:
                _log.warning("Lỗi ghi snapshot cho dòng auto logging: %s", e_snap)

            # Cập nhật visual feedback trên nút Save
            if btn is not None:
                self._show_save_success_effect(btn)

            QtWidgets.QMessageBox.information(
                None,
                "Thành công",
                f"Đã lưu thành công cấu hình cho dòng ảnh:\n{img_name}\n(ID: {final_id})"
            )
        except Exception as e:
            _log.error("Lỗi khi lưu dòng auto logging: %s", e)
            try:
                conn.rollback()
            except Exception:
                pass
            QtWidgets.QMessageBox.critical(None, "Lỗi lưu dữ liệu", f"Không thể lưu dữ liệu dòng này:\n{str(e)}")

    def generate_table(self,total_key):
        path = self.ui_logging.lineEdit_folder_path.text().strip()
        valid_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
        list_obj = []
        if path and os.path.isdir(path):
            list_obj = [
                os.path.join(path, f)
                for f in os.listdir(path)
                if os.path.isfile(os.path.join(path, f)) and os.path.splitext(f)[1].lower() in valid_exts
            ]
            list_obj.sort()

        total_cam = set()
        total_model = set()
        for cam, model in total_key:
            total_cam.add(cam)
            total_model.add(model)
        self.ui_logging.tableWidget.setRowCount(len(list_obj))
        for row, file_path in enumerate(list_obj):

            join_container = QtWidgets.QWidget()
            join_layout = QtWidgets.QHBoxLayout(join_container)
            join_layout.setContentsMargins(0, 0, 0, 0)
            join_layout.setAlignment(QtCore.Qt.AlignCenter)
            
            join_state = QCheckBox()
            join_state.setCheckState(QtCore.Qt.Checked)
            
            join_layout.addWidget(join_state)
            self.ui_logging.tableWidget.setCellWidget(row, 0, join_container)

            shot_item = QTableWidgetItem(file_path)
            self.ui_logging.tableWidget.setItem(row, 1, shot_item)

            desc_item = QTableWidgetItem("")
            self.ui_logging.tableWidget.setItem(row, 2, desc_item)
            
            combo_cam = QtWidgets.QComboBox()
            combo_cam.addItems(list(total_cam))
            self.ui_logging.tableWidget.setCellWidget(row, 3, combo_cam)
            
            combo_key = QtWidgets.QComboBox()
            combo_key.addItems(list(total_model))
            self.ui_logging.tableWidget.setCellWidget(row, 4, combo_key)
            
            detect_button = self._create_detect_button(file_path, combo_cam, combo_key)
            self.ui_logging.tableWidget.setCellWidget(row, 5, detect_button)
            
            from PyQt5.QtCore import Qt
            item_col6 = QTableWidgetItem("")
            item_col6.setTextAlignment(Qt.AlignCenter)
            self.ui_logging.tableWidget.setItem(row, 6, item_col6)
            
            item_col7 = QTableWidgetItem("")
            item_col7.setTextAlignment(Qt.AlignCenter)
            self.ui_logging.tableWidget.setItem(row, 7, item_col7)

            item_col8 = QTableWidgetItem("")
            item_col8.setTextAlignment(Qt.AlignCenter)
            self.ui_logging.tableWidget.setItem(row, 8, item_col8)

            save_button = self._create_save_button(row, file_path)
            self.ui_logging.tableWidget.setCellWidget(row, 9, save_button)

        self._adjust_table_columns()

        

    def show_image_preview(self):
        row = self.ui_logging.tableWidget.currentRow()
        col = self.ui_logging.tableWidget.currentColumn()
        if row < 0 or col != 1:
            return
        path = self.ui_logging.tableWidget.item(row, 1).text()
        pixmap = QPixmap(path)
        self.target_width = self.ui_logging.label_image_prev.width()
        self.target_height = self.ui_logging.label_image_prev.height()

        if not self.list_size:
            self.list_size.append(self.target_width)
            self.list_size.append(self.target_height)

        scaled_pixmap = pixmap.scaled(
            self.list_size[0],
            self.list_size[1],
            QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
        )
        self.ui_logging.label_image_prev.setPixmap(scaled_pixmap)


    def save_values_auto_log_to_db(self,camera_id,connection):
        self.camera_id = camera_id
        self.connection = connection

        from module_3.change_reason_dialog import ChangeReasonDialog
        from module_3.config_version_manager import save_snapshot

        curr_user = getattr(self, 'current_user', None) or 'Admin'
        curr_role = getattr(self, 'current_role', None) or 'full_control'

        reason_dlg = ChangeReasonDialog(
            current_user=curr_user,
            current_role=curr_role,
            context_info=f"Camera: {camera_id} (Cấu hình Auto Logging)",
            parent=getattr(self.ui_logging, 'centralwidget', None)
        )
        if reason_dlg.exec_() != QtWidgets.QDialog.Accepted:
            return

        change_reason, is_golden = reason_dlg.get_reason_and_golden()

        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QComboBox, QCheckBox, QPushButton
        cursor = connection.cursor()
        folder_path = self.ui_logging.lineEdit_folder_path.text().strip()

        row_count = self.ui_logging.tableWidget.rowCount()
        col_count = self.ui_logging.tableWidget.columnCount()
        list_insert = []
        
        for row in range(row_count):
            row_data = {}
            is_empty_row = True
            
            path_item = self.ui_logging.tableWidget.item(row, 1)
            path_image = path_item.text() if path_item else ""
            
            for col in range(col_count):
                value = None

                cell_widget = self.ui_logging.tableWidget.cellWidget(row, col)
                if cell_widget is not None:
                    if isinstance(cell_widget, QCheckBox):
                        value = cell_widget.isChecked()
                    elif isinstance(cell_widget, QComboBox):
                        value = cell_widget.currentText()
                    elif isinstance(cell_widget, QPushButton):
                        value = cell_widget.text()
                    else:
                        chk = cell_widget.findChild(QCheckBox)
                        if chk is not None:
                            value = chk.isChecked()
                else:

                    item_value = self.ui_logging.tableWidget.item(row, col)
                    if item_value is not None:
                        value = item_value.text().strip()
                    else:
                        value = None

                row_data[col] = value
                
                if value is not None and value != "" and value != False:
                    is_empty_row = False
                    
            if not is_empty_row:
                list_insert.append(row_data)
  
        if list_insert:
            try:
                cursor.execute(
                    f"DELETE FROM auto_logging WHERE camera_id = %s",
                    (camera_id,),
                )

                query = """
                    INSERT INTO auto_logging (
                        folder_path, join_state, image_path, description_image, 
                        select_camera, select_model, register, value_on, value_off, camera_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                for idx, item in enumerate(list_insert):
                    join_state = 1 if item.get(0) else 0
                    image_path = str(item.get(1, ""))
                    description_image = str(item.get(2, ""))
                    select_camera = str(item.get(3, ""))
                    select_model = str(item.get(4, ""))
                    register_val = str(item.get(6, ""))
                    value_on_val = str(item.get(7, ""))
                    value_off_val = str(item.get(8, ""))
                    
                    cursor.execute(query, (
                        folder_path, 
                        join_state, 
                        image_path, 
                        description_image, 
                        select_camera, 
                        select_model, 
                        register_val, 
                        value_on_val, 
                        value_off_val, 
                        camera_id
                    ))
                    new_id = cursor.lastrowid
                    if idx < self.ui_logging.tableWidget.rowCount():
                        t_item = self.ui_logging.tableWidget.item(idx, 1)
                        if t_item:
                            t_item.setData(Qt.UserRole, new_id)
                    
                connection.commit()

                try:
                    conn_raw = getattr(connection, 'connection', connection)
                    save_snapshot(
                        cursor=cursor,
                        connection=conn_raw,
                        scope_category='AUTO_LOGGING',
                        change_reason=change_reason,
                        changed_by=curr_user,
                        camera_id=str(camera_id),
                        user_role=curr_role,
                        is_golden=is_golden
                    )
                except Exception as e_snap:
                    pass

                print(f"Lưu thành công {len(list_insert)} dòng vào database auto_logging!")
                
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.information(None, "Thành công", "Đã lưu thiết lập Auto Logging và ghi nhận lịch sử!")
                
            except Exception as e:
                print("Lỗi khi lưu dữ liệu Auto Logging vào Database:", e)
                try:
                    connection.rollback()
                except:
                    pass
        else:
            print("Không có dữ liệu để lưu.")

    def open_config_history(self, connection=None, camera_id=None):
        """Mở cửa sổ Lịch Sử Cấu Hình, So Sánh Diff & Rollback cho Auto Logging."""
        conn = connection or getattr(self, 'connection', None)
        cur = self.cursor
        cam_id = camera_id or getattr(self, 'camera_id', None)
        if not conn:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(None, "Cảnh báo", "Chưa kết nối cơ sở dữ liệu để xem lịch sử cấu hình!")
            return

        from module_3.config_history_dialog import ConfigHistoryDialog

        curr_user = getattr(self, 'current_user', None) or 'Admin'
        curr_role = getattr(self, 'current_role', None) or 'full_control'
        raw_conn = getattr(conn, 'connection', conn)

        dlg = ConfigHistoryDialog(
            cursor=cur,
            connection=raw_conn,
            current_user=curr_user,
            current_role=curr_role,
            initial_category='AUTO_LOGGING',
            initial_camera_id=str(cam_id) if cam_id else '',
            parent=getattr(self.ui_logging, 'centralwidget', None)
        )
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            if cam_id:
                self.load_data_from_db(cam_id, conn)


    def load_data_from_db(self,camera_id,connection):
        self.camera_id = camera_id
        self.connection = connection
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QTableWidgetItem, QCheckBox, QComboBox, QPushButton
        
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, folder_path, join_state, image_path, description_image,
                   select_camera, select_model, register, value_on, value_off, camera_id
            FROM auto_logging WHERE camera_id = %s
            """,
            (camera_id,),
        )
        result = cursor.fetchall()
        
        if not result:
            print("Không có dữ liệu trong DB để load.")
            return
            
        # Lấy folder path từ dòng dữ liệu đầu tiên và set vào ô lineEdit
        self.ui_logging.lineEdit_folder_path.setText(str(result[0][1]))
        
        self.ui_logging.tableWidget.setRowCount(len(result))

        total_cam = set()
        total_model = set()
        if hasattr(self, 'built_in_objects') and self.built_in_objects:
            for k, v in self.built_in_objects.items():
                c_name = k.removeprefix('built-in-camera-').removeprefix('built-in-')
                total_cam.add(c_name)
                if 'model_loader' in v and isinstance(v['model_loader'], dict):
                    for m_tuple in v['model_loader'].keys():
                        if isinstance(m_tuple, tuple) and len(m_tuple) > 1:
                            total_model.add(m_tuple[1])
        
        for row, row_data in enumerate(result):
            # Mapping cột trong DB (dựa theo thứ tự SELECT):
            # 0: id, 1: folder_path, 2: join_state, 3: image_path, 4: description_image
            # 5: select_camera, 6: select_model, 7: register, 8: value_on, 9: value_off, 10: camera_id
            
            join_val = row_data[2]
            image_path_val = str(row_data[3])
            desc_val = str(row_data[4])
            camera_val = str(row_data[5])
            model_val = str(row_data[6])
            register_val = str(row_data[7])
            value_on_val = str(row_data[8])
            value_off_val = str(row_data[9])
            
            # Cột 0: Join State (QCheckBox nằm giữa)
            from PyQt5.QtWidgets import QWidget, QHBoxLayout
            join_container = QWidget()
            join_layout = QHBoxLayout(join_container)
            join_layout.setContentsMargins(0, 0, 0, 0)
            join_layout.setAlignment(Qt.AlignCenter)
            
            join_state = QCheckBox()
            join_state.setCheckState(Qt.Checked if join_val == 1 else Qt.Unchecked)
            
            join_layout.addWidget(join_state)
            self.ui_logging.tableWidget.setCellWidget(row, 0, join_container)
            
            # Cột 1: Image Path
            shot_item = QTableWidgetItem(image_path_val)
            shot_item.setData(Qt.UserRole, row_data[0])
            self.ui_logging.tableWidget.setItem(row, 1, shot_item)
            
            # Cột 2: Description
            desc_item = QTableWidgetItem(desc_val)
            self.ui_logging.tableWidget.setItem(row, 2, desc_item)
            
            # Cột 3: Select Camera (QComboBox)
            combo_cam = QComboBox()
            row_cam_options = set(total_cam)
            if camera_val:
                row_cam_options.add(camera_val)
            if row_cam_options:
                combo_cam.addItems(list(row_cam_options))
                combo_cam.setCurrentText(camera_val)
            else:
                combo_cam.addItem(camera_val)
            self.ui_logging.tableWidget.setCellWidget(row, 3, combo_cam)
            
            # Cột 4: Select Model (QComboBox)
            combo_key = QComboBox()
            row_model_options = set(total_model)
            if model_val:
                row_model_options.add(model_val)
            if row_model_options:
                combo_key.addItems(list(row_model_options))
                combo_key.setCurrentText(model_val)
            else:
                combo_key.addItem(model_val)
            self.ui_logging.tableWidget.setCellWidget(row, 4, combo_key)
            
            # Cột 5: View Detection (QPushButton)
            detect_button = self._create_detect_button(image_path_val, combo_cam, combo_key)
            self.ui_logging.tableWidget.setCellWidget(row, 5, detect_button)
            
            # Cột 6: Register (Căn giữa)
            item_col6 = QTableWidgetItem(register_val)
            item_col6.setTextAlignment(Qt.AlignCenter)
            self.ui_logging.tableWidget.setItem(row, 6, item_col6)
            
            # Cột 7: Value ON (Căn giữa)
            item_col7 = QTableWidgetItem(value_on_val)
            item_col7.setTextAlignment(Qt.AlignCenter)
            self.ui_logging.tableWidget.setItem(row, 7, item_col7)
            
            # Cột 8: Value OFF (Căn giữa)
            item_col8 = QTableWidgetItem(value_off_val)
            item_col8.setTextAlignment(Qt.AlignCenter)
            self.ui_logging.tableWidget.setItem(row, 8, item_col8)

            # Cột 9: Action (Save)
            save_button = self._create_save_button(row, image_path_val)
            self.ui_logging.tableWidget.setCellWidget(row, 9, save_button)
            
        self._adjust_table_columns()
        print(f"Đã load thành công {len(result)} dòng dữ liệu Logging!")


    def on_detect_clicked(self, file_path, combo_cam, combo_key, *args):
        self.split_key(combo_cam, combo_key)
        result_image_rgb = cv2.imread(file_path)
        if result_image_rgb is None:
            _log.error("Lỗi đọc ảnh: %s", file_path)
            return
        result_image_rgb = cv2.cvtColor(result_image_rgb, cv2.COLOR_BGR2RGB)
        
        self.target_width = self.ui_logging.label_image_prev.width()
        self.target_height = self.ui_logging.label_image_prev.height()

        if not self.list_size:
            self.list_size.append(self.target_width)
            self.list_size.append(self.target_height)

        if not hasattr(self, 'dict_view_results'):
            self.dict_view_results = {}

        camera_id = self.valid_key[0] if isinstance(self.valid_key, (tuple, list)) and len(self.valid_key) > 0 else 'camera-1'
        res_process = self.process.process_image_func(
            result_image_rgb, self.model_loader, self.pyuic, camera_id, self.valid_key
        )
        if isinstance(res_process, (tuple, list)):
            result_image_rgb = res_process[0]
            flag = res_process[1]
            list_register = res_process[2]
        else:
            flag = False
            list_register = {}
        self.dict_view_results[file_path] = list_register

        result_text = f'RESULT: {"OK" if flag else "NG"}'
        color = (0, 255, 0) if flag else (0, 0, 255)
        cv2.putText(result_image_rgb, result_text, (10, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        h, w = result_image_rgb.shape[:2]
        qimg = QtGui.QImage(result_image_rgb.data, w, h,
                            result_image_rgb.strides[0],
                            QtGui.QImage.Format_RGB888)
        pix = QtGui.QPixmap.fromImage(qimg)

        if self.list_size:
            pix = pix.scaled(self.list_size[0], self.list_size[1],
                         QtCore.Qt.KeepAspectRatio,
                         QtCore.Qt.SmoothTransformation)
        else:
            pix = pix.scaled(self.target_width, self.target_height,
                         QtCore.Qt.KeepAspectRatio,
                         QtCore.Qt.SmoothTransformation)
        QtCore.QMetaObject.invokeMethod(
            self.ui_logging.label_image_prev, "setPixmap",
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(QtGui.QPixmap, pix)
        )

    def detect_clicked(self):
        row = self.ui_logging.tableWidget.currentRow()
        col = self.ui_logging.tableWidget.currentColumn()


    def split_key(self, combo_cam, combo_key):
        valid_key_tuple = (combo_cam.currentText(), combo_key.currentText())
        self.valid_key = valid_key_tuple
        for key, val in self.built_in_objects.items():
            if self.valid_key[0] in key:
                self.valid_values = val
        self.pyuic = self.valid_values['pyuic'][self.valid_key]
        self.model_loader = self.valid_values['model_loader'][self.valid_key]
    