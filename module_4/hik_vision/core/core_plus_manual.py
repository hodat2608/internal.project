import sys,os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread, QMetaObject, Qt, Q_ARG
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QMessageBox
from core.CamOperation_class import *
from core.MvCameraControl_class import *
from core.MvErrorDefine_const import *
from core.CameraParams_header import *
import queue
import ctypes
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


class CameraWorker(QObject):
    image_ready = pyqtSignal(object)
    mirror_image_ready = pyqtSignal(object)

    def __init__(self, device):
        super().__init__()
        self.device = device
        self._streaming_mirror = False

    @pyqtSlot()
    def get_image(self):
        print('got it')
        img = self.device._internal_get_img()
        self.image_ready.emit(img)

    @pyqtSlot()
    def stream_mirror(self):
        self._streaming_mirror = True
        while self._streaming_mirror:
            img = self.device._internal_get_img()
            if img is not None:
                self.mirror_image_ready.emit(img)
            # Ngu dong nho de khong chiem 100% CPU
            QThread.msleep(15)

    @pyqtSlot()
    def capture_mirror(self):
        img = self.device._internal_get_img()
        if img is not None:
            self.mirror_image_ready.emit(img)
        # Ngu dong nho de khong chiem 100% CPU
        QThread.msleep(15)

    def stop_stream_mirror(self):
        self._streaming_mirror = False

class Initial_Device(QObject):
    def __init__(self, mainWindow, ui, _mirror_tab_widget):
        super().__init__()
        self.mainWindow = mainWindow
        self.ui = ui
        self._mirror_tab_widget = _mirror_tab_widget
        self.deviceList = MV_CC_DEVICE_INFO_LIST()
        self.cam = MvCamera()
        self.obj_cam_operation = 0
        self.isOpen = False
        self.isGrabbing = False
        self.isCalibMode = False
        self.task = queue.Queue()
        self.thread = QThread()
        self.worker = CameraWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.start()
        self.worker.image_ready.connect(self._display_image_to_ui)
        self.worker.mirror_image_ready.connect(self._display_mirror_image)
        self.list_size = []

    @pyqtSlot(object)
    def _display_mirror_image(self, img):
        if img is None:
            return
        try:
            if hasattr(self._mirror_tab_widget, 'mirror_device'):
                self._mirror_tab_widget.mirror_device.image = img
        except:
            pass
        h, w = img.shape[:2]
        qimg = QtGui.QImage(img.data, w, h, img.strides[0], QtGui.QImage.Format_RGB888)
        pix = QtGui.QPixmap.fromImage(qimg)
        QtCore.QMetaObject.invokeMethod(
            self._mirror_tab_widget.label_display_image, "set_pixmap_image",
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(QtGui.QPixmap, pix))

    def _internal_get_img(self):
        ret, img = self.obj_cam_operation.grab_frame(timeout=5000)
        if ret != 0 or img is None:
            print(f"Failed to grab frame! ret=0x{ret:08X}")
            return None
        return img

    def save_user_default(self):
        print(self.ui.comboBox_default_user.currentText())

    def enum_devices(self):
        ret = MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE | MV_USB_DEVICE, self.deviceList)
        if ret != 0:
            strError = "Enum devices fail! ret = :" + hex(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
            return ret

        if self.deviceList.nDeviceNum == 0:
            QMessageBox.warning(self.mainWindow, "Info", "Find no device", QMessageBox.Ok)
            return ret

        devList = []
        for i in range(0, self.deviceList.nDeviceNum):
            mvcc_dev_info = ctypes.cast(self.deviceList.pDeviceInfo[i], ctypes.POINTER(MV_CC_DEVICE_INFO)).contents
            if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE:
                PORT = 'GigE'
                chModelName = ''.join(chr(b) for b in mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName if b != 0)
                chUserDefinedName = ''.join(chr(b) for b in mvcc_dev_info.SpecialInfo.stGigEInfo.chUserDefinedName if b != 0)
                nip = mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp
                ip_str = '.'.join(str((nip >> offset) & 0xFF) for offset in [24, 16, 8, 0])
                devList.append(f"[{i}]%{PORT}%{chModelName}%{ip_str}")
            elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
                PORT = 'USB'
                chModelName = ''.join(chr(b) for b in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName if b != 0)
                chUserDefinedName = ''.join(chr(b) for b in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chUserDefinedName if b != 0)
                serial = ''.join(chr(b) for b in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber if b != 0)
                devList.append(f'[{i}]%{PORT}%{chModelName}%{serial}')

        self.ui.comboBox_device_list.clear()
        self.ui.comboBox_device_list.addItems(devList)
        self.ui.comboBox_device_list.setCurrentIndex(0)

    def open_device_camera(self):
        if self.isOpen:
            QMessageBox.warning(self.mainWindow, "Error", 'Camera is Running!', QMessageBox.Ok)
            return MV_E_CALLORDER

        nSelCamIndex = self.ui.comboBox_device_list.currentIndex()
        if nSelCamIndex < 0:
            QMessageBox.warning(self.mainWindow, "Error", 'Please select a camera!', QMessageBox.Ok)
            return MV_E_CALLORDER
        
        try:
            port = self.ui.comboBox_device_list.currentText().split('%')[1]
            chModeName = self.ui.comboBox_device_list.currentText().split('%')[2]
            strSerialNumberorIPaddress = self.ui.comboBox_device_list.currentText().split('%')[3]

            self.ui.label_dev_name.setText('HIK Vision')
            self.ui.label_PartNo.setText(chModeName)
            if port == 'GigE':
                self.ui.label_IP.setText(strSerialNumberorIPaddress)
                self.ui.label_SerialNo.setText('N/A')
            else:
                self.ui.label_SerialNo.setText(strSerialNumberorIPaddress)
                self.ui.label_IP.setText('N/A')
            self.ui.label_Port.setText(port)
        except:
            pass 

        self.obj_cam_operation = CameraOperation(self.cam, self.deviceList, nSelCamIndex)
        ret = self.obj_cam_operation.Open_device()
        if ret != 0:
            strError = "Open device failed ret:" + hex(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
            self.isOpen = False
        else:
            self.get_param()
            self.isOpen = True
            self.enable_controls()

    def start_grabbing_array(self):
        if self.ui.radioButton_free_run.isChecked():
            ret = self.obj_cam_operation.grabbing()
            if ret != 0:
                QMessageBox.warning(self.mainWindow, "Error",
                                     f"Failed to start grabbing array frame! ret=0x{ret:08X}",
                                     QMessageBox.Ok)
            print('Start Grabing Succesfully')
        else:
            ret = self.obj_cam_operation.not_grabbing()
            if ret != 0:
                QMessageBox.warning(self.mainWindow, "Error",
                                     f"Failed to stop grabbing array frame! ret=0x{ret:08X}",
                                     QMessageBox.Ok)  
             
    def start_grabbing_array_mirror(self):
        try:
            ret = self.obj_cam_operation.grabbing()
            if ret != 0:
                QMessageBox.warning(self.mainWindow, "Error",
                                        f"Failed to start grabbing array frame! ret=0x{ret:08X}",
                                        QMessageBox.Ok)
            print('Start Grabing Mirror Succesfully')
        except:
            QMessageBox.warning(self.mainWindow, "Error",
                                        f"Failed to start grabbing array frame!",
                                        QMessageBox.Ok)

    def GetImgArayBufferPushButton(self):
        QMetaObject.invokeMethod(
            self.worker,
            "get_image",
            Qt.QueuedConnection
        )

    def GetImgArayBuffer(self):
        ret, img = self.obj_cam_operation.grab_frame(timeout=5000)
        if ret != 0 or img is None:
            QMessageBox.warning(self.mainWindow, "Error",
                                f"Failed to grab frame! ret=0x{ret:08X}",
                                QMessageBox.Ok)
            return
        if self.ui.checkBox_display_img.isChecked():
            h, w = img.shape[:2]
            qimg = QtGui.QImage(img.data, w, h, img.strides[0], QtGui.QImage.Format_RGB888)
            pix = QtGui.QPixmap.fromImage(qimg)

            label_size = self.ui.label_display_image.size()
            if self.list_size == []:
                self.list_size.append(label_size)
            pix = pix.scaled(
                self.list_size[0],
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )

            QtCore.QMetaObject.invokeMethod(
                self.ui.label_display_image, "setPixmap",
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(QtGui.QPixmap, pix))
        return img

    def GetImgArayBuffer_mirror(self):
        ret, img = self.obj_cam_operation.grab_frame(timeout=5000)
        if ret != 0 or img is None:
            QMessageBox.warning(self.mainWindow, "Error",
                                f"Failed to grab frame! ret=0x{ret:08X}",
                                QMessageBox.Ok)
            return None

        try:
            if hasattr(self._mirror_tab_widget, 'mirror_device'):
                self._mirror_tab_widget.mirror_device.image = img
        except:
            pass

        h, w = img.shape[:2]
        qimg = QtGui.QImage(img.data, w, h, img.strides[0], QtGui.QImage.Format_RGB888)
        pix = QtGui.QPixmap.fromImage(qimg)

        label_size = self._mirror_tab_widget.label_display_image.size()
        if self.list_size == []:
            self.list_size.append(label_size)
        pix = pix.scaled(
            self.list_size[0],
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )

        QtCore.QMetaObject.invokeMethod(
            self._mirror_tab_widget.label_display_image, "set_pixmap_image",
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(QtGui.QPixmap, pix))
        return img

    @pyqtSlot(object)
    def _display_image_to_ui(self, img):
        if img is None:
            return
        if self.ui.checkBox_display_img.isChecked():
            h, w = img.shape[:2]
            qimg = QImage(img.data, w, h, img.strides[0], QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg)
            QMetaObject.invokeMethod(
                self.ui.label_display_image, "setPixmap",
                Qt.QueuedConnection,
                Q_ARG(QPixmap, pix)
            )

    def start_grabbing(self):
        ret = self.obj_cam_operation.Start_grabbing_origin(self.ui.label_display_image.winId())
        if ret != 0:
            strError = "Start grabbing failed ret:" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            self.isGrabbing = True
            self.enable_grabbing_controls()
    
    def start_grabbing_mirror(self):
        # KHONG DUNG Start_grabbing_mirror(winId()) vi SDK ve de len crosshair.
        # Dung luong python de convert thanh QPixmap va giao lai cho Qt ve.
        ret = self.obj_cam_operation.grabbing()
        if ret != 0:
            strError = "Start grabbing failed ret:" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            self.isGrabbing = True
            self.enable_grabbing_controls()
            # Goi ham stream async cua CameraWorker de day QPixmap
            QtCore.QMetaObject.invokeMethod(self.worker, "stream_mirror", QtCore.Qt.QueuedConnection)

    def stop_grabbing(self):
        ret = self.obj_cam_operation.Stop_grabbing()
        if ret != 0:
            strError = "Stop grabbing failed ret:" + ToHexStr(ret)
            QMessageBox.warning(self.mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            self.isGrabbing = False
            self.enable_grabbing_controls()

    def stop_grabbing_mirror(self):
        self.worker.stop_stream_mirror()
        ret = self.obj_cam_operation.not_grabbing()
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
            # self.ui.doubleSpinBox_Gamma.setValue((self.obj_cam_operation.camera_params['Gamma']))
            # self.ui.spinBox_balance_ratio.setValue(int(self.obj_cam_operation.camera_params['BalanceRatio']))

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
