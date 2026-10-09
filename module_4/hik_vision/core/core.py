# -- coding: utf-8 --
import sys,os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PyQt5.QtWidgets import *
from core.CamOperation_class import CameraOperation
from core.MvCameraControl_class import *
from core.MvErrorDefine_const import *
from core.CameraParams_header import *
import queue
from PyQt5 import QtCore, QtGui, QtWidgets, QtMultimedia

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

class Qthread_Helper(QtCore.QThread):
    image_buff_recevied = QtCore.pyqtSignal(object)
    image_buff_error = QtCore.pyqtSignal(str)

    def __init__(self, object_cam, parent = None):
        super().__init__(parent)
        self.obj_camera = object_cam
        self.running = True

    def run(self):
        ret,img = self.obj_camera.grab_frame(timeout=5000)
        print('noeeee',img)


import threading 
class Initial_Device():
    def __init__(self,mainWindow,ui):
        self.mainWindow=mainWindow
        self.ui = ui
        self.deviceList = MV_CC_DEVICE_INFO_LIST()
        self.cam = MvCamera()
        self.obj_cam_operation = 0
        self.isOpen = False
        self.isGrabbing= False
        self.isCalibMode = False
        self.task = queue.Queue()
        self.image_thread = None
        self.lock_timer = threading.Lock()

    def save_user_default(self): 
        print(self.ui.comboBox_default_user.currentText())
   
    def xFunc(event,self):
        global nSelCamIndex
        nSelCamIndex = TxtWrapBy("[", "]", self.ui.comboBox_device_list.get())
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
                PORT = 'GigE'
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
                PORT = 'USB'
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

                # devList.append("[" + str(i) + "]USB: " + chUserDefinedName + " " + chModelName
                #                + "(" + str(strSerialNumber) + ")")

                devList.append(f'[{str(i)}]%{PORT}%{chModelName}%{strSerialNumber}')
                
        self.ui.comboBox_device_list.clear()
        self.ui.comboBox_device_list.addItems(devList)
        self.ui.comboBox_device_list.setCurrentIndex(0)


    def open_device_camera(self):
        if self.isOpen:
            QMessageBox.warning(self.mainWindow, "Error", 'Camera is Running!', QMessageBox.Ok)
            return MV_E_CALLORDER

        nSelCamIndex = self.ui.comboBox_device_list.currentIndex()
        print(nSelCamIndex)
        if nSelCamIndex < 0:
            QMessageBox.warning(self.mainWindow, "Error", 'Please select a camera!', QMessageBox.Ok)
            return MV_E_CALLORDER
        
        port = self.ui.comboBox_device_list.currentText().split('%')[1]
        chModeName = self.ui.comboBox_device_list.currentText().split('%')[2]
        strSerialNumber = self.ui.comboBox_device_list.currentText().split('%')[3]

        self.ui.label_dev_name.setText('HIKROBOT')
        self.ui.label_PartNo.setText(chModeName)
        self.ui.label_SerialNo.setText(strSerialNumber)
        self.ui.label_Port.setText(port)

        self.obj_cam_operation = CameraOperation(self.cam, self.deviceList, nSelCamIndex)
        ret = self.obj_cam_operation.Open_device()
        if 0 != ret:
            strError = "Open device failed ret:" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
            self.isOpen = False
        else:
            self.get_param()
            self.isOpen = True
            self.enable_controls()

    def start_grabbing_array(self): 
        with self.lock_timer:
            if self.ui.radioButton_free_run.isChecked():
                print('start grabbing array frame')
                ret = self.obj_cam_operation.grabbing()
                if ret != 0:
                    QMessageBox.warning(self.mainWindow, "Error",
                                        f"Failed to start grabbing array frame! ret=0x{ret:08X}",
                                        QMessageBox.Ok)
                    return
            else:
                print('stop grabbing array frame')
                ret = self.obj_cam_operation.not_grabbing()
                if ret != 0:
                    QMessageBox.warning(self.mainWindow, "Error",
                                        f"Failed to stop grabbing array frame! ret=0x{ret:08X}",
                                        QMessageBox.Ok)
                    return

    def GetImgArayBuffer(self):
        with self.lock_timer:
            ret, img = self.obj_cam_operation.grab_frame(timeout=5000)
            print(img)
            if ret != 0 or img is None:
                QMessageBox.warning(self.mainWindow, "Error",
                                    f"Failed to grab frame! ret=0x{ret:08X}",
                                    QMessageBox.Ok)
                return
            if self.ui.checkBox_display_img.isChecked():
                h, w = img.shape[:2]
                qimg = QtGui.QImage(img.data, w, h, img.strides[0], QtGui.QImage.Format_RGB888)
                pix = QtGui.QPixmap.fromImage(qimg)
                QtCore.QMetaObject.invokeMethod(
                    self.ui.label_display_image, "setPixmap",
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(QtGui.QPixmap, pix))

        return img
    
    # def GetImgArayBuffer(self):
    #     self.image_thread = Qthread_Helper(self.obj_cam_operation)
    #     self.image_thread.start()

        # return img
    


    def start_grabbing(self):
        ret = self.obj_cam_operation.Start_grabbing_origin(self.ui.label_display_image.winId())
        if ret != 0:
            strError = "Start grabbing failed ret:" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            self.isGrabbing = True
            self.enable_grabbing_controls()

    def stop_grabbing(self):
        ret = self.obj_cam_operation.Stop_grabbing()
        if ret != 0:
            strError = "Stop grabbing failed ret:" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            self.isGrabbing = False
            self.enable_grabbing_controls()

    def close_device(self):
        if self.isOpen:
            self.obj_cam_operation.Close_device()
            self.isOpen = False
        self.isGrabbing = False
        self.enable_controls()

    def set_continue_mode(self):
        print('continue mode is oprating')
        strError = None
        ret = self.obj_cam_operation.Set_trigger_mode(False)
        if ret != 0:
            strError = "Set continue mode failed ret:" + ToHexStr(ret) + " mode is " 
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            self.ui.radioButton_triggermode.setChecked(False)

    def set_software_trigger_mode(self):
        ret = self.obj_cam_operation.Set_trigger_mode(True)
        if ret != 0:
            strError = "Set trigger mode failed ret:" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            self.ui.radioButton_check_continous.setChecked(False)

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
        ret = self.obj_cam_operation.load_params_user_selector(user_set_index=self.ui.comboBox_user_selector.currentIndex())
        if ret != MV_OK:
            strError = "Get param failed ret:" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            self.ui.doubleSpinBox_Exposure_Time.setValue((self.obj_cam_operation.camera_params['ExposureTime']))
            self.ui.doubleSpinBox_Gain.setValue((self.obj_cam_operation.camera_params['Gain']))
            self.ui.doubleSpinBox_FrameRate.setValue((self.obj_cam_operation.camera_params['AcquisitionFrameRate']))
            self.ui.spinBox_default_width.setValue((self.obj_cam_operation.camera_params['WidthMax']))
            self.ui.spinBox_default_height.setValue((self.obj_cam_operation.camera_params['HeightMax']))
            self.ui.spinBox_width_selector.setValue((self.obj_cam_operation.camera_params['Width']))
            self.ui.spinBox_height_selector.setValue((self.obj_cam_operation.camera_params['Height']))
            self.ui.spinBox_offset_x.setValue((self.obj_cam_operation.camera_params['OffsetX']))
            self.ui.spinBox_offset_y.setValue((self.obj_cam_operation.camera_params['OffsetY']))
            self.ui.doubleSpinBox_Gamma.setValue((self.obj_cam_operation.camera_params['Gamma']))
            self.ui.spinBox_balance_ratio.setValue((self.obj_cam_operation.camera_params['BalanceRatio']))

    def set_param(self):
        ret = self.obj_cam_operation.save_params_user_selector(self.ui)
        if ret != MV_OK:
            strError = "Set param failed ret:" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
        QMessageBox.information(self.mainWindow, "Save Successful", strError, QMessageBox.Ok)
        return MV_OK
    

    def user_set_load(self):
        self.get_param()

    def enable_controls(self):
        self.ui.groupBox_device_information.setEnabled(self.isOpen)
        self.ui.groupBox_throught.setEnabled(self.isOpen)
        self.ui.groupBox_grab_image.setEnabled(self.isOpen)
        self.ui.groupBox_TriggerSourceOff.setEnabled(self.isOpen)
        self.ui.groupBox_user_set_control.setEnabled(self.isOpen)
        self.ui.groupBox_Image_format_control.setEnabled(self.isOpen)
        self.ui.groupBox_acquisition_control.setEnabled(self.isOpen)
        self.ui.groupBox_analog_control.setEnabled(self.isOpen)
        self.ui.pushButton_stop_stream.setEnabled(self.isGrabbing)
        self.ui.pushButton_start_stream.setEnabled(not self.isGrabbing)

    def enable_grabbing_controls(self):
        self.ui.pushButton_start_stream.setEnabled(not self.isGrabbing)
        self.ui.pushButton_stop_stream.setEnabled(self.isGrabbing)
