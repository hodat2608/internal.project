"""
module_1/add_itemcode_dialog.py
────────────────────────────────
Dialog "Thêm mã hàng mới" với 2 chế độ:
  • Custom  — chỉ insert tên mới vào ITEMS_CODE, sau đó user tự cấu hình
              bằng ItemCodeConfigEditor.
  • Copy    — deep-copy toàn bộ cấu trúc DB từ một mã hàng đã có:
              ITEMS_CODE → NUMS_CAMERA → NUMS_MODEL
                                       → WEIGHTS
                                       → PARAMETERSET
                         → MODE_AUTO  → MODE_AUTO_SIGNAL
                                       → SHOTXMODEL
                                       → USER_SET_CAMERA
                         → DEFAULT_MODE_AUTO
              Tất cả id mới, FK remapped đúng.
"""
from __future__ import annotations

import mysql.connector
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QRadioButton, QButtonGroup,
    QComboBox, QPushButton, QFrame, QGroupBox,
    QMessageBox, QSizePolicy,
)
from app_logger.app_logger import get_logger as _get_logger

_log = _get_logger('module_1.add_itemcode_dialog')


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFrameShadow(QFrame.Sunken)
    return f


# ─────────────────────────────────────────────────────────────────────────────
#  Deep-copy engine
# ─────────────────────────────────────────────────────────────────────────────

class _DeepCopier:
    """
    Sao chép toàn bộ dữ liệu của một ITEMS_CODE (src) sang ITEMS_CODE mới
    (dst_name) trong cùng database, với id hoàn toàn mới.
    """

    def __init__(self, cursor, connection, db_name: str = ""):
        self._cur  = cursor
        self._conn = connection
        self._db   = db_name

    def _t(self, table: str) -> str:
        return f"`{self._db}`.{table}" if self._db else table

    # ── public entry ────────────────────────────────────────────────────────

    def run(self, src_item_id: int, dst_name: str, dst_register: str | None) -> int:
        """
        Trả về id của ITEMS_CODE mới vừa tạo.
        Raise Exception nếu lỗi (caller phải rollback).
        """
        new_item_id = self._copy_item_code(dst_name, dst_register)

        # cameras
        self._cur.execute(
            f"SELECT id, nums_camera, device_type, device_serial, connection_type, ip_address "
            f"FROM {self._t('NUMS_CAMERA')} WHERE item_code_id = %s ORDER BY nums_camera",
            (src_item_id,)
        )
        cameras = self._cur.fetchall()

        for cam_row in cameras:
            old_cam_id = cam_row[0]
            new_cam_id = self._copy_camera(cam_row, new_item_id)
            self._copy_models(old_cam_id, new_cam_id)
            self._copy_modes(old_cam_id, new_cam_id)
            self._copy_default_mode(old_cam_id, new_cam_id)

        self._conn.commit()
        _log.info("Deep-copy done: src item_id=%s → dst name='%s' new_id=%s", src_item_id, dst_name, new_item_id)
        return new_item_id

    # ── private steps ────────────────────────────────────────────────────────

    def _copy_item_code(self, name: str, register: str | None) -> int:
        self._cur.execute(
            f"INSERT INTO {self._t('ITEMS_CODE')} (name_line_code, assign_register) VALUES (%s, %s)",
            (name, register)
        )
        return self._cur.lastrowid

    def _copy_camera(self, cam_row: tuple, new_item_id: int) -> int:
        _, nums_camera, device_type, device_serial, connection_type, ip_address = cam_row
        self._cur.execute(
            f"""INSERT INTO {self._t('NUMS_CAMERA')}
               (nums_camera, device_type, device_serial, connection_type, ip_address, item_code_id)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (nums_camera, device_type, device_serial, connection_type, ip_address, new_item_id)
        )
        return self._cur.lastrowid

    def _copy_models(self, old_cam_id: int, new_cam_id: int):
        self._cur.execute(
            f"SELECT id, nums_model FROM {self._t('NUMS_MODEL')} WHERE camera_id = %s ORDER BY nums_model",
            (old_cam_id,)
        )
        models = self._cur.fetchall()
        for old_model_id, nums_model in models:
            self._cur.execute(
                f"INSERT INTO {self._t('NUMS_MODEL')} (nums_model, camera_id) VALUES (%s, %s)",
                (nums_model, new_cam_id)
            )
            new_model_id = self._cur.lastrowid
            self._copy_weights(old_model_id, new_model_id)
            self._copy_parameterset(old_model_id, new_model_id)

    def _copy_weights(self, old_model_id: int, new_model_id: int):
        try:
            self._cur.execute(f"SHOW COLUMNS FROM {self._t('WEIGHTS')} LIKE 'Image_format'")
            if not self._cur.fetchone():
                self._cur.execute(f"ALTER TABLE {self._t('WEIGHTS')} ADD COLUMN Image_format VARCHAR(255) DEFAULT 'PNG' AFTER Max_Detections")
        except Exception:
            pass

        self._cur.execute(
            f"""SELECT Weight_Path, Activity_History_Path, Conf_Value, Size_Value, Device, Source, Task,
                      Model_Runtime, Weight_TensorRT_Path, Classes_File_Path, IOU_Value, Max_Detections,
                      Image_format, Folder_NG_Original_Path, Save_NG_Original, Folder_NG_Detected_Path,
                      Save_NG_Detected, Folder_OK_Original_Path, Save_OK_Original, Folder_OK_Detected_Path,
                      Save_OK_Detected, Folder_Image_Logging
               FROM {self._t('WEIGHTS')} WHERE model_id = %s""",
            (old_model_id,)
        )
        for row in self._cur.fetchall():
            self._cur.execute(
                f"""INSERT INTO {self._t('WEIGHTS')}
                   (Weight_Path, Activity_History_Path, Conf_Value, Size_Value, Device, Source, Task,
                    Model_Runtime, Weight_TensorRT_Path, Classes_File_Path, IOU_Value, Max_Detections,
                    Image_format, Folder_NG_Original_Path, Save_NG_Original, Folder_NG_Detected_Path,
                    Save_NG_Detected, Folder_OK_Original_Path, Save_OK_Original, Folder_OK_Detected_Path,
                    Save_OK_Detected, Folder_Image_Logging, model_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (*row, new_model_id)
            )

    def _copy_parameterset(self, old_model_id: int, new_model_id: int):
        self._cur.execute(
            f"SELECT Label_Name, `Join`, OK, NG, Quantity, "
            f"Width_Min, Width_Max, Height_Min, Height_Max, Assign_Value, Confidence "
            f"FROM {self._t('PARAMETERSET')} WHERE model_id = %s",
            (old_model_id,)
        )
        for row in self._cur.fetchall():
            self._cur.execute(
                f"""INSERT INTO {self._t('PARAMETERSET')}
                   (Label_Name, `Join`, OK, NG, Quantity,
                    Width_Min, Width_Max, Height_Min, Height_Max, Assign_Value, Confidence, model_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (*row, new_model_id)
            )

    def _copy_modes(self, old_cam_id: int, new_cam_id: int):
        self._cur.execute(
            f"SELECT id, mode_name, assign_register FROM {self._t('MODE_AUTO')} WHERE camera_id = %s",
            (old_cam_id,)
        )
        modes = self._cur.fetchall()
        for old_mode_id, mode_name, assign_register in modes:
            self._cur.execute(
                f"INSERT INTO {self._t('MODE_AUTO')} (mode_name, assign_register, camera_id) VALUES (%s, %s, %s)",
                (mode_name, assign_register, new_cam_id)
            )
            new_mode_id = self._cur.lastrowid
            self._copy_mode_signals(old_mode_id, new_mode_id)
            self._copy_shotxmodel(old_mode_id, new_mode_id)
            self._copy_user_set_camera(old_mode_id, new_mode_id)

    def _copy_mode_signals(self, old_mode_id: int, new_mode_id: int):
        self._cur.execute(
            f"SELECT signal_name, address, read_register, read_value_on, read_value_off, "
            f"write_register, write_value_on, write_value_off "
            f"FROM {self._t('MODE_AUTO_SIGNAL')} WHERE mode_id = %s",
            (old_mode_id,)
        )
        for row in self._cur.fetchall():
            self._cur.execute(
                f"""INSERT INTO {self._t('MODE_AUTO_SIGNAL')}
                   (signal_name, address, read_register, read_value_on, read_value_off,
                    write_register, write_value_on, write_value_off, mode_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (*row, new_mode_id)
            )

    def _copy_shotxmodel(self, old_mode_id: int, new_mode_id: int):
        self._cur.execute(
            f"SELECT shot, no_of_model FROM {self._t('SHOTXMODEL')} WHERE mode_id = %s",
            (old_mode_id,)
        )
        for row in self._cur.fetchall():
            self._cur.execute(
                f"INSERT INTO {self._t('SHOTXMODEL')} (shot, no_of_model, mode_id) VALUES (%s, %s, %s)",
                (*row, new_mode_id)
            )

    def _copy_user_set_camera(self, old_mode_id: int, new_mode_id: int):
        self._cur.execute(
            f"SELECT index_user_selector, user_set_selector FROM {self._t('USER_SET_CAMERA')} WHERE mode_id = %s",
            (old_mode_id,)
        )
        for row in self._cur.fetchall():
            self._cur.execute(
                f"INSERT INTO {self._t('USER_SET_CAMERA')} (index_user_selector, user_set_selector, mode_id) VALUES (%s, %s, %s)",
                (*row, new_mode_id)
            )

    def _copy_default_mode(self, old_cam_id: int, new_cam_id: int):
        self._cur.execute(
            f"SELECT mode_name FROM {self._t('DEFAULT_MODE_AUTO')} WHERE camera_id = %s",
            (old_cam_id,)
        )
        for (mode_name,) in self._cur.fetchall():
            self._cur.execute(
                f"INSERT IGNORE INTO {self._t('DEFAULT_MODE_AUTO')} (mode_name, camera_id) VALUES (%s, %s)",
                (mode_name, new_cam_id)
            )


# ─────────────────────────────────────────────────────────────────────────────
#  Dialog UI
# ─────────────────────────────────────────────────────────────────────────────

class AddItemCodeDialog(QDialog):
    """
    Dialog "Thêm mã hàng mới" với 2 option:
      • Custom — chỉ tạo entry mới, cấu hình sau qua config_editor
      • Copy   — deep-copy toàn bộ DB từ mã hàng đã chọn

    Sau khi Apply thành công, thuộc tính:
      self.result_mode   : str  ('custom' | 'copy')
      self.result_name   : str  (tên mã hàng mới)
      self.result_item_id: int  (id mới trong ITEMS_CODE)
    """

    # Signal phát ra khi thêm thành công: (item_code_name, item_code_id, mode)
    item_added = QtCore.pyqtSignal(str, int, str)

    def __init__(self, connection, db_name: str, parent=None):
        super().__init__(parent)
        self._conn   = connection
        self._db     = db_name

        self.result_mode    = None
        self.result_name    = None
        self.result_item_id = None

        self.setWindowTitle(f"➕  Thêm mã hàng mới  —  {db_name.upper()}")
        self.setMinimumWidth(480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._build_ui()
        self._load_existing_items()

    # ─── UI ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        # ── Tên mã hàng mới ─────────────────────────────────────────────────
        name_group = QGroupBox("Thông tin mã hàng mới")
        name_grid  = QGridLayout(name_group)
        name_grid.setColumnStretch(1, 1)

        self._name_edit     = QLineEdit()
        self._name_edit.setPlaceholderText("Nhập tên mã hàng mới (bắt buộc)")
        self._register_edit = QLineEdit()
        self._register_edit.setPlaceholderText("VD: DM100  (tuỳ chọn)")

        name_grid.addWidget(QLabel("Tên mã hàng:"),      0, 0)
        name_grid.addWidget(self._name_edit,              0, 1)
        name_grid.addWidget(QLabel("Assign register:"),  1, 0)
        name_grid.addWidget(self._register_edit,          1, 1)
        root.addWidget(name_group)

        # ── Chế độ ──────────────────────────────────────────────────────────
        mode_group = QGroupBox("Chế độ tạo mã hàng")
        mode_vlay  = QVBoxLayout(mode_group)

        self._radio_custom = QRadioButton("🛠  Custom  —  Tự cấu hình sau (sẽ mở trình chỉnh sửa)")
        self._radio_copy   = QRadioButton("📋  Copy   —  Sao chép cấu hình từ mã hàng đã có")
        self._radio_custom.setChecked(True)

        btn_group = QButtonGroup(self)
        btn_group.addButton(self._radio_custom)
        btn_group.addButton(self._radio_copy)

        mode_vlay.addWidget(self._radio_custom)
        mode_vlay.addWidget(self._radio_copy)

        # Copy source selection (ẩn khi chọn Custom)
        self._copy_frame = QFrame()
        copy_lay = QHBoxLayout(self._copy_frame)
        copy_lay.setContentsMargins(20, 4, 0, 4)
        copy_lay.addWidget(QLabel("Sao chép từ:"))
        self._source_combo = QComboBox()
        self._source_combo.setMinimumWidth(220)
        copy_lay.addWidget(self._source_combo)
        copy_lay.addStretch()

        self._copy_frame.setVisible(False)
        mode_vlay.addWidget(self._copy_frame)
        root.addWidget(mode_group)

        # ── Note ────────────────────────────────────────────────────────────
        self._note_label = QLabel(
            "ℹ  Custom: mã hàng được tạo trống, bạn sẽ tự cấu hình số camera / model sau."
        )
        self._note_label.setStyleSheet("color: gray; font-size: 11px;")
        self._note_label.setWordWrap(True)
        root.addWidget(self._note_label)

        root.addWidget(_sep())

        # ── Buttons ──────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Hủy")
        btn_cancel.setFixedWidth(90)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        self._btn_apply = QPushButton("✔  Apply")
        self._btn_apply.setFixedWidth(120)
        self._btn_apply.setDefault(True)
        self._btn_apply.setStyleSheet(
            "background-color: #2980b9; color: white; font-weight: bold;"
            "border-radius: 4px; padding: 6px;"
        )
        self._btn_apply.clicked.connect(self._on_apply)
        btn_row.addWidget(self._btn_apply)

        root.addLayout(btn_row)

        # ── Signals ──────────────────────────────────────────────────────────
        self._radio_custom.toggled.connect(self._on_mode_toggled)
        self._radio_copy.toggled.connect(self._on_mode_toggled)

    def _on_mode_toggled(self):
        is_copy = self._radio_copy.isChecked()
        self._copy_frame.setVisible(is_copy)
        if is_copy:
            self._note_label.setText(
                "ℹ  Copy: toàn bộ cấu hình (camera, model, weight, parameter, PLC signal…) "
                "sẽ được sao chép với ID mới. Tên mã hàng mới phải khác mã hàng nguồn."
            )
        else:
            self._note_label.setText(
                "ℹ  Custom: mã hàng được tạo trống, bạn sẽ tự cấu hình số camera / model sau."
            )
        self.adjustSize()

    # ─── Load existing items for Copy combo ─────────────────────────────────

    def _load_existing_items(self):
        try:
            cur = self._conn.cursor()
            cur.execute(f"SELECT id, name_line_code FROM `{self._db}`.ITEMS_CODE ORDER BY name_line_code")
            rows = cur.fetchall()
            cur.close()
            self._source_combo.clear()
            if rows:
                for row_id, name in rows:
                    self._source_combo.addItem(name, userData=row_id)
            else:
                self._source_combo.addItem("(Chưa có mã hàng nào)")
                self._radio_copy.setEnabled(False)
                self._radio_copy.setToolTip("Chưa có mã hàng nào để copy")
        except Exception as e:
            _log.error("Error loading existing items: %s", e)

    # ─── Apply ────────────────────────────────────────────────────────────────

    def _on_apply(self):
        new_name = self._name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập tên mã hàng mới.")
            return

        register = self._register_edit.text().strip() or None
        mode     = 'copy' if self._radio_copy.isChecked() else 'custom'

        try:
            cur = self._conn.cursor()

            # Kiểm tra trùng tên
            cur.execute(f"SELECT id FROM `{self._db}`.ITEMS_CODE WHERE name_line_code = %s", (new_name,))
            if cur.fetchone():
                QMessageBox.warning(self, "Tên đã tồn tại",
                                    f"Mã hàng '{new_name}' đã tồn tại trong database '{self._db}'.")
                cur.close()
                return

            if mode == 'custom':
                # ── Custom: chỉ insert tên ──────────────────────────────────
                cur.execute(
                    f"INSERT INTO `{self._db}`.ITEMS_CODE (name_line_code, assign_register) VALUES (%s, %s)",
                    (new_name, register)
                )
                new_id = cur.lastrowid
                self._conn.commit()
                _log.info("Custom: inserted ITEMS_CODE '%s' id=%s", new_name, new_id)

            else:
                # ── Copy: deep-copy từ mã hàng đã chọn ──────────────────────
                src_id   = self._source_combo.currentData()
                src_name = self._source_combo.currentText()

                if src_id is None:
                    QMessageBox.warning(self, "Chưa chọn nguồn",
                                        "Vui lòng chọn mã hàng nguồn để sao chép.")
                    cur.close()
                    return

                if src_name == new_name:
                    QMessageBox.warning(self, "Trùng tên",
                                        "Tên mã hàng mới phải khác mã hàng nguồn.")
                    cur.close()
                    return

                copier = _DeepCopier(cur, self._conn, self._db)
                new_id = copier.run(src_id, new_name, register)
                _log.info("Copy: '%s' (id=%s) → '%s' (id=%s)", src_name, src_id, new_name, new_id)

            cur.close()

            self.result_mode    = mode
            self.result_name    = new_name
            self.result_item_id = new_id

            self.item_added.emit(new_name, new_id, mode)

            action_msg = (
                f"Đã tạo mã hàng '{new_name}' thành công!\n\n"
                f"Chế độ: {'Custom — hãy mở Chỉnh sửa cấu hình để thiết lập.' if mode == 'custom' else 'Copy — cấu hình đã được sao chép đầy đủ.'}"
            )
            QMessageBox.information(self, "Thành công", action_msg)
            self.accept()

        except mysql.connector.IntegrityError as e:
            self._conn.rollback()
            _log.error("IntegrityError adding item code: %s", e)
            QMessageBox.critical(self, "Lỗi trùng lặp",
                                 f"Tên mã hàng đã tồn tại hoặc vi phạm ràng buộc DB:\n{e}")
        except Exception as e:
            self._conn.rollback()
            _log.error("Error adding item code: %s", e)
            QMessageBox.critical(self, "Lỗi", f"Không thể tạo mã hàng:\n{e}")
