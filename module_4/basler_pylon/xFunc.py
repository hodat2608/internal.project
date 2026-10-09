

from pypylon import pylon
import cv2
import numpy as np
import time
from PyQt5.QtWidgets import *
from PyQt5 import QtCore, QtWidgets, QtGui

import datetime
from pypylon import genicam
import threading
import concurrent.futures
from base.IOConnection.basler_pylon.PyUICWidgets import *
class Basler_Pylon:
    def __init__(self,mainWindow,ui):
        self.mainWindow=mainWindow
        self.ui = ui
        self.camera = None
        self.isOpen = False
        self.isGrabbing= []
        self.isStreaming=False
        self.selected_folder_path = ''
        self.converter = pylon.ImageFormatConverter()
        self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
        self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.screen_geometry = QtWidgets.QApplication.desktop().screenGeometry()
        self.fullScreen()

    def initialize_camera(self):
        self.devices = pylon.TlFactory.GetInstance().EnumerateDevices()
        if len(self.devices) == 0:
            QMessageBox.warning(self.mainWindow, "Error", 'No connected devices found !', QMessageBox.Ok)
            return
        listDevice = []
        self.ui.ComboDevices.clear()
        for index, device in enumerate(self.devices):
            device.GetDeviceClass()
            device_info = f"[{str(index)}]{device.GetModelName()} serial:{device.GetSerialNumber()}"
            listDevice.append(device_info)
            self.ui.bnEnum.setEnabled(False)
            self.ui.bnOpen.setEnabled(True)
        if len(listDevice)==0: 
            self.ui.bnEnum.setEnabled(True)
        self.ui.ComboDevices.addItems(listDevice)
        self.ui.ComboDevices.setCurrentIndex(0)

    def open_device(self):
        selected_index = self.ui.ComboDevices.currentIndex()
        if selected_index == -1 or len(self.devices) == 0:
            QMessageBox.warning(self.mainWindow, "Error", 'Please select a camera!', QMessageBox.Ok)
            return
        try:
            self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice(self.devices[selected_index]))
            self.camera.Open()
        except genicam.GenericException as e :
            QMessageBox.warning(self.mainWindow, "Warning", f'Error Code: {e}', QMessageBox.Ok)
            return
        self.ui.bnClose.setEnabled(True)
        self.ui.bnOpen.setEnabled(False)
        self.ui.groupParam.setEnabled(True)
        self.ui.groupGrab_1.setEnabled(True)
        self.ui.radioTriggerMode.setChecked(True)
        self.ui.bnSoftwareTrigger.setEnabled(True)
        self.ui.bnSaveImage.setEnabled(True)
        self.ui.groupGrab.setEnabled(True)
        self.ui.radioContinueMode.setChecked(False)
        self.ui.bnStart.setEnabled(False)
        self.ui.bnStop.setEnabled(False)
        self.isOpen = True
        self.ExportValue()
        
    def SetValuePrams(self):
        if not self.isOpen: 
            QMessageBox.warning(self.mainWindow, "Warning", 'The device has been disconnected.!', QMessageBox.Ok)
        width = self.ui.edtwidth.text()
        height = self.ui.edtheight.text()
        OffsetX = self.ui.edtOffsetX.text()
        OffsetY = self.ui.edtOffsetY.text()
        exposure_time = self.ui.edtExposureTime.text()
        gain = self.ui.edtGain.text()
        AcquisitionFrameRate = self.ui.edtFrameRate.text()
        UserSet = self.ui.combo_usersetload.currentText()
        UserSetList = ['Default','UserSet1','UserSet2','UserSet3']   

        if int(float(width)) > self.camera.Width.Max: 
            QMessageBox.warning(self.mainWindow,"Warning",f'Value Width={width} must be equal or smaller than Max={self.camera.Width.Max}',QMessageBox.Ok)
            return 
        elif int(float(width)) < self.camera.Width.Min: 
            QMessageBox.warning(self.mainWindow,"Warning",f'Value Width={width} must be equal or higher than Min={self.camera.Width.Min}',QMessageBox.Ok)
            return 
        if int(float(height)) > self.camera.Height.Max: 
            QMessageBox.warning(self.mainWindow,"Warning",f'Value Height={height} must be equal or smaller than Max={self.camera.Height.Max}',QMessageBox.Ok)
            return
        elif int(float(height)) < self.camera.Height.Min: 
            QMessageBox.warning(self.mainWindow,"Warning",f'Value Width={height} must be equal or higher than Min={self.camera.Height.Min}',QMessageBox.Ok)
            return  
        if int(float(OffsetX)) > self.camera.OffsetX.Max: 
            QMessageBox.warning(self.mainWindow,"Warning",f'Value Width={OffsetX} must be equal or smaller than Max={self.camera.OffsetX.Max}',QMessageBox.Ok)
            return 
        elif int(float(OffsetX)) < self.camera.OffsetX.Min: 
            QMessageBox.warning(self.mainWindow,"Warning",f'Value Width={OffsetX} must be equal or higher than Min={self.camera.OffsetX.Min}',QMessageBox.Ok)
            return  
        if int(float(OffsetY)) > self.camera.OffsetY.Max: 
            QMessageBox.warning(self.mainWindow,"Warning",f'Value Height={OffsetY} must be equal or smaller than Max={self.camera.OffsetY.Max}',QMessageBox.Ok)
            return 
        elif int(float(OffsetY)) < self.camera.OffsetY.Min: 
            QMessageBox.warning(self.mainWindow,"Warning",f'Value Width={OffsetY} must be equal or higher than Min={self.camera.OffsetY.Min}',QMessageBox.Ok)
            return  
        if float(exposure_time) > self.camera.ExposureTime.Max: 
            QMessageBox.warning(self.mainWindow,"Warning",f'Value Height={exposure_time} must be equal or smaller than Max={self.camera.ExposureTime.Max}',QMessageBox.Ok)
            return 
        elif float(exposure_time) < self.camera.ExposureTime.Min: 
            QMessageBox.warning(self.mainWindow,"Warning",f'Value Width={exposure_time} must be equal or higher than Min={self.camera.ExposureTime.Min}',QMessageBox.Ok)
            return  
        if float(gain) > self.camera.Gain.Max: 
            QMessageBox.warning(self.mainWindow,"Warning",f'Value Width={gain} must be equal or smaller than Max={self.camera.Gain.Max}',QMessageBox.Ok)
            return 
        elif float(gain) < self.camera.Gain.Min: 
            QMessageBox.warning(self.mainWindow,"Warning",f'Value Width={gain} must be equal or higher than Min={self.camera.Gain.Min}',QMessageBox.Ok)
            return  
        if int(float(AcquisitionFrameRate)) > self.camera.AcquisitionFrameRate.Max: 
            QMessageBox.warning(self.mainWindow,"Warning",f'Value Height={AcquisitionFrameRate} must be equal or smaller than Max ={self.camera.AcquisitionFrameRate.Max}',QMessageBox.Ok)
            return 
        elif int(float(AcquisitionFrameRate))  < self.camera.AcquisitionFrameRate.Min: 
            QMessageBox.warning(self.mainWindow,"Warning",f'Value Width={AcquisitionFrameRate} must be equal or higher than Min={self.camera.AcquisitionFrameRate.Min}',QMessageBox.Ok)
            return  
        if str(UserSet) not in UserSetList: 
            QMessageBox.warning(self.mainWindow,"Warning",f'Value UserSet={str(UserSet)} must be in {UserSetList}',QMessageBox.Ok)
            return 
        try:
            self.camera.UserSetSelector.SetValue(str(UserSet))
            self.camera.UserSetLoad.Execute()
            if genicam.IsWritable(self.camera.Width):
                self.camera.Width.SetValue(int(float(width)))
            if genicam.IsWritable(self.camera.Height):
                self.camera.Height.SetValue(int(float(height)))
            if genicam.IsWritable(self.camera.OffsetX):
                self.camera.OffsetX.SetValue(int(float(OffsetX)))
            if genicam.IsWritable(self.camera.OffsetY):
                self.camera.OffsetY.SetValue(int(float(OffsetY)))
            if genicam.IsWritable(self.camera.ExposureTime):
                self.camera.ExposureTime.SetValue(float(exposure_time))
            if genicam.IsWritable(self.camera.Gain):
                self.camera.Gain.SetValue(float(gain))
            if genicam.IsWritable(self.camera.AcquisitionFrameRate):
                self.camera.AcquisitionFrameRate.SetValue(int(float(AcquisitionFrameRate)))
            self.camera.UserSetSave.Execute()    
        except genicam.GenericException as e:
            QMessageBox.critical(self.mainWindow, "Error", f"Could not apply configuration. Error: {str(e)}", QMessageBox.Ok)
        QMessageBox.information(self.mainWindow,"Warning",'Save Params Success')
        
    def ExportValue(self):
        UserSet = self.ui.combo_usersetload.currentText()
        self.camera.UserSetSelector.SetValue(str(UserSet))
        self.camera.UserSetLoad.Execute()
        self.ui.combo_usersetload.findText(self.camera.UserSetSelector.GetValue())
        self.ui.edtwidth.setText("{0:.1f}".format(self.camera.Width.GetValue()))
        self.ui.edtheight.setText("{0:.1f}".format(self.camera.Height.GetValue()))
        self.ui.edtOffsetX.setText("{0:.1f}".format(self.camera.OffsetX.GetValue()))
        self.ui.edtOffsetY.setText("{0:.1f}".format(self.camera.OffsetY.GetValue()))
        self.ui.edtExposureTime.setText("{0:.1f}".format(self.camera.ExposureTime.GetValue()))
        self.ui.edtGain.setText("{0:.1f}".format(self.camera.Gain.GetValue()))
        self.ui.edtFrameRate.setText("{0:.1f}".format(self.camera.AcquisitionFrameRate.GetValue()))

    def Trigger1(self):
        if self.isStreaming == True :
            QMessageBox.warning(self.mainWindow,"Warning",f'Camera is in streaming mode! Please stop stream before trigger',QMessageBox.Ok)
            return 
        self.isGrabbing = []
        try:
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            grab_result = self.camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
            if grab_result.GrabSucceeded():
                frame_bufer = self.converter.Convert(grab_result)
                img_buff = frame_bufer.GetArray()
                img_resized = cv2.resize(img_buff, (IMAGE_WIDTH, IMAGE_HEIGHT))
                img_flipped = cv2.flip(img_resized, 0)
                img_flipped = cv2.flip(img_flipped, 1)
                image_rgb = cv2.cvtColor(img_flipped, cv2.COLOR_BGR2RGB)
                height, width, channel = image_rgb.shape
                bytes_per_line = 3 * width
                q_img = QtGui.QImage(image_rgb.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888)
                pixmap = QtGui.QPixmap.fromImage(q_img)
                self.ui.labelDisplay.setPixmap(pixmap)
                name_file = str(datetime.datetime.now()).replace(':', '-').replace(' ', '_').replace('.', '-')
                if self.ui.checkbox.isChecked():
                    cv2.imwrite(f'{self.ui.folder_path_entry.text()}/{name_file}.jpg', image_rgb)
                else:
                    pass
                self.isGrabbing.append(pixmap)
                grab_result.Release()
            else:
                print("Error: Grabbing failed.")    
        except genicam.GenericException as e:
            print("Error: Could not grab image.") 
            print(e)   
        finally:
            self.camera.StopGrabbing()
            self.camera.Close()

    def close_device(self):
        self.camera.DestroyDevice()
        print('camera close success')
        self.ui.bnEnum.setEnabled(False)
        self.ui.bnClose.setEnabled(False)
        self.ui.bnOpen.setEnabled(True)
        self.ui.groupParam.setEnabled(False)
        self.ui.groupGrab.setEnabled(False)
        self.ui.groupGrab_1.setEnabled(False)
        self.isOpen = False

    def start_stream(self):
        self.isStreaming=True
        self.ui.bnStart.setEnabled(False)
        self.ui.bnStop.setEnabled(True)
        self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        self.timer = QtCore.QTimer(self.ui.centralWidget)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    def update_frame(self):
        try : 
            if self.camera.IsGrabbing():
                grab_result = self.camera.RetrieveResult(100000, pylon.TimeoutHandling_ThrowException)
                if grab_result.GrabSucceeded():
                    self.data2defaultScreen(grab_result)
                    try: 
                        self.data2fullScreen(grab_result)
                    except: 
                        QMessageBox.warning(self.mainWindow,"Warning",f'Please Push Full Screen mode First',QMessageBox.Ok)
                        pass
                grab_result.Release()
        except genicam.GenericException as e:
            raise genicam.RuntimeException("Could not Streaming")

    def stop_stream(self):
        if self.camera.IsGrabbing():
            self.camera.StopGrabbing()
            self.isStreaming=False
        self.ui.bnStart.setEnabled(True)
        self.ui.bnStop.setEnabled(False)
        if hasattr(self, 'timer'):
            self.timer.stop()

    def set_software_trigger_mode(self):
        self.ui.radioContinueMode.setChecked(False)
        self.ui.radioTriggerMode.setChecked(True)
        self.ui.groupGrab_1.setEnabled(True)
        self.ui.bnSoftwareTrigger.setEnabled(True)
        self.ui.bnSaveImage.setEnabled(True)
        self.ui.bnStart.setEnabled(False)

    def set_continue_mode(self):
        self.ui.radioContinueMode.setChecked(True)
        self.ui.radioTriggerMode.setChecked(False)
        self.ui.groupGrab.setEnabled(True)
        self.ui.bnStart.setEnabled(True)
        self.ui.bnSoftwareTrigger.setEnabled(False)
        self.ui.bnSaveImage.setEnabled(False)

    def save_img(self):
        current_time = str(datetime.datetime.now())
        name_folder = current_time.replace(':', '-').replace(' ', '_').replace('.', '-')
        file_path = filedialog.asksaveasfilename(
            defaultextension=f"{name_folder}.png",
            filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")],
            title="Save image as")
        if file_path:
            cv2.imwrite(file_path, self.isGrabbing[0])
            print(f"Image saved to: {file_path}")
        else:
            print("Save operation was canceled.")

    def open_folder_dialog(self):
        folder_path = filedialog.askdirectory(title="Select Folder")
        if folder_path:
            self.ui.folder_path_entry.setText(folder_path)

    def fullScreen(self): 
        self.ui.openFullScreenWindow()

    def data2defaultScreen(self,grab_result):
        frame_bufer = self.converter.Convert(grab_result)
        img_buff = frame_bufer.GetArray()
        img_resized = cv2.resize(img_buff, (IMAGE_WIDTH, IMAGE_HEIGHT))
        img_flipped = cv2.flip(img_resized, 0)
        img_flipped = cv2.flip(img_flipped, 1)
        image_rgb = cv2.cvtColor(img_flipped, cv2.COLOR_BGR2RGB)
        height, width, channel = image_rgb.shape
        bytes_per_line = 3 * width
        q_img = QtGui.QImage(image_rgb.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888)
        pixmap = QtGui.QPixmap.fromImage(q_img)
        self.ui.labelDisplay.setPixmap(pixmap)
    
    def data2fullScreen(self,grab_result):
        frame_bufer = self.converter.Convert(grab_result)
        img_buff = frame_bufer.GetArray()
        img_resized = cv2.resize(img_buff, (self.screen_geometry.width(), self.screen_geometry.height()))
        img_flipped = cv2.flip(img_resized, 0)
        img_flipped = cv2.flip(img_flipped, 1)
        image_rgb = cv2.cvtColor(img_flipped, cv2.COLOR_BGR2RGB)
        height, width, channel = image_rgb.shape
        bytes_per_line = 3 * width
        q_img = QtGui.QImage(image_rgb.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888)
        pixmap = QtGui.QPixmap.fromImage(q_img)
        self.ui.fullScreenLabel.setPixmap(pixmap)

    


