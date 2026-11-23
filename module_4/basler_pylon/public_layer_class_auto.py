import sys,os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread, QMetaObject, Qt, Q_ARG
from module_4.basler_pylon.init_device_auto import Initial_Device_Auto
import ctypes

class Layer_Initial_Device_Auto(Initial_Device_Auto, QObject):
    def __init__(self, serial, port):
        super().__init__(serial, port)

    def enum_devices_class(self):
        return self.EnumerateDevices()
        
    def open_device_camera_class(self):
       return self.OpenDevice()

    def start_grabbing_array_class(self):
        return self.StartGrab()
    
    def stop_grabbing_array_class(self):
        return self.StopGrab()

    def Retrieve_Image_Buffer(self):
        return self.trigger_hardware()

    def close_device_class(self):
        return self.close_device()
           
    def set_user_selector_class(self,user_index=None):
        print('-----------------------------------------------------')
        return self.load_userset(user_selector=f'UserSet{user_index}')

    def is_connected_class(self):
        try:
            if hasattr(self, 'camera') and self.camera is not None:
                if hasattr(self.camera, 'IsCameraDeviceRemoved') and self.camera.IsCameraDeviceRemoved():
                    return False
                if hasattr(self.camera, 'IsOpen') and not self.camera.IsOpen():
                    return False
                return True
        except Exception:
            return False
        return False
