
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                            QWidget, QTableWidget, QTableWidgetItem, QLabel, 
                            QHeaderView, QFrame, QPushButton, QSpacerItem, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon
from datetime import datetime

class ModernDataViewer(QMainWindow):
    def __init__(self,dict_return,file_path):
        super().__init__()
        self.file_path = file_path
        self.dict_return = dict_return
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('Data Analysis Viewer')
        self.setGeometry(100, 100, 700, 700)
      
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)

        self.create_header(main_layout)
        self.create_table(main_layout)
        self.create_footer(main_layout)
        self.load_data()
        
    def create_header(self, parent_layout):
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 15px;
                padding: 3px;
                border: 1px solid #e0e0e0;
            }
        """)
        header_layout = QHBoxLayout(header_frame)

        title_label = QLabel("🔍 Data Analysis Dashboard")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                border: none;
                padding: 10px;
            }
        """)
        status_layout = QVBoxLayout()
        self.time_label = QLabel()
        self.time_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #7f8c8d;
                border: none;
            }
        """)
        
        self.status_label = QLabel(f"📊 Số lượng Labels: {len(self.dict_return)}")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #34495e;
                font-weight: 500;
                border: none;
            }
        """)
        
        status_layout.addWidget(self.time_label)
        status_layout.addWidget(self.status_label)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addLayout(status_layout)
        
        parent_layout.addWidget(header_frame)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.update_time()
        
    def create_table(self, parent_layout):
        table_frame = QFrame()
        table_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 15px;
                border: 1px solid #e0e0e0;
            }
        """)
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(20, 20, 20, 20)
  
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['Label', 'Conf Threshold', 'Conf Result', 'Phán Định'])
  
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #ecf0f1;
                background-color: #ffffff;
                border: none;
                border-radius: 10px;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 12px;
                border-bottom: 1px solid #ecf0f1;
            }
            QTableWidget::item:selected {
                background-color: #e8f4fd;
                color: #2c3e50;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                padding: 15px;
                border: none;
                font-weight: bold;
                font-size: 14px;
            }
            QHeaderView::section:first {
                border-top-left-radius: 10px;
            }
            QHeaderView::section:last {
                border-top-right-radius: 10px;
            }
        """)
  
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        table_layout.addWidget(self.table)
        parent_layout.addWidget(table_frame)
        
    def create_footer(self, parent_layout):
        footer_frame = QFrame()
        footer_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 15px;
                padding: 15px;
                border: 1px solid #e0e0e0;
            }
        """)
        footer_layout = QHBoxLayout(footer_frame)
        
        legend_label = QLabel(f'Hiển thị kết quả cho: {self.file_path}')
        legend_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #7f8c8d;
                font-weight: 500;
                border: none;
            }
        """)
        
        refresh_btn = QPushButton("🔄 Refresh Data")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_data)
        
        footer_layout.addWidget(legend_label)
        footer_layout.addStretch()
        footer_layout.addWidget(refresh_btn)
        
        parent_layout.addWidget(footer_frame)
        
    def load_data(self):
        self.table.setRowCount(len(self.dict_return))
        
        for row, (label, data) in enumerate(self.dict_return.items()):
            label_item = QTableWidgetItem(str(label))
            label_item.setFont(QFont("Segoe UI", 12, QFont.Medium))
            
            threshold_item = QTableWidgetItem(str(data['conf_threshold']))
            threshold_item.setTextAlignment(Qt.AlignCenter)
            threshold_item.setFont(QFont("Segoe UI", 11))

            result_item = QTableWidgetItem(str(data['conf_result']))
            result_item.setTextAlignment(Qt.AlignCenter)
            result_item.setFont(QFont("Segoe UI", 11))
            
            status = "OK" if data['color_text00X0'] else "NG"
            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setFont(QFont("Segoe UI", 12, QFont.Bold))
            
            if data['color_text00X0']: 
                status_item.setForeground(QColor("#27ae60"))
                status_item.setBackground(QColor("#d5f4e6"))
            else:
                status_item.setForeground(QColor("#e74c3c"))
                status_item.setBackground(QColor("#fadbd8"))
            
            self.table.setItem(row, 0, label_item)
            self.table.setItem(row, 1, threshold_item)
            self.table.setItem(row, 2, result_item)
            self.table.setItem(row, 3, status_item)
    
            self.table.setRowHeight(row, 45)
    
    def update_time(self):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.setText(f"🕒 Last Updated: {current_time}")
        
    def refresh_data(self):
        self.load_data()
        
    
        ok_count = sum(1 for data in self.dict_return.values() if data['color_text00X0'])
        ng_count = len(self.dict_return) - ok_count
        
        self.status_label.setText(f"📊 Total: {len(self.dict_return)} | ✅ OK: {ok_count} | ❌ NG: {ng_count}")
        
    def update_dict_return(self, new_dict):
        self.dict_return = new_dict
        self.refresh_data()

def main(dict_return):
    app = QApplication(sys.argv)
    app.setApplicationName("Data Analysis Viewer")
    app.setApplicationVersion("1.0")
    window = ModernDataViewer(dict_return)
    window.show()
    
    # sys.exit(app.exec_())
_open_windows = []

def show_data_viewer(dict_return=None,key=None):
    """
    Function to show the data viewer window safely.
    This function can be called from your existing application.
    """
    global _open_windows
    
    # Check if QApplication already exists
    app = QApplication.instance()
    if app is None:
        # Create QApplication only if it doesn't exist
        app = QApplication(sys.argv)
        app.setApplicationName("Data Analysis Viewer")
        app.setApplicationVersion("1.0")
    
    # Create window
    window = ModernDataViewer(dict_return,key)
    
    # Keep reference to prevent garbage collection
    _open_windows.append(window)
    
    # Connect close event to cleanup
    def on_window_close():
        if window in _open_windows:
            _open_windows.remove(window)
    
    window.destroyed.connect(on_window_close)
    
    # Show window
    window.show()
    window.raise_()  # Bring to front
    window.activateWindow()  # Make it active
    
    return window