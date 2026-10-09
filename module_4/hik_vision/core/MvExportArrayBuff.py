# -- coding: utf-8 --
import sys,os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PyQt5.QtWidgets import *
from core.CamOperation_class import CameraOperation
from core.MvCameraControl_class import *
from core.MvErrorDefine_const import *
from core.CameraParams_header import *
from core.PyUICBasicDemo import Ui_MainWindow

import numpy as np

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


class Initialize_Device_Env_MVS():
    def __init__(self,mainWindow,ui):
        self.mainWindow=mainWindow
        self.ui = ui
        self.deviceList = MV_CC_DEVICE_INFO_LIST()
        self.cam = MvCamera()
        self.nSelCamIndex = 0
        self.obj_cam_operation = 0
        self.isOpen = False
        self.isGrabbing= False
        self.b_exit = False
        self.isCalibMode = False # 是否是标定模式（获取原始图像）
        self.tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE
        # self.initialize_device()

    def initialize_device(self):
        try:
            # self.enum_devices()
            # self.open_device()
            self.open_device_local()
        except: 
            print('Unable to load camera HIK device! Please check the device I/O connection')
            pass
   
    # 绑定下拉列表至设备信息索引
    def xFunc(event):
        # global nSelCamIndex
        # nSelCamIndex = TxtWrapBy("[", "]", ui.ComboDevices.get())
        pass

    # ch:枚举相机 | en:enum devices
    def enum_devices(self):

        ret = MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE | MV_USB_DEVICE, self.deviceList)
        if ret != 0:
            strError = "Enum devices fail! ret = :" + ToHexStr(ret)
            
            return ret

        if self.deviceList.nDeviceNum == 0:
           
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
                # devList.append("[" + str(i) + "]USB: " + chUserDefinedName + " " + chModelName
                #                + "(" + str(strSerialNumber) + ")")
                PORT = 'USB'
                devList.append(f'[{str(i)}]%{PORT}%{chModelName}%{strSerialNumber}')
        
        self.ui.comboBox_device_list.clear()
        self.ui.comboBox_device_list.addItems(devList)
        self.ui.comboBox_device_list.setCurrentIndex(0)

    # ch:打开相机 | en:open device
    def open_device(self):
       
        if self.isOpen:
            
            return MV_E_CALLORDER

        self.nSelCamIndex = self.ui.comboBox_device_list.currentIndex()
        print(self.nSelCamIndex)
        if self.nSelCamIndex < 0:
           
            return MV_E_CALLORDER
        
        

        port = self.ui.comboBox_device_list.currentText().split('%')[1]
        chModeName = self.ui.comboBox_device_list.currentText().split('%')[2]
        strSerialNumber = self.ui.comboBox_device_list.currentText().split('%')[3]

        self.ui.label_dev_name.setText('HIKROBOT')
        self.ui.label_PartNo.setText(chModeName)
        self.ui.label_SerialNo.setText(strSerialNumber)
        self.ui.label_Port.setText(port)

        self.obj_cam_operation = CameraOperation(obj_cam=self.cam,st_device_list = self.deviceList,n_connect_num=self.nSelCamIndex)
        ret = self.obj_cam_operation.Open_device()
        if 0 != ret:
            strError = "Open device failed ret:" + ToHexStr(ret)
            
            self.isOpen = False
        else:
            self.set_continue_mode()

            self.get_param()

            self.isOpen = True
            self.enable_controls()

    # ch:开始取流 | en:Start grab image
    def start_grabbing(self,task):
      
        ret = self.obj_cam_operation.Start_grabbing_origin(self.nSelCamIndex+1,task)
        if ret != 0:
            strError = "Start grabbing failed ret:" + ToHexStr(ret)
           
        else:
            self.isGrabbing = True
            # enable_controls()

    def GetImgsBuffer(self,task):
        
        ret = self.obj_cam_operation.Thread_process(task)
        print('1')
        if ret != 0:
            strError = "Start grabbing failed ret:" + ToHexStr(ret)
            
        else:
            self.isGrabbing = True
            # enable_controls()


    # ch:停止取流 | en:Stop grab image
    def stop_grabbing(self):
        ret = self.obj_cam_operation.Stop_grabbing()
        if ret != 0:
            strError = "Stop grabbing failed ret:" + ToHexStr(ret)
           
        else:
            self.isGrabbing = False
            # enable_controls()

    # ch:关闭设备 | Close device
    def close_device(self):
        
        if self.isOpen:
            self.obj_cam_operation.Close_device()
            self.isOpen = False
            self.b_exit = True

        self.isGrabbing = False

        # enable_controls()

    # ch:设置触发模式 | en:set trigger mode
    def set_continue_mode(self):
        strError = None

        ret = self.obj_cam_operation.Set_trigger_mode(False)
        if ret != 0:
            strError = "Set continue mode failed ret:" + ToHexStr(ret) + " mode is " 

    # ch:设置软触发模式 | en:set software trigger mode
    def set_software_trigger_mode(self):

        ret = self.obj_cam_operation.Set_trigger_mode(True)
        if ret != 0:
            strError = "Set trigger mode failed ret:" + ToHexStr(ret)
        
    # ch:设置触发命令 | en:set trigger software
    def trigger_once(self):
        ret = self.obj_cam_operation.Trigger_once()
        if ret != 0:
            strError = "TriggerSoftware failed ret:" + ToHexStr(ret)

    # ch:存图 | en:save image
    def save_bmp(self):
        ret = self.obj_cam_operation.Save_Bmp()
        if ret != MV_OK:
            strError = "Save BMP failed ret:" + ToHexStr(ret)
        else:
            print("Save image success")

    # ch: 获取参数 | en:get param
    # def get_param(self):
    #     ret = self.obj_cam_operation.Get_parameter()
    #     if ret != MV_OK:
    #         strError = "Get param failed ret:" + ToHexStr(ret)
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

    # ch: 设置参数 | en:set param
    def set_param(self,frame_rate,exposure,gain):

        ret = self.obj_cam_operation.Set_parameter(frame_rate, exposure, gain)
        if ret != MV_OK:
            strError = "Set param failed ret:" + ToHexStr(ret)
        return MV_OK
    

    # ch:开始取流 | en:Start grab image
    def IsImageColor(self,enType):
        dates = {
            PixelType_Gvsp_RGB8_Packed: 'color',
            PixelType_Gvsp_BGR8_Packed: 'color',
            PixelType_Gvsp_YUV422_Packed: 'color',
            PixelType_Gvsp_YUV422_YUYV_Packed: 'color',
            PixelType_Gvsp_BayerGR8: 'color',
            PixelType_Gvsp_BayerRG8: 'color',
            PixelType_Gvsp_BayerGB8: 'color',
            PixelType_Gvsp_BayerBG8: 'color',
            PixelType_Gvsp_BayerGB10: 'color',
            PixelType_Gvsp_BayerGB10_Packed: 'color',
            PixelType_Gvsp_BayerBG10: 'color',
            PixelType_Gvsp_BayerBG10_Packed: 'color',
            PixelType_Gvsp_BayerRG10: 'color',
            PixelType_Gvsp_BayerRG10_Packed: 'color',
            PixelType_Gvsp_BayerGR10: 'color',
            PixelType_Gvsp_BayerGR10_Packed: 'color',
            PixelType_Gvsp_BayerGB12: 'color',
            PixelType_Gvsp_BayerGB12_Packed: 'color',
            PixelType_Gvsp_BayerBG12: 'color',
            PixelType_Gvsp_BayerBG12_Packed: 'color',
            PixelType_Gvsp_BayerRG12: 'color',
            PixelType_Gvsp_BayerRG12_Packed: 'color',
            PixelType_Gvsp_BayerGR12: 'color',
            PixelType_Gvsp_BayerGR12_Packed: 'color',
            PixelType_Gvsp_Mono8: 'mono',
            PixelType_Gvsp_Mono10: 'mono',
            PixelType_Gvsp_Mono10_Packed: 'mono',
            PixelType_Gvsp_Mono12: 'mono',
            PixelType_Gvsp_Mono12_Packed: 'mono'}
        return dates.get(enType, '未知')
    
    def open_device_local(self):
        if self.nSelCamIndex < 0:
            print ("num cam error!")
        nConnectionNum = self.nSelCamIndex
        
        self.ret = MvCamera.MV_CC_EnumDevices(self.tlayerType, self.deviceList)
        if self.ret != 0:
            print ("enum devices fail! self.ret[0x%x]" % self.ret)
            sys.exit()
        if self.deviceList.nDeviceNum == 0:
            print ("find no device!")
            sys.exit()
        print ("Find %d devices!" % self.deviceList.nDeviceNum)
        for i in range(0, self.deviceList.nDeviceNum):
            mvcc_dev_info = cast(self.deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE:
                print("gige device: [%d]" % i)
                strModeName = ""
                for per in mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName:
                    strModeName = strModeName + chr(per)
                print("device model name: %s" % strModeName)
                nip1 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0xff000000) >> 24)
                nip2 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x00ff0000) >> 16)
                nip3 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x0000ff00) >> 8)
                nip4 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x000000ff)
                print("current ip: %d.%d.%d.%d\n" % (nip1, nip2, nip3, nip4))
            elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
                print("u3v device: [%d]" % i)
                strModeName = ""
                for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName:
                    if per == 0:
                        break
                    strModeName = strModeName + chr(per)
                print("device model name: %s" % strModeName)

                strSerialNumber = ""
                for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber:
                    if per == 0:
                        break
                    strSerialNumber = strSerialNumber + chr(per)
                print ("user serial number: %s" % strSerialNumber)

        if int(nConnectionNum) >= self.deviceList.nDeviceNum:
            print ("intput error!")
            sys.exit()
        stDeviceList = cast(self.deviceList.pDeviceInfo[int(nConnectionNum)], POINTER(MV_CC_DEVICE_INFO)).contents
        self.ret = self.cam.MV_CC_CreateHandle(stDeviceList)
        if self.ret != 0:
            self.cam.MV_CC_DestroyHandle()
            print ("create handle fail! self.ret[0x%x]" % self.ret)
            sys.exit()
        self.ret = self.cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
        if self.ret != 0:
            print ("open device fail! self.ret[0x%x]" % self.ret)
            sys.exit()
        stParam = MVCC_INTVALUE()
        memset(byref(stParam), 0, sizeof(MVCC_INTVALUE))
        self.ret = self.cam.MV_CC_GetIntValue("PayloadSize", stParam)
        if self.ret != 0:
            print("get payload size fail! self.ret[0x%x]" % self.ret)
            sys.exit()
        nPayloadSize = stParam.nCurValue
        self.ret = self.cam.MV_CC_StartGrabbing()
        if self.ret != 0:
            print ("start grabbing fail! self.ret[0x%x]" % self.ret)
            sys.exit()
        data_buffer = (c_ubyte * nPayloadSize)()
        self.isOpen = True

    def put_imgs_buff(self,task):
        if self.isOpen: 
            img_buff = None
            stOutFrame = MV_FRAME_OUT()
            memset(byref(stOutFrame), 0, sizeof(stOutFrame))
            ret = self.cam.MV_CC_GetImageBuffer(stOutFrame, 1000)
            if None != stOutFrame.pBufAddr and 0 == ret:
                stConvertParam = MV_CC_PIXEL_CONVERT_PARAM()
                memset(byref(stConvertParam), 0, sizeof(stConvertParam))
                if self.IsImageColor(stOutFrame.stFrameInfo.enPixelType) == 'mono':
                    print("mono!")
                    stConvertParam.enDstPixelType = PixelType_Gvsp_Mono8
                    nConvertSize = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight
                elif self.IsImageColor(stOutFrame.stFrameInfo.enPixelType) == 'color':
                    print("color!")
                    stConvertParam.enDstPixelType = PixelType_Gvsp_BGR8_Packed  # opecv要用BGR，不能使用RGB
                    nConvertSize = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight * 3
                else:
                    print("not support!!!")
                if img_buff is None:
                    img_buff = (c_ubyte * stOutFrame.stFrameInfo.nFrameLen)()
                stConvertParam.nWidth = stOutFrame.stFrameInfo.nWidth
                stConvertParam.nHeight = stOutFrame.stFrameInfo.nHeight
                stConvertParam.pSrcData = cast(stOutFrame.pBufAddr, POINTER(c_ubyte))
                stConvertParam.nSrcDataLen = stOutFrame.stFrameInfo.nFrameLen
                stConvertParam.enSrcPixelType = stOutFrame.stFrameInfo.enPixelType
                stConvertParam.pDstBuffer = (c_ubyte * nConvertSize)()
                stConvertParam.nDstBufferSize = nConvertSize
                self.ret = self.cam.MV_CC_ConvertPixelType(stConvertParam)
                if self.ret != 0:
                    print("convert pixel fail! self.ret[0x%x]" % self.ret)
                    del stConvertParam.pSrcData
                    sys.exit()
                if self.IsImageColor(stOutFrame.stFrameInfo.enPixelType) == 'color':
                    img_buff = (c_ubyte * stConvertParam.nDstLen)()
                    cdll.msvcrt.memcpy(byref(img_buff), stConvertParam.pDstBuffer, stConvertParam.nDstLen)
                    img_buff = np.frombuffer(img_buff, count=int(stConvertParam.nDstBufferSize), dtype=np.uint8)#data以流的形式读入转化成ndarray对象
                    img_buff = img_buff.reshape(stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nWidth,3)
                else:
                    print("no data[0x%x]" % self.ret)
            nRet = self.cam.MV_CC_FreeImageBuffer(stOutFrame)
            task.put(img_buff)
            if self.b_exit:
                if img_buff is not None:
                    del img_buff
        else: 
            print('camera have not open yet! ')

    def enable_controls(self):
        self.ui.groupBox_device_information.setEnabled(self.isOpen)
        self.ui.groupBox_throught.setEnabled(self.isOpen)
        self.ui.groupBox_grab_image.setEnabled(self.isOpen)
        self.ui.groupBox_user_set_control.setEnabled(self.isOpen)
        self.ui.groupBox_Image_format_control.setEnabled(self.isOpen)
        self.ui.groupBox_acquisition_control.setEnabled(self.isOpen)
        self.ui.groupBox_analog_control.setEnabled(self.isOpen)
        self.ui.pushButton_stop_stream.setEnabled(self.isGrabbing)
        self.ui.pushButton_start_stream.setEnabled(not self.isGrabbing)



# import queue
# task = queue.Queue()
# dev = Initialize_Device_Env_MVS(0) 
# dev.enum_devices()
# dev.open_device()
# dev.GetImgsBuffer(task)
# img = task.get()
# print(img)