

from pypylon import pylon
import cv2
import numpy as np
import time
from PyQt5.QtWidgets import *
from PyQt5 import QtCore, QtWidgets, QtGui

import datetime
from pypylon import genicam
import threading
from base.ultils import PLC_Connection
import socket

class Basler_Pylon_xFunc(PLC_Connection):
    def __init__(self,n_serial,n_UserSetSelector,host, port,*args, **kwargs):
        super(Basler_Pylon_xFunc, self).__init__(host, port,*args, **kwargs)
        super().__init__(host, port)
        self.n_serial = str(n_serial) 
        self.UserSetSelector = n_UserSetSelector
        self.camera = None
        self.isOpen = False
        self.isGrabbing= []
        self.converter = pylon.ImageFormatConverter()
        self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
        self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
        self.b_start_grabbing=False
        self.b_exit = False
        self.b_thread_closed = False
        self.initialize_camera_indirect()
        

    def check_connect(self):
        return self.isOpen

    def initialize_device(self): 
        try: 
            self.enum_devices()
            self.open_device()
            print("init successfully!")
        except: 
            print('Unable to load Basler device! Please check your connection')
            pass

    def initialize_camera_indirect(self):
        self.devices = pylon.TlFactory.GetInstance().EnumerateDevices()
        if len(self.devices) == 0:
            print('No Connected device, check your connection!')
            return
        if not self.isOpen :
            for index, device in enumerate(self.devices):
                device.GetDeviceClass()
                if device.GetSerialNumber() == self.n_serial: 
                    if device.GetSerialNumber() == self.n_serial: 
                        self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice(self.devices[index]))
                        self.camera.Open()
                        self.isOpen = True
                        self.b_thread_closed = False
                        print('Connected to Camera Device')
                    else : 
                        print('Camera serial number error. Please try again!')
                        return
        else: 
            print('Camera is running')

    def enum_devices(self):
        self.devices = pylon.TlFactory.GetInstance().EnumerateDevices()
        
    def open_device(self):
        id_UserSetConfirm = 0
        if not self.isOpen:
            for index, device in enumerate(self.devices):
                if device.GetSerialNumber() == self.n_serial: 
                    id_UserSetConfirm = index
                else : 
                    print('Camera serial number error. Please try again!')
                    return
            self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice(self.devices[id_UserSetConfirm]))
            self.camera.Open()
            self.camera.UserSetSelector.SetValue(self.UserSetSelector)
            self.camera.UserSetLoad.Execute()
            self.isOpen = True
            self.b_thread_closed = False
    
    def StartGrabbingInit(self): 
        self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

    def TriggerOnce(self,task,trigger,busy_c1,socket):
        self.writedata(socket,trigger,0)
        self.writedata(socket,busy_c1,1)
        self.writedata(socket,busy_c1,0)
        time.sleep(0.015)
        grab_result = self.camera.RetrieveResult(10, pylon.TimeoutHandling_ThrowException)
        if grab_result.GrabSucceeded():
            image_bufer = grab_result.Array
            task.put(image_bufer)
       
    def saveImage(self,grabResult,typeImage,quality = 100):
        now = datetime.now()
        dateTime = now.strftime("%d-%m-%Y_%H-%M-%S")
        img = pylon.PylonImage()
        img.AttachGrabResultBuffer(grabResult)
        if typeImage == "jpg" :
            ipo = pylon.ImagePersistenceOptions()
            ipo.SetQuality(quality)
            filename = f"{dateTime}.jpg"
            img.Save(pylon.ImageFileFormat_Jpeg, filename, ipo)
        else :
            filename = f"{dateTime}.png"
            img.Save(pylon.ImageFileFormat_Png, filename)


    def Start_grabbing(self, task):
        if not self.b_start_grabbing and self.isOpen:
            self.b_exit = False
            self.b_start_grabbing = True
            print("start grabbing successfully!")
            try:
                self.h_thread_handle = threading.Thread(target=Basler_Pylon_xFunc.TriggerOnce, args=(self, task))
                self.h_thread_handle.start()
                self.b_thread_closed = True
            finally:
                pass

    def Stop_grabbing(self):
        if self.b_start_grabbing and self.isOpen:
            if self.b_thread_closed:
                self.camera.StopGrabbing()
                self.camera.Close()    
                self.b_thread_closed = False
            print("stop grabbing successfully!")
            self.b_start_grabbing = False
            self.b_exit = True

    def Close_device(self):
        if self.isOpen:
            if self.b_thread_closed:
                self.camera.DestroyDevice()
                self.b_thread_closed = False
                self.b_exit = True
    
    def start_stream(self):
        self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        self.timer = QtCore.QTimer(self.ui.centralWidget)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    def update_frame(self):
        try : 
            if self.camera.IsGrabbing():
                grab_result = self.camera.RetrieveResult(100000, pylon.TimeoutHandling_ThrowException)
                if grab_result.GrabSucceeded():
                    frame_bufer = self.converter.Convert(grab_result)
                    img_buff = frame_bufer.GetArray()
                    image_rgb = cv2.cvtColor(img_buff, cv2.COLOR_BGR2RGB)
                    height, width, channel = image_rgb.shape
                    bytes_per_line = 3 * width
                    q_img = QtGui.QImage(image_rgb.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888)
                    pixmap = QtGui.QPixmap.fromImage(q_img)
                    self.ui.labelDisplay.setPixmap(pixmap)
                grab_result.Release()
        except genicam.GenericException as e:
            raise genicam.RuntimeException("Could not Streaming")

    def stop_stream(self):
        if self.camera.IsGrabbing():
            self.camera.StopGrabbing()
        if hasattr(self, 'timer'):
            self.timer.stop()

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



    


