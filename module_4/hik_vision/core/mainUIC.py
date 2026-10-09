from IOConnection.hik_mvs.PyUICBasicDemo import *
from IOConnection.hik_mvs.DeviceConfig import *

class Hik_MVS():

    def __init__(self): 
        app = QApplication(sys.argv)
        mainWindow = QMainWindow()
        ui = Ui_MainWindow()
        cfg = CFGIOConnector(mainWindow,ui)
        ui.setupUi(mainWindow)
        ui.bnEnum.clicked.connect(cfg.enum_devices)
        ui.bnOpen.clicked.connect(cfg.open_device)
        ui.bnClose.clicked.connect(cfg.close_device)
        ui.bnStart.clicked.connect(cfg.start_grabbing)
        ui.bnStop.clicked.connect(cfg.stop_grabbing)
        ui.bnSoftwareTrigger.clicked.connect(cfg.trigger_once)
        ui.radioTriggerMode.clicked.connect(cfg.set_software_trigger_mode)
        ui.radioContinueMode.clicked.connect(cfg.set_continue_mode)
        ui.bnGetParam.clicked.connect(cfg.get_param)
        ui.bnSetParam.clicked.connect(cfg.set_param)
        ui.bnSaveImage.clicked.connect(cfg.save_bmp)
        mainWindow.show()
        app.exec_()
        cfg.close_device()


