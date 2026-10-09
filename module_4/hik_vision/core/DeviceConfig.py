# -- coding: utf-8 --

from PyQt5.QtWidgets import *
from base.IOConnection.hik_mvs.MvsExportImgBuffer.CamOperation_class import CameraOperation
from base.IOConnection.hik_mvs.MvsExportImgBuffer.MvCameraControl_class import *
from base.IOConnection.hik_mvs.MvsExportImgBuffer.MvErrorDefine_const import *
from base.IOConnection.hik_mvs.MvsExportImgBuffer.CameraParams_header import *
from IOConnection.hik_mvs.DeviceConfig import *


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


class CFGIOConnector():
    def __init__(self,mainWindow,ui):
        self.mainWindow=mainWindow
        self.ui = ui
        self.deviceList = MV_CC_DEVICE_INFO_LIST()
        self.cam = MvCamera()
        self.obj_cam_operation = 0
        self.isOpen = False
        self.isGrabbing= False
        self.isCalibMode = False
   
    def xFunc(event,self):
        global nSelCamIndex
        nSelCamIndex = TxtWrapBy("[", "]", self.ui.ComboDevices.get())
        pass

    def enum_devices(self):

        ret = MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE | MV_USB_DEVICE, self.deviceList)
        if ret != 0:
            strError = "Enum devices fail! ret = :" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
            return ret

        if self.deviceList.nDeviceNum == 0:
            QMessageBox.warning(self.mainWindow, "Info", "Find no device", QMessageBox.Ok)
            return ret
        print("Find %d devices!" % self.deviceList.nDeviceNum)
        devList = []
        for i in range(0, self.deviceList.nDeviceNum):
            mvcc_dev_info = cast(self.deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE:
                print("\ngige device: [%d]" % i)
                chUserDefinedName = ""
                for per in mvcc_dev_info.SpecialInfo.stGigEInfo.chUserDefinedName:
                    if 0 == per:
                        break
                    chUserDefinedName = chUserDefinedName + chr(per)
                print("device user define name: %s" % chUserDefinedName)

                chModelName = ""
                for per in mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName:
                    if 0 == per:
                        break
                    chModelName = chModelName + chr(per)

                print("device model name: %s" % chModelName)

                nip1 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0xff000000) >> 24)
                nip2 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x00ff0000) >> 16)
                nip3 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x0000ff00) >> 8)
                nip4 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x000000ff)
                print("current ip: %d.%d.%d.%d\n" % (nip1, nip2, nip3, nip4))
                devList.append(
                    "[" + str(i) + "]GigE: " + chUserDefinedName + " " + chModelName + "(" + str(nip1) + "." + str(
                        nip2) + "." + str(nip3) + "." + str(nip4) + ")")
            elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
                print("\nu3v device: [%d]" % i)
                chUserDefinedName = ""
                for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chUserDefinedName:
                    if per == 0:
                        break
                    chUserDefinedName = chUserDefinedName + chr(per)
                print("device user define name: %s" % chUserDefinedName)

                chModelName = ""
                for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName:
                    if 0 == per:
                        break
                    chModelName = chModelName + chr(per)
                print("device model name: %s" % chModelName)

                strSerialNumber = ""
                for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber:
                    if per == 0:
                        break
                    strSerialNumber = strSerialNumber + chr(per)
                print("user serial number: %s" % strSerialNumber)
                devList.append("[" + str(i) + "]USB: " + chUserDefinedName + " " + chModelName
                               + "(" + str(strSerialNumber) + ")")
        self.ui.ComboDevices.clear()
        self.ui.ComboDevices.addItems(devList)
        self.ui.ComboDevices.setCurrentIndex(0)

    def open_device(self):
        if self.isOpen:
            QMessageBox.warning(self.mainWindow, "Error", 'Camera is Running!', QMessageBox.Ok)
            return MV_E_CALLORDER

        nSelCamIndex = self.ui.ComboDevices.currentIndex()
        if nSelCamIndex < 0:
            QMessageBox.warning(self.mainWindow, "Error", 'Please select a camera!', QMessageBox.Ok)
            return MV_E_CALLORDER

        self.obj_cam_operation = CameraOperation(self.cam, self.deviceList, nSelCamIndex)
        ret = self.obj_cam_operation.Open_device()
        if 0 != ret:
            strError = "Open device failed ret:" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
            self.isOpen = False
        else:
            self.set_continue_mode()
            self.get_param()
            self.isOpen = True
            self.enable_controls()

    def start_grabbing(self):
        ret = self.obj_cam_operation.Start_grabbing_origin(self.ui.widgetDisplay.winId())
        if ret != 0:
            strError = "Start grabbing failed ret:" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            self.isGrabbing = True
            self.enable_controls()

    def stop_grabbing(self):
        ret = self.obj_cam_operation.Stop_grabbing()
        if ret != 0:
            strError = "Stop grabbing failed ret:" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            self.isGrabbing = False
            self.enable_controls()

    def close_device(self):
        if self.isOpen:
            self.obj_cam_operation.Close_device()
            self.isOpen = False
        self.isGrabbing = False
        self.enable_controls()

    def set_continue_mode(self):
        strError = None
        ret = self.obj_cam_operation.Set_trigger_mode(False)
        if ret != 0:
            strError = "Set continue mode failed ret:" + ToHexStr(ret) + " mode is " 
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            self.ui.radioContinueMode.setChecked(True)
            self.ui.radioTriggerMode.setChecked(False)
            self.ui.bnSoftwareTrigger.setEnabled(False)

    def set_software_trigger_mode(self):
        ret = self.obj_cam_operation.Set_trigger_mode(True)
        if ret != 0:
            strError = "Set trigger mode failed ret:" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            self.ui.radioContinueMode.setChecked(False)
            self.ui.radioTriggerMode.setChecked(True)
            self.ui.bnSoftwareTrigger.setEnabled(self.isGrabbing)

    def trigger_once(self):
        ret = self.obj_cam_operation.Trigger_once()
        if ret != 0:
            strError = "TriggerSoftware failed ret:" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)

    def save_bmp(self):
        ret = self.obj_cam_operation.Save_Bmp()
        if ret != MV_OK:
            strError = "Save BMP failed ret:" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            print("Save image success")

    def get_param(self):
        ret = self.obj_cam_operation.Get_parameter()
        if ret != MV_OK:
            strError = "Get param failed ret:" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            self.ui.edtExposureTime.setText("{0:.2f}".format(self.obj_cam_operation.exposure_time))
            self.ui.edtGain.setText("{0:.2f}".format(self.obj_cam_operation.gain))
            self.ui.edtFrameRate.setText("{0:.2f}".format(self.obj_cam_operation.frame_rate))

    def set_param(self):
        frame_rate = self.ui.edtFrameRate.text()
        exposure = self.ui.edtExposureTime.text()
        gain = self.ui.edtGain.text()
        ret = self.obj_cam_operation.Set_parameter(frame_rate, exposure, gain)
        if ret != MV_OK:
            strError = "Set param failed ret:" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
        return MV_OK

    def enable_controls(self):
        self.ui.groupGrab.setEnabled(self.isOpen)
        self.ui.groupParam.setEnabled(self.isOpen)
        self.ui.bnOpen.setEnabled(not self.isOpen)
        self.ui.bnClose.setEnabled(self.isOpen)
        self.ui.bnStart.setEnabled(self.isOpen and (not self.isGrabbing))
        self.ui.bnStop.setEnabled(self.isOpen and self.isGrabbing)
        self.ui.bnSoftwareTrigger.setEnabled(self.isGrabbing and self.ui.radioTriggerMode.isChecked())
        self.ui.bnSaveImage.setEnabled(self.isOpen and self.isGrabbing)
    
