import sys,os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread, QMetaObject, Qt, Q_ARG
from core.CamOperation_class import *
from core.MvCameraControl_class import *
from core.MvErrorDefine_const import *
from core.CameraParams_header import *
from app_logger.app_logger import get_logger as _get_logger
_log = _get_logger('module_4.hik_vision.core.core_plus_auto')
import ctypes

class Initial_Device_Auto(QObject):
    def __init__(self,serial,port):
        super().__init__()
        self.deviceList = MV_CC_DEVICE_INFO_LIST()
        self.cam = MvCamera()
        self.obj_cam_operation = 0
        self.serial = serial
        self.port_connect = port
        self.user_set_selector = 0
        self.dict_device = {}

    def enum_devices(self):
        ret = MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE | MV_USB_DEVICE, self.deviceList)
        devList = []
        for index in range(0, self.deviceList.nDeviceNum):
            mvcc_dev_info = ctypes.cast(self.deviceList.pDeviceInfo[index], ctypes.POINTER(MV_CC_DEVICE_INFO)).contents
            if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE:
                chModelName = ''.join(chr(b) for b in mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName if b != 0)
                chUserDefinedName = ''.join(chr(b) for b in mvcc_dev_info.SpecialInfo.stGigEInfo.chUserDefinedName if b != 0)
                serial = ''.join(chr(b) for b in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber if b != 0)
                nip = mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp
                ip_str = '.'.join(str((nip >> offset) & 0xFF) for offset in [24, 16, 8, 0])
                devList.append(f"[{index}]%{self.port_connect}%{chModelName}%{ip_str}")
                self.dict_device[ip_str]=[]
                self.dict_device[ip_str].append({
                                'index': index,
                                'PORT': self.port_connect
                            })
            elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
                chModelName = ''.join(chr(b) for b in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName if b != 0)
                chUserDefinedName = ''.join(chr(b) for b in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chUserDefinedName if b != 0)
                serial = ''.join(chr(b) for b in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber if b != 0)
                devList.append(f'[{index}]%{self.port_connect}%{chModelName}%{serial}')
                self.dict_device[serial]=[]
                self.dict_device[serial].append({
                                'index': index,
                                'PORT': self.port_connect
                            })
        
    def open_device_camera(self):
        nSelCamIndex = self.dict_device[self.serial][0]['index']
        self.obj_cam_operation = CameraOperation(self.cam, self.deviceList, int(nSelCamIndex))
        ret = self.obj_cam_operation.Open_device()
        if ret != 0:
            strError = "[-] Open device failed ret:" + hex(ret)
            _log.error('Open camera HIK Failed, Please try again! Error: %s', strError)
        else:
            _log.info('Open camera HIK successfully')
            self.set_user_selector(user_index=1)

    def start_grabbing_array(self):
        ret = self.obj_cam_operation.grabbing()
        if ret != 0 :
            _log.error('Start Grabbing MVS DRIVER has been Failed!')
            return
        _log.info('Start Grabbing MVS DRIVER Succesfully!')
    
    def stop_grabbing_array(self):
        ret = self.obj_cam_operation.not_grabbing()
        if ret != 0 :
            _log.error('Stop Grabbing MVS DRIVER has been Failed!')
            return
        _log.info('Stop Grabbing MVS DRIVER Succesfully!')

    def GetImgArayBuffer(self):
        ret, img = self.obj_cam_operation.grab_frame(timeout=115)
        return img

    def close_device(self):
        self.obj_cam_operation.Close_device()
        _log.info('Close device camera HIK successfully')

           
    def set_user_selector(self,user_index=None):
        ret = self.obj_cam_operation.load_params_user_selector(user_set_index = user_index if user_index else self.user_set_selector) 
        _log.info('Set user selector HIK successfully')
        return ret