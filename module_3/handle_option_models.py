
import torch
from module_2 import root
from PyQt5.QtWidgets import (QMessageBox,QFileDialog)
import sys
from PyQt5.QtWidgets import (QFileDialog)
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QStyledItemDelegate, QStyleOptionButton, QStyle
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QStandardItem
from mysql.connector import Error
import cv2, numpy as np
from pathlib import Path
from typing import Final
COLUMN_MAPPING: Final[dict[str, str]] = {
    "Label Name":     "`Label_Name`",
    "Enabled [✓]":        "`Join`",
    "OK [🟢]":             "`OK`",
    "NG [🔴]":             "`NG`",
    "Qty":       "`Quantity`",
    "Min Width":      "`Width_Min`",
    "Max Width":      "`Width_Max`",
    "Min Height":     "`Height_Min`",
    "Max Height":     "`Height_Max`",
    "Register": "`Assign_Value`",
    "Value": "`Value`",
    "Confidence":     "`Confidence`",
}
import time
from _source.v5.v5 import v5s
from module_3.yolo_factory import YoloFactory

from app_logger.app_logger import get_logger as _get_logger
from module_1.root_path import resource_path
import os
import shutil
import sys
import hashlib

_log = _get_logger('module_3.handle_option_models')

# -- CẤU HÌNH THƯ MỤC TRUNG GIAN --
if getattr(sys, 'frozen', False):
    app_data = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or os.path.expanduser('~')
    BASE_DIR = os.path.join(app_data, 'MBC_Vision_Inspector')
else:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

WEIGHTS_DIR = os.path.join(BASE_DIR, 'workspace_weights')
os.makedirs(WEIGHTS_DIR, exist_ok=True)

class CheckboxDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        value = index.data(Qt.CheckStateRole)
        if value is not None:
            checkbox_style_option = QStyleOptionButton()
            checkbox_style_option.state |= QStyle.State_Enabled
            if int(value) == Qt.Checked:
                checkbox_style_option.state |= QStyle.State_On
            else:
                checkbox_style_option.state |= QStyle.State_Off

            checkbox_rect = self.parent().style().subElementRect(QStyle.SE_CheckBoxIndicator, checkbox_style_option, None)
            checkbox_style_option.rect = QRect(
                option.rect.x() + option.rect.width() // 2 - checkbox_rect.width() // 2,
                option.rect.y() + option.rect.height() // 2 - checkbox_rect.height() // 2,
                checkbox_rect.width(),
                checkbox_rect.height()
            )
            self.parent().style().drawControl(QStyle.CE_CheckBox, checkbox_style_option, painter)
        else:
            super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index):
        if event.type() == event.MouseButtonRelease:
            current_value = index.data(Qt.CheckStateRole)
            new_value = Qt.Unchecked if current_value == Qt.Checked else Qt.Checked
            model.setData(index, new_value, Qt.CheckStateRole)
        return True
    
    
class Process_Model:

    def __init__(self,uic):
        self.model = None
        self.file_path = None
        self.uic = uic
        self.list_layer = []
        self.list_layer_save = []
        self.keys_mapping = list(COLUMN_MAPPING.keys())
        self.file_path_detect = None
        self.model_loader = None
        self.path_object = None
        self.parametes_model = None
        self.result_model = None
        self.process_image_func = None
        
        self.is_unlocked = False
        
        # Inject standard properties into the generated UI object
        self.uic.ui_child = None 
        self.uic.i_code = None
        self.uic.db = None
        self.uic.connect_db = None
        self.uic.cursor = None
        self.uic.model_column = list(COLUMN_MAPPING.keys())
        self.uic.model = QStandardItemModel(0, len(self.uic.model_column))
        self.uic.model.setHorizontalHeaderLabels(self.uic.model_column)
        if hasattr(self.uic, 'tableView'):
            self.uic.tableView.setModel(self.uic.model)
            header = self.uic.tableView.horizontalHeader()
            for i in range(len(self.uic.model_column)):
                if i == 0:
                    header.setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeToContents)
                else:
                    header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)
            
        self.uic.is_unlocked = False

        self.set_ui_enabled(False)

    def toggle_lock(self, cursor, connect_db):
        if getattr(self, 'is_unlocked', False):
            self.lock_gui(cursor, connect_db, method=False, boolen=False)
            self.is_unlocked = False
            self.uic.pushButton_edit_params.setText("Edit Parameters")
        else:
            if self.lock_gui(cursor, connect_db, method=True, boolen=True):
                self.is_unlocked = True
                self.uic.pushButton_edit_params.setText("Lock Edit")

    def set_ui_enabled(self, enabled=False):
        widget_types = [
            QtWidgets.QPushButton, 
            QtWidgets.QLineEdit, 
            QtWidgets.QComboBox, 
            QtWidgets.QSpinBox, 
            QtWidgets.QDoubleSpinBox, 
            QtWidgets.QTableView,
            QtWidgets.QCheckBox, 
            QtWidgets.QRadioButton
        ]
        for widget_type in widget_types:
            for widget in self.uic.centralwidget.findChildren(widget_type):
                if widget != self.uic.pushButton_edit_params:
                    widget.setEnabled(enabled)
        self.uic.pushButton_edit_params.setEnabled(True)

    def lock_gui(self, cursor, connect_db, method=False, boolen=False):
        if method:
            dlg = QtWidgets.QDialog()
            dlg.setWindowTitle("User Authentication")
            dlg.setFixedSize(280, 160)
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

            layout.addWidget(QtWidgets.QLabel("Select User:"))
            layout.addWidget(user_combo)
            layout.addWidget(password_input)
            layout.addWidget(button)
            dlg.setLayout(layout)

            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                self.set_ui_enabled(enabled=boolen)
                return True
            else:
                return False
        else:
            self.set_ui_enabled(enabled=boolen)
            return True

    def browse_file(self):
            options = QtWidgets.QFileDialog.Options()
            self.file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                None,
                "Chọn file",
                "",
                "PyTorch Model (*.pt);;Tất cả các file (*)",
                options=options
            )
            if self.file_path:
                self.uic.lineEdit_weight_pytorch.setText(self.file_path)

    def browse_file_detect(self):
        options = QtWidgets.QFileDialog.Options()
        self.file_path_detect, _ = QtWidgets.QFileDialog.getOpenFileName(
            None,
            "Chọn file",
            "",
            "Hình ảnh (*.jpg *.png *.bmp);;Tất cả các file (*)",
            options=options
        )
        if self.file_path_detect:
            size = self.uic.label_5.size()
            width, height = size.width(), size.height()
            self.uic.lineEdit_weight_tensorrt.setText(self.file_path_detect)

            image = cv2.imread(self.file_path_detect)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            image = cv2.resize(image, (width, height))

            qimage = QtGui.QImage(image.data, image.shape[1], image.shape[0], image.strides[0], QtGui.QImage.Format_RGB888)
            pixmap = QtGui.QPixmap.fromImage(qimage)
            self.uic.label_5.setPixmap(pixmap)

    def browse_folder_activity_history(self):
            folder = QFileDialog.getExistingDirectory(
                None,
                "Select Folder",
                "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if folder:
                self.uic.lineEdit_data_change.setText(folder)

    def browse_file_engine_tensorrt(self):
            options = QtWidgets.QFileDialog.Options()
            self.file_path_engine_tensorrt, _ = QtWidgets.QFileDialog.getOpenFileName(
                None,
                "Chọn file",
                "",
                "Engine TensorRT (*.engine);;Tất cả các file (*)",
                options=options
            )
            if self.file_path_engine_tensorrt:
                self.uic.lineEdit_weight_tensorrt.setText(self.file_path_engine_tensorrt)

    def browse_file_classes(self):
        options = QtWidgets.QFileDialog.Options()
        self.file_path_classes, _ = QtWidgets.QFileDialog.getOpenFileName(
            None,
            "Chọn file",
            "",
            "Classes (*.txt);;Tất cả các file (*)",
            options=options
        )
        if self.file_path_classes:
            self.uic.lineEdit_classes_txt.setText(self.file_path_classes)
    

    def browse_folder_ng_img_original(self):
            folder = QFileDialog.getExistingDirectory(
                None,
                "Select Folder",
                "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if folder:
                self.uic.lineEdit_NG_image_original.setText(folder)

    def browse_folder_ng_img_detected(self):
            folder = QFileDialog.getExistingDirectory(
                None,
                "Select Folder",
                "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if folder:
                self.uic.lineEdit_NG_image_detected.setText(folder)

    def browse_folder_ok_img_original(self):
            folder = QFileDialog.getExistingDirectory(
                None,
                "Select Folder",
                "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if folder:
                self.uic.lineEdit_OK_image_original.setText(folder)

    def browse_folder_ok_img_detected(self):
            folder = QFileDialog.getExistingDirectory(
                None,
                "Select Folder",
                "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if folder:
                self.uic.lineEdit_OK_image_detected.setText(folder)

    def browse_folder_image_logging(self):
            folder = QFileDialog.getExistingDirectory(
                None,
                "Select Folder",
                "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if folder:
                self.uic.lineEdit_logging_image.setText(folder)
    

    def detect_img(self):
        if not self.file_path_detect:
            QMessageBox.warning(None, "Cảnh báo4", "Vui lòng chọn file trước.")
            return
        t1 = time.time()
        size = self.uic.label_5.size()
        width_widget, height_widget = size.width(), size.height()
        image = cv2.imread(self.file_path_detect) 
        result_image_rgb,flag = self.engine(image,width_widget,height_widget)
        if flag:
            cv2.putText(result_image_rgb, 'RESULT:OK',(10, 50),cv2.FONT_HERSHEY_COMPLEX,  0.5,(0,255,0),1)
        else:
            cv2.putText(result_image_rgb, 'RESULT:NG',(10, 50),cv2.FONT_HERSHEY_COMPLEX,  0.5,(0,0,255),1)
        t2 = time.time()
        cv2.putText(result_image_rgb, f"Time: {t2-t1:.3f} s", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        qimage = QtGui.QImage(result_image_rgb.data, result_image_rgb.shape[1], result_image_rgb.shape[0], result_image_rgb.strides[0], QtGui.QImage.Format_RGB888)
        pixmap = QtGui.QPixmap.fromImage(qimage)
        self.uic.label_5.setPixmap(pixmap)

    def save_parameter_before_load_weight(self):
        model = self.uic.model
        model_column = self.uic.model_column
        label_col_index = model_column.index(self.keys_mapping[0])
        for row in range(model.rowCount()): 
            label_item = model.item(row, label_col_index)
            if label_item is None:
                continue
            label_text = label_item.text().strip()
            row_data = {}
            for col in range(model.columnCount()): 
                item = model.item(row, col)
                if item is not None:
                    if item.isCheckable():
                        value = item.checkState() == Qt.Checked
                    else:
                        value = item.text()
                    row_data[model_column[col]] = value
            row_data[self.keys_mapping[0]] = label_text
            self.list_layer.append(row_data)
        _log.info("Save parameter before load weight successfully")
        return self.list_layer

    def load_model(self):
        weight_input = self.uic.lineEdit_weight_pytorch.text().strip()
        if not weight_input:
            QMessageBox.warning(None, "Cảnh báo5", "Vui lòng chọn file trước.")
            return

        if not os.path.isabs(weight_input):
            self.file_path = os.path.join(WEIGHTS_DIR, weight_input)
        else:
            if not os.path.exists(weight_input):
                # Fallback: Nếu CSDL cũ lưu path tuyệt đối từ máy khác, ta tự sửa lại thành path chuẩn của máy mới
                basename = os.path.basename(weight_input)
                self.file_path = os.path.join(WEIGHTS_DIR, basename)
            else:
                self.file_path = weight_input
            
        source_model = self.uic.comboBox_source.currentText()
        task_model = self.uic.comboBox_source_task.currentText()

        model_runtime = self.uic.comboBox_model_runtime.currentText()
        device = self.uic.comboBox_device_gpu.currentText()

        factory_result = YoloFactory.load_model(source_model, task_model, model_runtime, self.file_path, device)

        if factory_result.get("success"):
            self.path_object = factory_result.get("path_object")
            self.model_loader = factory_result.get("model_loader")
            self.result_model = factory_result.get("result_model")
            self.model = self.model_loader

            self.use_model()
                
            self.populateTable()
            _log.info(f"Load model {source_model} successfully")
        else:
            if factory_result.get("error_msg"):
                _log.warning(factory_result.get("error_msg"))
            return
        
    def populateTable(self):
        self.uic.model.removeRows(0, self.uic.model.rowCount())
        if isinstance(self.model.names, list) or isinstance(self.model.names, dict):
            for label in self.model.names if isinstance(self.model.names, list) else self.model.names.values():
                row_items = []
                checkbox_delegate = CheckboxDelegate(self.uic.tableView)
                for col_name in [self.keys_mapping[1], self.keys_mapping[2], self.keys_mapping[3]]:
                    col_index = self.uic.model_column.index(col_name)
                    self.uic.tableView.setItemDelegateForColumn(col_index, checkbox_delegate)

                for col in range(len(self.uic.model_column)): 
                    item = QStandardItem()
                    if col == self.uic.model_column.index(self.keys_mapping[0]): 
                        item.setText(str(label))
                        item.setTextAlignment(Qt.AlignCenter)
                    elif col in [self.uic.model_column.index(self.keys_mapping[1]),\
                                self.uic.model_column.index(self.keys_mapping[2]),\
                                self.uic.model_column.index(self.keys_mapping[3])]:
                        item.setCheckable(True)
                        item.setCheckState(Qt.Unchecked)
                    else:  
                        item.setText("0")
                        item.setTextAlignment(Qt.AlignCenter)
                    row_items.append(item)
                self.uic.model.appendRow(row_items)
        _log.info("Populate table successfully")
        
        
    def save_values_injection_safe(self, cursor, connector):
        try:
            row_count = self.uic.model.rowCount()
            col_count = self.uic.model.columnCount()
            list_insert = []
            for row in range(row_count):
                row_data = {}
                is_empty_row = True
                for col in range(col_count):
                    header = self.uic.model_column[col] 
                    item = self.uic.model.item(row, col)
                    if item is not None:
                        if item.isCheckable():
                            value = item.checkState() == Qt.Checked
                        else:
                            value = item.text().strip()
                            if value:
                                is_empty_row = False
                        row_data[header] = value
                    else:
                        row_data[header] = None
                if not is_empty_row:
                    list_insert.append(row_data)
            cursor.execute("""
                SELECT id FROM NUMS_MODEL
                WHERE camera_id = %s AND nums_model = %s
            """, (self.uic.comboBox_camera_id.currentText(), self.uic.comboBox_model_id.currentText()))

            result = cursor.fetchone()
            if not result:
                raise ValueError("Không tìm thấy model_id tương ứng.")
            
            _log.info("Find model_id successfully")

            model_id = result[0]
            weight_path_input = self.uic.lineEdit_weight_pytorch.text().strip()
            if weight_path_input and not os.path.isabs(weight_path_input):
                full_weight_path = os.path.join(WEIGHTS_DIR, weight_path_input)
            else:
                full_weight_path = weight_path_input
            weight_filename_for_db = ""
            if full_weight_path and full_weight_path.endswith('.pt'):
                if os.path.exists(full_weight_path):
                    try:
                        hasher = hashlib.md5()
                        with open(full_weight_path, 'rb') as f:
                            for chunk in iter(lambda: f.read(8192), b""):
                                hasher.update(chunk)
                        file_hash = hasher.hexdigest()[:8]
                        
                        original_name = os.path.basename(full_weight_path)
                        if original_name.startswith(f"{file_hash}_"):
                            weight_filename_for_db = original_name
                        else:
                            weight_filename_for_db = f"{file_hash}_{original_name}"
                            
                        target_path = os.path.join(WEIGHTS_DIR, weight_filename_for_db)
                        
                        if os.path.abspath(full_weight_path) != os.path.abspath(target_path):
                            shutil.copy2(full_weight_path, target_path)
                            _log.info("Smart-copied weight to %s", target_path)
                    except Exception as e:
                        _log.error("Failed to smart-copy weight: %s", e)
                            
            conf = self.uic.spinBox_confidenc_score.value()
            size = self.uic.comboBox_imgsz.currentText()
            activity_history = self.uic.lineEdit_data_change.text().strip()
            device_load_model = self.uic.comboBox_device_gpu.currentText()
            source_model = self.uic.comboBox_source.currentText()
            task_model = self.uic.comboBox_source_task.currentText()
            model_runtime = self.uic.comboBox_model_runtime.currentText()
            weight_tensorrt_path = self.uic.lineEdit_weight_tensorrt.text().strip()
            classes_file_path = self.uic.lineEdit_classes_txt.text().strip()
            iou_value = self.uic.spinBox_iou.value()
            max_detections = self.uic.spinBox_max_detection.value()
            folder_ng_original_path = self.uic.lineEdit_NG_image_original.text().strip()
            save_ng_original = self.uic.checkBox_NG_image_original.isChecked()
            folder_ng_detected_path = self.uic.lineEdit_NG_image_detected.text().strip()
            save_ng_detected = self.uic.checkBox_NG_image_detected.isChecked()
            folder_ok_original_path = self.uic.lineEdit_OK_image_original.text().strip()
            save_ok_original = self.uic.checkBox_OK_image_original.isChecked()
            folder_ok_detected_path = self.uic.lineEdit_OK_image_detected.text().strip()
            save_ok_detected = self.uic.checkBox_OK_image_detected.isChecked()
            folder_image_logging = self.uic.lineEdit_logging_image.text().strip()
            
            cursor.execute(
                    f"DELETE FROM WEIGHTS WHERE model_id = %s",
                    (model_id,),
                )
   
            if weight_filename_for_db and weight_filename_for_db.endswith('.pt'):
                cursor.execute("""
                    INSERT IGNORE INTO WEIGHTS
                    (Weight_Path, Activity_History_Path, Conf_Value, Size_Value, Device, Source, Task, Model_Runtime, Weight_TensorRT_Path, Classes_File_Path, IOU_Value, Max_Detections, Folder_NG_Original_Path, Save_NG_Original, Folder_NG_Detected_Path, Save_NG_Detected, Folder_OK_Original_Path, Save_OK_Original, Folder_OK_Detected_Path, Save_OK_Detected, Folder_Image_Logging, model_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (weight_filename_for_db, activity_history, conf, size, device_load_model, source_model, task_model,model_runtime, weight_tensorrt_path, classes_file_path, iou_value, max_detections, folder_ng_original_path, save_ng_original, folder_ng_detected_path, save_ng_detected, folder_ok_original_path, save_ok_original, folder_ok_detected_path, save_ok_detected, folder_image_logging, model_id))

            cursor.execute(
                    f"DELETE FROM PARAMETERSET WHERE model_id = %s",
                    (model_id,),
                )

            if list_insert:
                for row_idx, row_dict in enumerate(list_insert):
                    if "Register" in row_dict:
                        val = row_dict["Register"]
                        if val is not None and str(val).strip() != "":
                            row_dict["Register"] = str(val).upper()
                    if "Value" in row_dict:
                        val = row_dict["Value"]
                        if val is not None and str(val).strip() != "":
                            if not str(val).lstrip('-').isdigit():
                                QMessageBox.warning(None, "Loi Nhap Lieu", f"Dong {row_idx + 1}: Cot 'Value' phai la so nguyen.")
                                return
                    if "Confidence" in row_dict:
                        val = row_dict["Confidence"]
                        if val is not None and str(val).strip() != "":
                            if not str(val).lstrip('-').isdigit() or not (0 <= int(val) <= 100):
                                QMessageBox.warning(None, "Loi Nhap Lieu", f"Dong {row_idx + 1}: Cot 'Confidence' phai la so nguyen tu 0 den 100.")
                                return
                    for size_col in ["Min Width", "Max Width", "Min Height", "Max Height"]:
                        if size_col in row_dict:
                            val = row_dict[size_col]
                            if val is not None and str(val).strip() != "":
                                if not str(val).lstrip('-').isdigit():
                                    QMessageBox.warning(None, "Loi Nhap Lieu", f"Dong {row_idx + 1}: Cot '{size_col}' phai la so nguyen (khong chua dau thap phan hoac chu).")
                                    return
                param_fields = list(COLUMN_MAPPING.values())
                sql = f"""
                    INSERT IGNORE INTO PARAMETERSET 
                    ({', '.join(param_fields)}, model_id)
                    VALUES ({', '.join(['%s'] * (len(param_fields) + 1))})
                """

                for row_dict in list_insert:
                    values = [row_dict.get(ui_col, None) for ui_col in COLUMN_MAPPING.keys()]
                    values.append(model_id)
                    cursor.execute(sql, values)

                connector.connection.commit()
            _log.info("Save parameter successfully")
            QMessageBox.information(None, "Thành công", "Lưu thông số thành công")

        except Error as e:
            connector.connection.rollback()
            QMessageBox.critical(None, "Lỗi", f"MySQL Error: {e}")
            _log.error("Save parameter failed: %s", e)

        except Exception as e:
            connector.connection.rollback()
            QMessageBox.critical(None, "Lỗi không xác định", str(e))
            _log.error("Save parameter failed: %s", e)

    def load_data_injection_safe(self):
        model = self.uic.model
        model_column = self.uic.model_column
        label_col_index = model_column.index(self.keys_mapping[0])

        for row in range(model.rowCount()):
            label_item = model.item(row, label_col_index)
            if label_item is None:
                continue
            label_text = label_item.text().strip()
            for param_dict in self.list_layer:
                if param_dict[self.keys_mapping[0]] == label_text:
                    for col, col_name in enumerate(model_column):
                        value = param_dict.get(col_name)
                        item = QStandardItem()
                        if col == label_col_index:
                            item.setText(label_text)
                            item.setTextAlignment(Qt.AlignCenter)
                        elif col_name in [self.keys_mapping[1], self.keys_mapping[2], self.keys_mapping[3]]:
                            item.setCheckable(True)
                            item.setCheckState(Qt.Checked if value else Qt.Unchecked)
                        else:
                            item.setText(str(value))
                            item.setTextAlignment(Qt.AlignCenter)
                        model.setItem(row, col, item)

        _log.info("Load parameter successfully")
            
    def assign_values(self,model,camera,code):  
        self.uic.comboBox_line_code_id.clear()
        self.uic.comboBox_camera_id.clear()
        self.uic.comboBox_model_id.clear()
        self.uic.comboBox_line_code_id.addItem(str(code))
        self.uic.comboBox_camera_id.addItem(str(camera))
        self.uic.comboBox_model_id.addItem(str(model))

    def collect_device(self):
        devices = torch.cuda.device_count()
        for i in range(devices):
            self.uic.comboBox_device_gpu.addItem(f'cuda:{i}-{torch.cuda.get_device_name(i)}')

    def use_model(self):
        """Tự động bind hàm xử lý ảnh từ bất cứ phiên bản YOLO nào (V5, V8...) được load."""
        if self.result_model is not None and hasattr(self.result_model, 'run_model'):
            self.process_image_func = self.result_model.run_model
            print('activated by run_model')
        else:
            self.process_image_func = None
            _log.warning("result_model is missing or does not have a run_model method")
        
    def load_parameter_injection_safe(self, camera_id, model, cursor, connect_db, tabWidget, ui_instances):
        try:
            weight_path = None
            cursor.execute("""
                SELECT Weight_Path, Activity_History_Path ,Conf_Value, Size_Value, Device,Source,Task,
                Model_Runtime, Weight_TensorRT_Path, Classes_File_Path, IOU_Value, Max_Detections, Folder_NG_Original_Path, Save_NG_Original, Folder_NG_Detected_Path, Save_NG_Detected, Folder_OK_Original_Path, Save_OK_Original, Folder_OK_Detected_Path, Save_OK_Detected, Folder_Image_Logging
                FROM WEIGHTS
                WHERE model_id = (SELECT id FROM NUMS_MODEL WHERE camera_id = %s AND nums_model = %s)
            """, (camera_id, model))
            result = cursor.fetchall()

            if result:
                weight_db_val, activity_history, conf_value, size_value, device, source, task, model_runtime, weight_tensorrt_path, classes_file_path, iou_value, max_detections, folder_ng_original_path, save_ng_original, folder_ng_detected_path, save_ng_detected, folder_ok_original_path, save_ok_original, folder_ok_detected_path, save_ok_detected, folder_image_logging = result[0]
                
                weight_path = ""
                weight_filename = ""
                if weight_db_val and weight_db_val.endswith('.pt'):
                    weight_filename = os.path.basename(weight_db_val)
                    weight_path = os.path.join(WEIGHTS_DIR, weight_filename)
                    # Tính năng migrate: Tự động copy file từ path cũ sang folder mới nếu chưa có
                    if not os.path.exists(weight_path) and os.path.exists(weight_db_val):
                        try:
                            shutil.copy2(weight_db_val, weight_path)
                            _log.info("Migrated weight to %s", weight_path)
                        except Exception:
                            pass
                self.uic.lineEdit_weight_pytorch.setText(weight_filename)
                self.uic.spinBox_confidenc_score.setValue(conf_value)
                self.uic.comboBox_imgsz.setCurrentText(str(size_value))
                self.uic.lineEdit_data_change.setText(activity_history)
                self.uic.comboBox_device_gpu.setCurrentText(device)
                self.uic.comboBox_source.setCurrentText(source)
                self.uic.comboBox_source_task.setCurrentText(task)
                self.uic.comboBox_model_runtime.setCurrentText(model_runtime)
                self.uic.lineEdit_weight_tensorrt.setText(weight_tensorrt_path)
                self.uic.lineEdit_classes_txt.setText(classes_file_path)
                self.uic.spinBox_iou.setValue(iou_value)
                self.uic.spinBox_max_detection.setValue(max_detections)
                self.uic.lineEdit_NG_image_original.setText(folder_ng_original_path)
                self.uic.checkBox_NG_image_original.setChecked(save_ng_original)
                self.uic.lineEdit_NG_image_detected.setText(folder_ng_detected_path)
                self.uic.checkBox_NG_image_detected.setChecked(save_ng_detected)
                self.uic.lineEdit_OK_image_original.setText(folder_ok_original_path)
                self.uic.checkBox_OK_image_original.setChecked(save_ok_original)
                self.uic.lineEdit_OK_image_detected.setText(folder_ok_detected_path)
                self.uic.checkBox_OK_image_detected.setChecked(save_ok_detected)
                self.uic.lineEdit_logging_image.setText(folder_image_logging)

                # Gọi Factory xử lý toàn bộ logic khởi tạo Model
                factory_result = YoloFactory.load_model(source, task, model_runtime, weight_path, device)
                if factory_result.get("success"):
                    self.path_object = factory_result.get("path_object")
                    self.model_loader = factory_result.get("model_loader")
                    self.result_model = factory_result.get("result_model")
                    # Liên kết logic xử lý image inference vào self.process_image_func
                    self.use_model()
                else:
                    if factory_result.get("error_msg"):
                        _log.warning(factory_result.get("error_msg"))

        except Error as e:
            connect_db.connection.rollback()
            QMessageBox.critical(None, "Lỗi", f"MySQL Error: {e}")
            return

        try:
            reverse_column_map = {v: k for k, v in COLUMN_MAPPING.items()}

            db_columns = list(COLUMN_MAPPING.values())
            cursor.execute(f"""
                SELECT {', '.join(db_columns)}
                FROM PARAMETERSET
                WHERE model_id = (SELECT id FROM NUMS_MODEL WHERE camera_id = %s AND nums_model = %s)
            """, (camera_id, model))
            result = cursor.fetchall()
            if result:
                self.uic.model.removeRows(0, self.uic.model.rowCount())
                
                # Check an toàn tránh lỗi 'NoneType' object has no attribute 'names'
                if self.model_loader is not None and hasattr(self.model_loader, 'names'):
                    for label_name in (self.model_loader.names if isinstance(self.model_loader.names, list) else self.model_loader.names.values()):
                        for row_data in result:
                            if str(row_data[db_columns.index(list(COLUMN_MAPPING.values())[0])]) == str(label_name):
                                row_items = []
                                checkbox_delegate = CheckboxDelegate(self.uic.tableView)
                                for col_name in [self.keys_mapping[1], self.keys_mapping[2], self.keys_mapping[3]]:
                                    col_index = self.uic.model_column.index(col_name)
                                    self.uic.tableView.setItemDelegateForColumn(col_index, checkbox_delegate)

                                for ui_col in self.uic.model_column:
                                    db_col = COLUMN_MAPPING[ui_col]
                                    db_value = row_data[db_columns.index(db_col)]

                                    item = QStandardItem()
                                    if ui_col == self.keys_mapping[0]:
                                        item.setText(str(label_name))
                                        item.setTextAlignment(Qt.AlignCenter)
                                    elif ui_col in [self.keys_mapping[1], self.keys_mapping[2], self.keys_mapping[3]]:
                                        item.setCheckable(True)
                                        item.setCheckState(Qt.Checked if db_value else Qt.Unchecked)
                                    else:
                                        item.setText(str(db_value))
                                        item.setTextAlignment(Qt.AlignCenter)
                                    row_items.append(item)
                                self.uic.model.appendRow(row_items)   
                else:
                    _log.warning("Not found label model data in database")  
            self.parametes_model = self.save_parameter_before_load_weight()
        except Error as e:
            connect_db.connection.rollback()
            QMessageBox.critical(None, "Lỗi", f"MySQL Error: {e}")

        except Exception as e:
            connect_db.connection.rollback()
            QMessageBox.critical(None, "Lỗi không xác định", str(e))
    # CREATE TABLE IF NOT EXISTS mode_display (
    #     id              INT AUTO_INCREMENT PRIMARY KEY,
    #     display_mode    VARCHAR(255) NOT NULL,
    #     layout_mode     VARCHAR(255) NOT NULL,
    #     FOREIGN KEY (item_code_id) REFERENCES ITEMS_CODE(id) ON DELETE CASCADE
    # """,
    def save_display_mode(self,cursor,connection,item_code_id,display_mode,layout_mode,show_layout):
        cursor.execute("""
            SELECT * FROM mode_display
            WHERE item_code_id = %s
        """,(item_code_id,))
        if result_cursor := cursor.fetchall():
            cursor.execute("""
                UPDATE mode_display
                SET display_mode = %s, layout_mode = %s,show_layout = %s
                WHERE item_code_id = %s
            """,(display_mode,layout_mode,show_layout,item_code_id))
            connection.connection.commit()
        else:
            cursor.execute("""
                INSERT INTO mode_display (item_code_id, display_mode, layout_mode,show_layout)
                VALUES (%s, %s, %s,%s)
            """,(item_code_id,display_mode,layout_mode,show_layout))
            connection.connection.commit()


    def load_display_mode(self,cursor,connection,item_code_id,ui):
        cursor.execute("""
            SELECT display_mode, layout_mode,show_layout FROM mode_display
            WHERE item_code_id = %s
        """,(item_code_id,))
        if result_cursor := cursor.fetchone():
            display_mode, layout_mode,show_layout = result_cursor
            ui.comboBox_display_mode.setCurrentText(display_mode)
            ui.comboBox_layout_mode_by.setCurrentText(layout_mode)
            ui.comboBox_show_ui.setCurrentText(show_layout)
            

            
class Process_Camera_Device:

    def __init__(self,connection,cursor,uic=None):
        self.uic = uic
        self.connection = connection
        self.cursor = cursor

    def query_camera_type(self, item_code_id, camera):
        self.cursor.execute("""
            SELECT device_type, device_serial, connection_type, ip_address
            FROM NUMS_CAMERA 
            WHERE item_code_id = %s AND nums_camera = %s
        """, (item_code_id, camera))

        row = self.cursor.fetchone()
        if row is None:
            raise ValueError(f"[query_camera_type] Không tìm thấy camera '{camera}' với item_code_id '{item_code_id}'")

        device_type, serial, conn_type, ip_address = row
        return device_type, serial, conn_type, ip_address
    
    def query_mode_id_to_user_index(self,item_code_id,device_ui):
        try:
            camera_name = self.uic.comboBox_camera.currentText()
            mode_name = self.uic.comboBox_mode_auto.currentText()
            index_user_selector = device_ui.comboBox_user_selector.currentIndex()
            user_set_selector = device_ui.comboBox_user_selector.currentText()
            self.cursor.execute("""
                        SELECT id FROM NUMS_CAMERA 
                        WHERE item_code_id = %s AND nums_camera = %s
                    """, (item_code_id, camera_name))
                
            result_camera_id = self.cursor.fetchone() 
            if (camera_id := result_camera_id[0] if result_camera_id else None):
                self.cursor.execute("""
                    SELECT id FROM MODE_AUTO 
                    WHERE mode_name = %s AND camera_id = %s 
                """, (mode_name,camera_id))
                if mode_id := self.cursor.fetchone()[0]:
                    self.cursor.execute("""
                    SELECT * FROM USER_SET_CAMERA 
                    WHERE mode_id = %s
                """, (mode_id,))
                result_record = self.cursor.fetchone() 
                if not result_record:
                    self.cursor.execute("""
                        INSERT INTO USER_SET_CAMERA (index_user_selector, user_set_selector,mode_id)
                        VALUES (%s, %s, %s)
                    """, (index_user_selector,user_set_selector,mode_id))
                    
                else:
                    self.cursor.execute("""
                        UPDATE USER_SET_CAMERA 
                        SET index_user_selector = %s, user_set_selector = %s
                        WHERE mode_id = %s
                    """, (index_user_selector,user_set_selector,mode_id))

            self.connection.connection.commit()
            QMessageBox.information(None, "Information", f"Lưu thay đổi thành công")
        except Error as error:
            QMessageBox.critical(None, "Error", f"Lỗi Insert: {str(error)}")


        
    