"""
module_1/config_editor.py
─────────────────────────
Cửa sổ chỉnh sửa cấu hình cho một item_code đã chọn từ menu.
Cho phép:
  • Xem / sửa tên ITEMS_CODE (assign_register)
  • Thêm / bớt số lượng NUMS_CAMERA
  • Với mỗi camera: xem / sửa thông tin device; thêm / bớt NUMS_MODEL
Dữ liệu hiện có trong DB sẽ được load và hiển thị ngay khi mở.
Khi nhấn "Lưu", dữ liệu sẽ được đồng bộ lại vào DB (upsert / delete cascade).
"""

from __future__ import annotations
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox, QGroupBox,
    QScrollArea, QMessageBox, QFrame, QSizePolicy,
)
from app_logger.app_logger import get_logger as _get_logger

_log = _get_logger('module_1.config_editor')
from module_2.StyleSheet import *

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _label(text: str, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    if bold:
        f = lbl.font()
        f.setBold(True)
        lbl.setFont(f)
    return lbl


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    return line


# ─────────────────────────────────────────────────────────────────────────────
#  Camera block widget (1 camera + N model rows)
# ─────────────────────────────────────────────────────────────────────────────

class CameraBlock(QGroupBox):
    """Widget đại diện cho 1 dòng NUMS_CAMERA + danh sách NUMS_MODEL của nó."""

    remove_requested = QtCore.pyqtSignal(object)  # emits self

    def __init__(self, cam_index: int, cam_data: dict | None = None, parent=None):
        """
        cam_index : số thứ tự hiển thị (1-based)
        cam_data  : dict với keys:
                      id, nums_camera, device_type, device_serial,
                      connection_type, ip_address,
                      models: list[dict(id, nums_model)]
        """
        super().__init__(f"Camera {cam_index}", parent)
        self._cam_index = cam_index
        self._db_id     = cam_data.get('id') if cam_data else None  # row id trong DB

        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #aaa;
                border-radius: 6px;
                margin-top: 10px;
                padding: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)

        root = QVBoxLayout(self)

        # ── Device info grid ────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        self._device_type    = QLineEdit()
        self._device_serial  = QLineEdit()
        self._connection_type= QLineEdit()
        self._ip_address     = QLineEdit()

        grid.addWidget(_label("Device type:"),      0, 0)
        grid.addWidget(self._device_type,           0, 1)
        grid.addWidget(_label("Serial:"),           0, 2)
        grid.addWidget(self._device_serial,         0, 3)
        grid.addWidget(_label("Connection:"),       1, 0)
        grid.addWidget(self._connection_type,       1, 1)
        grid.addWidget(_label("IP address:"),       1, 2)
        grid.addWidget(self._ip_address,            1, 3)

        root.addLayout(grid)

        # ── Models section ──────────────────────────────────────────────────
        root.addWidget(_label("  Số lượng model:", bold=True))

        model_ctrl = QHBoxLayout()
        self._model_spin = QSpinBox()
        self._model_spin.setRange(0, 50)
        self._model_spin.setFixedWidth(80)
        self._model_spin.setToolTip("Số model (NUMS_MODEL) cho camera này")
        model_ctrl.addWidget(_label("Số model:"))
        model_ctrl.addWidget(self._model_spin)
        model_ctrl.addStretch()
        root.addLayout(model_ctrl)

        # ── Remove button ────────────────────────────────────────────────────
        btn_remove = QPushButton(f"🗑  Xóa Camera {cam_index}")
        btn_remove.setStyleSheet("color: #c0392b; font-weight: bold;")
        btn_remove.clicked.connect(lambda: self.remove_requested.emit(self))
        root.addWidget(btn_remove)

        # ── Populate with existing data ──────────────────────────────────────
        if cam_data:
            self._device_type.setText(cam_data.get('device_type', ''))
            self._device_serial.setText(cam_data.get('device_serial', ''))
            self._connection_type.setText(cam_data.get('connection_type', ''))
            self._ip_address.setText(cam_data.get('ip_address', ''))
            models = cam_data.get('models', [])
            self._model_spin.setValue(len(models))
            # store existing model ids for delta computation
            self._existing_model_ids: list[int] = [m['id'] for m in models]
        else:
            self._existing_model_ids = []

    # ── Public accessors ────────────────────────────────────────────────────

    @property
    def db_id(self) -> int | None:
        return self._db_id

    def get_data(self) -> dict:
        return {
            'db_id'          : self._db_id,
            'device_type'    : self._device_type.text().strip(),
            'device_serial'  : self._device_serial.text().strip(),
            'connection_type': self._connection_type.text().strip(),
            'ip_address'     : self._ip_address.text().strip(),
            'num_models'     : self._model_spin.value(),
            'existing_model_ids': list(self._existing_model_ids),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  Main editor window
# ─────────────────────────────────────────────────────────────────────────────

class ItemCodeConfigEditor(QMainWindow):
    """
    Cửa sổ chỉnh sửa cấu hình cho 1 item_code.

    Parameters
    ----------
    connection : mysql.connector connection đang hoạt động
    db_name    : tên database (schema) chứa item_code đó
    item_code  : giá trị name_line_code cần chỉnh sửa
    """

    def __init__(self, connection, db_name: str, item_code: str):
        super().__init__()
        self._conn      = connection
        self._db_name   = db_name
        self._item_code = item_code

        self._item_db_id: int | None = None   # id trong ITEMS_CODE
        self._camera_blocks: list[CameraBlock] = []

        self.setWindowTitle(f"Chỉnh sửa cấu hình — {item_code}  [{db_name}]")
        self.setMinimumSize(760, 580)
        self.resize(900, 680)
        self._build_ui()
        self._load_data()

    # ─── UI skeleton ────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        setStyleSheet(central)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(14, 14, 14, 14)

        # ── Header ──────────────────────────────────────────────────────────
        hdr = _label(f"🔧  Cấu hình mã hàng:  {self._item_code}  (DB: {self._db_name})", bold=True)
        hdr.setStyleSheet("font-size: 14px; color: #2c3e50; padding-bottom: 4px;")
        main_layout.addWidget(hdr)
        main_layout.addWidget(_separator())

        # ── ITEMS_CODE fields ────────────────────────────────────────────────
        ic_group = QGroupBox("ITEMS_CODE — thông tin mã hàng")
        ic_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        ic_layout = QGridLayout(ic_group)
        ic_layout.setColumnStretch(1, 1)

        self._name_edit          = QLineEdit()
        self._register_edit      = QLineEdit()
        self._value_bit_on_spin  = QSpinBox()
        self._value_bit_on_spin.setRange(-9999999, 9999999)
        self._value_bit_on_spin.setValue(1)
        self._value_bit_off_spin = QSpinBox()
        self._value_bit_off_spin.setRange(-9999999, 9999999)
        self._value_bit_off_spin.setValue(0)
        self._name_edit.setPlaceholderText("Tên mã hàng (name_line_code)")
        self._register_edit.setPlaceholderText("VD: DM100")

        ic_layout.addWidget(_label("Tên mã hàng:"),     0, 0)
        ic_layout.addWidget(self._name_edit,             0, 1)
        ic_layout.addWidget(_label("Assign register:"), 1, 0)
        ic_layout.addWidget(self._register_edit,         1, 1)
        ic_layout.addWidget(_label("Value bit ON:"),    2, 0)
        ic_layout.addWidget(self._value_bit_on_spin,     2, 1)
        ic_layout.addWidget(_label("Value bit OFF:"),   3, 0)
        ic_layout.addWidget(self._value_bit_off_spin,    3, 1)

        main_layout.addWidget(ic_group)

        # ── Scroll area for cameras ──────────────────────────────────────────
        cam_header = QHBoxLayout()
        cam_header.addWidget(_label("NUMS_CAMERA — danh sách camera", bold=True))
        cam_header.addStretch()
        btn_add_cam = QPushButton("➕  Thêm Camera")
        btn_add_cam.setStyleSheet(
            "background-color: #27ae60; color: white; font-weight: bold;"
            "border-radius: 4px; padding: 4px 12px;"
        )
        btn_add_cam.clicked.connect(self._add_camera)
        cam_header.addWidget(btn_add_cam)
        main_layout.addLayout(cam_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self._cam_container = QWidget()
        self._cam_layout    = QVBoxLayout(self._cam_container)
        self._cam_layout.setAlignment(Qt.AlignTop)
        self._cam_layout.setSpacing(8)

        scroll.setWidget(self._cam_container)
        main_layout.addWidget(scroll, stretch=1)

        # ── Bottom buttons ───────────────────────────────────────────────────
        main_layout.addWidget(_separator())
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Hủy")
        btn_cancel.setFixedWidth(100)
        btn_cancel.clicked.connect(self.close)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("💾  Lưu")
        btn_save.setFixedWidth(120)
        btn_save.setStyleSheet(
            "background-color: #2980b9; color: white; font-weight: bold;"
            "border-radius: 4px; padding: 6px;"
        )
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_save)

        main_layout.addLayout(btn_row)

    # ─── Load existing data from DB ──────────────────────────────────────────

    def _load_data(self):
        try:
            cur = self._conn.cursor()
            db = self._db_name

            # ITEMS_CODE
            cur.execute(
                f"SELECT id, name_line_code, assign_register, value_bit_on, value_bit_off FROM `{db}`.ITEMS_CODE WHERE name_line_code = %s",
                (self._item_code,)
            )
            row = cur.fetchone()
            if not row:
                QMessageBox.warning(self, "Không tìm thấy",
                                    f"Mã hàng '{self._item_code}' không tồn tại trong DB.")
                return

            self._item_db_id = row[0]
            self._name_edit.setText(row[1] or '')
            self._register_edit.setText(row[2] or '')
            self._value_bit_on_spin.setValue(int(row[3]) if row[3] is not None else 1)
            self._value_bit_off_spin.setValue(int(row[4]) if row[4] is not None else 0)

            # NUMS_CAMERA
            cur.execute(
                f"""SELECT id, nums_camera, device_type, device_serial,
                          connection_type, ip_address
                   FROM `{db}`.NUMS_CAMERA
                   WHERE item_code_id = %s
                   ORDER BY nums_camera""",
                (self._item_db_id,)
            )
            cameras = cur.fetchall()

            for cam_row in cameras:
                cam_id = cam_row[0]
                # NUMS_MODEL for this camera
                cur.execute(
                    f"SELECT id, nums_model FROM `{db}`.NUMS_MODEL WHERE camera_id = %s ORDER BY nums_model",
                    (cam_id,)
                )
                models = [{'id': m[0], 'nums_model': m[1]} for m in cur.fetchall()]

                cam_data = {
                    'id'             : cam_row[0],
                    'nums_camera'    : cam_row[1],
                    'device_type'    : cam_row[2] or '',
                    'device_serial'  : cam_row[3] or '',
                    'connection_type': cam_row[4] or '',
                    'ip_address'     : cam_row[5] or '',
                    'models'         : models,
                }
                self._add_camera(cam_data)

            cur.close()
            _log.info("Config editor loaded data for %s/%s", self._db_name, self._item_code)

        except Exception as e:
            _log.error("Error loading config data: %s", e)
            QMessageBox.critical(self, "Lỗi", f"Không thể tải dữ liệu:\n{e}")

    # ─── Camera management ───────────────────────────────────────────────────

    def _add_camera(self, cam_data: dict | None = None):
        idx   = len(self._camera_blocks) + 1
        block = CameraBlock(idx, cam_data, parent=self._cam_container)
        block.remove_requested.connect(self._remove_camera)
        self._cam_layout.addWidget(block)
        self._camera_blocks.append(block)

    def _remove_camera(self, block: CameraBlock):
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            f"Xóa camera này?\n"
            f"{'(Dữ liệu camera đã lưu trong DB sẽ bị xóa khi nhấn Lưu.)' if block.db_id else ''}",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._cam_layout.removeWidget(block)
        block.deleteLater()
        self._camera_blocks.remove(block)
        # re-title remaining blocks
        for i, b in enumerate(self._camera_blocks, 1):
            b.setTitle(f"Camera {i}")

    # ─── Save ────────────────────────────────────────────────────────────────

    def _save(self):
        new_name = self._name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Thiếu dữ liệu", "Tên mã hàng không được để trống.")
            return

        try:
            cur = self._conn.cursor()
            db = self._db_name

            # ── 1. Update ITEMS_CODE ─────────────────────────────────────────
            cur.execute(
                f"""UPDATE `{db}`.ITEMS_CODE 
                   SET name_line_code = %s, assign_register = %s, value_bit_on = %s, value_bit_off = %s 
                   WHERE id = %s""",
                (
                    new_name,
                    self._register_edit.text().strip() or None,
                    self._value_bit_on_spin.value(),
                    self._value_bit_off_spin.value(),
                    self._item_db_id
                )
            )

            # ── 2. Collect current camera db-ids (to detect removed ones) ───
            cur.execute(
                f"SELECT id FROM `{db}`.NUMS_CAMERA WHERE item_code_id = %s", (self._item_db_id,)
            )
            existing_cam_ids = {row[0] for row in cur.fetchall()}
            kept_cam_ids     = set()

            # ── 3. Upsert cameras ────────────────────────────────────────────
            for cam_idx, block in enumerate(self._camera_blocks, 1):
                data = block.get_data()
                cam_db_id = data['db_id']

                if cam_db_id:
                    # UPDATE existing
                    cur.execute(f"""
                        UPDATE `{db}`.NUMS_CAMERA
                           SET nums_camera     = %s,
                               device_type     = %s,
                               device_serial   = %s,
                               connection_type = %s,
                               ip_address      = %s
                         WHERE id = %s
                    """, (
                        cam_idx,
                        data['device_type'],
                        data['device_serial'],
                        data['connection_type'],
                        data['ip_address'],
                        cam_db_id,
                    ))
                    kept_cam_ids.add(cam_db_id)
                else:
                    # INSERT new
                    cur.execute(f"""
                        INSERT INTO `{db}`.NUMS_CAMERA
                            (nums_camera, device_type, device_serial,
                             connection_type, ip_address, item_code_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        cam_idx,
                        data['device_type'],
                        data['device_serial'],
                        data['connection_type'],
                        data['ip_address'],
                        self._item_db_id,
                    ))
                    cam_db_id = cur.lastrowid
                    kept_cam_ids.add(cam_db_id)

                # ── 4. Sync NUMS_MODEL for this camera ───────────────────────
                num_models_wanted = data['num_models']
                cur.execute(
                    f"SELECT id FROM `{db}`.NUMS_MODEL WHERE camera_id = %s ORDER BY nums_model",
                    (cam_db_id,)
                )
                existing_models = [row[0] for row in cur.fetchall()]

                # Remove excess models (from end)
                while len(existing_models) > num_models_wanted:
                    mid = existing_models.pop()
                    cur.execute(f"DELETE FROM `{db}`.NUMS_MODEL WHERE id = %s", (mid,))

                # Add missing models
                for m_idx in range(len(existing_models) + 1, num_models_wanted + 1):
                    cur.execute(
                        f"INSERT INTO `{db}`.NUMS_MODEL (nums_model, camera_id) VALUES (%s, %s)",
                        (m_idx, cam_db_id)
                    )

            # ── 5. Delete cameras removed by user ────────────────────────────
            removed_cam_ids = existing_cam_ids - kept_cam_ids
            for cid in removed_cam_ids:
                cur.execute(f"DELETE FROM `{db}`.NUMS_CAMERA WHERE id = %s", (cid,))

            self._conn.commit()
            cur.close()

            _log.info("Config saved for %s/%s", self._db_name, new_name)
            QMessageBox.information(self, "Thành công",
                                    f"Đã lưu cấu hình cho mã hàng '{new_name}' thành công!")
            # Refresh item_code in memory
            self._item_code = new_name
            self.setWindowTitle(f"Chỉnh sửa cấu hình — {new_name}  [{self._db_name}]")

        except Exception as e:
            self._conn.rollback()
            _log.error("Error saving config: %s", e)
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu cấu hình:\n{e}")
