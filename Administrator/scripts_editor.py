# -*- coding: utf-8 -*-
"""
AI Vision - Integrated Script IDE (Professional Edition)
=======================================================
Nâng cấp từ scripts_editor.py gốc, giữ nguyên:
  * DeveloperAuthDialog (SHA-256), CustomFileFilterProxyModel, PythonHighlighter,
    CodeEditor, FindReplaceWidget, IDEWindow, open_scripts_editor(...)

Tính năng mới:
  * Nhiều tab, đánh dấu chưa lưu, tự phát hiện file bị sửa bên ngoài, khôi phục phiên làm việc
  * Highlight đầy đủ (chuỗi nhiều dòng, decorator, builtins, self...), theme Light/Dark
  * Soạn thảo thông minh: auto-indent, auto-close ngoặc/nháy, comment, move/duplicate/delete line,
    bracket matching, smart Home/Backspace, zoom Ctrl+Wheel
  * Autocomplete (từ khóa + từ trong file; dùng `jedi` nếu có), lint live (pyflakes nếu có)
  * Find/Replace (Aa / từ nguyên / regex, đếm kết quả), Find in Files, Go to Line,
    Quick Open (Ctrl+P), Command Palette (Ctrl+Shift+P), Outline (class/def)
  * Run / Debug (pdb + breakpoint) / Stop, console có stdin, click traceback để nhảy tới dòng
  * Format (black / autopep8), cài pip package, chọn interpreter, menu chuột phải cho Explorer

Phụ thuộc bắt buộc: PyQt5.  Tùy chọn: jedi, pyflakes, black hoặc autopep8
"""
import os
import re
import ast
import sys
import glob
import time
import shutil
import codecs
import hashlib
import keyword
import builtins
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QTextEdit,
    QFileDialog, QMessageBox, QDialog, QLabel, QLineEdit, QPushButton, QAction, QToolBar,
    QStatusBar, QInputDialog, QSplitter, QTreeView, QFileSystemModel, QTabWidget,
    QStackedWidget, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem, QCheckBox, QMenu, QCompleter
)
from PyQt5.QtCore import (
    Qt, QRect, QSize, QPoint, QSortFilterProxyModel, QProcess, QProcessEnvironment, QSettings,
    QTimer, QFileSystemWatcher, QStringListModel, pyqtSignal, QUrl, QEvent
)
from PyQt5.QtGui import (
    QColor, QPainter, QTextFormat, QFont, QSyntaxHighlighter, QTextCharFormat, QKeySequence,
    QTextCursor, QTextOption, QDesktopServices
)

try:                                    # tùy chọn: gợi ý code thông minh
    import jedi
except Exception:
    jedi = None
try:                                    # tùy chọn: phân tích tĩnh
    from pyflakes import api as _pf_api
except Exception:
    _pf_api = None

# =========================================================================
# HẰNG SỐ & THEME
# =========================================================================
PY_KEYWORDS = list(keyword.kwlist)
PY_BUILTINS = sorted(n for n in dir(builtins) if not n.startswith("_"))
JUNK_DIRS = {"_internal", "__pycache__", "build", "dist", ".git", ".vscode", ".idea", "venv",
             ".venv", "node_modules", ".mypy_cache", ".pytest_cache", ".ide_backups"}
TEXT_EXTS = (".py", ".pyw", ".json", ".txt", ".ini", ".cfg", ".toml", ".yaml", ".yml", ".md",
             ".csv", ".html", ".css", ".js", ".sql", ".bat", ".sh", ".qss", ".ui")
PAIRS = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}
OPEN_B = {"(": ")", "[": "]", "{": "}"}
CLOSE_B = {")": "(", "]": "[", "}": "{"}
MAX_BACKUPS = 10

THEMES = {
    "Light": dict(bg="#FFFFFF", fg="#1E1E1E", gutter_bg="#F0F0F0", gutter_fg="#2B91AF",
                  curline="#F3F3F3", sel="#ADD6FF", keyword="#0000FF", builtin="#267F99",
                  string="#A31515", comment="#008000", number="#098658", func="#795E26",
                  deco="#AF00DB", cls="#267F99", self_="#001080", panel_bg="#F8FAFC",
                  toolbar_bg="#EEF2F7", tab_bg="#E2E8F0", input_bg="#FFFFFF", btn_bg="#E2E8F0",
                  border="#CBD5E1", accent="#2563EB", bracket="#BAD7FF", found="#FFE08A",
                  err="#E11D48", warn="#D97706", debug_line="#FFF59D"),
    "Dark": dict(bg="#1E1E1E", fg="#D4D4D4", gutter_bg="#252526", gutter_fg="#858585",
                 curline="#2A2D2E", sel="#264F78", keyword="#569CD6", builtin="#4EC9B0",
                 string="#CE9178", comment="#6A9955", number="#B5CEA8", func="#DCDCAA",
                 deco="#C586C0", cls="#4EC9B0", self_="#9CDCFE", panel_bg="#252526",
                 toolbar_bg="#333333", tab_bg="#2D2D2D", input_bg="#3C3C3C", btn_bg="#3C3C3C",
                 border="#3F3F46", accent="#0E639C", bracket="#515C6A", found="#614D00",
                 err="#F14C4C", warn="#CCA700", debug_line="#5C5000"),
    "VS Code Dark+": dict(bg="#1E1E1E", fg="#D4D4D4", gutter_bg="#1E1E1E", gutter_fg="#858585",
                 curline="#282828", sel="#264F78", keyword="#569CD6", builtin="#4EC9B0",
                 string="#CE9178", comment="#6A9955", number="#B5CEA8", func="#DCDCAA",
                 deco="#C586C0", cls="#4EC9B0", self_="#9CDCFE", panel_bg="#252526",
                 toolbar_bg="#333333", tab_bg="#2D2D2D", input_bg="#3C3C3C", btn_bg="#3C3C3C",
                 border="#3F3F46", accent="#007ACC", bracket="#515C6A", found="#614D00",
                 err="#F14C4C", warn="#CCA700", debug_line="#5C5000"),
    "Monokai": dict(bg="#272822", fg="#F8F8F2", gutter_bg="#272822", gutter_fg="#90908A",
                 curline="#3E3D32", sel="#49483E", keyword="#F92672", builtin="#66D9EF",
                 string="#E6DB74", comment="#75715E", number="#AE81FF", func="#A6E22E",
                 deco="#FD971F", cls="#A6E22E", self_="#FD971F", panel_bg="#1E1F1C",
                 toolbar_bg="#272822", tab_bg="#1E1F1C", input_bg="#272822", btn_bg="#272822",
                 border="#3E3D32", accent="#F92672", bracket="#49483E", found="#E6DB74",
                 err="#F92672", warn="#FD971F", debug_line="#75715E"),
    "GitHub Light": dict(bg="#FFFFFF", fg="#24292E", gutter_bg="#FFFFFF", gutter_fg="#B3B3B3",
                 curline="#F6F8FA", sel="#B3D4FC", keyword="#D73A49", builtin="#005CC5",
                 string="#032F62", comment="#6A737D", number="#005CC5", func="#6F42C1",
                 deco="#D73A49", cls="#6F42C1", self_="#E36209", panel_bg="#F6F8FA",
                 toolbar_bg="#FFFFFF", tab_bg="#F6F8FA", input_bg="#FFFFFF", btn_bg="#FAFBFC",
                 border="#E1E4E8", accent="#0366D6", bracket="#D73A49", found="#FFF275",
                 err="#CB2431", warn="#B08800", debug_line="#FFFBD7"),
}


def build_qss(t):
    return f"""
QMainWindow, QDialog {{ background:{t['panel_bg']}; }}
QWidget {{ color:{t['fg']}; }}
QMenuBar, QMenu, QToolBar, QStatusBar {{ background:{t['toolbar_bg']}; color:{t['fg']}; }}
QMenu::item:selected, QMenuBar::item:selected {{ background:{t['accent']}; color:white; }}
QToolBar {{ border:none; spacing:2px; }}
QToolButton:hover {{ background:{t['accent']}; color:white; }}
QPlainTextEdit {{ background:{t['bg']}; color:{t['fg']}; selection-background-color:{t['sel']};
                  selection-color:{t['fg']}; border:none; }}
QTreeView, QTreeWidget, QListWidget {{ background:{t['panel_bg']}; color:{t['fg']}; border:none; }}
QTreeView::item:selected, QTreeWidget::item:selected, QListWidget::item:selected
    {{ background:{t['accent']}; color:white; }}
QHeaderView::section {{ background:{t['tab_bg']}; color:{t['fg']}; border:none; padding:3px; }}
QTabWidget::pane {{ border:none; }}
QTabBar::tab {{ background:{t['tab_bg']}; color:{t['fg']}; padding:6px 12px;
                border-right:1px solid {t['border']}; }}
QTabBar::tab:selected {{ background:{t['bg']}; border-top:2px solid {t['accent']}; }}
QLineEdit {{ background:{t['input_bg']}; color:{t['fg']}; border:1px solid {t['border']}; padding:3px; }}
QPushButton {{ background:{t['btn_bg']}; border:1px solid {t['border']}; padding:3px 8px;
               border-radius:3px; }}
QPushButton:hover {{ background:{t['accent']}; color:white; }}
QPushButton:checked {{ background:{t['accent']}; color:white; }}
QSplitter::handle {{ background:{t['border']}; }}
QCheckBox {{ spacing:4px; }}
QToolTip {{ background:{t['panel_bg']}; color:{t['fg']}; border:1px solid {t['border']}; }}
#findBox {{ background:{t['panel_bg']}; border:1px solid {t['border']}; }}
"""


def default_python():
    if not getattr(sys, "frozen", False):
        return sys.executable
    return shutil.which("python") or shutil.which("python3") or ""


def iter_project_files(root, exts=TEXT_EXTS, limit=20000):
    n = 0
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in JUNK_DIRS and not d.endswith(".egg-info")]
        for fn in fns:
            if fn.lower().endswith(exts):
                yield os.path.join(dp, fn)
                n += 1
                if n >= limit:
                    return


def norm(path):
    return os.path.normcase(os.path.abspath(path))


# =========================================================================
# BẢO MẬT: XÁC THỰC DEVELOPER BẰNG SHA-256 HASH  (giữ nguyên)
# =========================================================================
class DeveloperAuthDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Developer Authentication")
        self.setFixedSize(400, 180)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.authenticated = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        lbl_title = QLabel("🔒 TRUY CẬP HỆ THỐNG MÃ NGUỒN")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #DC2626;")
        lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_title)

        lbl_desc = QLabel("Cảnh báo: Việc chỉnh sửa mã nguồn có thể gây hỏng toàn bộ phần mềm.\n"
                          "Vui lòng nhập Master Developer Key để tiếp tục.")
        lbl_desc.setStyleSheet("color: #475569; font-size: 11px;")
        lbl_desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_desc)

        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("Nhập Developer Key...")
        self.key_input.setStyleSheet("padding: 5px; font-size: 12px; border: 1px solid #CBD5E1; border-radius: 3px;")
        layout.addWidget(self.key_input)

        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Hủy bỏ")
        self.btn_login = QPushButton("Xác thực")
        self.btn_login.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold;")

        btn_cancel.clicked.connect(self.reject)
        self.btn_login.clicked.connect(self._verify)
        self.key_input.returnPressed.connect(self._verify)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(self.btn_login)
        layout.addLayout(btn_layout)

    def _verify(self):
        EXPECTED_HASH = "96cae35ce8a9b0244178bf28e4966c2ce1b8385723a96a6b838858cdd6ca0a1e"
        user_input_hash = hashlib.sha256(self.key_input.text().encode("utf-8")).hexdigest()
        if user_input_hash == EXPECTED_HASH:
            self.authenticated = True
            self.accept()
        else:
            QMessageBox.critical(self, "Lỗi xác thực", "Sai Developer Key. Từ chối truy cập!")
            self.key_input.clear()


# =========================================================================
# FILE FILTER PROXY MODEL (ẨN RÁC PYINSTALLER)
# =========================================================================
class CustomFileFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_all = False

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        file_name = model.fileName(index)

        if model.isDir(index):
            if file_name in JUNK_DIRS or file_name.endswith(".egg-info"):
                return False
        elif not self.show_all:
            if not file_name.lower().endswith(TEXT_EXTS):
                return False
        elif file_name.lower().endswith((".pyc", ".pyo")):
            return False
        return super().filterAcceptsRow(source_row, source_parent)


# =========================================================================
# PHÂN TÍCH LỖI (LINT)
# =========================================================================
class _FlakeCollector:
    def __init__(self):
        self.msgs = []

    def unexpectedError(self, filename, msg):
        self.msgs.append((1, 0, "error", str(msg)))

    def syntaxError(self, filename, msg, lineno, offset, text):
        self.msgs.append((lineno or 1, offset or 0, "error", str(msg)))

    def flake(self, message):
        try:
            text = message.message % message.message_args
        except Exception:
            text = str(message)
        self.msgs.append((message.lineno, getattr(message, "col", 0), "warning", text))


def analyze_code(code, filename="<string>"):
    """Trả về list (line, col, 'error'|'warning', message)."""
    try:
        compile(code, filename, "exec", dont_inherit=True)
    except SyntaxError as e:
        return [(e.lineno or 1, e.offset or 0, "error", e.msg)]
    except Exception as e:  # ví dụ: null bytes
        return [(1, 0, "error", str(e))]
    if _pf_api is None:
        return []
    col = _FlakeCollector()
    try:
        _pf_api.check(code, filename, col)
    except Exception:
        pass
    return col.msgs


# =========================================================================
# SYNTAX HIGHLIGHTING
# =========================================================================
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document, theme):
        super().__init__(document)
        self.set_theme(theme, rehighlight=False)

    @staticmethod
    def _fmt(color, bold=False, italic=False):
        f = QTextCharFormat()
        f.setForeground(QColor(color))
        if bold:
            f.setFontWeight(QFont.Bold)
        if italic:
            f.setFontItalic(True)
        return f

    def set_theme(self, t, rehighlight=True):
        F = self._fmt
        self.f_keyword = F(t["keyword"], bold=True)
        self.f_builtin = F(t["builtin"])
        self.f_string = F(t["string"])
        self.f_comment = F(t["comment"], italic=True)
        self.f_number = F(t["number"])
        self.f_func = F(t["func"])
        self.f_cls = F(t["cls"], bold=True)
        self.f_deco = F(t["deco"])
        self.f_self = F(t["self_"], italic=True)
        # (regex, format, group) - rule đứng sau ghi đè rule đứng trước
        self.rules = [
            (re.compile(r"\b([A-Za-z_]\w*)(?=\s*\()"), self.f_func, 1),
            (re.compile(r"(?<![\w.])(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|"
                        r"\d[\d_]*\.?[\d_]*(?:[eE][+-]?\d+)?j?)\b"), self.f_number, 0),
            (re.compile(r"^\s*(@[\w.]+)"), self.f_deco, 1),
            (re.compile(r"\bdef\s+(\w+)"), self.f_func, 1),
            (re.compile(r"\bclass\s+(\w+)"), self.f_cls, 1),
            (re.compile(r"(?<![.\w])(?:%s)\b" % "|".join(PY_BUILTINS)), self.f_builtin, 0),
            (re.compile(r"\b(?:self|cls)\b"), self.f_self, 0),
            (re.compile(r"\b(?:%s)\b" % "|".join(PY_KEYWORDS)), self.f_keyword, 0),
        ]
        if rehighlight:
            self.rehighlight()

    @staticmethod
    def _find_end(text, start, quote):
        j, n = start, len(text)
        while j < n:
            if text[j] == "\\":
                j += 2
                continue
            if text.startswith(quote, j):
                return j
            j += 1
        return -1

    def highlightBlock(self, text):
        self.setCurrentBlockState(0)
        for rx, fmt, grp in self.rules:
            for m in rx.finditer(text):
                if m.start(grp) >= 0:
                    self.setFormat(m.start(grp), m.end(grp) - m.start(grp), fmt)

        n, i = len(text), 0
        prev = self.previousBlockState()
        if prev in (1, 2):                       # đang trong chuỗi ''' hoặc """
            q = "'''" if prev == 1 else '"""'
            end = self._find_end(text, 0, q)
            if end < 0:
                self.setFormat(0, n, self.f_string)
                self.setCurrentBlockState(prev)
                return
            self.setFormat(0, end + 3, self.f_string)
            i = end + 3
        while i < n:
            c = text[i]
            if c == "#":
                self.setFormat(i, n - i, self.f_comment)
                return
            if c in "\"'":
                s = i
                while s > 0 and i - s < 2 and text[s - 1] in "rRbBfFuU":
                    s -= 1
                q3 = c * 3
                if text.startswith(q3, i):
                    end = self._find_end(text, i + 3, q3)
                    if end < 0:
                        self.setFormat(s, n - s, self.f_string)
                        self.setCurrentBlockState(1 if c == "'" else 2)
                        return
                    self.setFormat(s, end + 3 - s, self.f_string)
                    i = end + 3
                else:
                    end = self._find_end(text, i + 1, c)
                    stop = n if end < 0 else end + 1
                    self.setFormat(s, stop - s, self.f_string)
                    i = stop
                continue
            i += 1


# =========================================================================
# CODE EDITOR
# =========================================================================
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)

    def mousePressEvent(self, event):
        self.codeEditor.gutter_click(event.y())


class CodeEditor(QPlainTextEdit):
    zoomRequested = pyqtSignal(int)

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.path = None
        self.encoding = "utf-8"
        self.eol = "\n"
        self.mtime = 0.0
        self.breakpoints = set()
        self.diagnostics = []
        self.debug_line = None
        self._search_spans = []
        self._comp_ctx = None

        self.lineNumberArea = LineNumberArea(self)
        self.highlighter = PythonHighlighter(self.document(), theme)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.refresh_extras)

        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.set_font_size(11)

        self.completer = QCompleter(self)
        self.completer_model = QStringListModel(self)
        self.completer.setModel(self.completer_model)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.activated[str].connect(self.insert_completion)

        self.updateLineNumberAreaWidth(0)
        self.refresh_extras()

    # ---------------- cấu hình ----------------
    def set_font_size(self, size):
        f = self.font()
        f.setPointSize(size)
        self.setFont(f)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))
        self.updateLineNumberAreaWidth(0)

    def apply_theme(self, theme):
        self.theme = theme
        self.highlighter.set_theme(theme)
        self.lineNumberArea.update()
        self.refresh_extras()

    def set_language(self, is_python):
        self.highlighter.setDocument(self.document() if is_python else None)

    def set_diagnostics(self, diags):
        self.diagnostics = diags
        self.lineNumberArea.update()
        self.refresh_extras()

    def set_search_highlights(self, spans):
        self._search_spans = spans
        self.refresh_extras()

    def set_debug_line(self, line):
        self.debug_line = line
        self.refresh_extras()

    def goto_line(self, line, col=0, focus=True):
        block = self.document().findBlockByNumber(max(0, line - 1))
        if not block.isValid():
            block = self.document().lastBlock()
        cur = QTextCursor(block)
        cur.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, min(col, max(0, block.length() - 1)))
        self.setTextCursor(cur)
        self.centerCursor()
        if focus:
            self.setFocus()

    # ---------------- gutter ----------------
    def lineNumberAreaWidth(self):
        digits = len(str(max(1, self.blockCount())))
        return 26 + self.fontMetrics().horizontalAdvance("9") * digits

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def gutter_click(self, y):
        line = self.cursorForPosition(QPoint(0, y)).blockNumber() + 1
        self.breakpoints.symmetric_difference_update({line})
        self.lineNumberArea.update()

    def toggle_breakpoint(self):
        self.breakpoints.symmetric_difference_update({self.textCursor().blockNumber() + 1})
        self.lineNumberArea.update()

    def lineNumberAreaPaintEvent(self, event):
        t = self.theme
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor(t["gutter_bg"]))
        diag = {}
        for ln, _c, sev, _m in self.diagnostics:
            if diag.get(ln) != "error":
                diag[ln] = sev
        cur_line = self.textCursor().blockNumber()
        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        fh = self.fontMetrics().height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                ln = num + 1
                if ln in diag:
                    painter.fillRect(0, int(top), 3, int(bottom - top),
                                     QColor(t["err"] if diag[ln] == "error" else t["warn"]))
                if ln in self.breakpoints:
                    painter.setBrush(QColor("#E51400"))
                    painter.setPen(Qt.NoPen)
                    painter.drawEllipse(6, int(top + (fh - 10) / 2), 10, 10)
                painter.setPen(QColor(t["fg"] if num == cur_line else t["gutter_fg"]))
                painter.drawText(0, int(top), self.lineNumberArea.width() - 5, fh,
                                 Qt.AlignRight | Qt.AlignVCenter, str(ln))
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            num += 1

    # ---------------- extra selections ----------------
    def _sel(self, cursor, color=None, full=False, wave=None):
        s = QTextEdit.ExtraSelection()
        if color:
            s.format.setBackground(QColor(color))
        if full:
            s.format.setProperty(QTextFormat.FullWidthSelection, True)
        if wave:
            s.format.setUnderlineStyle(QTextCharFormat.WaveUnderline)
            s.format.setUnderlineColor(QColor(wave))
        s.cursor = cursor
        return s

    def _span_cursor(self, a, b):
        c = QTextCursor(self.document())
        c.setPosition(a)
        c.setPosition(b, QTextCursor.KeepAnchor)
        return c

    def _match_bracket(self):
        doc = self.document()
        pos = self.textCursor().position()
        for p in (pos, pos - 1):
            if p < 0:
                continue
            ch = doc.characterAt(p)
            if ch in OPEN_B:
                step, target = 1, OPEN_B[ch]
            elif ch in CLOSE_B:
                step, target = -1, CLOSE_B[ch]
            else:
                continue
            depth, q, limit = 0, p, 30000
            while 0 <= q < doc.characterCount() and limit > 0:
                c = doc.characterAt(q)
                if c == ch:
                    depth += 1
                elif c == target:
                    depth -= 1
                    if depth == 0:
                        return p, q
                q += step
                limit -= 1
        return None

    def refresh_extras(self):
        t, sels = self.theme, []
        if not self.isReadOnly():
            c = self.textCursor()
            c.clearSelection()
            sels.append(self._sel(c, t["curline"], full=True))
        if self.debug_line:
            blk = self.document().findBlockByNumber(self.debug_line - 1)
            if blk.isValid():
                sels.append(self._sel(QTextCursor(blk), t["debug_line"], full=True))
        for a, b in self._search_spans[:1500]:
            sels.append(self._sel(self._span_cursor(a, b), t["found"]))
        m = self._match_bracket()
        if m:
            for p in m:
                sels.append(self._sel(self._span_cursor(p, p + 1), t["bracket"]))
        for ln, _c, sev, _msg in self.diagnostics[:200]:
            blk = self.document().findBlockByNumber(ln - 1)
            if not blk.isValid():
                continue
            txt = blk.text()
            ind = len(txt) - len(txt.lstrip())
            end = len(txt.rstrip())
            if end > ind:
                sels.append(self._sel(self._span_cursor(blk.position() + ind, blk.position() + end),
                                      wave=t["err"] if sev == "error" else t["warn"]))
        self.setExtraSelections(sels)

    # ---------------- thao tác dòng ----------------
    def _line_range(self):
        cur = self.textCursor()
        doc = self.document()
        s = doc.findBlock(cur.selectionStart()).blockNumber()
        end_pos = cur.selectionEnd()
        e_block = doc.findBlock(end_pos)
        e = e_block.blockNumber()
        if cur.hasSelection() and end_pos == e_block.position() and e > s:
            e -= 1
        return s, e

    def toggle_comment(self):
        s, e = self._line_range()
        doc = self.document()
        blocks = [doc.findBlockByNumber(i) for i in range(s, e + 1)]
        non_empty = [b for b in blocks if b.text().strip()]
        all_commented = bool(non_empty) and all(b.text().strip().startswith("#") for b in non_empty)
        cur = self.textCursor()
        cur.beginEditBlock()
        for b in blocks:
            t = b.text()
            if not t.strip():
                continue
            ind = len(t) - len(t.lstrip())
            c = QTextCursor(b)
            c.setPosition(b.position() + ind)
            if all_commented:
                c.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 2 if t[ind:ind + 2] == "# " else 1)
                c.removeSelectedText()
            else:
                c.insertText("# ")
        cur.endEditBlock()

    def indent(self):
        cur = self.textCursor()
        if cur.hasSelection() and self._line_range()[0] != self._line_range()[1]:
            s, e = self._line_range()
            cur.beginEditBlock()
            for i in range(s, e + 1):
                b = self.document().findBlockByNumber(i)
                if b.text().strip():
                    QTextCursor(b).insertText("    ")
            cur.endEditBlock()
        else:
            col = cur.positionInBlock()
            cur.insertText(" " * (4 - col % 4))

    def unindent(self):
        s, e = self._line_range()
        cur = self.textCursor()
        cur.beginEditBlock()
        for i in range(s, e + 1):
            b = self.document().findBlockByNumber(i)
            t = b.text()
            n = 0
            if t.startswith("\t"):
                n = 1
            else:
                while n < 4 and n < len(t) and t[n] == " ":
                    n += 1
            if n:
                c = QTextCursor(b)
                c.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, n)
                c.removeSelectedText()
        cur.endEditBlock()

    def duplicate_line(self):
        s, e = self._line_range()
        doc = self.document()
        text = "\n".join(doc.findBlockByNumber(i).text() for i in range(s, e + 1))
        last = doc.findBlockByNumber(e)
        c = self.textCursor()
        c.beginEditBlock()
        c.setPosition(last.position() + last.length() - 1)
        c.insertText("\n" + text)
        c.endEditBlock()
        self.setTextCursor(c)

    def delete_line(self):
        s, e = self._line_range()
        doc = self.document()
        first, last = doc.findBlockByNumber(s), doc.findBlockByNumber(e)
        c = self.textCursor()
        c.beginEditBlock()
        if last.next().isValid():
            c.setPosition(first.position())
            c.setPosition(last.position() + last.length(), QTextCursor.KeepAnchor)
        else:
            start = max(0, first.position() - 1)
            c.setPosition(start)
            c.setPosition(last.position() + last.length() - 1, QTextCursor.KeepAnchor)
        c.removeSelectedText()
        c.endEditBlock()
        self.setTextCursor(c)

    def move_lines(self, d):
        s, e = self._line_range()
        doc = self.document()
        if (d < 0 and s == 0) or (d > 0 and e >= doc.blockCount() - 1):
            return
        first, last = doc.findBlockByNumber(s), doc.findBlockByNumber(e)
        block_text = "\n".join(doc.findBlockByNumber(i).text() for i in range(s, e + 1))
        c = self.textCursor()
        c.beginEditBlock()
        if d < 0:
            nb = first.previous()
            region_start = nb.position()
            region_end = last.position() + last.length() - 1
            new = block_text + "\n" + nb.text()
            sel_start = region_start
        else:
            nb = last.next()
            region_start = first.position()
            region_end = nb.position() + nb.length() - 1
            new = nb.text() + "\n" + block_text
            sel_start = region_start + len(nb.text()) + 1
        c.setPosition(region_start)
        c.setPosition(region_end, QTextCursor.KeepAnchor)
        c.insertText(new)
        c.endEditBlock()
        c.setPosition(sel_start)
        c.setPosition(sel_start + len(block_text), QTextCursor.KeepAnchor)
        self.setTextCursor(c)

    # ---------------- bàn phím ----------------
    def _smart_newline(self):
        cur = self.textCursor()
        cur.beginEditBlock()
        if cur.hasSelection():
            cur.removeSelectedText()
        text, pos = cur.block().text(), cur.positionInBlock()
        before, after = text[:pos], text[pos:]
        indent = re.match(r"[ \t]*", text).group()
        stripped = before.rstrip()
        if stripped and stripped[-1] in OPEN_B and after.lstrip()[:1] == OPEN_B[stripped[-1]]:
            cur.insertText("\n" + indent + "    " + "\n" + indent)
            cur.movePosition(QTextCursor.Up)
            cur.movePosition(QTextCursor.EndOfLine)
        else:
            extra = ""
            if stripped and not stripped.lstrip().startswith("#") and (stripped[-1] == ":" or stripped[-1] in OPEN_B):
                extra = "    "
            elif re.match(r"\s*(return|pass|break|continue|raise)\b", before) and len(indent) >= 4:
                indent = indent[:-4]
            cur.insertText("\n" + indent + extra)
        cur.endEditBlock()
        self.setTextCursor(cur)
        self.ensureCursorVisible()

    def _smart_backspace(self):
        cur = self.textCursor()
        if cur.hasSelection():
            return False
        text, pos = cur.block().text(), cur.positionInBlock()
        if 0 < pos < len(text) and text[pos - 1] in PAIRS and PAIRS[text[pos - 1]] == text[pos]:
            cur.beginEditBlock()
            cur.deletePreviousChar()
            cur.deleteChar()
            cur.endEditBlock()
            return True
        if pos > 0 and text[:pos].strip() == "" and " " in text[:pos]:
            n = pos % 4 or 4
            cur.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, n)
            cur.removeSelectedText()
            return True
        return False

    def keyPressEvent(self, e):
        popup = self.completer.popup()
        k, mods, text = e.key(), e.modifiers(), e.text()
        if popup.isVisible() and k in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab, Qt.Key_Escape, Qt.Key_Backtab):
            e.ignore()
            return
        if k == Qt.Key_Space and mods & Qt.ControlModifier:
            self.show_completions(force=True)
            return
        plain = not (mods & (Qt.ControlModifier | Qt.AltModifier))
        if k in (Qt.Key_Return, Qt.Key_Enter) and not (mods & Qt.ControlModifier):
            self._smart_newline()
            return
        if k == Qt.Key_Tab and plain:
            self.indent()
            return
        if k == Qt.Key_Backtab:
            self.unindent()
            return
        if k == Qt.Key_Backspace and plain and self._smart_backspace():
            return
        if k == Qt.Key_Home and plain:
            cur = self.textCursor()
            t = cur.block().text()
            first = len(t) - len(t.lstrip())
            target = first if cur.positionInBlock() != first else 0
            cur.setPosition(cur.block().position() + target,
                            QTextCursor.KeepAnchor if mods & Qt.ShiftModifier else QTextCursor.MoveAnchor)
            self.setTextCursor(cur)
            return
        if text and plain and len(text) == 1 and (text in PAIRS or text in CLOSE_B):
            if self._auto_pair(text):
                return
        super().keyPressEvent(e)
        if text and plain and (text.isalnum() or text in "._"):
            self.show_completions(force=False)
        elif popup.isVisible():
            popup.hide()

    def _auto_pair(self, ch):
        cur = self.textCursor()
        line, pos = cur.block().text(), cur.positionInBlock()
        prv = line[pos - 1] if pos > 0 else ""
        nxt = line[pos] if pos < len(line) else ""
        if not cur.hasSelection() and nxt == ch and (ch in CLOSE_B or ch in "\"'"):
            cur.movePosition(QTextCursor.Right)
            self.setTextCursor(cur)
            return True
        if ch not in PAIRS:
            return False
        if cur.hasSelection():
            sel = cur.selectedText().replace("\u2029", "\n")
            cur.insertText(ch + sel + PAIRS[ch])
            return True
        if ch in "\"'":
            if line[max(0, pos - 2):pos] == ch * 2 and nxt != ch:
                cur.insertText(ch + ch * 3)
                cur.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 3)
                self.setTextCursor(cur)
                return True
            if prv.isalnum() or prv in "_\\" or nxt.isalnum():
                return False
        elif nxt and (nxt.isalnum() or nxt == "_"):
            return False
        cur.insertText(ch + PAIRS[ch])
        cur.movePosition(QTextCursor.Left)
        self.setTextCursor(cur)
        return True

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            self.zoomRequested.emit(1 if e.angleDelta().y() > 0 else -1)
            e.accept()
        else:
            super().wheelEvent(e)

    # ---------------- autocomplete ----------------
    def show_completions(self, force=False):
        cur = self.textCursor()
        before = cur.block().text()[:cur.positionInBlock()]
        m = re.search(r"[A-Za-z_]\w*$", before)
        prefix = m.group() if m else ""
        head = before[:len(before) - len(prefix)]
        after_dot = head.endswith(".")
        popup = self.completer.popup()
        if not force and not after_dot and len(prefix) < 2:
            popup.hide()
            return
        ctx = (cur.blockNumber(), len(head))
        if not (popup.isVisible() and ctx == self._comp_ctx):
            items = []
            if jedi is not None and (force or after_dot):
                try:
                    comps = jedi.Script(self.toPlainText(), path=self.path).complete(
                        cur.blockNumber() + 1, cur.positionInBlock() - len(prefix))
                    items = [c.name for c in comps][:300]
                except Exception:
                    items = []
            if not items and not after_dot:
                words = set(re.findall(r"[A-Za-z_]\w{2,}", self.toPlainText()))
                items = sorted((set(PY_KEYWORDS) | set(PY_BUILTINS) | words) - {prefix})
            if not items:
                popup.hide()
                return
            self.completer_model.setStringList(items)
            self._comp_ctx = ctx
        self.completer.setCompletionPrefix(prefix)
        if self.completer.completionCount() == 0:
            popup.hide()
            return
        popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
        rect = self.cursorRect()
        rect.translate(self.lineNumberAreaWidth(), 0)
        rect.setWidth(popup.sizeHintForColumn(0) + popup.verticalScrollBar().sizeHint().width() + 10)
        self.completer.complete(rect)

    def insert_completion(self, completion):
        prefix = self.completer.completionPrefix()
        cur = self.textCursor()
        cur.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, len(prefix))
        cur.insertText(completion)
        self.setTextCursor(cur)


# =========================================================================
# FIND AND REPLACE WIDGET (VS CODE STYLE)
# =========================================================================
class FindReplaceWidget(QWidget):
    MAX_MATCHES = 20000

    def __init__(self, editor=None, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setObjectName("findBox")
        self.setVisible(False)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        find_layout = QHBoxLayout()
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find...")
        self.btn_case = QPushButton("Aa")
        self.btn_word = QPushButton("ab")
        self.btn_regex = QPushButton(".*")
        for b, tip in ((self.btn_case, "Phân biệt hoa/thường"), (self.btn_word, "Khớp từ nguyên"),
                       (self.btn_regex, "Regex")):
            b.setCheckable(True)
            b.setFixedSize(28, 26)
            b.setToolTip(tip)
        self.lbl_count = QLabel("")
        self.lbl_count.setMinimumWidth(70)
        self.btn_next = QPushButton("↓")
        self.btn_prev = QPushButton("↑")
        self.btn_close = QPushButton("✕")
        for btn in (self.btn_next, self.btn_prev, self.btn_close):
            btn.setFixedSize(26, 26)
        for w in (self.find_input, self.btn_case, self.btn_word, self.btn_regex, self.lbl_count,
                  self.btn_prev, self.btn_next, self.btn_close):
            find_layout.addWidget(w)

        replace_layout = QHBoxLayout()
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace...")
        self.btn_replace = QPushButton("Replace")
        self.btn_replace_all = QPushButton("All")
        replace_layout.addWidget(self.replace_input)
        replace_layout.addWidget(self.btn_replace)
        replace_layout.addWidget(self.btn_replace_all)

        layout.addLayout(find_layout)
        layout.addLayout(replace_layout)
        self.setFixedWidth(460)

        self.btn_next.clicked.connect(lambda: self.find_next(True))
        self.btn_prev.clicked.connect(lambda: self.find_next(False))
        self.btn_close.clicked.connect(self.close_panel)
        self.btn_replace.clicked.connect(self.replace_current)
        self.btn_replace_all.clicked.connect(self.replace_all)
        self.find_input.returnPressed.connect(lambda: self.find_next(True))
        self.find_input.textChanged.connect(self._on_text_changed)
        for b in (self.btn_case, self.btn_word, self.btn_regex):
            b.toggled.connect(self.update_highlights)

    # -------- tiện ích --------
    def set_editor(self, editor):
        if self.editor is not None and self.editor is not editor:
            try:
                self.editor.set_search_highlights([])
            except RuntimeError:
                pass
        self.editor = editor
        if self.isVisible():
            self.update_highlights()

    def close_panel(self):
        self.hide()
        if self.editor:
            self.editor.set_search_highlights([])
            self.editor.setFocus()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close_panel()
        else:
            super().keyPressEvent(e)

    def _regex(self):
        pat = self.find_input.text()
        if not pat:
            return None
        if not self.btn_regex.isChecked():
            pat = re.escape(pat)
        if self.btn_word.isChecked():
            pat = r"\b" + pat + r"\b"
        flags = 0 if self.btn_case.isChecked() else re.IGNORECASE
        flags |= re.MULTILINE
        try:
            rx = re.compile(pat, flags)
            self.find_input.setStyleSheet("")
            return rx
        except re.error:
            self.find_input.setStyleSheet("border:1px solid #E11D48;")
            return None

    def _matches(self):
        rx = self._regex()
        if rx is None or self.editor is None:
            return []
        out = []
        for m in rx.finditer(self.editor.toPlainText()):
            if m.end() > m.start():
                out.append((m.start(), m.end()))
                if len(out) >= self.MAX_MATCHES:
                    break
        return out

    def update_highlights(self, *_):
        if not self.editor or not self.isVisible():
            return
        spans = self._matches()
        self.editor.set_search_highlights(spans)
        if self.find_input.text():
            self.lbl_count.setText(f"{len(spans)} kết quả" if spans else "Không có")
        else:
            self.lbl_count.setText("")

    def _on_text_changed(self, _):
        self.update_highlights()
        self.find_next(True, incremental=True)

    def find_next(self, forward=True, incremental=False):
        if not self.editor:
            return
        spans = self._matches()
        self.editor.set_search_highlights(spans)
        if not spans:
            self.lbl_count.setText("Không có" if self.find_input.text() else "")
            return
        cur = self.editor.textCursor()
        if forward:
            pos = cur.selectionStart() if incremental else cur.selectionEnd()
            target = next((s for s in spans if s[0] >= pos), spans[0])
        else:
            pos = cur.selectionStart()
            target = next((s for s in reversed(spans) if s[0] < pos), spans[-1])
        c = QTextCursor(self.editor.document())
        c.setPosition(target[0])
        c.setPosition(target[1], QTextCursor.KeepAnchor)
        self.editor.setTextCursor(c)
        self.editor.centerCursor()
        self.lbl_count.setText(f"{spans.index(target) + 1} / {len(spans)}")

    def _expand(self, m):
        rep = self.replace_input.text()
        if self.btn_regex.isChecked():
            try:
                return m.expand(rep)
            except Exception:
                return rep
        return rep

    def replace_current(self):
        rx = self._regex()
        if rx is None or not self.editor:
            return
        cur = self.editor.textCursor()
        sel = cur.selectedText().replace("\u2029", "\n")
        m = rx.fullmatch(sel) if cur.hasSelection() else None
        if m:
            cur.insertText(self._expand(m))
        self.find_next(True)

    def replace_all(self):
        rx = self._regex()
        if rx is None or not self.editor:
            return
        text = self.editor.toPlainText()
        new, count = rx.subn(self._expand, text)
        if count:
            keep = self.editor.textCursor().position()
            c = self.editor.textCursor()
            c.beginEditBlock()
            c.select(QTextCursor.Document)
            c.insertText(new)
            c.endEditBlock()
            c.setPosition(min(keep, len(new)))
            self.editor.setTextCursor(c)
        self.update_highlights()
        self.lbl_count.setText(f"Đã thay thế {count} vị trí")


# =========================================================================
# QUICK PICKER (Quick Open / Command Palette)
# =========================================================================
class QuickPicker(QDialog):
    def __init__(self, parent, title, items):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.resize(600, 380)
        self.items = items
        self.payload = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(title + " ...")
        self.listw = QListWidget()
        lay.addWidget(self.edit)
        lay.addWidget(self.listw)
        self.edit.textChanged.connect(self._filter)
        self.edit.returnPressed.connect(self._accept_current)
        self.listw.itemActivated.connect(lambda _it: self._accept_current())
        self.edit.installEventFilter(self)
        self._filter("")

    @staticmethod
    def _score(q, label):
        l = label.lower()
        if q in l:
            return l.index(q)
        i = 0
        for ch in l:
            if i < len(q) and ch == q[i]:
                i += 1
        return 1000 if i == len(q) else None

    def _filter(self, text):
        q = text.lower().strip()
        self.listw.clear()
        ranked = []
        for label, payload in self.items:
            s = 0 if not q else self._score(q, label)
            if s is not None:
                ranked.append((s, label, payload))
        ranked.sort(key=lambda r: r[0])
        for _s, label, payload in ranked[:300]:
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, payload)
            self.listw.addItem(it)
        if self.listw.count():
            self.listw.setCurrentRow(0)

    def eventFilter(self, obj, ev):
        if obj is self.edit and ev.type() == QEvent.KeyPress and ev.key() in (Qt.Key_Up, Qt.Key_Down):
            row = self.listw.currentRow() + (1 if ev.key() == Qt.Key_Down else -1)
            self.listw.setCurrentRow(max(0, min(row, self.listw.count() - 1)))
            return True
        return super().eventFilter(obj, ev)

    def _accept_current(self):
        it = self.listw.currentItem()
        if it:
            self.payload = it.data(Qt.UserRole)
            self.accept()


# =========================================================================
# CONSOLE / OUTPUT (chạy script, stdin, pdb)
# =========================================================================
class OutputEdit(QPlainTextEdit):
    lineActivated = pyqtSignal(str)

    def mouseDoubleClickEvent(self, e):
        super().mouseDoubleClickEvent(e)
        self.lineActivated.emit(self.cursorForPosition(e.pos()).block().text())


class ConsolePanel(QWidget):
    started = pyqtSignal()
    finished = pyqtSignal(int)
    debugLocation = pyqtSignal(str, int)
    jumpRequested = pyqtSignal(str, int)

    PDB_RE = re.compile(r"^(?:\(Pdb\) )*> (.+?)\((\d+)\)[^\n]*$")
    TB_RE = re.compile(r'File "(.+?)", line (\d+)')

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.debug_bar = QWidget()
        dl = QHBoxLayout(self.debug_bar)
        dl.setContentsMargins(4, 2, 4, 2)
        dl.addWidget(QLabel("Debug (pdb):"))
        for label, cmd in (("▶ Continue", "c"), ("⤵ Step", "s"), ("⏭ Next", "n"),
                           ("⤴ Return", "r"), ("📍 Where", "w"), ("⏹ Quit", "q")):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, c=cmd: self.send(c))
            dl.addWidget(b)
        dl.addStretch()
        self.debug_bar.setVisible(False)

        self.out = OutputEdit()
        self.out.setReadOnly(True)
        self.out.setMaximumBlockCount(20000)
        f = QFont("Consolas", 10)
        f.setStyleHint(QFont.Monospace)
        self.out.setFont(f)
        self.out.lineActivated.connect(self._line_activated)

        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Nhập stdin / lệnh pdb rồi nhấn Enter...")
        self.inp.returnPressed.connect(self._submit)

        lay.addWidget(self.debug_bar)
        lay.addWidget(self.out)
        lay.addWidget(self.inp)

        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyRead.connect(self._read)
        self.proc.finished.connect(self._done)
        self.proc.errorOccurred.connect(self._error)
        self.proc.started.connect(self._on_started)
        self._pending = []
        self._buf = ""
        self._t0 = 0.0

    def is_running(self):
        return self.proc.state() != QProcess.NotRunning

    def clear_output(self):
        self.out.clear()

    def append(self, text):
        self.out.moveCursor(QTextCursor.End)
        self.out.insertPlainText(text)
        self.out.moveCursor(QTextCursor.End)

    def run(self, program, args, cwd, pending_input=None, debug=False):
        if self.is_running():
            return False
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        self.proc.setProcessEnvironment(env)
        self.proc.setWorkingDirectory(cwd)
        self._pending = list(pending_input or [])
        self._buf = ""
        self.debug_bar.setVisible(debug)
        self.append(f"$ {program} {' '.join(args)}\n")
        self._t0 = time.time()
        self.proc.start(program, args)
        return True

    def stop(self):
        if self.is_running():
            self.proc.kill()
            self.proc.waitForFinished(1500)

    def send(self, text):
        if self.is_running():
            self.append(text + "\n")
            self.proc.write((text + "\n").encode("utf-8"))

    def _submit(self):
        self.send(self.inp.text())
        self.inp.clear()

    def _on_started(self):
        for line in self._pending:
            self.proc.write((line + "\n").encode("utf-8"))
        self._pending = []
        self.started.emit()

    def _read(self):
        data = bytes(self.proc.readAll()).decode("utf-8", "replace").replace("\r\n", "\n")
        self.append(data)
        self._buf += data
        *lines, self._buf = self._buf.split("\n")
        for ln in lines:
            m = self.PDB_RE.match(ln)
            if m:
                self.debugLocation.emit(m.group(1), int(m.group(2)))

    def _done(self, code, _status):
        self.append(f"\n[Tiến trình kết thúc với mã {code} sau {time.time() - self._t0:.2f}s]\n")
        self.debug_bar.setVisible(False)
        self.finished.emit(code)

    def _error(self, err):
        if err == QProcess.FailedToStart:
            self.append("[Không thể khởi chạy interpreter. Hãy chọn lại ở Tools ▸ Select Interpreter]\n")

    def _line_activated(self, line):
        m = self.TB_RE.search(line) or self.PDB_RE.match(line)
        if m:
            self.jumpRequested.emit(m.group(1), int(m.group(2)))


# =========================================================================
# MAIN IDE WINDOW
# =========================================================================
class IDEWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Vision - Integrated Script IDE")
        self.resize(1400, 860)
        self.settings = QSettings("AIVision", "ScriptIDE")

        self.theme_name = self.settings.value("theme", "Light")
        if self.theme_name not in THEMES:
            self.theme_name = "Light"
        self.theme = THEMES[self.theme_name]
        self.font_size = int(self.settings.value("font_size", 11))
        self.word_wrap = self.settings.value("word_wrap", False, type=bool)
        self.show_ws = self.settings.value("show_ws", False, type=bool)
        self.interpreter = self.settings.value("interpreter", "") or default_python()

        # Base directory (giữ nguyên logic gốc)
        if getattr(sys, "frozen", False):
            self.root_path = sys._MEIPASS if hasattr(sys, "_MEIPASS") else os.path.dirname(sys.executable)
        else:
            self.root_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        saved_root = self.settings.value("root", "")
        self.tree_root = saved_root if saved_root and os.path.isdir(saved_root) else self.root_path

        self._palette_actions = []
        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self.on_external_change)
        self.lint_timer = QTimer(self, singleShot=True, interval=700)
        self.lint_timer.timeout.connect(self.run_lint)
        self.outline_timer = QTimer(self, singleShot=True, interval=1000)
        self.outline_timer.timeout.connect(self.build_outline)

        self._build_ui()
        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_statusbar()
        self.apply_theme(self.theme_name)
        self._restore_session()
        self.status.showMessage("Ready")

    # =====================================================================
    # UI
    # =====================================================================
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)

        self.vsplit = QSplitter(Qt.Vertical)
        self.hsplit = QSplitter(Qt.Horizontal)
        v.addWidget(self.vsplit)

        # --- SIDEBAR: Explorer + Outline ---
        sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        self.side_tabs = QTabWidget()
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(self.tree_root)
        self.proxy_model = CustomFileFilterProxyModel()
        self.proxy_model.setSourceModel(self.file_model)

        self.tree_view = QTreeView()
        self.tree_view.setModel(self.proxy_model)
        self.set_tree_root(self.tree_root)
        self.tree_view.setColumnWidth(0, 250)
        for c in (1, 2, 3):
            self.tree_view.hideColumn(c)
        self.tree_view.setHeaderHidden(True)
        self.tree_view.clicked.connect(self.on_file_clicked)
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.tree_context_menu)

        self.outline_tree = QTreeWidget()
        self.outline_tree.setHeaderHidden(True)
        self.outline_tree.itemDoubleClicked.connect(self._outline_activated)
        self.outline_tree.itemClicked.connect(self._outline_activated)
        self.side_tabs.addTab(self.tree_view, "Explorer")
        self.side_tabs.addTab(self.outline_tree, "Outline")

        self.btn_settings = QPushButton("⚙️ Settings")
        self.btn_settings.setStyleSheet("text-align: left; padding: 8px; font-weight: bold; border: none;")
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.clicked.connect(self.show_settings_menu)
        
        sidebar_layout.addWidget(self.side_tabs, 1)
        sidebar_layout.addWidget(self.btn_settings)

        # --- VÙNG SOẠN THẢO ---
        editor_area = QWidget()
        el = QVBoxLayout(editor_area)
        el.setContentsMargins(0, 0, 0, 0)
        el.setSpacing(0)
        self.find_widget = FindReplaceWidget(None)
        el.addWidget(self.find_widget, alignment=Qt.AlignTop | Qt.AlignRight)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        welcome = QLabel("Mở file (Ctrl+O) • Quick Open (Ctrl+P) • Command Palette (Ctrl+Shift+P)")
        welcome.setAlignment(Qt.AlignCenter)
        self.stack = QStackedWidget()
        self.stack.addWidget(welcome)
        self.stack.addWidget(self.tabs)
        el.addWidget(self.stack, 1)

        self.hsplit.addWidget(sidebar_widget)
        self.hsplit.addWidget(editor_area)
        self.hsplit.setSizes([300, 1100])
        self.hsplit.setStretchFactor(1, 1)

        # --- PANEL DƯỚI: Output / Problems / Search ---
        self.bottom_tabs = QTabWidget()
        self.console = ConsolePanel()
        self.console.finished.connect(self._on_run_finished)
        self.console.debugLocation.connect(self.on_debug_location)
        self.console.jumpRequested.connect(lambda p, ln: self.open_path(p, ln))
        self.problems = QTreeWidget()
        self.problems.setColumnCount(3)
        self.problems.setHeaderLabels(["", "Dòng", "Mô tả"])
        self.problems.setRootIsDecorated(False)
        self.problems.setColumnWidth(0, 30)
        self.problems.setColumnWidth(1, 60)
        self.problems.itemActivated.connect(self._problem_activated)
        self.problems.itemClicked.connect(self._problem_activated)
        self.bottom_tabs.addTab(self.console, "Output")
        self.bottom_tabs.addTab(self.problems, "Problems")
        self.bottom_tabs.addTab(self._build_search_panel(), "Search")

        self.vsplit.addWidget(self.hsplit)
        self.vsplit.addWidget(self.bottom_tabs)
        self.vsplit.setSizes([620, 220])
        self.vsplit.setStretchFactor(0, 1)

    def _build_search_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        row = QHBoxLayout()
        self.fif_input = QLineEdit()
        self.fif_input.setPlaceholderText("Tìm trong toàn bộ thư mục đang mở...")
        self.fif_case = QCheckBox("Aa")
        self.fif_regex = QCheckBox(".*")
        btn = QPushButton("Tìm")
        row.addWidget(self.fif_input)
        row.addWidget(self.fif_case)
        row.addWidget(self.fif_regex)
        row.addWidget(btn)
        self.fif_results = QTreeWidget()
        self.fif_results.setHeaderHidden(True)
        lay.addLayout(row)
        lay.addWidget(self.fif_results)
        btn.clicked.connect(self.find_in_files)
        self.fif_input.returnPressed.connect(self.find_in_files)
        self.fif_results.itemActivated.connect(self._fif_activated)
        self.fif_results.itemClicked.connect(self._fif_activated)
        return w

    def _create_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.lbl_problems = QLabel("✔ 0  ⚠ 0")
        self.lbl_pos = QLabel("Ln 1, Col 1")
        self.lbl_enc = QLabel("UTF-8")
        self.lbl_eol = QLabel("LF")
        self.lbl_interp = QLabel("")
        for w in (self.lbl_problems, self.lbl_pos, self.lbl_enc, self.lbl_eol, self.lbl_interp):
            self.status.addPermanentWidget(w)
        self._update_interp_label()

    def _update_interp_label(self):
        self.lbl_interp.setText("🐍 " + (os.path.basename(self.interpreter) if self.interpreter else "no interpreter"))
        self.lbl_interp.setToolTip(self.interpreter)

    def show_settings_menu(self):
        menu = QMenu(self)
        menu.addAction("🎨 Color Theme", self.show_theme_picker)
        menu.addAction("⌨️ Keyboard Shortcuts", lambda: QMessageBox.information(self, "Shortcuts", "Ctrl+P: Quick Open\nCtrl+Shift+P: Command Palette\nCtrl+F: Find/Replace\nCtrl+Shift+F: Find in Files\nCtrl+S: Save\nCtrl+/: Toggle Comment\nAlt+Up/Down: Move Line\nCtrl+D: Duplicate Line"))
        menu.addAction("⚙️ Settings", lambda: QMessageBox.information(self, "Settings", "Settings file support sẽ có trong bản tới!"))
        
        pos = self.btn_settings.mapToGlobal(self.btn_settings.rect().bottomLeft())
        pos.setY(pos.y() - menu.sizeHint().height() - self.btn_settings.height())
        menu.exec_(pos)

    def show_theme_picker(self):
        items = [(name, name) for name in THEMES.keys()]
        picker = QuickPicker(self, "Select Color Theme", items)
        if picker.exec_():
            self.apply_theme(picker.payload)

    # =====================================================================
    # ACTIONS / MENUS
    # =====================================================================
    def _act(self, text, slot, shortcut=None, checkable=False, checked=False):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if checkable:
            a.setCheckable(True)
            a.setChecked(checked)
        a.triggered.connect(slot)
        self._palette_actions.append(a)
        return a

    def _ed(self, name, *args):
        def fn(*_):
            ed = self.current_editor()
            if ed:
                getattr(ed, name)(*args)
        return fn

    def _create_actions(self):
        A = self._act
        # File
        self.act_open_folder = A("📁 Open Folder", lambda: self.open_folder(), "Ctrl+Shift+O")
        self.act_open_file = A("📂 Open File", lambda: self.open_file(), "Ctrl+O")
        self.act_new_file = A("📄 New File", lambda: self.new_file(), "Ctrl+N")
        self.act_new_untitled = A("New Untitled", lambda: self.new_untitled(), "Ctrl+Alt+N")
        self.act_save = A("💾 Save File", lambda: self.save_file(), "Ctrl+S")
        self.act_save_as = A("Save As...", lambda: self.save_as(), "Ctrl+Shift+S")
        self.act_save_all = A("Save All", lambda: self.save_all())
        self.act_close_tab = A("Close Tab", lambda: self.close_tab(self.tabs.currentIndex()), "Ctrl+W")
        self.act_quick_open = A("Quick Open...", lambda: self.quick_open(), "Ctrl+P")
        self.act_palette = A("Command Palette...", lambda: self.command_palette(), "Ctrl+Shift+P")
        self.act_next_tab = A("Next Tab", lambda: self._step_tab(1), "Ctrl+PgDown")
        self.act_prev_tab = A("Previous Tab", lambda: self._step_tab(-1), "Ctrl+PgUp")
        # Edit
        self.act_undo = A("↩ Undo", self._ed("undo"), QKeySequence.Undo)
        self.act_redo = A("↪ Redo", self._ed("redo"), QKeySequence.Redo)
        self.act_cut = A("Cut", self._ed("cut"), QKeySequence.Cut)
        self.act_copy = A("Copy", self._ed("copy"), QKeySequence.Copy)
        self.act_paste = A("Paste", self._ed("paste"), QKeySequence.Paste)
        self.act_select_all = A("Select All", self._ed("selectAll"), QKeySequence.SelectAll)
        self.act_find = A("🔍 Find / Replace", lambda: self.show_find_replace(), "Ctrl+F")
        self.act_find_next = A("Find Next", lambda: self.find_widget.find_next(True), "F3")
        self.act_find_prev = A("Find Previous", lambda: self.find_widget.find_next(False), "Shift+F3")
        self.act_find_files = A("Find in Files...", lambda: self.show_find_in_files(), "Ctrl+Shift+F")
        self.act_goto = A("Go to Line...", lambda: self.goto_line_dialog(), "Ctrl+G")
        self.act_comment = A("Toggle Comment", self._ed("toggle_comment"), "Ctrl+/")
        self.act_indent = A("Indent", self._ed("indent"), "Ctrl+]")
        self.act_unindent = A("Unindent", self._ed("unindent"), "Ctrl+[")
        self.act_dup = A("Duplicate Line", self._ed("duplicate_line"), "Ctrl+D")
        self.act_del_line = A("Delete Line", self._ed("delete_line"), "Ctrl+Shift+K")
        self.act_move_up = A("Move Line Up", self._ed("move_lines", -1), "Alt+Up")
        self.act_move_down = A("Move Line Down", self._ed("move_lines", 1), "Alt+Down")
        self.act_complete = A("Trigger Suggestions", self._ed("show_completions", True))
        self.act_format = A("✨ Format Document", lambda: self.format_document(), "Ctrl+Alt+L")
        # View
        self.act_zoom_in = A("Zoom In", lambda: self.zoom(1), "Ctrl+=")
        self.act_zoom_out = A("Zoom Out", lambda: self.zoom(-1), "Ctrl+-")
        self.act_zoom_reset = A("Reset Zoom", lambda: self.zoom(0), "Ctrl+0")
        self.act_theme_light = A("Theme: Light", lambda: self.apply_theme("Light"))
        self.act_theme_dark = A("Theme: Dark", lambda: self.apply_theme("Dark"))
        self.act_wrap = A("Word Wrap", lambda c: self.set_word_wrap(c), "Alt+Z", True, self.word_wrap)
        self.act_ws = A("Show Whitespace", lambda c: self.set_show_ws(c), None, True, self.show_ws)
        self.act_show_all = A("Show All Files in Explorer", lambda c: self._set_show_all(c), None, True, False)
        self.act_toggle_side = A("Toggle Sidebar", lambda: self.side_tabs.setVisible(not self.side_tabs.isVisible()), "Ctrl+B")
        self.act_toggle_panel = A("Toggle Bottom Panel", lambda: self.bottom_tabs.setVisible(not self.bottom_tabs.isVisible()), "Ctrl+J")
        self.act_fullscreen = A("Full Screen", lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen(), "F11")
        # Run / Build
        self.act_run = A("▶ Run", lambda: self.run_current(), "F5")
        self.act_debug = A("🐞 Debug", lambda: self.debug_current(), "F6")
        self.act_stop = A("⏹ Stop", lambda: self.console.stop(), "Shift+F5")
        self.act_bp = A("Toggle Breakpoint", self._ed("toggle_breakpoint"), "F9")
        self.act_bp_clear = A("Clear All Breakpoints", lambda: self.clear_breakpoints())
        self.act_check = A("🔨 Check Syntax", lambda: self.check_syntax(), "F7")
        # Tools
        self.act_interp = A("Select Interpreter...", lambda: self.select_interpreter())
        self.act_pip = A("Install Package (pip)...", lambda: self.pip_install())
        self.act_clear_out = A("Clear Output", lambda: self.console.clear_output())

    def _create_menus(self):
        mb = self.menuBar()
        m = mb.addMenu("File")
        for a in (self.act_open_folder, self.act_open_file, self.act_new_file, self.act_new_untitled,
                  None, self.act_save, self.act_save_as, self.act_save_all, None,
                  self.act_quick_open, self.act_close_tab):
            m.addAction(a) if a else m.addSeparator()
        m = mb.addMenu("Edit")
        for a in (self.act_undo, self.act_redo, None, self.act_cut, self.act_copy, self.act_paste,
                  self.act_select_all, None, self.act_find, self.act_find_next, self.act_find_prev,
                  self.act_find_files, self.act_goto, None, self.act_comment, self.act_indent,
                  self.act_unindent, self.act_dup, self.act_del_line, self.act_move_up,
                  self.act_move_down, None, self.act_complete, self.act_format):
            m.addAction(a) if a else m.addSeparator()
        m = mb.addMenu("View")
        for a in (self.act_palette, None, self.act_theme_light, self.act_theme_dark, None,
                  self.act_zoom_in, self.act_zoom_out, self.act_zoom_reset, None, self.act_wrap,
                  self.act_ws, self.act_show_all, None, self.act_toggle_side, self.act_toggle_panel,
                  self.act_next_tab, self.act_prev_tab, self.act_fullscreen):
            m.addAction(a) if a else m.addSeparator()
        m = mb.addMenu("Run")
        for a in (self.act_run, self.act_debug, self.act_stop, None, self.act_bp, self.act_bp_clear):
            m.addAction(a) if a else m.addSeparator()
        m = mb.addMenu("Build")
        m.addAction(self.act_check)
        m = mb.addMenu("Tools")
        for a in (self.act_interp, self.act_pip, self.act_format, self.act_clear_out):
            m.addAction(a)

    def _create_toolbar(self):
        tb = QToolBar("Main Toolbar")
        tb.setObjectName("mainToolbar")
        self.addToolBar(tb)
        for a in (self.act_open_folder, self.act_open_file, self.act_new_file, self.act_save, None,
                  self.act_undo, self.act_redo, None, self.act_find, self.act_format, None,
                  self.act_run, self.act_debug, self.act_stop, None, self.act_check):
            tb.addAction(a) if a else tb.addSeparator()

    # =====================================================================
    # THEME / VIEW
    # =====================================================================
    def apply_theme(self, name):
        self.theme_name, self.theme = name, THEMES[name]
        self.setStyleSheet(build_qss(self.theme))
        for ed in self.editors():
            ed.apply_theme(self.theme)
        self.settings.setValue("theme", name)

    def zoom(self, d):
        self.font_size = 11 if d == 0 else max(6, min(40, self.font_size + d))
        for ed in self.editors():
            ed.set_font_size(self.font_size)
        self.settings.setValue("font_size", self.font_size)

    def set_word_wrap(self, on):
        self.word_wrap = bool(on)
        for ed in self.editors():
            ed.setLineWrapMode(QPlainTextEdit.WidgetWidth if on else QPlainTextEdit.NoWrap)
        self.settings.setValue("word_wrap", self.word_wrap)

    def set_show_ws(self, on):
        self.show_ws = bool(on)
        for ed in self.editors():
            opt = ed.document().defaultTextOption()
            flags = opt.flags()
            opt.setFlags(flags | QTextOption.ShowTabsAndSpaces if on else flags & ~QTextOption.ShowTabsAndSpaces)
            ed.document().setDefaultTextOption(opt)
        self.settings.setValue("show_ws", self.show_ws)

    def _set_show_all(self, on):
        self.proxy_model.show_all = bool(on)
        self.proxy_model.invalidateFilter()

    # =====================================================================
    # EXPLORER
    # =====================================================================
    def set_tree_root(self, path):
        self.tree_root = path
        self.file_model.setRootPath(path)
        root_index = self.file_model.index(path)
        self.tree_view.setRootIndex(self.proxy_model.mapFromSource(root_index))

    def _path_of(self, proxy_index):
        return self.file_model.filePath(self.proxy_model.mapToSource(proxy_index))

    def on_file_clicked(self, proxy_index):
        file_path = self._path_of(proxy_index)
        if os.path.isfile(file_path):
            self.open_path(file_path)

    def tree_context_menu(self, pos):
        idx = self.tree_view.indexAt(pos)
        path = self._path_of(idx) if idx.isValid() else self.tree_root
        target_dir = path if os.path.isdir(path) else os.path.dirname(path)
        menu = QMenu(self)
        menu.addAction("New File...", lambda: self.new_file(target_dir))
        menu.addAction("New Folder...", lambda: self.new_folder(target_dir))
        if idx.isValid():
            menu.addSeparator()
            menu.addAction("Rename...", lambda: self.rename_path(path))
            menu.addAction("Delete", lambda: self.delete_path(path))
            menu.addSeparator()
            menu.addAction("Copy Path", lambda: QApplication.clipboard().setText(path))
        menu.addAction("Reveal in File Manager", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(target_dir)))
        menu.exec_(self.tree_view.viewport().mapToGlobal(pos))

    def new_folder(self, base):
        name, ok = QInputDialog.getText(self, "New Folder", "Tên thư mục:")
        if ok and name:
            try:
                os.makedirs(os.path.join(base, name), exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể tạo thư mục:\n{e}")

    def rename_path(self, path):
        name, ok = QInputDialog.getText(self, "Rename", "Tên mới:", text=os.path.basename(path))
        if not ok or not name or name == os.path.basename(path):
            return
        new = os.path.join(os.path.dirname(path), name)
        try:
            os.rename(path, new)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể đổi tên:\n{e}")
            return
        for ed in self.editors():
            if ed.path and norm(ed.path) == norm(path):
                self.watcher.removePath(path)
                ed.path = new
                self.watcher.addPath(new)
                ed.set_language(new.lower().endswith((".py", ".pyw")))
                self._refresh_tab_title(ed)

    def delete_path(self, path):
        if QMessageBox.question(self, "Xóa", f"Xóa vĩnh viễn:\n{path}?") != QMessageBox.Yes:
            return
        try:
            shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể xóa:\n{e}")
            return
        for ed in list(self.editors()):
            if ed.path and norm(ed.path).startswith(norm(path)):
                ed.document().setModified(False)
                self.close_tab(self.tabs.indexOf(ed))

    # =====================================================================
    # TAB / FILE
    # =====================================================================
    def editors(self):
        return [self.tabs.widget(i) for i in range(self.tabs.count())]

    def current_editor(self):
        w = self.tabs.currentWidget()
        return w if isinstance(w, CodeEditor) else None

    def find_editor(self, path):
        for ed in self.editors():
            if ed.path and norm(ed.path) == norm(path):
                return ed
        return None

    def _read_file(self, path):
        with open(path, "rb") as f:
            raw = f.read()
        enc = "utf-8-sig" if raw.startswith(codecs.BOM_UTF8) else "utf-8"
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            enc, text = "cp1252", raw.decode("cp1252", "replace")
        eol = "\r\n" if "\r\n" in text else "\n"
        return text.replace("\r\n", "\n").replace("\r", "\n"), enc, eol

    def _new_editor(self):
        ed = CodeEditor(self.theme)
        ed.set_font_size(self.font_size)
        ed.setLineWrapMode(QPlainTextEdit.WidgetWidth if self.word_wrap else QPlainTextEdit.NoWrap)
        if self.show_ws:
            opt = ed.document().defaultTextOption()
            opt.setFlags(opt.flags() | QTextOption.ShowTabsAndSpaces)
            ed.document().setDefaultTextOption(opt)
        ed.zoomRequested.connect(self.zoom)
        ed.document().modificationChanged.connect(lambda _m, e=ed: self._refresh_tab_title(e))
        ed.textChanged.connect(self._on_text_changed)
        ed.cursorPositionChanged.connect(lambda e=ed: self._update_cursor_status(e))
        return ed

    def _add_tab(self, ed, title):
        idx = self.tabs.addTab(ed, title)
        self.tabs.setCurrentIndex(idx)
        self.stack.setCurrentIndex(1)
        return idx

    def open_path(self, path, line=None):
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            self.status.showMessage(f"Không tìm thấy: {path}")
            return None
        ed = self.find_editor(path)
        if ed is None:
            if os.path.getsize(path) > 5 * 1024 * 1024 and QMessageBox.question(
                    self, "File lớn", "File lớn hơn 5MB, có thể chậm. Vẫn mở?") != QMessageBox.Yes:
                return None
            try:
                text, enc, eol = self._read_file(path)
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể đọc file:\n{e}")
                return None
            ed = self._new_editor()
            ed.path, ed.encoding, ed.eol = path, enc, eol
            ed.mtime = os.path.getmtime(path)
            ed.set_language(path.lower().endswith((".py", ".pyw")))
            ed.setPlainText(text)
            ed.document().setModified(False)
            self._add_tab(ed, os.path.basename(path))
            self.tabs.setTabToolTip(self.tabs.indexOf(ed), path)
            if path not in self.watcher.files():
                self.watcher.addPath(path)
        else:
            self.tabs.setCurrentWidget(ed)
        if line:
            ed.goto_line(line, focus=False)
        self.status.showMessage(f"Editing: {os.path.basename(path)}")
        return ed

    def load_file(self, file_path):          # giữ tên hàm gốc
        return self.open_path(file_path)

    def new_untitled(self):
        ed = self._new_editor()
        ed.set_language(True)
        self._add_tab(ed, "Untitled")
        ed.setFocus()

    def _refresh_tab_title(self, ed):
        i = self.tabs.indexOf(ed)
        if i < 0:
            return
        name = os.path.basename(ed.path) if ed.path else "Untitled"
        self.tabs.setTabText(i, name + (" ●" if ed.document().isModified() else ""))
        if ed is self.current_editor():
            self._update_title()

    def _update_title(self):
        ed = self.current_editor()
        if ed:
            name = os.path.basename(ed.path) if ed.path else "Untitled"
            self.setWindowTitle(f"{'● ' if ed.document().isModified() else ''}{name} - Script IDE")
        else:
            self.setWindowTitle("AI Vision - Integrated Script IDE")

    def _step_tab(self, d):
        n = self.tabs.count()
        if n:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + d) % n)

    def maybe_save(self, ed):
        if not ed.document().isModified():
            return True
        self.tabs.setCurrentWidget(ed)
        name = os.path.basename(ed.path) if ed.path else "Untitled"
        r = QMessageBox.question(self, "Lưu thay đổi?", f"'{name}' có thay đổi chưa lưu.",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if r == QMessageBox.Save:
            return self.save_editor(ed)
        return r == QMessageBox.Discard

    def close_tab(self, index):
        if index < 0:
            return
        ed = self.tabs.widget(index)
        if not self.maybe_save(ed):
            return
        if ed.path:
            self.watcher.removePath(ed.path)
        self.find_widget.set_editor(None) if self.find_widget.editor is ed else None
        self.tabs.removeTab(index)
        ed.deleteLater()
        if self.tabs.count() == 0:
            self.stack.setCurrentIndex(0)
            self.on_tab_changed(-1)

    def on_tab_changed(self, _i):
        ed = self.current_editor()
        self.find_widget.set_editor(ed)
        self._update_title()
        self._update_cursor_status(ed)
        self.run_lint()
        self.build_outline()

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder", self.tree_root)
        if folder:
            self.set_tree_root(folder)
            self.side_tabs.setCurrentIndex(0)
            self.status.showMessage(f"Opened Folder: {os.path.basename(folder)}")

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Script", self.tree_root,
            "Python Files (*.py *.pyw);;JSON Files (*.json);;All Files (*)")
        if file_path:
            self.open_path(file_path)
            self.set_tree_root(os.path.dirname(file_path))

    def new_file(self, target_dir=None):
        if not target_dir:
            target_dir = self.tree_root
            idx = self.tree_view.currentIndex()
            if idx.isValid():
                p = self._path_of(idx)
                target_dir = p if os.path.isdir(p) else os.path.dirname(p)
        file_name, ok = QInputDialog.getText(self, "New File", "Enter new file name (e.g. script.py):")
        if ok and file_name:
            new_path = os.path.join(target_dir, file_name)
            if os.path.exists(new_path):
                QMessageBox.warning(self, "Cảnh báo", "File đã tồn tại.")
                return
            try:
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                with open(new_path, "w", encoding="utf-8") as f:
                    f.write("")
                self.open_path(new_path)
                self.status.showMessage(f"Đã tạo file: {file_name}")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể tạo file:\n{e}")

    # ---------------- lưu ----------------
    def _backup(self, path):
        if not os.path.exists(path):
            return None
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = os.path.join(os.path.dirname(path), f"{os.path.basename(path)}.{ts}.bak")
        shutil.copy2(path, bak)
        olds = sorted(glob.glob(glob.escape(path) + ".*.bak"))
        for old in olds[:-MAX_BACKUPS]:
            try:
                os.remove(old)
            except OSError:
                pass
        return bak

    def save_editor(self, ed):
        if ed.path is None:
            return self.save_editor_as(ed)
        try:
            bak = self._backup(ed.path)
            with open(ed.path, "w", encoding=ed.encoding, newline="") as f:
                f.write(ed.toPlainText().replace("\n", ed.eol))
            ed.mtime = os.path.getmtime(ed.path)
            ed.document().setModified(False)
            if ed.path not in self.watcher.files():
                self.watcher.addPath(ed.path)
            self.status.showMessage(
                f"Saved: {os.path.basename(ed.path)}" + (f"  (backup: {os.path.basename(bak)})" if bak else ""), 5000)
            if ed is self.current_editor():
                self.run_lint()
            return True
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu file:\n{e}")
            return False

    def save_editor_as(self, ed):
        start = ed.path or os.path.join(self.tree_root, "untitled.py")
        path, _ = QFileDialog.getSaveFileName(self, "Save As", start, "Python (*.py);;All Files (*)")
        if not path:
            return False
        if ed.path:
            self.watcher.removePath(ed.path)
        ed.path = path
        ed.set_language(path.lower().endswith((".py", ".pyw")))
        self.tabs.setTabToolTip(self.tabs.indexOf(ed), path)
        return self.save_editor(ed)

    def save_file(self):                      # giữ tên hàm gốc
        ed = self.current_editor()
        if not ed:
            QMessageBox.information(self, "Thông báo", "Chưa có file nào được mở.")
            return False
        return self.save_editor(ed)

    def save_as(self):
        ed = self.current_editor()
        return self.save_editor_as(ed) if ed else False

    def save_all(self):
        for ed in self.editors():
            if ed.document().isModified():
                self.save_editor(ed)

    def on_external_change(self, path):
        ed = self.find_editor(path)
        if not ed:
            return
        if os.path.exists(path):
            if path not in self.watcher.files():
                self.watcher.addPath(path)
            try:
                m = os.path.getmtime(path)
            except OSError:
                return
            if abs(m - ed.mtime) < 0.01:
                return
            if ed.document().isModified() and QMessageBox.question(
                    self, "File đã thay đổi",
                    f"'{os.path.basename(path)}' bị sửa bên ngoài.\nTải lại và bỏ thay đổi trong editor?") != QMessageBox.Yes:
                ed.mtime = m
                return
            try:
                text, enc, eol = self._read_file(path)
            except Exception:
                return
            pos = ed.textCursor().position()
            ed.encoding, ed.eol, ed.mtime = enc, eol, m
            ed.setPlainText(text)
            ed.document().setModified(False)
            c = ed.textCursor()
            c.setPosition(min(pos, len(text)))
            ed.setTextCursor(c)
            self.status.showMessage(f"Đã tải lại: {os.path.basename(path)}", 4000)
        else:
            self.status.showMessage(f"File đã bị xóa trên đĩa: {os.path.basename(path)}", 6000)

    # =====================================================================
    # STATUS / LINT / OUTLINE
    # =====================================================================
    def _on_text_changed(self):
        self.lint_timer.start()
        self.outline_timer.start()

    def _update_cursor_status(self, ed):
        if ed is None or ed is not self.current_editor():
            if ed is None:
                self.lbl_pos.setText("")
                self.lbl_enc.setText("")
                self.lbl_eol.setText("")
            return
        c = ed.textCursor()
        sel = f" ({len(c.selectedText())} chọn)" if c.hasSelection() else ""
        self.lbl_pos.setText(f"Ln {c.blockNumber() + 1}, Col {c.positionInBlock() + 1}{sel}")
        self.lbl_enc.setText(ed.encoding.upper().replace("-SIG", " BOM"))
        self.lbl_eol.setText("CRLF" if ed.eol == "\r\n" else "LF")

    def run_lint(self):
        ed = self.current_editor()
        self.problems.clear()
        if not ed or (ed.path and not ed.path.lower().endswith((".py", ".pyw"))):
            self.lbl_problems.setText("✔ 0  ⚠ 0")
            self.bottom_tabs.setTabText(1, "Problems")
            return
        diags = analyze_code(ed.toPlainText(), ed.path or "<untitled>")
        ed.set_diagnostics(diags)
        t = self.theme
        for ln, col, sev, msg in sorted(diags, key=lambda d: d[0]):
            it = QTreeWidgetItem(["✖" if sev == "error" else "⚠", str(ln), msg])
            it.setData(0, Qt.UserRole, (ln, col))
            for c in range(3):
                it.setForeground(c, QColor(t["err"] if sev == "error" else t["warn"]))
            self.problems.addTopLevelItem(it)
        errs = sum(1 for d in diags if d[2] == "error")
        warns = len(diags) - errs
        self.lbl_problems.setText(f"✖ {errs}  ⚠ {warns}")
        self.bottom_tabs.setTabText(1, f"Problems ({len(diags)})" if diags else "Problems")

    def _problem_activated(self, item, _col=0):
        ed = self.current_editor()
        if ed:
            ln, col = item.data(0, Qt.UserRole)
            ed.goto_line(ln, max(0, col - 1))

    def build_outline(self):
        ed = self.current_editor()
        if not ed or (ed.path and not ed.path.lower().endswith((".py", ".pyw"))):
            self.outline_tree.clear()
            return
        try:
            mod = ast.parse(ed.toPlainText())
        except SyntaxError:
            return                              # giữ outline cũ khi code đang gõ dở
        self.outline_tree.clear()

        def walk(nodes, parent):
            for n in nodes:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    icon = "◆ " if isinstance(n, ast.ClassDef) else "ƒ "
                    it = QTreeWidgetItem(parent, [icon + n.name])
                    it.setData(0, Qt.UserRole, n.lineno)
                    walk(n.body, it)
        walk(mod.body, self.outline_tree.invisibleRootItem())
        self.outline_tree.expandAll()

    def _outline_activated(self, item, _col=0):
        ed = self.current_editor()
        if ed:
            ed.goto_line(item.data(0, Qt.UserRole))

    def check_syntax(self):
        ed = self.current_editor()
        if not ed:
            return
        self.run_lint()
        errs = [d for d in ed.diagnostics if d[2] == "error"]
        if not errs:
            QMessageBox.information(self, "Build Status", "✅ Code hợp lệ. Không có lỗi cú pháp!")
            self.status.showMessage("Syntax OK")
        else:
            ln, _c, _s, msg = errs[0]
            line = ed.document().findBlockByNumber(ln - 1).text()
            QMessageBox.critical(self, "Syntax Error", f"❌ Lỗi cú pháp tại dòng {ln}:\n\n{line}\n{msg}")
            self.status.showMessage("Syntax Error Detected")
            ed.goto_line(ln)

    # =====================================================================
    # TÌM KIẾM / ĐIỀU HƯỚNG
    # =====================================================================
    def show_find_replace(self):
        ed = self.current_editor()
        if not ed:
            return
        sel = ed.textCursor().selectedText()
        if sel and "\u2029" not in sel:
            self.find_widget.find_input.setText(sel)
        self.find_widget.set_editor(ed)
        self.find_widget.setVisible(True)
        self.find_widget.find_input.setFocus()
        self.find_widget.find_input.selectAll()
        self.find_widget.update_highlights()

    def show_find_in_files(self):
        ed = self.current_editor()
        if ed:
            sel = ed.textCursor().selectedText()
            if sel and "\u2029" not in sel:
                self.fif_input.setText(sel)
        self.bottom_tabs.setVisible(True)
        self.bottom_tabs.setCurrentIndex(2)
        self.fif_input.setFocus()
        self.fif_input.selectAll()

    def find_in_files(self):
        pat = self.fif_input.text()
        self.fif_results.clear()
        if not pat:
            return
        if not self.fif_regex.isChecked():
            pat = re.escape(pat)
        try:
            rx = re.compile(pat, 0 if self.fif_case.isChecked() else re.IGNORECASE)
        except re.error as e:
            QMessageBox.warning(self, "Regex lỗi", str(e))
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        total, files = 0, 0
        try:
            for fp in iter_project_files(self.tree_root):
                try:
                    if os.path.getsize(fp) > 2 * 1024 * 1024:
                        continue
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.read().splitlines()
                except OSError:
                    continue
                node = None
                for i, line in enumerate(lines, 1):
                    if rx.search(line):
                        if node is None:
                            node = QTreeWidgetItem([os.path.relpath(fp, self.tree_root)])
                            node.setData(0, Qt.UserRole, (fp, 1))
                            self.fif_results.addTopLevelItem(node)
                            files += 1
                        child = QTreeWidgetItem(node, [f"{i}: {line.strip()[:200]}"])
                        child.setData(0, Qt.UserRole, (fp, i))
                        total += 1
                        if total >= 3000:
                            break
                if total >= 3000:
                    break
        finally:
            QApplication.restoreOverrideCursor()
        self.fif_results.expandAll()
        self.status.showMessage(f"Tìm thấy {total} kết quả trong {files} file" + (" (đã cắt bớt)" if total >= 3000 else ""))

    def _fif_activated(self, item, _col=0):
        fp, ln = item.data(0, Qt.UserRole)
        self.open_path(fp, ln)

    def goto_line_dialog(self):
        ed = self.current_editor()
        if not ed:
            return
        n, ok = QInputDialog.getInt(self, "Go to Line", "Số dòng:", ed.textCursor().blockNumber() + 1,
                                    1, ed.blockCount())
        if ok:
            ed.goto_line(n)

    def quick_open(self):
        root = self.tree_root
        items = [(os.path.relpath(p, root), p) for p in iter_project_files(root)]
        dlg = QuickPicker(self, "Quick Open", items)
        if dlg.exec_() == QDialog.Accepted and dlg.payload:
            self.open_path(dlg.payload)

    def command_palette(self):
        items = []
        for a in self._palette_actions:
            label = a.text().replace("&", "")
            sc = a.shortcut().toString()
            items.append((f"{label}    [{sc}]" if sc else label, a))
        dlg = QuickPicker(self, "Command Palette", items)
        if dlg.exec_() == QDialog.Accepted and dlg.payload:
            dlg.payload.trigger()

    # =====================================================================
    # CHẠY / DEBUG
    # =====================================================================
    def run_current(self):
        self._run(False)

    def debug_current(self):
        self._run(True)

    def _run(self, debug):
        ed = self.current_editor()
        if not ed:
            return
        if self.console.is_running():
            QMessageBox.information(self, "Đang chạy", "Một tiến trình đang chạy. Hãy Stop (Shift+F5) trước.")
            return
        if ed.path is None or ed.document().isModified():
            if not self.save_editor(ed):
                return
        if not ed.path.lower().endswith((".py", ".pyw")):
            self.status.showMessage("Chỉ chạy được file .py")
            return
        if not self.interpreter or not os.path.exists(self.interpreter):
            QMessageBox.warning(self, "Interpreter", "Chưa cấu hình Python interpreter hợp lệ.\nVào Tools ▸ Select Interpreter.")
            return
        self.bottom_tabs.setVisible(True)
        self.bottom_tabs.setCurrentIndex(0)
        self.console.clear_output()
        args, pending = ["-u"], []
        if debug:
            args += ["-m", "pdb"]
            if ed.breakpoints:
                pending = [f"b {ed.path}:{ln}" for ln in sorted(ed.breakpoints)] + ["c"]
        args.append(ed.path)
        self.console.run(self.interpreter, args, os.path.dirname(ed.path), pending, debug)
        self.status.showMessage("Debugging..." if debug else "Running...")

    def _on_run_finished(self, code):
        for ed in self.editors():
            ed.set_debug_line(None)
        self.status.showMessage(f"Hoàn tất (exit code {code})", 5000)

    def on_debug_location(self, path, line):
        for ed in self.editors():
            ed.set_debug_line(None)
        if not os.path.isfile(path):
            return
        ed = self.open_path(path, line)
        if ed:
            ed.set_debug_line(line)

    def clear_breakpoints(self):
        for ed in self.editors():
            ed.breakpoints.clear()
            ed.lineNumberArea.update()

    def select_interpreter(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Python interpreter", os.path.dirname(self.interpreter or ""))
        if path:
            self.interpreter = path
            self.settings.setValue("interpreter", path)
            self._update_interp_label()

    def pip_install(self):
        pkg, ok = QInputDialog.getText(self, "pip install", "Tên package (vd: requests black):")
        if not ok or not pkg.strip() or self.console.is_running() or not self.interpreter:
            return
        self.bottom_tabs.setVisible(True)
        self.bottom_tabs.setCurrentIndex(0)
        self.console.run(self.interpreter, ["-m", "pip", "install"] + pkg.split(), self.tree_root)

    def format_document(self):
        ed = self.current_editor()
        if not ed:
            return
        code = ed.toPlainText()
        new = None
        try:
            import black
            new = black.format_str(code, mode=black.Mode())
        except ImportError:
            try:
                import autopep8
                new = autopep8.fix_code(code)
            except ImportError:
                QMessageBox.information(self, "Format", "Cần cài `black` hoặc `autopep8`:\n"
                                        "Tools ▸ Install Package (pip) ▸ black")
                return
        except Exception as e:
            QMessageBox.warning(self, "Format lỗi", f"Không thể format (code có lỗi cú pháp?):\n{e}")
            return
        if new is not None and new != code:
            keep = ed.textCursor().blockNumber()
            c = ed.textCursor()
            c.beginEditBlock()
            c.select(QTextCursor.Document)
            c.insertText(new)
            c.endEditBlock()
            ed.goto_line(keep + 1, focus=False)
            self.status.showMessage("Đã format document", 4000)

    # =====================================================================
    # PHIÊN LÀM VIỆC
    # =====================================================================
    def _restore_session(self):
        files = self.settings.value("open_files", [])
        if isinstance(files, str):
            files = [files]
        for p in files or []:
            if os.path.isfile(p):
                self.open_path(p)
        active = int(self.settings.value("active_tab", 0) or 0)
        if 0 <= active < self.tabs.count():
            self.tabs.setCurrentIndex(active)
        geo = self.settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)

    def closeEvent(self, event):
        for ed in self.editors():
            if not self.maybe_save(ed):
                event.ignore()
                return
        self.console.stop()
        self.settings.setValue("open_files", [e.path for e in self.editors() if e.path])
        self.settings.setValue("active_tab", self.tabs.currentIndex())
        self.settings.setValue("root", self.tree_root)
        self.settings.setValue("geometry", self.saveGeometry())
        event.accept()


# =========================================================================
# PUBLIC LAUNCHER
# =========================================================================
_OPEN_WINDOWS = []


def open_scripts_editor(cursor, connect_db, connection, parent=None):
    auth = DeveloperAuthDialog(parent)
    if auth.exec_() == QDialog.Accepted and auth.authenticated:
        win = IDEWindow(parent)
        _OPEN_WINDOWS.append(win)               # tránh bị GC khi caller không giữ tham chiếu
        win.setAttribute(Qt.WA_DeleteOnClose, False)
        win.show()
        return win
    return None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = open_scripts_editor(None, None, None)
    sys.exit(app.exec_() if w else 0)
