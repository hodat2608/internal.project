"""
app_logger.py - Hệ thống logging tập trung cho Legion Vision System.

Sử dụng:
    from module_3.app_logger import get_logger
    logger = get_logger(__name__)
    logger.info("Camera 1 initialized")
    logger.warning("Retrying connection...")
    logger.error("Camera failed: ...")

Cửa sổ log được tự động mở khi gọi open_log_window() từ entry point.
"""

import logging
import sys
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QComboBox, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QMetaObject, Q_ARG
from PyQt5.QtGui import QFont, QColor, QTextCursor, QTextCharFormat

# ─────────────────────────────────────────────────────────────────────────────
# Qt Signal Bridge – dùng để emit log từ bất kỳ thread nào vào main thread
# ─────────────────────────────────────────────────────────────────────────────
class _LogSignalBridge(QObject):
    log_emitted = pyqtSignal(int, str, str)  # level, logger_name, message


_bridge = _LogSignalBridge()


# ─────────────────────────────────────────────────────────────────────────────
# Custom Handler – gắn vào root logger, forward mọi record sang Qt
# ─────────────────────────────────────────────────────────────────────────────
class _QtHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            _bridge.log_emitted.emit(record.levelno, record.name, msg)
        except Exception:
            pass


_qt_handler = _QtHandler()
_qt_handler.setFormatter(
    logging.Formatter(
        fmt="%(asctime)s  [%(levelname)-8s]  %(name)s  →  %(message)s",
        datefmt="%H:%M:%S"
    )
)
_qt_handler.setLevel(logging.DEBUG)

# Stream handler để vẫn in ra terminal
_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(
    logging.Formatter(fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
)
_stream_handler.setLevel(logging.DEBUG)

import os
from logging.handlers import TimedRotatingFileHandler

# Đường dẫn file log an toàn (tránh lỗi WinError 5)
if getattr(sys, 'frozen', False):
    app_data = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or os.path.expanduser('~')
    log_dir = os.path.join(app_data, 'MBC_Vision_Inspector', 'System_Logs')
else:
    log_dir = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'System_Logs')

os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, 'error_log.txt')

# Sử dụng TimedRotatingFileHandler để tự động cắt file log mỗi nửa đêm (midnight)
# Giữ lại log của 30 ngày gần nhất (backupCount=30)
_file_handler = TimedRotatingFileHandler(log_file_path, when='midnight', interval=1, backupCount=30, encoding='utf-8')
_file_handler.setFormatter(
    logging.Formatter(fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
_file_handler.setLevel(logging.DEBUG)

# Gắn vào root logger một lần duy nhất
_root_logger = logging.getLogger("legion")
_root_logger.setLevel(logging.DEBUG)
if not _root_logger.handlers:
    _root_logger.addHandler(_qt_handler)
    _root_logger.addHandler(_stream_handler)
    _root_logger.addHandler(_file_handler)
    _root_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Lấy logger con của 'legion'. VD: get_logger('main_core')"""
    return _root_logger.getChild(name)


# ─────────────────────────────────────────────────────────────────────────────
# Log Viewer Window
# ─────────────────────────────────────────────────────────────────────────────
_LEVEL_STYLES: dict[int, tuple[str, str]] = {
    logging.DEBUG:    ("#A9B7C6", "DEBUG"),
    logging.INFO:     ("#6A9955", "INFO"),
    logging.WARNING:  ("#CE9178", "WARNING"),
    logging.ERROR:    ("#F44747", "ERROR"),
    logging.CRITICAL: ("#FF0000", "CRITICAL"),
}

_MIN_FILTER = {
    "ALL":      logging.DEBUG,
    "INFO+":    logging.INFO,
    "WARNING+": logging.WARNING,
    "ERROR+":   logging.ERROR,
}


class LogViewerWindow(QMainWindow):
    """Cửa sổ hiển thị log realtime cho Legion Vision System."""

    _instance = None

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🖥  Legion Vision – System Log")
        self.resize(1100, 500)
        self.setMinimumSize(700, 300)
        self._min_level = logging.DEBUG
        self._max_lines = 2000
        self._line_count = 0
        self._all_logs = []  # Lưu toàn bộ log để render lại khi đổi filter
        self._setup_ui()

        _bridge.log_emitted.connect(self._append_log)

    def _setup_ui(self):
        # ── Main widget ──
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        # ── Toolbar ──
        toolbar = QFrame()
        toolbar.setStyleSheet("QFrame { background:#1E1E1E; border-radius:6px; }")
        toolbar.setMaximumHeight(48)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 4, 10, 4)

        title_lbl = QLabel("Legion Vision — System Log")
        title_font = QFont("Segoe UI", 11, QFont.Bold)
        title_lbl.setFont(title_font)
        title_lbl.setStyleSheet("color:#569CD6;")
        toolbar_layout.addWidget(title_lbl)
        toolbar_layout.addStretch()

        # Filter combo
        filter_lbl = QLabel("Filter:")
        filter_lbl.setStyleSheet("color:#CCCCCC; font-size:10px;")
        toolbar_layout.addWidget(filter_lbl)

        self._filter_combo = QComboBox()
        self._filter_combo.addItems(list(_MIN_FILTER.keys()))
        self._filter_combo.setFixedWidth(110)
        self._filter_combo.setStyleSheet("""
            QComboBox { background:#2D2D2D; color:#DCDCDC; border:1px solid #555; border-radius:4px; padding:2px 6px; font-size:10px; }
            QComboBox QAbstractItemView { background:#2D2D2D; color:#DCDCDC; selection-background-color:#3C3F41; }
        """)
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self._filter_combo)

        # Clear button
        btn_clear = QPushButton("  Clear")
        btn_clear.setFixedWidth(80)
        btn_clear.setStyleSheet("""
            QPushButton { background:#3C3F41; color:#DCDCDC; border:1px solid #555; border-radius:4px; padding:4px; font-size:10px; }
            QPushButton:hover { background:#4C5052; }
        """)
        btn_clear.clicked.connect(self._clear)
        toolbar_layout.addWidget(btn_clear)

        root_layout.addWidget(toolbar)

        # ── Log text area ──
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(QFont("Consolas", 9))
        self._text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                border: 1px solid #3C3F41;
                border-radius: 6px;
            }
        """)
        self._text.setLineWrapMode(QTextEdit.NoWrap)
        root_layout.addWidget(self._text)

        # ── Status bar ──
        self._status = QLabel("Sẵn sàng. Đang lắng nghe log...")
        self._status.setStyleSheet("color:#6A9955; font-size:9px; padding:2px 4px;")
        root_layout.addWidget(self._status)

        self.setStyleSheet("QMainWindow { background:#252526; }")

    def _on_filter_changed(self, text: str):
        self._min_level = _MIN_FILTER.get(text, logging.DEBUG)
        self._refresh_logs()

    def _refresh_logs(self):
        """Xóa trắng giao diện và in lại toàn bộ log thỏa mãn Filter"""
        self._text.clear()
        self._line_count = 0
        cursor = self._text.textCursor()
        for level, message, color in self._all_logs:
            if level >= self._min_level:
                fmt = QTextCharFormat()
                fmt.setForeground(QColor(color))
                cursor.movePosition(QTextCursor.End)
                cursor.insertText(message + "\n", fmt)
                self._line_count += 1
        self._text.setTextCursor(cursor)
        self._text.ensureCursorVisible()

    def _append_log(self, level: int, logger_name: str, message: str):
        color, level_tag = _LEVEL_STYLES.get(level, ("#D4D4D4", "LOG"))
        
        # Lưu vào danh sách tổng
        self._all_logs.append((level, message, color))
        if len(self._all_logs) > self._max_lines:
            self._all_logs.pop(0)

        # Nếu không thỏa mãn filter hiện tại thì không in ra (chỉ lưu ẩn)
        if level < self._min_level:
            return

        # Xóa bớt trên UI nếu quá dòng
        if self._line_count >= self._max_lines:
            cursor = self._text.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, 200)
            cursor.removeSelectedText()
            self._line_count -= 200

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(message + "\n", fmt)
        self._text.setTextCursor(cursor)
        self._text.ensureCursorVisible()
        self._line_count += 1
        self._status.setText(f"Dòng cuối: {message[:80]}...")

    def _clear(self):
        self._text.clear()
        self._all_logs.clear()
        self._line_count = 0
        self._status.setText("Đã xóa log.")

    def closeEvent(self, event):
        # Ẩn thay vì đóng để log vẫn tiếp tục hoạt động
        event.ignore()
        self.hide()


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
_log_window: LogViewerWindow | None = None


def open_log_window() -> LogViewerWindow:
    """
    Tạo (hoặc lấy lại) cửa sổ log và hiển thị nó.
    Gọi hàm này một lần duy nhất khi khởi động ứng dụng.
    """
    global _log_window
    if _log_window is None:
        _log_window = LogViewerWindow()
    _log_window.show()
    _log_window.raise_()
    return _log_window
