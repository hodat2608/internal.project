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
_log = _get_logger('auto_logging_process')

class AutoLoggingProcess:
    def __init__(self,ui_logging,cursor,process=None,built_in_objects={}):
        self.ui_logging = ui_logging
        self.cursor = cursor
        self.list_size = []
        self.process = process
        self.built_in_objects = built_in_objects
    
    def broswer_folder(self):
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(
            None,
            "Chọn thư mục lưu trữ",
            "",
            QtWidgets.QFileDialog.ShowDirsOnly |
            QtWidgets.QFileDialog.DontResolveSymlinks
        )
        self.ui_logging.lineEdit_folder_path.setText(folder_path)

    def generate_table(self,total_key):
        path = self.ui_logging.lineEdit_folder_path.text().strip()
        list_obj = glob.glob(os.path.join(path, '*.jpg'))

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
            
            detect_button = QtWidgets.QPushButton("Detect")
            
            from functools import partial
            detect_button.clicked.connect(partial(self.on_detect_clicked, file_path, combo_cam, combo_key))
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
            
        header = self.ui_logging.tableWidget.horizontalHeader()
        header.setCascadingSectionResizes(False) 
        
        for i in range(self.ui_logging.tableWidget.columnCount()):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Interactive)
            
        self.ui_logging.tableWidget.resizeColumnToContents(0)
        self.ui_logging.tableWidget.resizeColumnToContents(1)
        
        col0_width = self.ui_logging.tableWidget.columnWidth(0)
        col1_width = self.ui_logging.tableWidget.columnWidth(1)
        
        if col1_width < 300:
            col1_width = 300
            self.ui_logging.tableWidget.setColumnWidth(1, col1_width)
        
        table_width = self.ui_logging.tableWidget.viewport().width()
        if table_width < 100: table_width = 1000
        
        remaining_space = table_width - col0_width - col1_width
        remaining_cols = self.ui_logging.tableWidget.columnCount() - 2
        
        if remaining_cols > 0:
            width_per_col = max(100, remaining_space // remaining_cols)
            for i in range(2, self.ui_logging.tableWidget.columnCount()):
                self.ui_logging.tableWidget.setColumnWidth(i, width_per_col)

        

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
                
                for item in list_insert:
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
                    
                connection.commit()
                print(f"Lưu thành công {len(list_insert)} dòng vào database auto_logging!")
                
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.information(None, "Thành công", "Đã lưu thiết lập Auto Logging vào database!")
                
            except Exception as e:
                print("Lỗi khi lưu dữ liệu Auto Logging vào Database:", e)
                try:
                    connection.rollback()
                except:
                    pass
        else:
            print("Không có dữ liệu để lưu.")


    def load_data_from_db(self,camera_id,connection):
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
            detect_button = QPushButton("Detect")
            from functools import partial
            detect_button.clicked.connect(partial(self.on_detect_clicked, image_path_val, combo_cam, combo_key))
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
            
        # -- CẤU HÌNH LẠI ĐỘ RỘNG CÁC CỘT GIỐNG HÀM GENERATE --
        header = self.ui_logging.tableWidget.horizontalHeader()
        header.setCascadingSectionResizes(False)
        for i in range(self.ui_logging.tableWidget.columnCount()):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Interactive)
            
        self.ui_logging.tableWidget.resizeColumnToContents(0)
        self.ui_logging.tableWidget.resizeColumnToContents(1)
        
        col0_width = self.ui_logging.tableWidget.columnWidth(0)
        col1_width = self.ui_logging.tableWidget.columnWidth(1)
        if col1_width < 300:
            col1_width = 300
            self.ui_logging.tableWidget.setColumnWidth(1, col1_width)
            
        table_width = self.ui_logging.tableWidget.viewport().width()
        if table_width < 100: table_width = 1000
        
        remaining_space = table_width - col0_width - col1_width
        remaining_cols = self.ui_logging.tableWidget.columnCount() - 2
        
        if remaining_cols > 0:
            width_per_col = max(100, remaining_space // remaining_cols)
            for i in range(2, self.ui_logging.tableWidget.columnCount()):
                self.ui_logging.tableWidget.setColumnWidth(i, width_per_col)
                
        print(f"Đã load thành công {len(result)} dòng dữ liệu Logging!")


    def on_detect_clicked(self, file_path, combo_cam, combo_key, *args):
        self.split_key(combo_cam, combo_key)
        result_image_rgb = cv2.imread(file_path)
        if result_image_rgb is None:
            _log.error("Lỗi đọc ảnh: %s", file_path)
            return
        
        self.target_width = self.ui_logging.label_image_prev.width()
        self.target_height = self.ui_logging.label_image_prev.height()

        if not self.list_size:
            self.list_size.append(self.target_width)
            self.list_size.append(self.target_height)

        if not hasattr(self, 'dict_view_results'):
            self.dict_view_results = {}

        result_image_rgb, flag, list_register,_ = self.process.process_image_func(
                result_image_rgb, self.model_loader, self.pyuic, True, self.valid_key, 12,
                mode_load_jumper=False,
            )
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
    