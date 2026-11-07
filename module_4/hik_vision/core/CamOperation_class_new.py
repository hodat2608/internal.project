import sys
import os
import threading
import time
import inspect
import ctypes
from ctypes import *
import numpy as np
import cv2

from core.CameraParams_header import *
from core.MvCameraControl_class import *
from core.MvErrorDefine_const import *


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


def Stop_thread(thread):
    Async_raise(thread.ident, SystemExit)


class CameraOperation:

    def __init__(self, obj_cam, st_device_list, n_connect_num=0, b_open_device=False,
                 b_start_grabbing=False, h_thread_handle=None, b_thread_closed=False,
                 st_frame_info=None, b_exit=False, b_save_bmp=False, b_save_jpg=False,
                 buf_save_image=None, n_save_image_size=0, n_win_gui_id=0,
                 frame_rate=0, exposure_time=0, gain=0):

        self.obj_cam             = obj_cam
        self.st_device_list      = st_device_list
        self.n_connect_num       = n_connect_num
        self.b_open_device       = b_open_device
        self.b_start_grabbing    = b_start_grabbing
        self.b_thread_closed     = b_thread_closed
        self.st_frame_info       = st_frame_info
        self.b_exit              = b_exit
        self.b_save_bmp          = b_save_bmp
        self.b_save_jpg          = b_save_jpg
        self.buf_grab_image      = None
        self.buf_grab_image_size = 0
        self.buf_save_image      = buf_save_image
        self.n_save_image_size   = n_save_image_size
        self.h_thread_handle     = h_thread_handle
        self.frame_rate          = frame_rate
        self.exposure_time       = exposure_time  # µs
        self.gain                = gain

        self.buf_lock = threading.Lock()

        # Frame number của frame cuối đã trả về thành công
        self._last_frame_num = -1

        # Timeout GetImageBuffer = exposure_ms + overhead, tự cập nhật sau Get_all_parameter()
        self._retrieve_timeout_ms = self._calc_timeout_ms(exposure_time)

    def _calc_timeout_ms(self, exposure_us):
        """
        Tính timeout GetImageBuffer từ exposure time (µs).
        Công thức: exposure_ms + 10ms overhead. Tối thiểu 20ms.
        """
        if exposure_us and exposure_us > 0:
            return max(20, int(exposure_us / 1000) + 10)
        return 20

    # ─────────────────────────────────────────────
    # MỞ THIẾT BỊ
    # ─────────────────────────────────────────────
    def Open_device(self):
        if not self.b_open_device:
            if self.n_connect_num < 0:
                return MV_E_CALLORDER

            nConnectionNum = int(self.n_connect_num)
            stDeviceList = cast(
                self.st_device_list.pDeviceInfo[nConnectionNum],
                POINTER(MV_CC_DEVICE_INFO)
            ).contents

            self.obj_cam = MvCamera()
            ret = self.obj_cam.MV_CC_CreateHandle(stDeviceList)
            if ret != 0:
                self.obj_cam.MV_CC_DestroyHandle()
                return ret

            ret = self.obj_cam.MV_CC_OpenDevice()
            if ret != 0:
                return ret

            self.b_open_device   = True
            self.b_thread_closed = False

            # Tối ưu packet size cho GigE
            if stDeviceList.nTLayerType == MV_GIGE_DEVICE:
                nPacketSize = self.obj_cam.MV_CC_GetOptimalPacketSize()
                if int(nPacketSize) > 0:
                    ret = self.obj_cam.MV_CC_SetIntValue("GevSCPSPacketSize", nPacketSize)
                    if ret != 0:
                        print("warning: set packet size fail! ret[0x%x]" % ret)
                else:
                    print("warning: get packet size fail! ret[0x%x]" % nPacketSize)

            ret = self.configure_software_trigger()
            if ret != 0:
                print("warning: configure software trigger fail! ret[0x%x]" % ret)
                return ret

            print("Open device & configure software trigger successfully")
            return MV_OK

    # ─────────────────────────────────────────────
    # CẤU HÌNH SOFTWARE TRIGGER
    # ─────────────────────────────────────────────
    def configure_software_trigger(self):
        ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
        if ret != 0:
            print("set trigger mode OFF fail! ret[0x%x]" % ret)
            return ret

        ret = self.obj_cam.MV_CC_SetEnumValue("TriggerSource", MV_TRIGGER_SOURCE_SOFTWARE)
        if ret != 0:
            print("set trigger source SOFTWARE fail! ret[0x%x]" % ret)
            return ret

        ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_ON)
        if ret != 0:
            print("set trigger mode ON fail! ret[0x%x]" % ret)
            return ret

        # Warm-up + flush: chỉ cần lúc configure, không cần trong mỗi lần chụp
        time.sleep(0.05)
        self._flush_image_buffer()

        # Reset frame counter sau mỗi lần configure
        self._last_frame_num = -1

        print("Software trigger configured successfully")
        return MV_OK

    # ─────────────────────────────────────────────
    # FLUSH BUFFER
    # ─────────────────────────────────────────────
    def _flush_image_buffer(self, max_flush=10):
        """Xả hết frame cũ trong queue. Chỉ gọi lúc init/configure/grabbing."""
        stOutFrame = MV_FRAME_OUT()
        flushed = 0
        for _ in range(max_flush):
            memset(byref(stOutFrame), 0, sizeof(stOutFrame))
            ret = self.obj_cam.MV_CC_GetImageBuffer(stOutFrame, 5)
            if ret == 0 and stOutFrame.pBufAddr is not None:
                self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
                flushed += 1
            else:
                break
        if flushed:
            print(f"Flushed {flushed} stale frame(s) from buffer")

    def flush_buffer(self, max_flush=10):
        """Alias cho _flush_image_buffer để tương thích với core_plus_auto_new."""
        return self._flush_image_buffer(max_flush)

    # ─────────────────────────────────────────────
    # SOFTWARE TRIGGER + LẤY ẢNH  ← CRITICAL PATH
    # ─────────────────────────────────────────────
    def Trigger_Camera_Software(self, max_retries=3):
        """
        Gửi trigger → lấy frame MỚI.
        """
        for attempt in range(max_retries):
            try:
                # ── Bước 1: Gửi trigger ─────────────────
                ret = self.obj_cam.MV_CC_SetCommandValue("TriggerSoftware")
                if ret != 0:
                    print("Execute software trigger fail! ret[0x%x] (attempt %d/%d)"
                          % (ret, attempt + 1, max_retries))
                    continue

                # ── Bước 2: Lấy frame MỚI ───────────────
                img = self._retrieve_new_frame(self._retrieve_timeout_ms)
                if img is not None:
                    return img

                print("Trigger OK nhưng không lấy được frame mới (attempt %d/%d)"
                      % (attempt + 1, max_retries))

            except Exception as e:
                print(f"Trigger Error (attempt {attempt + 1}/{max_retries}): {e}")

        print("Trigger thất bại sau %d lần thử" % max_retries)
        return None

    # ─────────────────────────────────────────────
    # LẤY FRAME MỚI
    # ─────────────────────────────────────────────
    def _retrieve_new_frame(self, timeout_ms, max_poll=5):
        """
        Poll GetImageBuffer tối đa max_poll lần.
        """
        stOutFrame = MV_FRAME_OUT()

        for poll in range(max_poll):
            memset(byref(stOutFrame), 0, sizeof(stOutFrame))

            with self.buf_lock:
                ret = self.obj_cam.MV_CC_GetImageBuffer(stOutFrame, 50)

                if ret != 0 or stOutFrame.pBufAddr is None:
                    print("Get image buffer fail! ret[0x%x] (poll %d/%d)"
                          % (ret, poll + 1, max_poll))
                    return None

                try:
                    img = self._convert_frame(stOutFrame)
                    if img is not None:
                        return img
                    else:
                        return None
                finally:
                    self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)

        print(f"Không lấy được frame mới sau {max_poll} lần poll")
        return None

    # ─────────────────────────────────────────────
    # CONVERT PIXEL FORMAT → NUMPY ARRAY (RGB)
    # ─────────────────────────────────────────────
    def _convert_frame(self, stOutFrame):
        # 1. Tự động lấy Pixel Format từ thông tin Frame (cực nhanh, không cần gọi API)
        pixel_type = stOutFrame.stFrameInfo.enPixelType
        nWidth = stOutFrame.stFrameInfo.nWidth
        nHeight = stOutFrame.stFrameInfo.nHeight
        data_length = nWidth * nHeight

        # Khởi tạo buffer an toàn và copy dữ liệu thô từ camera
        img_buff = (ctypes.c_ubyte * data_length)()
        ctypes.memmove(ctypes.byref(img_buff), stOutFrame.pBufAddr, data_length)

        # Chuyển về Numpy Array 2 chiều
        raw_img = np.frombuffer(img_buff, dtype=np.uint8, count=data_length)
        raw_img = raw_img.reshape((nHeight, nWidth))

        # 2. Xử lý ảnh tuỳ theo Pixel Format chuẩn GenICam Hikvision
        if pixel_type == 0x01080008:
            # PixelType_Gvsp_BayerGR8 -> Giải mã đúng BayerGR sang RGB
            img = cv2.cvtColor(raw_img, cv2.COLOR_BayerGR2RGB)
            return img

        elif pixel_type == 0x01080009:
            # PixelType_Gvsp_BayerRG8 -> Giải mã đúng BayerRG sang RGB
            img = cv2.cvtColor(raw_img, cv2.COLOR_BayerRG2RGB)
            return img

        elif pixel_type == 0x0108000a:
            # PixelType_Gvsp_BayerGB8 -> Giải mã đúng BayerGB sang RGB
            img = cv2.cvtColor(raw_img, cv2.COLOR_BayerGB2RGB)
            return img

        elif pixel_type == 0x0108000b:
            # PixelType_Gvsp_BayerBG8 -> Giải mã đúng BayerBG sang RGB
            img = cv2.cvtColor(raw_img, cv2.COLOR_BayerBG2RGB)
            return img

        elif pixel_type == 0x01080001:
            # Mono8 (Trắng Đen)
            return cv2.cvtColor(raw_img, cv2.COLOR_GRAY2RGB)

        else:
            print(f"Chưa hỗ trợ định dạng PixelFormat này: {hex(pixel_type)}")
            try:
                return cv2.cvtColor(raw_img, cv2.COLOR_BayerGR2RGB)
            except Exception:
                return raw_img

    # ─────────────────────────────────────────────
    # START / STOP GRABBING
    # ─────────────────────────────────────────────
    def grabbing(self):
        ret = self.obj_cam.MV_CC_StartGrabbing()
        if ret != 0:
            print("Start grabbing fail! ret[0x%x]" % ret)
            return ret
        self.b_start_grabbing = True
        time.sleep(0.05)
        self._flush_image_buffer()
        self._last_frame_num = -1  # Reset sau mỗi lần StartGrabbing
        return MV_OK

    def not_grabbing(self):
        ret = self.obj_cam.MV_CC_StopGrabbing()
        if ret != 0:
            print("Stop grabbing fail! ret[0x%x]" % ret)
            return ret
        self.b_start_grabbing = False
        return MV_OK

    # ─────────────────────────────────────────────
    # PIXEL FORMAT HELPER
    # ─────────────────────────────────────────────
    def IsImageColor(self, enPixelType):
        mono_formats = [
            PixelType_Gvsp_Mono8,
            PixelType_Gvsp_Mono10,
            PixelType_Gvsp_Mono12,
        ]
        return 'mono' if enPixelType in mono_formats else 'color'

    # ─────────────────────────────────────────────
    # LOAD USER SET PARAMS
    # ─────────────────────────────────────────────
    def load_params_user_selector(self, user_set_index=0):
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

        print(f"[-] Load UserSet{user_set_index} from MVS Successfully!")

        # UserSetLoad có thể reset TriggerMode → cấu hình lại
        ret = self.configure_software_trigger()
        if ret != 0:
            print("warning: re-configure software trigger after UserSetLoad fail!")
            return ret

        return self.Get_all_parameter()

    # ─────────────────────────────────────────────
    # ĐỌC TẤT CẢ PARAMS TỪ CAMERA
    # ─────────────────────────────────────────────
    def Get_all_parameter(self):
        if not self.b_open_device:
            return -1

        self.camera_params = {}

        float_params = ["AcquisitionFrameRate", "ExposureTime", "Gain", "Gamma"]
        for name in float_params:
            stVal = MVCC_FLOATVALUE()
            memset(byref(stVal), 0, sizeof(MVCC_FLOATVALUE))
            ret = self.obj_cam.MV_CC_GetFloatValue(name, stVal)
            self.camera_params[name] = stVal.fCurValue if ret == 0 else None

        bool_params = ["GammaEnable"]
        for name in bool_params:
            stVal = c_bool(False)
            ret = self.obj_cam.MV_CC_GetBoolValue(name, stVal)
            self.camera_params[name] = stVal.value if ret == 0 else None

        enum_params = [
            "BalanceWhiteAuto", "PixelFormat", "AcquisitionMode", "TriggerMode",
            "TriggerSource", "ExposureAuto", "GainAuto", "BinningSelector", "TestPattern"
        ]
        for name in enum_params:
            stVal = MVCC_ENUMVALUE()
            memset(byref(stVal), 0, sizeof(MVCC_ENUMVALUE))
            ret = self.obj_cam.MV_CC_GetEnumValue(name, stVal)
            self.camera_params[name] = stVal.nCurValue if ret == 0 else None

        int_params = [
            "BinningHorizontal", "BinningVertical", "OffsetX", "OffsetY",
            "WidthMax", "HeightMax", "Width", "Height", "BalanceRatio"
        ]
        for name in int_params:
            stVal = MVCC_INTVALUE()
            memset(byref(stVal), 0, sizeof(MVCC_INTVALUE))
            ret = self.obj_cam.MV_CC_GetIntValue(name, stVal)
            self.camera_params[name] = stVal.nCurValue if ret == 0 else None

        # Cập nhật timeout tối ưu từ exposure thực tế
        exposure_us = self.camera_params.get("ExposureTime")
        if exposure_us:
            self._retrieve_timeout_ms = self._calc_timeout_ms(exposure_us)
            print(f"[Camera] ExposureTime = {exposure_us/1000:.2f} ms  "
                  f"→ retrieve timeout = {self._retrieve_timeout_ms} ms")

        return MV_OK

    # ─────────────────────────────────────────────
    # ĐÓNG THIẾT BỊ
    # ─────────────────────────────────────────────
    def Close_device(self):
        if self.b_open_device:
            if self.b_thread_closed:
                Stop_thread(self.h_thread_handle)
                self.b_thread_closed = False
            ret = self.obj_cam.MV_CC_CloseDevice()
            if ret != 0:
                return ret

        self.obj_cam.MV_CC_DestroyHandle()
        self.b_open_device    = False
        self.b_start_grabbing = False
        self.b_exit           = True
        print("close device successfully!")
