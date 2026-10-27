from module_1.layout_cameratab import Ui_MainWindow as Ui_CameraTab
from module_1.layout_modeltab import Ui_MainWindow as Ui_ModelTab
from PyQt5.QtWidgets import QMessageBox
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QLineEdit, 
                             QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, 
                             QFrame, QComboBox, QScrollArea, QMessageBox, QSpinBox,
                             QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
                             QGroupBox)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap
from module_1.mysql_connector import Ui_MainWindow as Ui_MySQLConnector
import mysql.connector
from mysql.connector import Error
from module_1.database import Connect2Mysql
from module_1.confirm_dataset import Ui_MainWindow as FormConfirmTable
import sys
from module_1.dashboard_ver1 import Ui_MainWindow as Database_Management
from module_1.main_core import *
from PyQt5 import QtCore, QtGui, QtWidgets
import queue
from PyQt5.QtCore import QTimer

class Pyuic5():
    def __init__(self,ui_db,connection,main_core):
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
        self.connection = connection
        self.MainWindow = QtWidgets.QMainWindow()
        self.ui = Database_Management()
        self.ui.setupUi(self.MainWindow)
        self.mysqlWindow = QtWidgets.QMainWindow()
        self.mysqlUi = Ui_MySQLConnector()
        self.mysqlUi.setupUi(self.mysqlWindow)
        self.formmysqlWindow = QtWidgets.QMainWindow()
        self.form_mysql = FormConfirmTable(self.ui)
        self.form_mysql.setupUi(self.formmysqlWindow)
        self.connect = Connect2Mysql(self.mysqlUi, self.form_mysql, self.ui, self.connection)
        self.core = core(self.connect,ui_db,self.ui,main_core)
        self.mysqlUi.pushButton_cancel.clicked.connect(lambda _ , u=self.connect: u.connect_to_mysql())
        self.ui.pushButton_5.clicked.connect(lambda _ , u=self.mysqlWindow: u.show())
        self.ui.pushButton_2.clicked.connect(self.form_mysql.save_config)
        self.ui.pushButton_3.clicked.connect(self.formmysqlWindow.show)
        self.ui.pushButton_4.clicked.connect(self.form_mysql.clear_data)
        self.ui.pushButton.clicked.connect(self.connect.create_item_code_device)
        self.form_mysql.confirm_btn.clicked.connect(self.connect.commitment)
        self.ui.pushButton_6.clicked.connect(lambda:self.core.query_device(self.MainWindow))
        # self.MainWindow.show()
