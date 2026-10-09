import sys,os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread, QMetaObject, Qt, Q_ARG
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QMessageBox
import queue
import ctypes
from PyQt5 import QtCore, QtGui, QtWidgets, QtMultimedia
from module_4.basler_pylon.init_device_manual import Initial_Device_Manual

# 获取选取设备信息的索引，通过[]之间的字符去解析
def TxtWrapBy(start_str, end, all):
    start = all.find(start_str)
    if start >= 0:
        start += len(start_str)
        end = all.find(end, start)
        if end >= 0:
            return all[start:end].strip()


# 将返回的错误码转换为十六进制显示
def ToHexStr(num):
    chaDic = {10: 'a', 11: 'b', 12: 'c', 13: 'd', 14: 'e', 15: 'f'}
    hexStr = ""
    if num < 0:
        num = num + 2 ** 32
    while num >= 16:
        digit = num % 16
        hexStr = chaDic.get(digit, str(digit)) + hexStr
        num //= 16
    hexStr = chaDic.get(num, str(num)) + hexStr
    return hexStr


class Layer_Initial_Device_Manual(Initial_Device_Manual):
    def __init__(self, mainWindow, ui, _mirror_tab_widget=None):
        super().__init__(mainWindow, ui)
        

    def _internal_get_img_public_class(self):
        return self._internal_get_img()

    def save_user_default_public_class(self):
        return self.save_user_default()

    def enum_devices_public_class(self):
        return self.EnumerateDevices()

    def open_device_camera_public_class(self):
        return self.OpenDevice() 
    
    def start_grabbing_array_public_class(self):
        return self.StartGrab()   

    def GetImgArayBufferPushButton_public_class(self):
        return self.trigger_hardware()

    def GetImgArayBuffer_public_class(self):
        return self.GetImgArayBuffer()

    @pyqtSlot(object)
    def _display_image_to_ui_public_class(self, img):
        return self._display_image_to_ui()

    def start_grabbing_public_class(self):
        return self.start_grabbing()

    def stop_grabbing_public_class(self):
        return self.stop_grabbing()

    def close_device_public_class(self):
        return self.close_device()
    
    def set_continue_mode_public_class(self):
        return self.set_continue_mode()

    def set_software_trigger_mode_public_class(self):
        return self.set_software_trigger_mode()

    def trigger_once_public_class(self):
        return self.trigger_once()

    def save_bmp_public_class(self):
        return self.save_bmp()

    def get_param_public_class(self):
        return self.get_param()

    def set_param_public_class(self):
        return self.set_param()
    
    def user_set_load_public_class(self):
        return self.user_set_load()

    def enable_controls_public_class(self):
        return self.enable_controls()

    def enable_grabbing_controls_public_class(self):
        return self.enable_grabbing_controls()
