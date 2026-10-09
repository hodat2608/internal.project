from PyQt5.QtWidgets import QProgressDialog, QApplication
from PyQt5.QtCore import Qt

class AppProgressBar:
    def __init__(self, title="Vui lòng chờ", message="Đang xử lý...", maximum=100, parent=None):
        self.progress = QProgressDialog(message, None, 0, maximum, parent)
        self.progress.setWindowTitle(title)
        self.progress.setWindowModality(Qt.ApplicationModal)
        self.progress.setWindowFlags(self.progress.windowFlags() | Qt.WindowStaysOnTopHint | Qt.CustomizeWindowHint | Qt.Tool)
        self.progress.setMinimumDuration(0)
        self.progress.setCancelButton(None)
        self.progress.setValue(0)
        self.progress.show()
        self.progress.raise_()
        self.progress.activateWindow()
        QApplication.processEvents()

    def update_progress(self, val=None, text=None):
        if text:
            self.progress.setLabelText(text)
        if val is not None:
            self.progress.setValue(val)
        self.progress.raise_()
        self.progress.activateWindow()
        QApplication.processEvents()

    def close(self):
        self.progress.close()
