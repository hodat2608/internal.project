"""
Module: config_history_dialog.py
Mục đích: Cửa sổ quản lý toàn diện Lịch sử Cấu hình, Biến động Thiết định (Audit Trail)
và Khôi phục Điểm chuẩn (Rollback) cho hệ thống Machine Vision công nghiệp.
Giao diện chuẩn doanh nghiệp: Tone sáng trầm (Slate theme), bảng Diff trực quan highlight màu sắc.
"""

import json
import csv
from datetime import datetime
from typing import Dict, Any, List, Optional
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

from module_3.config_version_manager import (
    ensure_config_history_table,
    get_history_records,
    get_latest_snapshot,
    rollback_snapshot,
    toggle_golden_status,
    compute_diff,
    _get_history_table_name
)
from module_3.change_reason_dialog import RollbackPasswordDialog


CATEGORY_MAP = {
    'ALL': 'Tất cả phân loại',
    'MODEL_PARAMS': 'AI Model & Bảng Nhãn',
    'TASK_RULES': 'Quy tắc Task Rules',
    'PLC_SETTINGS': 'Cấu hình PLC Settings',
    'MODE_AUTO': 'Chế độ Auto Signals & Shot x Model',
    'MIRROR_CONFIG': 'Cấu hình Mirror',
    'AUTO_LOGGING': 'Cấu hình Auto Logging'
}


class ConfigHistoryDialog(QtWidgets.QDialog):
    """
    Cửa sổ chính Quản Lý Lịch Sử Cấu Hình, So Sánh Diff & Phục Hồi Phiên Bản.
    """
    def __init__(
        self,
        cursor,
        connection,
        current_user: str = "Unknown",
        current_role: str = "modify",
        default_category: str = "ALL",
        default_camera: str = "",
        default_model_id: Optional[int] = None,
        initial_category: Optional[str] = None,
        initial_camera_id: Optional[str] = None,
        initial_model_id: Optional[int] = None,
        initial_mode_id: Optional[int] = None,
        parent=None
    ):
        super().__init__(parent)
        self.connection = connection
        self._own_cursor = False
        if self.connection and hasattr(self.connection, 'cursor'):
            try:
                self.cursor = self.connection.cursor(buffered=True)
                self._own_cursor = True
            except Exception:
                self.cursor = cursor
        else:
            self.cursor = cursor

        self.current_user = str(current_user or 'Unknown').strip()
        self.current_role = str(current_role or 'modify').strip().lower()
        self.default_category = initial_category or default_category or "ALL"
        self.default_camera = str(initial_camera_id or default_camera or "")
        self.default_model_id = initial_model_id if initial_model_id is not None else default_model_id
        self.default_mode_id = initial_mode_id

        self.records_cache: List[Dict[str, Any]] = []
        self.selected_record: Optional[Dict[str, Any]] = None

        self.setWindowTitle("Quản Lý Lịch Sử Thay Đổi")
        self.resize(1280, 800)
        self.setMinimumSize(1050, 620)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowMinMaxButtonsHint
            | Qt.WindowCloseButtonHint
        )

        ensure_config_history_table(self.cursor, self.connection)
        self._init_ui()
        self._load_filters_data()
        self.reload_history()

    def _init_ui(self):
        # Thiết kế Slate Theme - Sang trọng, êm dịu, tương phản cao, chuẩn công nghiệp
        self.setStyleSheet("""
            QDialog {
                background-color: #f1f5f9;
                color: #0f172a;
                font-family: 'Segoe UI';
            }
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 14px;
                font-weight: bold;
                font-size: 13px;
                color: #0f172a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 8px;
                background-color: #ffffff;
                color: #1e293b;
            }
            QFrame#filterFrame, QFrame#bottomFrame {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
            QLabel {
                color: #334155;
                font-size: 13px;
                font-weight: 500;
            }
            QComboBox, QLineEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 12px;
                color: #0f172a;
            }
            QComboBox:focus, QLineEdit:focus {
                border: 1.5px solid #2563eb;
            }
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                gridline-color: #f1f5f9;
                font-size: 12px;
                color: #1e293b;
            }
            QTableWidget::item {
                padding: 4px 6px;
                border-bottom: 1px solid #f1f5f9;
            }
            QTableWidget::item:selected {
                background-color: #dbeafe;
                color: #1e40af;
                font-weight: bold;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #334155;
                padding: 6px;
                border: 1px solid #e2e8f0;
                font-weight: bold;
                font-size: 12px;
            }
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                background-color: #ffffff;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #e2e8f0;
                color: #475569;
                padding: 8px 16px;
                font-weight: bold;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #2563eb;
                border-bottom: 2px solid #2563eb;
            }
            QPushButton {
                background-color: #ffffff;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                color: #0f172a;
                border-color: #94a3b8;
            }
            QPushButton#btnRollback {
                background-color: #ea580c;
                color: #ffffff !important;
                border: 1px solid #c2410c;
                padding: 8px 20px;
                font-size: 13px;
            }
            QPushButton#btnRollback:hover {
                background-color: #c2410c;
            }
            QPushButton#btnGolden {
                background-color: #fef3c7;
                color: #b45309 !important;
                border: 1px solid #fcd34d;
            }
            QPushButton#btnGolden:hover {
                background-color: #fde68a;
            }
        """)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # ─────────────────────────────────────────────────────────────────────
        # 1. THANH BỘ LỌC (TOP FILTER BAR)
        # ─────────────────────────────────────────────────────────────────────
        filter_frame = QtWidgets.QFrame()
        filter_frame.setObjectName("filterFrame")
        f_layout = QtWidgets.QHBoxLayout(filter_frame)
        f_layout.setContentsMargins(12, 8, 12, 8)
        f_layout.setSpacing(10)

        f_layout.addWidget(QtWidgets.QLabel("Phân loại:"))
        self.combo_category = QtWidgets.QComboBox()
        for k, v in CATEGORY_MAP.items():
            self.combo_category.addItem(v, k)
        self.combo_category.currentIndexChanged.connect(self.reload_history)
        f_layout.addWidget(self.combo_category)

        f_layout.addWidget(QtWidgets.QLabel("Camera:"))
        self.combo_camera = QtWidgets.QComboBox()
        self.combo_camera.addItem("Tất cả Camera", "ALL")
        self.combo_camera.currentIndexChanged.connect(self.reload_history)
        f_layout.addWidget(self.combo_camera)

        f_layout.addWidget(QtWidgets.QLabel("Model:"))
        self.combo_model = QtWidgets.QComboBox()
        self.combo_model.addItem("Tất cả Model", "ALL")
        self.combo_model.currentIndexChanged.connect(self.reload_history)
        f_layout.addWidget(self.combo_model)

        f_layout.addWidget(QtWidgets.QLabel("Tìm kiếm:"))
        self.line_search = QtWidgets.QLineEdit()
        self.line_search.setPlaceholderText("Tìm theo User, lý do...")
        self.line_search.textChanged.connect(self._apply_text_filter)
        f_layout.addWidget(self.line_search)

        self.chk_golden_only = QtWidgets.QCheckBox("⭐ Chỉ Bản Chuẩn")
        self.chk_golden_only.setStyleSheet("font-weight: bold; color: #b45309;")
        self.chk_golden_only.toggled.connect(self.reload_history)
        f_layout.addWidget(self.chk_golden_only)

        self.btn_refresh = QtWidgets.QPushButton("↺ Làm Mới")
        self.btn_refresh.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.btn_refresh.clicked.connect(self.reload_history)
        f_layout.addWidget(self.btn_refresh)

        main_layout.addWidget(filter_frame)

        # ─────────────────────────────────────────────────────────────────────
        # 2. KHUNG CHÍNH SPLITTER: TIMELINE (TRÁI) & DIFF INSPECTOR (PHẢI)
        # ─────────────────────────────────────────────────────────────────────
        splitter = QtWidgets.QSplitter(Qt.Horizontal)

        # ── KHUNG TRÁI: TIMELINE LIST ──
        left_widget = QtWidgets.QWidget()
        l_box = QtWidgets.QVBoxLayout(left_widget)
        l_box.setContentsMargins(0, 0, 0, 0)
        l_box.setSpacing(6)

        lbl_timeline = QtWidgets.QLabel("🕒 Timeline")
        lbl_timeline.setStyleSheet("font-weight: bold; color: #1e293b; font-size: 13px;")
        l_box.addWidget(lbl_timeline)

        self.table_timeline = QtWidgets.QTableWidget(0, 7)
        self.table_timeline.setHorizontalHeaderLabels([
            "ID", "Thời Gian", "Người Sửa", "Phân Loại", "Lý Do Thiết Định", "Điểm Sửa", "Chuẩn"
        ])
        self.table_timeline.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        self.table_timeline.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_timeline.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table_timeline.setAlternatingRowColors(True)
        self.table_timeline.verticalHeader().setVisible(False)
        self.table_timeline.verticalHeader().setDefaultSectionSize(32)
        self.table_timeline.itemSelectionChanged.connect(self._on_timeline_row_selected)
        l_box.addWidget(self.table_timeline)
        splitter.addWidget(left_widget)

        # ── KHUNG PHẢI: DETAIL & DIFF VIEWER ──
        right_widget = QtWidgets.QWidget()
        r_box = QtWidgets.QVBoxLayout(right_widget)
        r_box.setContentsMargins(0, 0, 0, 0)
        r_box.setSpacing(6)

        # Info Header Card của bản đang chọn
        self.card_info = QtWidgets.QFrame()
        self.card_info.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px;")
        c_layout = QtWidgets.QVBoxLayout(self.card_info)
        c_layout.setContentsMargins(8, 4, 8, 4)
        c_layout.setSpacing(2)

        self.lbl_selected_title = QtWidgets.QLabel("Chưa chọn phiên bản nào")
        self.lbl_selected_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #0f172a;")
        c_layout.addWidget(self.lbl_selected_title)

        self.lbl_selected_meta = QtWidgets.QLabel("Vui lòng nhấp vào 1 dòng trên danh sách bên trái để xem chi tiết.")
        self.lbl_selected_meta.setStyleSheet("color: #64748b; font-size: 12px;")
        self.lbl_selected_meta.setWordWrap(True)
        c_layout.addWidget(self.lbl_selected_meta)
        r_box.addWidget(self.card_info)

        # Tabs: Tab 1 (Bảng Diff), Tab 2 (Full JSON)
        self.tabs_detail = QtWidgets.QTabWidget()

        # Tab 1: Visual Diff Table
        self.tab_diff = QtWidgets.QWidget()
        t1_layout = QtWidgets.QVBoxLayout(self.tab_diff)
        t1_layout.setContentsMargins(4, 4, 4, 4)

        self.table_diff = QtWidgets.QTableWidget(0, 5)
        self.table_diff.setHorizontalHeaderLabels([
            "Phân Loại", "Hạng Mục", "Trước Thay Đổi", "Sau Thay Đổi", "Trạng Thái"
        ])
        header_diff = self.table_diff.horizontalHeader()
        header_diff.setSectionResizeMode(0, QtWidgets.QHeaderView.Interactive)
        self.table_diff.setColumnWidth(0, 160)
        header_diff.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header_diff.setSectionResizeMode(2, QtWidgets.QHeaderView.Interactive)
        self.table_diff.setColumnWidth(2, 140)
        header_diff.setSectionResizeMode(3, QtWidgets.QHeaderView.Interactive)
        self.table_diff.setColumnWidth(3, 140)
        header_diff.setSectionResizeMode(4, QtWidgets.QHeaderView.Interactive)
        self.table_diff.setColumnWidth(4, 110)
        self.table_diff.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_diff.setAlternatingRowColors(True)
        self.table_diff.verticalHeader().setVisible(False)
        self.table_diff.verticalHeader().setDefaultSectionSize(30)
        t1_layout.addWidget(self.table_diff)
        self.tabs_detail.addTab(self.tab_diff, "🔍 Chi Tiết Các Điểm Thay Đổi")

        # Tab 2: Full Snapshot JSON
        self.tab_raw = QtWidgets.QWidget()
        t2_layout = QtWidgets.QVBoxLayout(self.tab_raw)
        t2_layout.setContentsMargins(4, 4, 4, 4)
        self.txt_raw_json = QtWidgets.QTextEdit()
        self.txt_raw_json.setReadOnly(True)
        self.txt_raw_json.setStyleSheet("background-color: #f8fafc; font-family: 'Consolas', monospace; font-size: 11px;")
        t2_layout.addWidget(self.txt_raw_json)
        self.tabs_detail.addTab(self.tab_raw, "📄 Bản Chụp Toàn Bộ")

        r_box.addWidget(self.tabs_detail)
        splitter.addWidget(right_widget)

        # Tỉ lệ 42% : 58%
        splitter.setSizes([520, 720])
        main_layout.addWidget(splitter, 1)

        # ─────────────────────────────────────────────────────────────────────
        # 3. THANH THAO TÁC ĐÁY (BOTTOM ACTION BAR)
        # ─────────────────────────────────────────────────────────────────────
        bottom_frame = QtWidgets.QFrame()
        bottom_frame.setObjectName("bottomFrame")
        b_layout = QtWidgets.QHBoxLayout(bottom_frame)
        b_layout.setContentsMargins(12, 8, 12, 8)
        b_layout.setSpacing(10)

        self.btn_golden = QtWidgets.QPushButton("⭐ Đánh Dấu / Bỏ Bản Chuẩn")
        self.btn_golden.setObjectName("btnGolden")
        self.btn_golden.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.btn_golden.setToolTip("Đánh dấu phiên bản được chọn là Bản Chuẩn Nghiệm Thu")
        self.btn_golden.clicked.connect(self._on_toggle_golden_clicked)
        b_layout.addWidget(self.btn_golden)

        self.btn_export_csv = QtWidgets.QPushButton("📊 Xuất File Báo Cáo (CSV)")
        self.btn_export_csv.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.btn_export_csv.clicked.connect(self._on_export_csv_clicked)
        b_layout.addWidget(self.btn_export_csv)

        b_layout.addStretch()

        self.btn_rollback = QtWidgets.QPushButton("↺ Khôi Phục Phiên Bản Này")
        self.btn_rollback.setObjectName("btnRollback")
        self.btn_rollback.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.btn_rollback.setToolTip("Khôi phục toàn bộ thông số CSDL về phiên bản đang chọn (Yêu cầu mật khẩu Full Control)")
        self.btn_rollback.clicked.connect(self._on_rollback_clicked)
        b_layout.addWidget(self.btn_rollback)

        self.btn_close = QtWidgets.QPushButton("Đóng")
        self.btn_close.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        self.btn_close.clicked.connect(self.accept)
        b_layout.addWidget(self.btn_close)

        main_layout.addWidget(bottom_frame)

    # ─────────────────────────────────────────────────────────────────────────
    # DỮ LIỆU & LOGIC
    # ─────────────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if getattr(self, '_own_cursor', False) and self.cursor:
            try:
                self.cursor.close()
            except Exception:
                pass
        super().closeEvent(event)

    def _load_filters_data(self):
        """Nạp danh sách Camera và Model vào combobox bộ lọc."""
        # Nạp Camera
        try:
            self.cursor.execute("SELECT id, nums_camera FROM NUMS_CAMERA ORDER BY id ASC")
            for r in self.cursor.fetchall():
                c_id, c_name = r
                self.combo_camera.addItem(f"{c_name} (ID: {c_id})", str(c_name))
        except Exception:
            pass

        # Nạp Model
        try:
            self.cursor.execute("SELECT id, nums_model FROM NUMS_MODEL ORDER BY id ASC")
            for r in self.cursor.fetchall():
                m_id, m_name = r
                self.combo_model.addItem(f"Model {m_name} (ID: {m_id})", m_id)
        except Exception:
            pass

        # Set giá trị mặc định nếu có truyền vào
        if self.default_category:
            idx = self.combo_category.findData(self.default_category)
            if idx >= 0:
                self.combo_category.setCurrentIndex(idx)

        if self.default_camera:
            idx = self.combo_camera.findData(self.default_camera)
            if idx < 0:
                c_digits = ''.join(ch for ch in str(self.default_camera) if ch.isdigit())
                for i in range(self.combo_camera.count()):
                    item_d = str(self.combo_camera.itemData(i))
                    if item_d == c_digits or ''.join(ch for ch in item_d if ch.isdigit()) == c_digits:
                        idx = i
                        break
            if idx >= 0:
                self.combo_camera.setCurrentIndex(idx)

        if self.default_model_id is not None:
            idx = self.combo_model.findData(self.default_model_id)
            if idx >= 0:
                self.combo_model.setCurrentIndex(idx)

    def reload_history(self):
        """Truy vấn lại danh sách bản ghi lịch sử từ CSDL."""
        cat = self.combo_category.currentData()
        cam = self.combo_camera.currentData()
        m_id = self.combo_model.currentData()
        only_gold = self.chk_golden_only.isChecked()

        cam_param = None if cam == 'ALL' else cam
        model_param = None if m_id == 'ALL' else m_id

        self.records_cache = get_history_records(
            self.cursor,
            scope_category=cat,
            camera_id=cam_param,
            model_id=model_param,
            only_golden=only_gold,
            limit=250
        )

        self._populate_timeline_table(self.records_cache)

    def _populate_timeline_table(self, records: List[Dict[str, Any]]):
        """Đổ dữ liệu lên bảng Timeline bên trái."""
        self.table_timeline.setRowCount(0)
        self.table_timeline.setRowCount(len(records))

        for row, rec in enumerate(records):
            # 0. ID
            it_id = QtWidgets.QTableWidgetItem(str(rec['id']))
            it_id.setTextAlignment(Qt.AlignCenter)
            self.table_timeline.setItem(row, 0, it_id)

            # 1. Thời Gian
            dt_str = str(rec['created_at'])
            try:
                if isinstance(rec['created_at'], datetime):
                    dt_str = rec['created_at'].strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                pass
            it_time = QtWidgets.QTableWidgetItem(dt_str)
            self.table_timeline.setItem(row, 1, it_time)

            # 2. Người Sửa
            u_role = rec.get('user_role', 'modify')
            it_user = QtWidgets.QTableWidgetItem(f"{rec.get('changed_by', 'Unknown')}")
            it_user.setToolTip(f"Quyền: {u_role}")
            self.table_timeline.setItem(row, 2, it_user)

            # 3. Phân Loại
            cat_display = CATEGORY_MAP.get(rec.get('scope_category'), rec.get('scope_category'))
            it_cat = QtWidgets.QTableWidgetItem(cat_display)
            self.table_timeline.setItem(row, 3, it_cat)

            # 4. Lý Do Thiết Định
            it_reason = QtWidgets.QTableWidgetItem(rec.get('change_reason', ''))
            it_reason.setToolTip(rec.get('change_reason', ''))
            self.table_timeline.setItem(row, 4, it_reason)

            # 5. Điểm Sửa
            d_cnt = rec.get('diff_count', 0)
            it_diff = QtWidgets.QTableWidgetItem(f"{d_cnt} điểm" if d_cnt > 0 else "Gốc/Đầy đủ")
            it_diff.setTextAlignment(Qt.AlignCenter)
            if d_cnt > 0:
                it_diff.setForeground(QtGui.QBrush(QtGui.QColor("#2563eb")))
            self.table_timeline.setItem(row, 5, it_diff)

            # 6. Bản Chuẩn Golden
            is_gold = bool(rec.get('is_golden'))
            it_gold = QtWidgets.QTableWidgetItem("⭐ Chuẩn" if is_gold else "")
            it_gold.setTextAlignment(Qt.AlignCenter)
            if is_gold:
                it_gold.setForeground(QtGui.QBrush(QtGui.QColor("#b45309")))
                it_gold.setBackground(QtGui.QBrush(QtGui.QColor("#fef3c7")))
            self.table_timeline.setItem(row, 6, it_gold)

        if len(records) > 0:
            self.table_timeline.selectRow(0)
        else:
            self._clear_detail_panel()

    def _apply_text_filter(self):
        """Lọc nhanh theo từ khóa tìm kiếm trên bảng timeline."""
        q = self.line_search.text().strip().lower()
        if not q:
            filtered = self.records_cache
        else:
            filtered = [
                r for r in self.records_cache
                if q in str(r.get('changed_by', '')).lower()
                or q in str(r.get('change_reason', '')).lower()
                or q in str(r.get('version_tag', '')).lower()
            ]
        self._populate_timeline_table(filtered)

    def _on_timeline_row_selected(self):
        """Xử lý khi người dùng chọn 1 mốc thời gian trên Timeline."""
        rows = self.table_timeline.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        item_id = self.table_timeline.item(row, 0)
        if not item_id:
            return

        sid = int(item_id.text())
        rec = next((r for r in self.records_cache if r['id'] == sid), None)
        if not rec:
            return

        self.selected_record = rec
        self._display_selected_detail(rec)

    def _display_selected_detail(self, rec: Dict[str, Any]):
        """Hiển thị chi tiết bản ghi lên bảng Diff và thẻ thông tin."""
        sid = rec['id']
        tag = rec.get('version_tag', '')
        user = rec.get('changed_by', 'Unknown')
        role = rec.get('user_role', 'modify')
        reason = rec.get('change_reason', 'Không có lý do')
        is_gold = bool(rec.get('is_golden'))
        cat = CATEGORY_MAP.get(rec.get('scope_category'), rec.get('scope_category'))
        dt_str = str(rec.get('created_at', ''))

        # Header Info Card
        gold_badge = " <span style='background:#fef3c7; color:#b45309; padding:2px 8px; border-radius:4px; font-weight:bold;'>⭐ BẢN CHUẨN NGHIỆM THU</span>" if is_gold else ""
        self.lbl_selected_title.setText(f"Phiên bản #{sid} [{tag}] - {cat}{gold_badge}")
        self.lbl_selected_title.setTextFormat(Qt.RichText)

        meta_text = f"👤 Người sửa: <b>{user}</b> <i>[{role}]</i> | 🕒 Lúc: <b>{dt_str}</b><br>📝 Lý do: <b>{reason}</b>"
        self.lbl_selected_meta.setText(meta_text)
        self.lbl_selected_meta.setTextFormat(Qt.RichText)

        # 1. Đổ dữ liệu vào bảng Diff
        diff_list = rec.get('diff_list', [])
        self.table_diff.setRowCount(0)
        self.table_diff.setRowCount(len(diff_list))

        for r_idx, d in enumerate(diff_list):
            # 0. Phân loại
            it_cat = QtWidgets.QTableWidgetItem(d.get('category', ''))
            self.table_diff.setItem(r_idx, 0, it_cat)

            # 1. Thông số / Hạng mục
            it_item = QtWidgets.QTableWidgetItem(d.get('item', ''))
            it_item.setToolTip(d.get('item', ''))
            self.table_diff.setItem(r_idx, 1, it_item)

            # 2. Giá trị Trước Thay Đổi (Cũ)
            v_old = str(d.get('old_val', ''))
            it_old = QtWidgets.QTableWidgetItem(v_old)
            it_old.setForeground(QtGui.QBrush(QtGui.QColor("#dc2626")))
            it_old.setBackground(QtGui.QBrush(QtGui.QColor("#fef2f2")))
            self.table_diff.setItem(r_idx, 2, it_old)

            # 3. Giá trị Sau Thay Đổi (Mới)
            v_new = str(d.get('new_val', ''))
            it_new = QtWidgets.QTableWidgetItem(v_new)
            it_new.setForeground(QtGui.QBrush(QtGui.QColor("#16a34a")))
            it_new.setBackground(QtGui.QBrush(QtGui.QColor("#f0fdf4")))
            self.table_diff.setItem(r_idx, 3, it_new)

            # 4. Trạng Thái / Hành động
            action = str(d.get('action', '')).upper()
            if not action:
                if v_old in ('(Trống)', '(Chưa có)'):
                    action = 'ADDED'
                elif v_new in ('(Bị xóa)', '(Đã xóa)'):
                    action = 'DELETED'
                else:
                    action = 'MODIFIED'

            if action == 'ADDED':
                action_text = "➕ Thêm mới"
                fg_color = "#16a34a"
                bg_color = "#f0fdf4"
            elif action == 'DELETED':
                action_text = "❌ Đã xóa"
                fg_color = "#dc2626"
                bg_color = "#fef2f2"
            else:
                action_text = "✏️ Sửa đổi"
                fg_color = "#0284c7"
                bg_color = "#f0f9ff"

            it_status = QtWidgets.QTableWidgetItem(action_text)
            it_status.setTextAlignment(Qt.AlignCenter)
            it_status.setForeground(QtGui.QBrush(QtGui.QColor(fg_color)))
            it_status.setBackground(QtGui.QBrush(QtGui.QColor(bg_color)))
            font_st = it_status.font()
            font_st.setBold(True)
            it_status.setFont(font_st)
            self.table_diff.setItem(r_idx, 4, it_status)

        if not diff_list:
            self.table_diff.setRowCount(1)
            msg_it = QtWidgets.QTableWidgetItem("Bản ghi này là bản Snapshot toàn bộ ban đầu (Không có điểm sửa đổi so sánh).")
            msg_it.setForeground(QtGui.QBrush(QtGui.QColor("#64748b")))
            self.table_diff.setItem(0, 1, msg_it)

        # 2. Đổ dữ liệu Full Snapshot JSON
        try:
            tbl_name = _get_history_table_name(self.cursor)
            self.cursor.execute(f"SELECT full_config_json FROM {tbl_name} WHERE id = %s", (sid,))
            raw_row = self.cursor.fetchone()
            if raw_row and raw_row[0]:
                parsed = json.loads(raw_row[0])
                pretty_json = json.dumps(parsed, indent=2, ensure_ascii=False)
                self.txt_raw_json.setPlainText(pretty_json)
            else:
                self.txt_raw_json.setPlainText("Không có dữ liệu JSON.")
        except Exception as e:
            self.txt_raw_json.setPlainText(f"Lỗi đọc JSON: {e}")

    def _clear_detail_panel(self):
        self.selected_record = None
        self.lbl_selected_title.setText("Không có dữ liệu")
        self.lbl_selected_meta.setText("Không tìm thấy bản ghi lịch sử phù hợp với bộ lọc hiện tại.")
        self.table_diff.setRowCount(0)
        self.txt_raw_json.clear()

    # ─────────────────────────────────────────────────────────────────────────
    # NÚT THAO TÁC: ROLLBACK, TOGGLE GOLDEN, EXPORT
    # ─────────────────────────────────────────────────────────────────────────

    def _on_rollback_clicked(self):
        """Khôi phục phiên bản đang chọn với bảo mật kiểm tra mật khẩu Full Control."""
        if not self.selected_record:
            QtWidgets.QMessageBox.warning(self, "Chưa Chọn Phiên Bản", "Vui lòng chọn 1 phiên bản trên danh sách bên trái để khôi phục!")
            return

        sid = self.selected_record['id']
        tag = self.selected_record.get('version_tag', '')
        reason = self.selected_record.get('change_reason', '')
        cat = CATEGORY_MAP.get(self.selected_record.get('scope_category'), self.selected_record.get('scope_category'))

        # 1. Kiểm tra quyền hạn
        if self.current_role not in ('full_control', '__admin__'):
            QtWidgets.QMessageBox.critical(
                self,
                "Không Đủ Quyền Hạn",
                f"Tài khoản hiện tại '<b>{self.current_user}</b>' [Quyền: {self.current_role}] không có quyền thực hiện Rollback.<br><br>"
                "Chức năng khôi phục chỉ dành riêng cho tài khoản có quyền <b>Toàn Quyền (Full Control)</b> hoặc <b>Administrator</b>!"
            )
            return

        # 2. Mở hộp thoại nhập mật khẩu xác thực bảo mật
        target_desc = f"Phiên bản #{sid} [{tag}] - {cat}<br>Lý do bản cũ: '{reason}'"
        pwd_dlg = RollbackPasswordDialog(self.current_user, target_desc, self.cursor, self)
        if pwd_dlg.exec_() != QtWidgets.QDialog.Accepted or not pwd_dlg.is_authorized:
            return

        # 3. Thực hiện Rollback
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(Qt.WaitCursor))
        try:
            ok, msg = rollback_snapshot(self.cursor, self.connection, sid, performed_by=self.current_user)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        if ok:
            QtWidgets.QMessageBox.information(
                self,
                "Khôi Phục Thành Công",
                f"✅ <b>Đã khôi phục thành công toàn bộ cấu hình về phiên bản #{sid}!</b><br><br>"
                f"Hệ thống đã tự động lưu vết sự kiện Rollback này vào Audit Trail.<br>"
                f"Vui lòng đóng và mở lại cửa sổ thiết định để tải lại thông số mới nhất."
            )
            self.reload_history()
        else:
            QtWidgets.QMessageBox.critical(self, "Lỗi Khôi Phục", f"❌ Không thể khôi phục cấu hình:\n\n{msg}")

    def _on_toggle_golden_clicked(self):
        """Bật / tắt đánh dấu Bản chuẩn (Golden Config)."""
        if not self.selected_record:
            QtWidgets.QMessageBox.warning(self, "Chưa Chọn Phiên Bản", "Vui lòng chọn 1 phiên bản để đánh dấu!")
            return

        if self.current_role not in ('full_control', '__admin__'):
            QtWidgets.QMessageBox.warning(self, "Không Đủ Quyền Hạn", "Chỉ tài khoản Toàn Quyền (Full Control) hoặc Administrator mới được phép đánh dấu Bản Chuẩn!")
            return

        sid = self.selected_record['id']
        ok, new_state, msg = toggle_golden_status(self.cursor, self.connection, sid)
        if ok:
            self.reload_history()
            # Tìm lại và chọn đúng dòng vừa toggle
            for r in range(self.table_timeline.rowCount()):
                it = self.table_timeline.item(r, 0)
                if it and int(it.text()) == sid:
                    self.table_timeline.selectRow(r)
                    break
        else:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể cập nhật Bản Chuẩn:\n{msg}")

    def _on_export_csv_clicked(self):
        """Xuất danh sách biến động ra file CSV phục vụ kiểm toán chất lượng."""
        if not self.records_cache:
            QtWidgets.QMessageBox.warning(self, "Trống", "Không có dữ liệu lịch sử để xuất file!")
            return

        default_name = f"Audit_Trail_History_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Lưu Báo Cáo Lịch Sử Biến Động",
            default_name,
            "CSV Files (*.csv);;All Files (*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Thời Gian", "Người Sửa", "Quyền", "Phân Loại", "Camera", "Model ID", "Lý Do Thiết Định", "Điểm Thay Đổi", "Bản Chuẩn Golden"])
                for r in self.records_cache:
                    writer.writerow([
                        r['id'],
                        str(r.get('created_at', '')),
                        r.get('changed_by', ''),
                        r.get('user_role', ''),
                        CATEGORY_MAP.get(r.get('scope_category'), r.get('scope_category')),
                        r.get('camera_id', ''),
                        r.get('model_id', ''),
                        r.get('change_reason', ''),
                        r.get('diff_count', 0),
                        "YES" if r.get('is_golden') else "NO"
                    ])
            QtWidgets.QMessageBox.information(self, "Thành Công", f"Đã xuất thành công {len(self.records_cache)} bản ghi lịch sử ra file:\n{file_path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi Xuất File", f"Không thể ghi file:\n{e}")
