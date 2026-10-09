from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import *
import sys
from xFunc import *
from PyUICWidgets import *

class BaslerPylon():
    def __init__(self): 
        app = QApplication(sys.argv)
        mainWindow = QMainWindow()
        ui = Ui_MainWindow()
        cfg = Basler_Pylon(mainWindow,ui)
        ui.setupUi(mainWindow)
        ui.bnEnum.clicked.connect(cfg.initialize_camera)
        ui.bnOpen.clicked.connect(cfg.open_device)
        ui.bnSetParam.clicked.connect(cfg.SetValuePrams)
        ui.bnGetParam.clicked.connect(cfg.ExportValue)
        ui.bnClose.clicked.connect(cfg.close_device)
        ui.radioTriggerMode.clicked.connect(cfg.set_software_trigger_mode)
        ui.radioContinueMode.clicked.connect(cfg.set_continue_mode)
        ui.bnSoftwareTrigger.clicked.connect(cfg.Trigger1)
        ui.bnStart.clicked.connect(cfg.start_stream)
        ui.bnStop.clicked.connect(cfg.stop_stream)
        ui.bnSaveImage.clicked.connect(cfg.save_img)
        ui.bnFolderBrowser.clicked.connect(cfg.open_folder_dialog)
        ui.fullScreenButton.clicked.connect(cfg.fullScreen)
        mainWindow.show()
        app.exec_()

