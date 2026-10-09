import sys,os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread, QMetaObject, Qt, Q_ARG
from core.MvCameraControl_class import *
from core.MvErrorDefine_const import *
from core.CameraParams_header import *
from core.core_plus_auto import Initial_Device_Auto
from core.CamOperation_class import *
# from core.core_plus_auto_new import Initial_Device_Auto
# from core.CamOperation_class_new import *
import ctypes

class Layer_Initial_Device_Auto(Initial_Device_Auto, QObject):
    def __init__(self, serial, port):
        super().__init__(serial, port)

    def enum_devices_class(self):
        return self.enum_devices()
        
    def open_device_camera_class(self):
       return self.open_device_camera()

    def start_grabbing_array_class(self):
        return self.start_grabbing_array()
    
    def stop_grabbing_array_class(self):
        return self.stop_grabbing_array()

    def Retrieve_Image_Buffer(self):
        return self.GetImgArayBuffer()

    def close_device_class(self):
        return self.close_device()
           
    def set_user_selector_class(self,user_index=None):
        print('-----------------------------------------------------')
        return self.set_user_selector(user_index=user_index)