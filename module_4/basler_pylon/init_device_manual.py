from pypylon import pylon
from datetime import datetime
import os,cv2
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread, QMetaObject, Qt, Q_ARG
from PyQt5.QtGui import QImage, QPixmap
import time
from PyQt5.QtWidgets import QMessageBox
class Initial_Device_Manual:

    def __init__(self,mainWindow, ui):
        self.mainWindow = mainWindow
        self.ui = ui
        self.isOpen = False
        self.isGrabbing = False
        self.camera = None
        self.dict_dev_list = {}

    def get_camera_information(self,device):
        name = device.GetFriendlyName()
        parts = name.split(" ")
        model_name = parts[1]
        product_id = parts[2].strip("()")
        port_type = device.GetDeviceClass()
        return model_name, product_id,port_type

    def EnumerateDevices(self):
        devList = []
        devices = pylon.TlFactory.GetInstance().EnumerateDevices()
        if len(devices) == 0:
            QMessageBox.warning(self.mainWindow, "Info", "Find no device", QMessageBox.Ok)
        for id, device in enumerate(devices):
            model_name, product_id,port_type = self.get_camera_information(device)
            devList.append(f'[{id}]%{port_type}%{model_name}%{product_id}')
            self.dict_dev_list[id] = [{'class_device': device}] 
        self.ui.comboBox_device_list.clear()
        self.ui.comboBox_device_list.addItems(devList)
        self.ui.comboBox_device_list.setCurrentIndex(0)

    def OpenDevice(self):
        if self.isOpen:
            QMessageBox.warning(self.mainWindow, "Error", 'Camera is Running!', QMessageBox.Ok)
        nSelCamIndex = self.ui.comboBox_device_list.currentIndex()
        
        if nSelCamIndex < 0:
            QMessageBox.warning(self.mainWindow, "Error", 'Please select a camera!', QMessageBox.Ok)

        self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice(self.dict_dev_list[nSelCamIndex][0]['class_device']))
        if self.camera :
            self.camera.Open()
            self.isOpen = True
            self.enable_controls()
            try:
                port = self.ui.comboBox_device_list.currentText().split('%')[1]
                chModeName = self.ui.comboBox_device_list.currentText().split('%')[2]
                strSerialNumber = self.ui.comboBox_device_list.currentText().split('%')[3]

                self.ui.label_dev_name.setText('Basler')
                self.ui.label_PartNo.setText(chModeName)
                self.ui.label_SerialNo.setText(strSerialNumber)
                self.ui.label_Port.setText(port)
            except:
                pass 

            print('Open camera BASLER successfully')
        else:
            print('Open camera BASLER failed!')

    def load_nodemap(self,path_nodemap_pfs):
        self.loadSettings(path_nodemap_pfs)

    def load_userset(self,user_selector): 
        self.camera.UserSetSelector.SetValue(user_selector)
        self.camera.UserSetLoad.Execute()
        print('Load user setting camera 1 successfully')

    def loadSettings(self,nodeFile):
        if nodeFile :
            pylon.FeaturePersistence.Load(nodeFile, self.camera.GetNodeMap(), True)
            print('Load node map camera 1 successfully')

    def StopGrab(self):
        if self.isGrabbing:
            self.camera.StopGrabbing()
            self.isGrabbing = False
            print('Camera Stop Grabbing.')

    def StartGrab(self):
        if self.isGrabbing:
            print('Camera Start Grabbing.')
            return
        
        self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        self.isGrabbing = True

    def camera_check_USB(self,usb_port):
        lines = os.popen(f"echo vnm | sudo -S dmesg | grep -E '{usb_port}.*SerialNumber:'").read()
        serial_name_camera = [line.strip() for line in lines.splitlines()][-1].split(" ")[-1]
        return serial_name_camera

    def connect_camera(self,serial_number):
        try :
            self.devices = pylon.TlFactory.GetInstance().EnumerateDevices()
            for index, device in enumerate(self.devices):
                if device.GetSerialNumber() == serial_number: 
                    camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice(self.devices[index]))              
                return camera
        except Exception as error :
            print("Connect Camera",error)
    
    def Trigger_Camera_Software(self):
        time.sleep(0.025)
        time.sleep(0.008)
        while True:
            try :
                if self.camera.WaitForFrameTriggerReady(2000, pylon.TimeoutHandling_ThrowException):
                    self.camera.ExecuteSoftwareTrigger()
                    grabResult = self.camera.RetrieveResult(2000, pylon.TimeoutHandling_ThrowException) 
                    if grabResult.GrabSucceeded():
                        img = grabResult.Array
                        return img
                        # imgs.put(img)
            except Exception as error:
                print("Trigger Error: ",error) 

    def configure_software_trigger(self):
        self.camera.TriggerMode.SetValue('Off')
        self.camera.TriggerSelector.SetValue('FrameStart')
        self.camera.TriggerMode.SetValue('On')
        self.camera.TriggerSourcer.SetValue('Software')

    def configure_hardware_trigger(self):
        self.camera.TriggerMode.setvalue('On')
        self.camera.TriggerSource.setvalue('Line1')
        self.camera.TriggerActivation.setvalue('RisingEdge')

    def trigger_hardware(self):
        try:
            grabResult = self.camera.RetrieveResult(100, pylon.TimeoutHandling_ThrowException)
            if grabResult.GrabSucceeded(): 
                img = grabResult.GetArray()
                cv2.imwrite('swap.jpg',img)
                if self.ui.checkBox_display_img.isChecked():
                    h, w = img.shape[:2]
                    qimg = QImage(img.data, w, h, img.strides[0], QImage.Format_RGB888)
                    pix = QPixmap.fromImage(qimg)
                    QMetaObject.invokeMethod(
                        self.ui.label_display_image, "setPixmap",
                        Qt.QueuedConnection,
                        Q_ARG(QPixmap, pix)
                    )
        except Exception as e: 
            print('Triger Error: ',e) 
            
    def close_device(self):
        self.StopGrab()
        self.camera.Close()
        self.camera.DestroyDevice()
        self.isOpen = False
        self.enable_controls()


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
        