# -- coding: utf-8 --
import sys
import threading
import msvcrt
import numpy as np
import time
import sys, os
import datetime
import inspect
import ctypes
import random
from ctypes import *
import sys
import threading
import msvcrt
import numpy as np
from ctypes import *
# -- coding: utf-8 --
import sys
import threading
import msvcrt
import numpy as np
import cv2
import time
import sys, os
import datetime
import inspect
import ctypes
import random
from PIL import Image
from ctypes import *

# sys.path.append("../MvImport")

from core.CameraParams_header import *
from core.MvCameraControl_class import *

# 强制关闭线程
def Async_raise(tid, exctype):
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")


# 停止线程
def Stop_thread(thread):
    Async_raise(thread.ident, SystemExit)


# 转为16进制字符串
def To_hex_str(num):
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


# 是否是Mono图像
def Is_mono_data(enGvspPixelType):
    if PixelType_Gvsp_Mono8 == enGvspPixelType or PixelType_Gvsp_Mono10 == enGvspPixelType \
            or PixelType_Gvsp_Mono10_Packed == enGvspPixelType or PixelType_Gvsp_Mono12 == enGvspPixelType \
            or PixelType_Gvsp_Mono12_Packed == enGvspPixelType:
        return True
    else:
        return False


# 是否是彩色图像
def Is_color_data(enGvspPixelType):
    if PixelType_Gvsp_BayerGR8 == enGvspPixelType or PixelType_Gvsp_BayerRG8 == enGvspPixelType \
            or PixelType_Gvsp_BayerGB8 == enGvspPixelType or PixelType_Gvsp_BayerBG8 == enGvspPixelType \
            or PixelType_Gvsp_BayerGR10 == enGvspPixelType or PixelType_Gvsp_BayerRG10 == enGvspPixelType \
            or PixelType_Gvsp_BayerGB10 == enGvspPixelType or PixelType_Gvsp_BayerBG10 == enGvspPixelType \
            or PixelType_Gvsp_BayerGR12 == enGvspPixelType or PixelType_Gvsp_BayerRG12 == enGvspPixelType \
            or PixelType_Gvsp_BayerGB12 == enGvspPixelType or PixelType_Gvsp_BayerBG12 == enGvspPixelType \
            or PixelType_Gvsp_BayerGR10_Packed == enGvspPixelType or PixelType_Gvsp_BayerRG10_Packed == enGvspPixelType \
            or PixelType_Gvsp_BayerGB10_Packed == enGvspPixelType or PixelType_Gvsp_BayerBG10_Packed == enGvspPixelType \
            or PixelType_Gvsp_BayerGR12_Packed == enGvspPixelType or PixelType_Gvsp_BayerRG12_Packed == enGvspPixelType \
            or PixelType_Gvsp_BayerGB12_Packed == enGvspPixelType or PixelType_Gvsp_BayerBG12_Packed == enGvspPixelType \
            or PixelType_Gvsp_YUV422_Packed == enGvspPixelType or PixelType_Gvsp_YUV422_YUYV_Packed == enGvspPixelType:
        return True
    else:
        return False


# Mono图像转为python数组
def Mono_numpy(data, nWidth, nHeight):
    data_ = np.frombuffer(data, count=int(nWidth * nHeight), dtype=np.uint8, offset=0)
    data_mono_arr = data_.reshape(nHeight, nWidth)
    numArray = np.zeros([nHeight, nWidth, 1], "uint8")
    numArray[:, :, 0] = data_mono_arr
    return numArray


# 彩色图像转为python数组
def Color_numpy(data, nWidth, nHeight):
    data_ = np.frombuffer(data, count=int(nWidth * nHeight * 3), dtype=np.uint8, offset=0)
    data_r = data_[0:nWidth * nHeight * 3:3]
    data_g = data_[1:nWidth * nHeight * 3:3]
    data_b = data_[2:nWidth * nHeight * 3:3]

    data_r_arr = data_r.reshape(nHeight, nWidth)
    data_g_arr = data_g.reshape(nHeight, nWidth)
    data_b_arr = data_b.reshape(nHeight, nWidth)
    numArray = np.zeros([nHeight, nWidth, 3], "uint8")

    numArray[:, :, 0] = data_r_arr
    numArray[:, :, 1] = data_g_arr
    numArray[:, :, 2] = data_b_arr
    return numArray


# 相机操作类
class CameraOperation:

    def __init__(self, obj_cam, st_device_list, n_connect_num=0, b_open_device=False, b_start_grabbing=False,
                 h_thread_handle=None,
                 b_thread_closed=False, st_frame_info=None, b_exit=False, b_save_bmp=False, b_save_jpg=False,
                 buf_save_image=None,
                 n_save_image_size=0, n_win_gui_id=0, frame_rate=0, exposure_time=0, gain=0):

        self.obj_cam = obj_cam
        self.st_device_list = st_device_list
        self.n_connect_num = n_connect_num
        self.b_open_device = b_open_device
        self.b_start_grabbing = b_start_grabbing
        self.b_thread_closed = b_thread_closed
        self.st_frame_info = st_frame_info
        self.b_exit = b_exit
        self.b_save_bmp = b_save_bmp
        self.b_save_jpg = b_save_jpg
        self.buf_grab_image = None
        self.buf_grab_image_size = 0
        self.buf_save_image = buf_save_image
        self.n_save_image_size = n_save_image_size
        self.h_thread_handle = h_thread_handle
        self.b_thread_closed
        self.frame_rate = frame_rate
        self.exposure_time = exposure_time
        self.gain = gain
        self.buf_lock = threading.Lock()  # 取图和存图的buffer锁
        self.stOutFrame = MV_FRAME_OUT() 

    # 打开相机
    def Open_device(self):
        if not self.b_open_device:
            if self.n_connect_num < 0:
                return MV_E_CALLORDER

            # ch:选择设备并创建句柄 | en:Select device and create handle
            nConnectionNum = int(self.n_connect_num)
            stDeviceList = cast(self.st_device_list.pDeviceInfo[int(nConnectionNum)],
                                POINTER(MV_CC_DEVICE_INFO)).contents
            self.obj_cam = MvCamera()
            ret = self.obj_cam.MV_CC_CreateHandle(stDeviceList)
            if ret != 0:
                self.obj_cam.MV_CC_DestroyHandle()
                return ret

            ret = self.obj_cam.MV_CC_OpenDevice()
            if ret != 0:
                return ret
            self.b_open_device = True
            self.b_thread_closed = False

            # ch:探测网络最佳包大小(只对GigE相机有效) | en:Detection network optimal package size(It only works for the GigE camera)
            if stDeviceList.nTLayerType == MV_GIGE_DEVICE:
                nPacketSize = self.obj_cam.MV_CC_GetOptimalPacketSize()
                if int(nPacketSize) > 0:
                    ret = self.obj_cam.MV_CC_SetIntValue("GevSCPSPacketSize", nPacketSize)
                    if ret != 0:
                        print("warning: set packet size fail! ret[0x%x]" % ret)
                else:
                    print("warning: set packet size fail! ret[0x%x]" % nPacketSize)

            stBool = c_bool(False)
            ret = self.obj_cam.MV_CC_GetBoolValue("AcquisitionFrameRateEnable", stBool)
            if ret != 0:
                print("get acquisition frame rate enable fail! ret[0x%x]" % ret)

            # ch:设置触发模式为off | en:Set trigger mode as off
            ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
            if ret != 0:
                print("set trigger mode fail! ret[0x%x]" % ret)
            
            
            return MV_OK
        
    def grabbing(self):
        ret = self.obj_cam.MV_CC_StartGrabbing()
        if ret != 0:
            return ret
        return MV_OK
    
    def not_grabbing(self):
            ret = self.obj_cam.MV_CC_StopGrabbing()
            if ret != 0:
                return ret
            return MV_OK


    # 开始取图
    def Start_grabbing_origin(self, winHandle):
        if not self.b_start_grabbing and self.b_open_device:
            self.b_exit = False
            ret = self.obj_cam.MV_CC_StartGrabbing()
            if ret != 0:
                return ret
            self.b_start_grabbing = True
            print("start grabbing successfully!")
            try:
                thread_id = random.randint(1, 10000)
                self.h_thread_handle = threading.Thread(target=CameraOperation.Work_thread_origin, args=(self, winHandle))
                self.h_thread_handle.start()
                self.b_thread_closed = True
            finally:
                pass
            return MV_OK

        return MV_E_CALLORDER

    # 停止取图
    def Stop_grabbing(self):
        if self.b_start_grabbing and self.b_open_device:
            # 退出线程
            if self.b_thread_closed:
                Stop_thread(self.h_thread_handle)
                self.b_thread_closed = False
            ret = self.obj_cam.MV_CC_StopGrabbing()
            if ret != 0:
                return ret
            print("stop grabbing successfully!")
            self.b_start_grabbing = False
            self.b_exit = True
            return MV_OK
        else:
            return MV_E_CALLORDER

    # 关闭相机
    def Close_device(self):
        if self.b_open_device:
            # 退出线程
            if self.b_thread_closed:
                Stop_thread(self.h_thread_handle)
                self.b_thread_closed = False
            ret = self.obj_cam.MV_CC_CloseDevice()
            if ret != 0:
                return ret

        # ch:销毁句柄 | Destroy handle
        self.obj_cam.MV_CC_DestroyHandle()
        self.b_open_device = False
        self.b_start_grabbing = False
        self.b_exit = True
        print("close device successfully!")

        return MV_OK

    # 设置触发模式
    def Set_trigger_mode(self, is_trigger_mode):
        if not self.b_open_device:
            return MV_E_CALLORDER

        if not is_trigger_mode:
            ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", 0)
            if ret != 0:
                return ret
        else:
            ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", 1)
            if ret != 0:
                return ret
            ret = self.obj_cam.MV_CC_SetEnumValue("TriggerSource", 7)
            if ret != 0:
                return ret

        return MV_OK

    # 软触发一次
    def Trigger_once(self):
        if self.b_open_device:
            return self.obj_cam.MV_CC_SetCommandValue("TriggerSoftware")
        
    def save_params_user_selector(self,ui):
        if not self.b_open_device:
            print("Device is not opened.")
            return -1
        
        self.Set_parameter(ui)

        user_set_index = ui.comboBox_user_selector.currentIndex()
        if user_set_index:
            ret = self.obj_cam.MV_CC_SetEnumValue("UserSetSelector", user_set_index)
            if ret != 0:
                print("Failed to select UserSet1.")
                return ret

            ret = self.obj_cam.MV_CC_SetCommandValue("UserSetSave")
            if ret != 0:
                print(f"Failed to save settings to UserSet{user_set_index}.")
                return ret

            print(f"Settings saved to UserSet{user_set_index} successfully.")
            return 0
        else:
            return user_set_index

    def load_params_user_selector(self,user_set_index=0):
        print(f'[-] Loading UserSet{user_set_index} from MVS...')
        if not self.b_open_device:
            return -1

        ret = self.obj_cam.MV_CC_SetEnumValue("UserSetSelector", user_set_index)
        if ret != 0:
            print(f"=> Failed to select user set {user_set_index}, error: {ret}")
            return ret

        ret = self.obj_cam.MV_CC_SetCommandValue("UserSetLoad")
        if ret != 0:
            print(f"=> Failed to load user set {user_set_index}, error: {ret}")
            return ret
        
        print(f"[-] Load UserSet{user_set_index} from MVS Succesfully!")
        MV_OK = self.Get_all_parameter()

        return MV_OK    


    def Get_all_parameter(self):
        if not self.b_open_device:
            return -1

        self.camera_params = {}

        # --- FLOAT PARAMS ---
        float_params = ["AcquisitionFrameRate", "ExposureTime", "Gain", "Gamma"]
        for name in float_params:
            stVal = MVCC_FLOATVALUE()
            memset(byref(stVal), 0, sizeof(MVCC_FLOATVALUE))
            ret = self.obj_cam.MV_CC_GetFloatValue(name, stVal)
            if ret == 0:
                self.camera_params[name] = stVal.fCurValue
            else:
                self.camera_params[name] = None

        # --- BOOL PARAMS ---
        bool_params = ["GammaEnable"]
        for name in bool_params:
            stVal = c_bool(False)
            ret = self.obj_cam.MV_CC_GetBoolValue(name, stVal)
            if ret == 0:
                self.camera_params[name] = stVal.value
            else:
                self.camera_params[name] = None

        # --- ENUM PARAMS ---
        enum_params = [
            "BalanceWhiteAuto", "PixelFormat", "AcquisitionMode", "TriggerMode",
            "TriggerSource", "ExposureAuto", "GainAuto", "BinningSelector", "TestPattern"
        ]
        for name in enum_params:
            stVal = MVCC_ENUMVALUE()
            memset(byref(stVal), 0, sizeof(MVCC_ENUMVALUE))
            ret = self.obj_cam.MV_CC_GetEnumValue(name, stVal)
            if ret == 0:
                self.camera_params[name] = stVal.nCurValue
            else:
                self.camera_params[name] = None

        # --- INT PARAMS ---
        int_params = ["BinningHorizontal", "BinningVertical", "OffsetX", "OffsetY", "WidthMax", "HeightMax","Width","Height", "BalanceRatio"]
        for name in int_params:
            stVal = MVCC_INTVALUE()
            memset(byref(stVal), 0, sizeof(MVCC_INTVALUE))
            ret = self.obj_cam.MV_CC_GetIntValue(name, stVal)
            if ret == 0:
                self.camera_params[name] = stVal.nCurValue
            else:
                self.camera_params[name] = None
        return MV_OK


    # 获取参数
    def Get_parameter(self):
        if self.b_open_device:
            stFloatParam_FrameRate = MVCC_FLOATVALUE()
            memset(byref(stFloatParam_FrameRate), 0, sizeof(MVCC_FLOATVALUE))
            stFloatParam_exposureTime = MVCC_FLOATVALUE()
            memset(byref(stFloatParam_exposureTime), 0, sizeof(MVCC_FLOATVALUE))
            stFloatParam_gain = MVCC_FLOATVALUE()
            memset(byref(stFloatParam_gain), 0, sizeof(MVCC_FLOATVALUE))
            ret = self.obj_cam.MV_CC_GetFloatValue("AcquisitionFrameRate", stFloatParam_FrameRate)
            if ret != 0:
                return ret
            self.frame_rate = stFloatParam_FrameRate.fCurValue

            ret = self.obj_cam.MV_CC_GetFloatValue("ExposureTime", stFloatParam_exposureTime)
            if ret != 0:
                return ret
            self.exposure_time = stFloatParam_exposureTime.fCurValue

            ret = self.obj_cam.MV_CC_GetFloatValue("Gain", stFloatParam_gain)
            if ret != 0:
                return ret
            self.gain = stFloatParam_gain.fCurValue

            return MV_OK

    # 设置参数
    def Set_parameter(self,ui):
        frameRate = ui.doubleSpinBox_FrameRate.text()
        exposureTime = ui.doubleSpinBox_Exposure_Time.text()
        gain = ui.doubleSpinBox_Gain.text()
        width_selector = ui.spinBox_width_selector.text()
        height_selector = ui.spinBox_height_selector.text()
        OffSet_X = ui.spinBox_offset_x.text()
        OffSet_Y = ui.spinBox_offset_y.text()

        if '' == frameRate or '' == exposureTime or '' == gain or '' == width_selector or '' == height_selector or '' == OffSet_X or '' == OffSet_X or '' == OffSet_Y:
            print('show info', 'please type in the text box !')
            return MV_E_PARAMETER
        
        if self.b_open_device:
            ret = self.obj_cam.MV_CC_SetFloatValue("ExposureTime", float(exposureTime))
            if ret != 0:
                print('show error', 'set exposure time fail! ret = ' + To_hex_str(ret))
                return ret

            ret = self.obj_cam.MV_CC_SetFloatValue("Gain", float(gain))
            if ret != 0:
                print('show error', 'set gain fail! ret = ' + To_hex_str(ret))
                return ret

            ret = self.obj_cam.MV_CC_SetFloatValue("AcquisitionFrameRate", float(frameRate))
            if ret != 0:
                print('show error', 'set acquistion frame rate fail! ret = ' + To_hex_str(ret))
                return ret
            
            ret = self.obj_cam.MV_CC_SetIntValue("Width", int(width_selector))
            if ret != 0:
                print('show error', 'set Width time fail! ret = ' + To_hex_str(ret))
                return ret
            
            ret = self.obj_cam.MV_CC_SetIntValue("Height", int(height_selector))
            if ret != 0:
                print('show error', 'set Height time fail! ret = ' + To_hex_str(ret))
                return ret
            
            ret = self.obj_cam.MV_CC_SetIntValue("OffsetX", int(OffSet_X))
            if ret != 0:
                print('show error', 'set OffSet_X time fail! ret = ' + To_hex_str(ret))
                return ret
            
            ret = self.obj_cam.MV_CC_SetIntValue("OffsetY", int(OffSet_Y))
            if ret != 0:
                print('show error', 'set OffSet_Y time fail! ret = ' + To_hex_str(ret))
                return ret

            print('show info', 'set parameter success!')

            return MV_OK

    # 取图线程函数
    def Work_thread_origin(self, winHandle):
        # self.stOutFrame = MV_FRAME_OUT()
        stFrameInfo = MV_FRAME_OUT_INFO_EX()
        img_buff = None
        numArray = None

        stPayloadSize = MVCC_INTVALUE_EX()
        ret_temp = self.obj_cam.MV_CC_GetIntValueEx("PayloadSize", stPayloadSize)
        if ret_temp != MV_OK:
            return
        NeedBufSize = int(stPayloadSize.nCurValue)
        while True:
            if self.buf_grab_image_size < NeedBufSize:
                self.buf_grab_image = (c_ubyte * NeedBufSize)()
                self.buf_grab_image_size = NeedBufSize

            ret = self.obj_cam.MV_CC_GetOneFrameTimeout(self.buf_grab_image, self.buf_grab_image_size, stFrameInfo)

            # ret = self.obj_cam.MV_CC_GetImageBuffer(self.stOutFrame, 1000)
            if 0 == ret:
                # 拷贝图像和图像信息
                if self.buf_save_image is None:
                    self.buf_save_image = (c_ubyte * stFrameInfo.nFrameLen)()
                self.st_frame_info = stFrameInfo

                # 获取缓存锁
                self.buf_lock.acquire()
                cdll.msvcrt.memcpy(byref(self.buf_save_image), self.buf_grab_image, self.st_frame_info.nFrameLen)
                self.buf_lock.release()

                print("get one frame: Width[%d], Height[%d], nFrameNum[%d]"
                      % (self.st_frame_info.nWidth, self.st_frame_info.nHeight, self.st_frame_info.nFrameNum))
                # 释放缓存
                # self.obj_cam.MV_CC_FreeImageBuffer(self.stOutFrame)
            else:
                print("no data, ret = " + To_hex_str(ret))
                continue

            # 使用Display接口显示图像
            stDisplayParam = MV_DISPLAY_FRAME_INFO()
            memset(byref(stDisplayParam), 0, sizeof(stDisplayParam))
            stDisplayParam.hWnd = int(winHandle)
            stDisplayParam.nWidth = self.st_frame_info.nWidth
            stDisplayParam.nHeight = self.st_frame_info.nHeight
            stDisplayParam.enPixelType = self.st_frame_info.enPixelType
            stDisplayParam.pData = self.buf_save_image
            stDisplayParam.nDataLen = self.st_frame_info.nFrameLen
            self.obj_cam.MV_CC_DisplayOneFrame(stDisplayParam)

            # 是否退出
            if self.b_exit:
                if img_buff is not None:
                    del img_buff
                if self.buf_save_image is not None:
                    del self.buf_save_image
                break

    # 存jpg图像
    def Save_jpg(self):

        if self.buf_save_image is None:
            return

        # 获取缓存锁
        self.buf_lock.acquire()

        file_path = str(self.st_frame_info.nFrameNum) + ".jpg"

        stSaveParam = MV_SAVE_IMG_TO_FILE_PARAM()
        stSaveParam.enPixelType = self.st_frame_info.enPixelType  # ch:相机对应的像素格式 | en:Camera pixel type
        stSaveParam.nWidth = self.st_frame_info.nWidth  # ch:相机对应的宽 | en:Width
        stSaveParam.nHeight = self.st_frame_info.nHeight  # ch:相机对应的高 | en:Height
        stSaveParam.nDataLen = self.st_frame_info.nFrameLen
        stSaveParam.pData = cast(self.buf_save_image, POINTER(c_ubyte))
        stSaveParam.enImageType = MV_Image_Jpeg  # ch:需要保存的图像类型 | en:Image format to save
        stSaveParam.nQuality = 80
        stSaveParam.pImagePath = file_path.encode('ascii')
        stSaveParam.iMethodValue = 2
        ret = self.obj_cam.MV_CC_SaveImageToFile(stSaveParam)

        self.buf_lock.release()
        return ret

    # 存BMP图像
    def Save_Bmp(self):

        if 0 == self.buf_save_image:
            return

        # 获取缓存锁
        self.buf_lock.acquire()

        file_path = str(self.st_frame_info.nFrameNum) + ".bmp"

        stSaveParam = MV_SAVE_IMG_TO_FILE_PARAM()
        stSaveParam.enPixelType = self.st_frame_info.enPixelType  # ch:相机对应的像素格式 | en:Camera pixel type
        stSaveParam.nWidth = self.st_frame_info.nWidth  # ch:相机对应的宽 | en:Width
        stSaveParam.nHeight = self.st_frame_info.nHeight  # ch:相机对应的高 | en:Height
        stSaveParam.nDataLen = self.st_frame_info.nFrameLen
        stSaveParam.pData = cast(self.buf_save_image, POINTER(c_ubyte))
        stSaveParam.enImageType = MV_Image_Bmp  # ch:需要保存的图像类型 | en:Image format to save
        stSaveParam.nQuality = 8
        stSaveParam.pImagePath = file_path.encode('ascii')
        stSaveParam.iMethodValue = 2
        ret = self.obj_cam.MV_CC_SaveImageToFile(stSaveParam)

        self.buf_lock.release()

        return ret
    
    def Thread_process(self,task):
        if not self.b_start_grabbing and self.b_open_device:
            self.b_exit = False
            ret = self.obj_cam.MV_CC_StartGrabbing()
            if ret != 0:
                print('wrong fall')
                return ret
            self.b_start_grabbing = True
            print("start grabbing successfully!")
            try:
                thread_id = random.randint(1, 10000)
                self.h_thread_handle = threading.Thread(target=CameraOperation.Work_thread_get_buff, args=(self,task))
                self.h_thread_handle.start()
                self.b_thread_closed = True
            finally:
                pass
            return MV_OK

        return MV_E_CALLORDER

    def Work_thread_get_buff(self,task):
        
        memset(byref(self.stOutFrame), 0, sizeof(self.stOutFrame))
        img_buff = None
        buf_cache = None
        numArray = None
        ret = self.obj_cam.MV_CC_GetImageBuffer(self.stOutFrame, 5000)
        print(f'ret:0x{ret:08X}')
        # if 0 == ret:
        if None == buf_cache:
            buf_cache = (c_ubyte * self.stOutFrame.stFrameInfo.nFrameLen)()
        self.st_frame_info = self.stOutFrame.stFrameInfo
        cdll.msvcrt.memcpy(byref(buf_cache), self.stOutFrame.pBufAddr, self.st_frame_info.nFrameLen)
        print ("get one frame: Width[%d], Height[%d], nFrameNum[%d]"  % (self.st_frame_info.nWidth, self.st_frame_info.nHeight, self.st_frame_info.nFrameNum))
        self.n_save_image_size = self.st_frame_info.nWidth * self.st_frame_info.nHeight * 3 + 2048
        if img_buff is None:
            img_buff = (c_ubyte * self.n_save_image_size)()
        stConvertParam = MV_CC_PIXEL_CONVERT_PARAM()
        memset(byref(stConvertParam), 0, sizeof(stConvertParam))
        stConvertParam.nWidth = self.st_frame_info.nWidth
        stConvertParam.nHeight = self.st_frame_info.nHeight
        stConvertParam.pSrcData = cast(buf_cache, POINTER(c_ubyte))
        stConvertParam.nSrcDataLen = self.st_frame_info.nFrameLen
        stConvertParam.enSrcPixelType = self.st_frame_info.enPixelType 
        if PixelType_Gvsp_RGB8_Packed == self.st_frame_info.enPixelType:
            numArray = CameraOperation.Color_numpy(self,buf_cache,self.st_frame_info.nWidth,self.st_frame_info.nHeight)
        else:
            nConvertSize = self.st_frame_info.nWidth * self.st_frame_info.nHeight * 3
            stConvertParam.enDstPixelType = PixelType_Gvsp_RGB8_Packed
            stConvertParam.pDstBuffer = (c_ubyte * nConvertSize)()
            stConvertParam.nDstBufferSize = nConvertSize
            ret = self.obj_cam.MV_CC_ConvertPixelType(stConvertParam)
            cdll.msvcrt.memcpy(byref(img_buff), stConvertParam.pDstBuffer, nConvertSize)
            numArray = CameraOperation.Color_numpy(self,img_buff,self.st_frame_info.nWidth,self.st_frame_info.nHeight)
        self.obj_cam.MV_CC_FreeImageBuffer(self.stOutFrame)
        task.put(numArray)
        if self.b_exit == True:
            if img_buff is not None:
                del img_buff


    # def grab_frame(self,timeout):
    #     time.sleep(0.01)
    #     img_buff = None
    #     stOutFrame = MV_FRAME_OUT()
    #     memset(byref(stOutFrame), 0, sizeof(stOutFrame))
    #     ret = self.obj_cam.MV_CC_GetImageBuffer(stOutFrame, 50)
    #     if None != stOutFrame.pBufAddr and 0 == ret:
    #         # print ("MV_CC_GetImageBuffer: Width[%d], Height[%d], nFrameNum[%d]"  % (stOutFrame.stFrameInfo.nWidth, stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nFrameNum))
    #         stConvertParam = MV_CC_PIXEL_CONVERT_PARAM()
    #         memset(byref(stConvertParam), 0, sizeof(stConvertParam))
    #         if self.IsImageColor(stOutFrame.stFrameInfo.enPixelType) == 'mono':
    #             # print("mono!")
    #             stConvertParam.enDstPixelType = PixelType_Gvsp_Mono8
    #             nConvertSize = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight
    #         elif self.IsImageColor(stOutFrame.stFrameInfo.enPixelType) == 'color':
    #             # print("color!")
    #             stConvertParam.enDstPixelType = PixelType_Gvsp_BGR8_Packed  # opecv要用BGR，不能使用RGB
    #             nConvertSize = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight * 3
    #         else:
    #             print("not support!!!")
    #         if img_buff is None:
    #             img_buff = (c_ubyte * stOutFrame.stFrameInfo.nFrameLen)()
    #         stConvertParam.nWidth = stOutFrame.stFrameInfo.nWidth
    #         stConvertParam.nHeight = stOutFrame.stFrameInfo.nHeight
    #         stConvertParam.pSrcData = cast(stOutFrame.pBufAddr, POINTER(c_ubyte))
    #         stConvertParam.nSrcDataLen = stOutFrame.stFrameInfo.nFrameLen
    #         stConvertParam.enSrcPixelType = stOutFrame.stFrameInfo.enPixelType
    #         stConvertParam.pDstBuffer = (c_ubyte * nConvertSize)()
    #         stConvertParam.nDstBufferSize = nConvertSize
    #         ret = self.obj_cam.MV_CC_ConvertPixelType(stConvertParam)
    #         if ret != 0:
    #             print("convert pixel fail! ret[0x%x]" % ret)
    #             del stConvertParam.pSrcData
    #             sys.exit()
    #         # else:
    #             # print("convert ok!!")
    #         if self.IsImageColor(stOutFrame.stFrameInfo.enPixelType) == 'color':
    #             img_buff = (c_ubyte * stConvertParam.nDstLen)()
    #             cdll.msvcrt.memcpy(byref(img_buff), stConvertParam.pDstBuffer, stConvertParam.nDstLen)
    #             img_buff = np.frombuffer(img_buff, count=int(stConvertParam.nDstBufferSize), dtype=np.uint8)#data以流的形式读入转化成ndarray对象
    #             img_buff = img_buff.reshape(stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nWidth,3)
    #             # print("color ok!!")

    #         else:
    #             print("no data[0x%x]" % ret)
    #         nRet = self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
    #         return 0,img_buff


    
    def grab_frame(self, timeout=10):
        # time.sleep(0.01)

        memset(byref(self.stOutFrame), 0, sizeof(MV_FRAME_OUT))

  
        ret = self.obj_cam.MV_CC_GetImageBuffer(self.stOutFrame, timeout)
        if ret != 0:
            return ret, None

        frame_info = self.stOutFrame.stFrameInfo
        buf_cache = (c_ubyte * frame_info.nFrameLen)()
        cdll.msvcrt.memcpy(byref(buf_cache), self.stOutFrame.pBufAddr, frame_info.nFrameLen)
        # time.sleep(0.005)
        if frame_info.enPixelType == PixelType_Gvsp_RGB8_Packed:
          
            numArray = CameraOperation.Color_numpy(None,
                            buf_cache, frame_info.nWidth, frame_info.nHeight)
        else:
            # time.sleep(0.005)
            nConvertSize = frame_info.nWidth * frame_info.nHeight * 3
            convertParam = MV_CC_PIXEL_CONVERT_PARAM()
            memset(byref(convertParam), 0, sizeof(convertParam))
            convertParam.nWidth = frame_info.nWidth
            convertParam.nHeight = frame_info.nHeight
            convertParam.pSrcData = cast(buf_cache, POINTER(c_ubyte))
            convertParam.nSrcDataLen = frame_info.nFrameLen
            convertParam.enSrcPixelType = frame_info.enPixelType
            convertParam.enDstPixelType = PixelType_Gvsp_RGB8_Packed
            dst_buf = (c_ubyte * nConvertSize)()
            convertParam.pDstBuffer = dst_buf
            convertParam.nDstBufferSize = nConvertSize
            # time.sleep(0.005)
            ret2 = self.obj_cam.MV_CC_ConvertPixelType(convertParam)
            if ret2 != 0:
                self.obj_cam.MV_CC_FreeImageBuffer(self.stOutFrame)
                return ret2, None
            # time.sleep(0.005)
            numArray = CameraOperation.Color_numpy(None,
                            dst_buf, frame_info.nWidth, frame_info.nHeight)
        self.obj_cam.MV_CC_FreeImageBuffer(self.stOutFrame)

        return 0, numArray



    def sure_gte_img(self):
        try:
            hThreadHandle = threading.Thread(target=self.work_thread_array)
            hThreadHandle.start()
        except:
            print ("error: unable to start thread")

    def work_thread_array(self,cam=0, pData=0, nDataSize=0):
        ret = self.obj_cam.MV_CC_StartGrabbing()
        img_buff = None
        buf_cache = None
        numArray = None
        self.stOutFrame = MV_FRAME_OUT()  
        memset(byref(self.stOutFrame), 0, sizeof(self.stOutFrame))
        ret = self.obj_cam.MV_CC_GetImageBuffer(self.stOutFrame, 5000)
        if 0 == ret:
            if None == buf_cache:
                buf_cache = (c_ubyte * self.stOutFrame.stFrameInfo.nFrameLen)()
            st_frame_info = self.stOutFrame.stFrameInfo
            cdll.msvcrt.memcpy(byref(buf_cache), self.stOutFrame.pBufAddr, st_frame_info.nFrameLen)
            print ("Camera[%d]:get one frame: Width[%d], Height[%d], nFrameNum[%d]"  % (1,st_frame_info.nWidth, st_frame_info.nHeight, st_frame_info.nFrameNum))
            n_save_image_size = st_frame_info.nWidth * st_frame_info.nHeight * 3 + 2048
            if img_buff is None:
                img_buff = (c_ubyte * n_save_image_size)()
        else:
            print("Camera fails")
    
        #转换像素结构体赋值
        stConvertParam = MV_CC_PIXEL_CONVERT_PARAM()
        memset(byref(stConvertParam), 0, sizeof(stConvertParam))
        stConvertParam.nWidth = st_frame_info.nWidth
        stConvertParam.nHeight = st_frame_info.nHeight
        stConvertParam.pSrcData = cast(buf_cache, POINTER(c_ubyte))
        stConvertParam.nSrcDataLen = st_frame_info.nFrameLen
        stConvertParam.enSrcPixelType = st_frame_info.enPixelType 

        # RGB直接显示
        if PixelType_Gvsp_RGB8_Packed == st_frame_info.enPixelType:
            numArray = self.Color_numpy(buf_cache,st_frame_info.nWidth,st_frame_info.nHeight)
        else:
            nConvertSize = st_frame_info.nWidth * st_frame_info.nHeight * 3
            stConvertParam.enDstPixelType = PixelType_Gvsp_RGB8_Packed
            stConvertParam.pDstBuffer = (c_ubyte * nConvertSize)()
            stConvertParam.nDstBufferSize = nConvertSize
            ret = self.obj_cam.MV_CC_ConvertPixelType(stConvertParam)
            cdll.msvcrt.memcpy(byref(img_buff), stConvertParam.pDstBuffer, nConvertSize)
            numArray = self.Color_numpy(img_buff,st_frame_info.nWidth,st_frame_info.nHeight)
            
        current_image = Image.fromarray(numArray).resize((500, 500))
        cv2.imwrite('img123.jpg',numArray)
    
    def Color_numpy(self,data,nWidth,nHeight):
        data_ = np.frombuffer(data, count=int(nWidth*nHeight*3), dtype=np.uint8, offset=0)
        data_r = data_[0:nWidth*nHeight*3:3]
        data_g = data_[1:nWidth*nHeight*3:3]
        data_b = data_[2:nWidth*nHeight*3:3]

        data_r_arr = data_r.reshape(nHeight, nWidth)
        data_g_arr = data_g.reshape(nHeight, nWidth)
        data_b_arr = data_b.reshape(nHeight, nWidth)
        numArray = np.zeros([nHeight, nWidth, 3],"uint8")

        numArray[:, :, 0] = data_r_arr
        numArray[:, :, 1] = data_g_arr
        numArray[:, :, 2] = data_b_arr
        return numArray
    
    def To_hex_str(num):
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
