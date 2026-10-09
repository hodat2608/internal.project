from pypylon import pylon
from datetime import datetime
import os,cv2
import time

class Initial_Device_Auto:

    def __init__(self,serial_device,port):
        self.serial_device = int(serial_device)
        self.dict_device = {}
        self.camera = None
        
    def get_camera_information(self,device):
        name = device.GetFriendlyName()
        parts = name.split(" ")
        model_name = parts[1]
        product_id = parts[2].strip("()")
        port_type = device.GetDeviceClass()
        return model_name, product_id,port_type

    def EnumerateDevices(self):
        devices = pylon.TlFactory.GetInstance().EnumerateDevices()
        for device in devices:
            model_name, product_id,port_type = self.get_camera_information(device)
            self.dict_device[int(product_id)] = []
            self.dict_device[int(product_id)].append({
                                'class_device': device,
                                'model_name': model_name,
                                'port': port_type
                            })   

    def OpenDevice(self):
        self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice(self.dict_device[self.serial_device][0]['class_device']))
        if self.camera:
            self.camera.Open()
            print('- Open camera BASLER successfully')
        else:
            print('- Open camera BASLER Failed, Please try again!')

    def load_nodemap(self,path_nodemap_pfs):
        self.loadSettings(path_nodemap_pfs)

    def load_userset(self,user_selector): 
        print(f'[-] Loading {user_selector} from Pylon...')
        self.camera.UserSetSelector.SetValue(user_selector)
        self.camera.UserSetLoad.Execute()
        print(f'[-] Load {user_selector} from Pylon successfully!')

    def loadSettings(self,nodeFile):
        if nodeFile :
            pylon.FeaturePersistence.Load(nodeFile, self.camera.GetNodeMap(), True)
            print('- Load node map camera 1 successfully')

    def StopGrab(self):
        self.camera.StopGrabbing()
        print('[-] Stop Grabbing PYLON 8.0 DRIVER Succesfully!')

    def StartGrab(self):
        self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        print('[-] Start Grabbing PYLON 8.0 DRIVER Succesfully!')

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
            print("- Connect Camera",error)
    
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
                image = grabResult.GetArray()
                cv2.imwrite('swap123123.jpg',image)
                return image
        except Exception as e: 
            print('Triger Error: ',e) 
            
    def close_device(self):
        self.camera.Close()
        self.camera.DestroyDevice()
        
# dev = Initial_Device_Auto(25039618)
# dev.EnumerateDevices()
# dev.OpenDevice()
# dev.StartGrab()
# dev.Trigger_Camera_Software()