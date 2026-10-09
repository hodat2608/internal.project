
# from core.CameraParams_header import *
# from core.MvCameraControl_class import *
# import threading
# import time
# import numpy as np
# import sys
# from ctypes import *
# import inspect

# def Async_raise(tid, exctype):
#     tid = ctypes.c_long(tid)
#     if not inspect.isclass(exctype):
#         exctype = type(exctype)
#     res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
#     if res == 0:
#         raise ValueError("invalid thread id")
#     elif res != 1:
#         ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
#         raise SystemError("PyThreadState_SetAsyncExc failed")

# def Stop_thread(thread):
#     Async_raise(thread.ident, SystemExit)

# class CameraOperation:

#     def __init__(self, obj_cam, st_device_list, n_connect_num=0, b_open_device=False, 
#                  b_start_grabbing=False, h_thread_handle=None, b_thread_closed=False, 
#                  st_frame_info=None, b_exit=False, b_save_bmp=False, b_save_jpg=False,
#                  buf_save_image=None, n_save_image_size=0, n_win_gui_id=0, 
#                  frame_rate=0, exposure_time=0, gain=0):

#         self.obj_cam = obj_cam
#         self.st_device_list = st_device_list
#         self.n_connect_num = n_connect_num
#         self.b_open_device = b_open_device
#         self.b_start_grabbing = b_start_grabbing
#         self.b_thread_closed = b_thread_closed
#         self.st_frame_info = st_frame_info
#         self.b_exit = b_exit
#         self.b_save_bmp = b_save_bmp
#         self.b_save_jpg = b_save_jpg
#         self.buf_grab_image = None
#         self.buf_grab_image_size = 0
#         self.buf_save_image = buf_save_image
#         self.n_save_image_size = n_save_image_size
#         self.h_thread_handle = h_thread_handle
#         self.frame_rate = frame_rate
#         self.exposure_time = exposure_time
#         self.gain = gain
#         self.buf_lock = threading.Lock()  # Lock dùng chung khi trigger + lấy ảnh
#         self._last_frame_num = -1
#     # ─────────────────────────────────────────────
#     # MỞ THIẾT BỊ + CẤU HÌNH SOFTWARE TRIGGER
#     # ─────────────────────────────────────────────
#     def Open_device(self):
#         if not self.b_open_device:
#             if self.n_connect_num < 0:
#                 return MV_E_CALLORDER

#             nConnectionNum = int(self.n_connect_num)
#             stDeviceList = cast(
#                 self.st_device_list.pDeviceInfo[nConnectionNum],
#                 POINTER(MV_CC_DEVICE_INFO)
#             ).contents

#             self.obj_cam = MvCamera()
#             ret = self.obj_cam.MV_CC_CreateHandle(stDeviceList)
#             if ret != 0:
#                 self.obj_cam.MV_CC_DestroyHandle()
#                 return ret

#             ret = self.obj_cam.MV_CC_OpenDevice()
#             if ret != 0:
#                 return ret

#             self.b_open_device = True
#             self.b_thread_closed = False

#             # Tối ưu packet size cho GigE
#             if stDeviceList.nTLayerType == MV_GIGE_DEVICE:
#                 nPacketSize = self.obj_cam.MV_CC_GetOptimalPacketSize()
#                 if int(nPacketSize) > 0:
#                     ret = self.obj_cam.MV_CC_SetIntValue("GevSCPSPacketSize", nPacketSize)
#                     if ret != 0:
#                         print("warning: set packet size fail! ret[0x%x]" % ret)
#                 else:
#                     print("warning: get packet size fail! ret[0x%x]" % nPacketSize)

#             # ── Cấu hình Software Trigger ──────────────
#             ret = self.configure_software_trigger()
#             if ret != 0:
#                 print("warning: configure software trigger fail! ret[0x%x]" % ret)
#                 return ret

#             print("Open device & configure software trigger successfully")
#             return MV_OK

#     # ─────────────────────────────────────────────
#     # CẤU HÌNH SOFTWARE TRIGGER (tách riêng để dễ gọi lại)
#     # Mirror: configure_software_trigger() của Basler
#     # ─────────────────────────────────────────────
#     def configure_software_trigger(self):
#         # Bước 1: Tắt trigger trước khi cấu hình
#         ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
#         if ret != 0:
#             print("set trigger mode OFF fail! ret[0x%x]" % ret)
#             return ret

#         # Bước 2: Chọn nguồn trigger là Software
#         ret = self.obj_cam.MV_CC_SetEnumValue("TriggerSource", MV_TRIGGER_SOURCE_SOFTWARE)
#         if ret != 0:
#             print("set trigger source SOFTWARE fail! ret[0x%x]" % ret)
#             return ret

#         # Bước 3: Bật trigger mode
#         ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_ON)
#         if ret != 0:
#             print("set trigger mode ON fail! ret[0x%x]" % ret)
#             return ret

#         print("Software trigger configured successfully")
#         return MV_OK

#     # ─────────────────────────────────────────────
#     # SOFTWARE TRIGGER + LẤY ẢNH
#     # Mirror: Trigger_Camera_Software() của Basler
#     # ─────────────────────────────────────────────
#     def Trigger_Camera_Software(self, max_retries=5):
#         """
#         Gửi lệnh software trigger → chờ ảnh → trả về numpy array.
#         Trả về None nếu thất bại sau max_retries lần.
#         """
#         time.sleep(0.005)
#         retries = 0

#         while retries < max_retries:
#             try:
#                 with self.buf_lock:
#                     # Bước 1: Gửi lệnh trigger
#                     ret = self.obj_cam.MV_CC_SetCommandValue("TriggerSoftware")
#                     if ret != 0:
#                         print("Execute software trigger fail! ret[0x%x]" % ret)
#                         retries += 1
#                         # time.sleep(0.05)
#                         continue

#                     time.sleep(0.001)  # Chờ sensor phơi sáng xong

#                     # Bước 2: Lấy ảnh từ buffer
#                     img = self._retrieve_image()
#                     if img is not None:
#                         return img

#                 # time.sleep(0.01)

#             except Exception as error:
#                 print(f"Trigger Error (attempt {retries + 1}): {error}")
#                 retries += 1
#                 # time.sleep(0.05)

#         print("Trigger thất bại sau nhiều lần thử")
#         return None

#     # ─────────────────────────────────────────────
#     # LẤY & CONVERT ẢNH (tách riêng khỏi trigger)
#     # ─────────────────────────────────────────────
#     def _retrieve_image(self, timeout_ms=50):
#         """
#         Lấy ảnh từ buffer sau khi trigger.
#         Trả về numpy array (BGR hoặc Mono) hoặc None nếu lỗi.
#         """
#         stOutFrame = MV_FRAME_OUT()
#         memset(byref(stOutFrame), 0, sizeof(stOutFrame))

#         ret = self.obj_cam.MV_CC_GetImageBuffer(stOutFrame, timeout_ms)
#         if ret != 0 or stOutFrame.pBufAddr is None:
#             print("Get image buffer fail! ret[0x%x]" % ret)
#             return None

#         try:
#             img = self._convert_frame(stOutFrame)
#             return img
#         finally:
#             # Luôn giải phóng buffer dù convert thành công hay lỗi
#             # Mirror: grabResult.Release() của Basler
#             self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)


#     # ─────────────────────────────────────────────
#     # LẤY & CONVERT ẢNH (tách riêng khỏi trigger)
#     # ─────────────────────────────────────────────
    

#     # ─────────────────────────────────────────────
#     # CONVERT PIXEL FORMAT → NUMPY ARRAY
#     # ─────────────────────────────────────────────
#     def _convert_frame(self, stOutFrame):
#         """
#         Convert frame từ raw format sang numpy array BGR hoặc Mono8.
#         """
#         pixel_type = stOutFrame.stFrameInfo.enPixelType
#         color_mode = self.IsImageColor(pixel_type)

#         stConvertParam = MV_CC_PIXEL_CONVERT_PARAM()
#         memset(byref(stConvertParam), 0, sizeof(stConvertParam))

#         if color_mode == 'mono':
#             stConvertParam.enDstPixelType = PixelType_Gvsp_Mono8
#             nConvertSize = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight
#             channels = 1

#         elif color_mode == 'color':
#             stConvertParam.enDstPixelType = PixelType_Gvsp_BGR8_Packed
#             nConvertSize = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight * 3
#             channels = 3

#         else:
#             print("Pixel type not supported!")
#             return None

#         stConvertParam.nWidth        = stOutFrame.stFrameInfo.nWidth
#         stConvertParam.nHeight       = stOutFrame.stFrameInfo.nHeight
#         stConvertParam.pSrcData      = cast(stOutFrame.pBufAddr, POINTER(c_ubyte))
#         stConvertParam.nSrcDataLen   = stOutFrame.stFrameInfo.nFrameLen
#         stConvertParam.enSrcPixelType= pixel_type
#         stConvertParam.pDstBuffer    = (c_ubyte * nConvertSize)()
#         stConvertParam.nDstBufferSize= nConvertSize

#         ret = self.obj_cam.MV_CC_ConvertPixelType(stConvertParam)
#         if ret != 0:
#             print("Convert pixel fail! ret[0x%x]" % ret)
#             return None

#         # Copy ra numpy array độc lập (mirror: grabResult.Array.copy() của Basler)
#         img_buff = (c_ubyte * stConvertParam.nDstLen)()
#         cdll.msvcrt.memcpy(byref(img_buff), stConvertParam.pDstBuffer, stConvertParam.nDstLen)
#         img = np.frombuffer(img_buff, dtype=np.uint8, count=stConvertParam.nDstLen)

#         if color_mode == 'color':
#             img = img.reshape(stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nWidth, 3)
#         else:
#             img = img.reshape(stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nWidth)

#         return img

#     # ─────────────────────────────────────────────
#     # START / STOP GRABBING
#     # ─────────────────────────────────────────────
#     def grabbing(self):
#         ret = self.obj_cam.MV_CC_StartGrabbing()
#         if ret != 0:
#             print("Start grabbing fail! ret[0x%x]" % ret)
#             return ret

#         self.b_start_grabbing = True

#         # Warm-up: chờ cho đến khi GetImageBuffer trả về thành công
#         # Không cần ảnh đúng, chỉ cần pipeline sẵn sàng
#         # self._warm_up_pipeline()

#         return MV_OK

#     def not_grabbing(self):
#         ret = self.obj_cam.MV_CC_StopGrabbing()
#         if ret != 0:
#             print("Stop grabbing fail! ret[0x%x]" % ret)
#             return ret
#         self.b_start_grabbing = False
#         return MV_OK

#     def IsImageColor(self, enPixelType):
#         # Giữ nguyên logic của bạn — chỉ cần implement đúng
#         mono_formats = [PixelType_Gvsp_Mono8, PixelType_Gvsp_Mono10, PixelType_Gvsp_Mono12]
#         if enPixelType in mono_formats:
#             return 'mono'
#         return 'color'
    
    
#     def load_params_user_selector(self,user_set_index=0):
#         print(f'[-] Loading UserSet{user_set_index} from MVS...')
#         if not self.b_open_device:
#             return -1

#         ret = self.obj_cam.MV_CC_SetEnumValue("UserSetSelector", user_set_index)
#         if ret != 0:
#             print(f"=> Failed to select user set {user_set_index}, error: {ret}")
#             return ret

#         ret = self.obj_cam.MV_CC_SetCommandValue("UserSetLoad")
#         if ret != 0:
#             print(f"=> Failed to load user set {user_set_index}, error: {ret}")
#             return ret
        
#         print(f"[-] Load UserSet{user_set_index} from MVS Succesfully!")
#         MV_OK = self.Get_all_parameter()

#         return MV_OK  
    
#     def Get_all_parameter(self):
#         if not self.b_open_device:
#             return -1

#         self.camera_params = {}

#         # --- FLOAT PARAMS ---
#         float_params = ["AcquisitionFrameRate", "ExposureTime", "Gain", "Gamma"]
#         for name in float_params:
#             stVal = MVCC_FLOATVALUE()
#             memset(byref(stVal), 0, sizeof(MVCC_FLOATVALUE))
#             ret = self.obj_cam.MV_CC_GetFloatValue(name, stVal)
#             if ret == 0:
#                 self.camera_params[name] = stVal.fCurValue
#             else:
#                 self.camera_params[name] = None

#         # --- BOOL PARAMS ---
#         bool_params = ["GammaEnable"]
#         for name in bool_params:
#             stVal = c_bool(False)
#             ret = self.obj_cam.MV_CC_GetBoolValue(name, stVal)
#             if ret == 0:
#                 self.camera_params[name] = stVal.value
#             else:
#                 self.camera_params[name] = None

#         # --- ENUM PARAMS ---
#         enum_params = [
#             "BalanceWhiteAuto", "PixelFormat", "AcquisitionMode", "TriggerMode",
#             "TriggerSource", "ExposureAuto", "GainAuto", "BinningSelector", "TestPattern"
#         ]
#         for name in enum_params:
#             stVal = MVCC_ENUMVALUE()
#             memset(byref(stVal), 0, sizeof(MVCC_ENUMVALUE))
#             ret = self.obj_cam.MV_CC_GetEnumValue(name, stVal)
#             if ret == 0:
#                 self.camera_params[name] = stVal.nCurValue
#             else:
#                 self.camera_params[name] = None

#         # --- INT PARAMS ---
#         int_params = ["BinningHorizontal", "BinningVertical", "OffsetX", "OffsetY", "WidthMax", "HeightMax","Width","Height", "BalanceRatio"]
#         for name in int_params:
#             stVal = MVCC_INTVALUE()
#             memset(byref(stVal), 0, sizeof(MVCC_INTVALUE))
#             ret = self.obj_cam.MV_CC_GetIntValue(name, stVal)
#             if ret == 0:
#                 self.camera_params[name] = stVal.nCurValue
#             else:
#                 self.camera_params[name] = None
#         return MV_OK



#     def Close_device(self):
#         if self.b_open_device:
#             # 退出线程
#             if self.b_thread_closed:
#                 Stop_thread(self.h_thread_handle)
#                 self.b_thread_closed = False
#             ret = self.obj_cam.MV_CC_CloseDevice()
#             if ret != 0:
#                 return ret

#         # ch:销毁句柄 | Destroy handle
#         self.obj_cam.MV_CC_DestroyHandle()
#         self.b_open_device = False
#         self.b_start_grabbing = False
#         self.b_exit = True
#         print("close device successfully!")
  








#_________________________________#____________________________________#__________________________________#___________________________________#_________________#

# from core.CameraParams_header import *
# from core.MvCameraControl_class import *
# import threading
# import time
# import numpy as np
# import sys
# from ctypes import *
# import inspect


# def Async_raise(tid, exctype):
#     tid = ctypes.c_long(tid)
#     if not inspect.isclass(exctype):
#         exctype = type(exctype)
#     res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
#     if res == 0:
#         raise ValueError("invalid thread id")
#     elif res != 1:
#         ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
#         raise SystemError("PyThreadState_SetAsyncExc failed")


# def Stop_thread(thread):
#     Async_raise(thread.ident, SystemExit)


# class CameraOperation:

#     def __init__(self, obj_cam, st_device_list, n_connect_num=0, b_open_device=False,
#                  b_start_grabbing=False, h_thread_handle=None, b_thread_closed=False,
#                  st_frame_info=None, b_exit=False, b_save_bmp=False, b_save_jpg=False,
#                  buf_save_image=None, n_save_image_size=0, n_win_gui_id=0,
#                  frame_rate=0, exposure_time=0, gain=0):

#         self.obj_cam             = obj_cam
#         self.st_device_list      = st_device_list
#         self.n_connect_num       = n_connect_num
#         self.b_open_device       = b_open_device
#         self.b_start_grabbing    = b_start_grabbing
#         self.b_thread_closed     = b_thread_closed
#         self.st_frame_info       = st_frame_info
#         self.b_exit              = b_exit
#         self.b_save_bmp          = b_save_bmp
#         self.b_save_jpg          = b_save_jpg
#         self.buf_grab_image      = None
#         self.buf_grab_image_size = 0
#         self.buf_save_image      = buf_save_image
#         self.n_save_image_size   = n_save_image_size
#         self.h_thread_handle     = h_thread_handle
#         self.frame_rate          = frame_rate
#         self.exposure_time       = exposure_time  # µs
#         self.gain                = gain

#         self.buf_lock        = threading.Lock()
#         self._last_frame_num = -1

#         # ── Tính sẵn timeout tối ưu từ exposure_time ──
#         # exposure_time (µs) → ms, cộng thêm 5ms buffer
#         # Nếu chưa biết exposure lúc __init__, dùng 20ms mặc định,
#         # sẽ được cập nhật sau khi Get_all_parameter()
#         self._retrieve_timeout_ms = self._calc_timeout_ms(exposure_time)

#     def _calc_timeout_ms(self, exposure_us):
#         """
#         Tính timeout GetImageBuffer từ exposure time.
#         exposure_us : exposure time tính bằng µs (vd 8000–10000)
#         Công thức  : exposure_ms + 5ms overhead, tối thiểu 20ms
#         """
#         if exposure_us and exposure_us > 0:
#             return max(20, int(exposure_us / 1000) + 5)
#         return 20  # mặc định an toàn

#     # ─────────────────────────────────────────────
#     # MỞ THIẾT BỊ
#     # ─────────────────────────────────────────────
#     def Open_device(self):
#         if not self.b_open_device:
#             if self.n_connect_num < 0:
#                 return MV_E_CALLORDER

#             nConnectionNum = int(self.n_connect_num)
#             stDeviceList = cast(
#                 self.st_device_list.pDeviceInfo[nConnectionNum],
#                 POINTER(MV_CC_DEVICE_INFO)
#             ).contents

#             self.obj_cam = MvCamera()
#             ret = self.obj_cam.MV_CC_CreateHandle(stDeviceList)
#             if ret != 0:
#                 self.obj_cam.MV_CC_DestroyHandle()
#                 return ret

#             ret = self.obj_cam.MV_CC_OpenDevice()
#             if ret != 0:
#                 return ret

#             self.b_open_device   = True
#             self.b_thread_closed = False

#             # Tối ưu packet size cho GigE
#             if stDeviceList.nTLayerType == MV_GIGE_DEVICE:
#                 nPacketSize = self.obj_cam.MV_CC_GetOptimalPacketSize()
#                 if int(nPacketSize) > 0:
#                     ret = self.obj_cam.MV_CC_SetIntValue("GevSCPSPacketSize", nPacketSize)
#                     if ret != 0:
#                         print("warning: set packet size fail! ret[0x%x]" % ret)
#                 else:
#                     print("warning: get packet size fail! ret[0x%x]" % nPacketSize)

#             ret = self.configure_software_trigger()
#             if ret != 0:
#                 print("warning: configure software trigger fail! ret[0x%x]" % ret)
#                 return ret

#             print("Open device & configure software trigger successfully")
#             return MV_OK

#     # ─────────────────────────────────────────────
#     # CẤU HÌNH SOFTWARE TRIGGER
#     # ─────────────────────────────────────────────
#     def configure_software_trigger(self):
#         ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
#         if ret != 0:
#             print("set trigger mode OFF fail! ret[0x%x]" % ret)
#             return ret

#         ret = self.obj_cam.MV_CC_SetEnumValue("TriggerSource", MV_TRIGGER_SOURCE_SOFTWARE)
#         if ret != 0:
#             print("set trigger source SOFTWARE fail! ret[0x%x]" % ret)
#             return ret

#         ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_ON)
#         if ret != 0:
#             print("set trigger mode ON fail! ret[0x%x]" % ret)
#             return ret

#         # Warm-up nhỏ sau khi đổi trigger mode, sau đó xả buffer cũ.
#         # Chỉ cần ở đây (lúc cấu hình), KHÔNG cần trong mỗi lần chụp.
#         time.sleep(0.05)
#         self._flush_image_buffer()

#         print("Software trigger configured successfully")
#         return MV_OK

#     # ─────────────────────────────────────────────
#     # FLUSH BUFFER — chỉ gọi lúc init / configure
#     # ─────────────────────────────────────────────
#     def _flush_image_buffer(self, max_flush=10):
#         """Xả hết frame cũ còn sót trong buffer."""
#         stOutFrame = MV_FRAME_OUT()
#         flushed = 0
#         for _ in range(max_flush):
#             memset(byref(stOutFrame), 0, sizeof(stOutFrame))
#             ret = self.obj_cam.MV_CC_GetImageBuffer(stOutFrame, 5)
#             if ret == 0 and stOutFrame.pBufAddr is not None:
#                 self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
#                 flushed += 1
#             else:
#                 break
#         if flushed:
#             print(f"Flushed {flushed} stale frame(s) from buffer")

#     # ─────────────────────────────────────────────
#     # SOFTWARE TRIGGER + LẤY ẢNH  ← CRITICAL PATH
#     # Không có sleep, không có lock thừa,
#     # timeout = exposure_ms + 5ms overhead
#     # ─────────────────────────────────────────────
#     def Trigger_Camera_Software(self, max_retries=3):
#         """
#         Luồng tối ưu tốc độ (1 thread tuần tự):

#           1. Gửi TriggerSoftware
#           2. GetImageBuffer với timeout = exposure_ms + 5ms
#              → ảnh về sau đúng ~exposure_time, không chờ thêm
#           3. Convert → trả về numpy array

#         Không có sleep() trong critical path.
#         Retry chỉ xảy ra khi thực sự lỗi (hiếm).

#         max_retries: giảm xuống 3 vì tuần tự — nếu lỗi thật thì retry nhiều cũng không giúp được
#         """
#         for attempt in range(max_retries):
#             try:
#                 # ── Bước 1: Gửi trigger ─────────────────
#                 ret = self.obj_cam.MV_CC_SetCommandValue("TriggerSoftware")
#                 if ret != 0:
#                     # 0x80000206: camera chưa sẵn sàng
#                     # Vì tuần tự nên lỗi này rất hiếm — chờ ngắn rồi thử lại
#                     print("Execute software trigger fail! ret[0x%x] (attempt %d/%d)"
#                           % (ret, attempt + 1, max_retries))
#                     time.sleep(0.015)
#                     continue
#                 time.sleep(0.001)
#                 # ── Bước 2: Lấy ảnh ─────────────────────
#                 # timeout = exposure_ms + 5ms, không poll vòng lặp
#                 img = self._retrieve_image(self._retrieve_timeout_ms)
#                 if img is not None:
#                     return img
#                 time.sleep(0.01)
#                 # Trigger OK nhưng buffer trống — rất hiếm khi timeout đúng
#                 print("Trigger OK nhưng không lấy được ảnh (attempt %d/%d)"
#                       % (attempt + 1, max_retries))

#             except Exception as e:
#                 print(f"Trigger Error (attempt {attempt + 1}/{max_retries}): {e}")
#                 time.sleep(0.015)

#         print("Trigger thất bại sau %d lần thử" % max_retries)
#         return None

#     # ─────────────────────────────────────────────
#     # LẤY ẢNH TỪ BUFFER
#     # ─────────────────────────────────────────────
#     def _retrieve_image(self, timeout_ms):
#         """
#         Lấy 1 frame từ buffer với timeout cho trước.
#         buf_lock bảo vệ GetImageBuffer + FreeImageBuffer.
#         """
#         stOutFrame = MV_FRAME_OUT()
#         memset(byref(stOutFrame), 0, sizeof(stOutFrame))

#         with self.buf_lock:
#             ret = self.obj_cam.MV_CC_GetImageBuffer(stOutFrame, timeout_ms)
#             if ret != 0 or stOutFrame.pBufAddr is None:
#                 print("Get image buffer fail! ret[0x%x]" % ret)
#                 return None
#             try:
#                 return self._convert_frame(stOutFrame)
#             finally:
#                 self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)

#     # ─────────────────────────────────────────────
#     # CONVERT PIXEL FORMAT → NUMPY ARRAY
#     # ─────────────────────────────────────────────
#     def _convert_frame(self, stOutFrame):
#         pixel_type = stOutFrame.stFrameInfo.enPixelType
#         color_mode = self.IsImageColor(pixel_type)

#         stConvertParam = MV_CC_PIXEL_CONVERT_PARAM()
#         memset(byref(stConvertParam), 0, sizeof(stConvertParam))

#         if color_mode == 'mono':
#             stConvertParam.enDstPixelType = PixelType_Gvsp_Mono8
#             nConvertSize = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight
#         elif color_mode == 'color':
#             stConvertParam.enDstPixelType = PixelType_Gvsp_BGR8_Packed
#             nConvertSize = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight * 3
#         else:
#             print("Pixel type not supported!")
#             return None

#         stConvertParam.nWidth         = stOutFrame.stFrameInfo.nWidth
#         stConvertParam.nHeight        = stOutFrame.stFrameInfo.nHeight
#         stConvertParam.pSrcData       = cast(stOutFrame.pBufAddr, POINTER(c_ubyte))
#         stConvertParam.nSrcDataLen    = stOutFrame.stFrameInfo.nFrameLen
#         stConvertParam.enSrcPixelType = pixel_type
#         stConvertParam.pDstBuffer     = (c_ubyte * nConvertSize)()
#         stConvertParam.nDstBufferSize = nConvertSize

#         ret = self.obj_cam.MV_CC_ConvertPixelType(stConvertParam)
#         if ret != 0:
#             print("Convert pixel fail! ret[0x%x]" % ret)
#             return None

#         img_buff = (c_ubyte * stConvertParam.nDstLen)()
#         cdll.msvcrt.memcpy(byref(img_buff), stConvertParam.pDstBuffer, stConvertParam.nDstLen)
#         img = np.frombuffer(img_buff, dtype=np.uint8, count=stConvertParam.nDstLen)

#         if color_mode == 'color':
#             img = img.reshape(stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nWidth, 3)
#         else:
#             img = img.reshape(stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nWidth)

#         return img

#     # ─────────────────────────────────────────────
#     # START / STOP GRABBING
#     # ─────────────────────────────────────────────
#     def grabbing(self):
#         ret = self.obj_cam.MV_CC_StartGrabbing()
#         if ret != 0:
#             print("Start grabbing fail! ret[0x%x]" % ret)
#             return ret
#         self.b_start_grabbing = True
#         # Flush sau StartGrabbing để pipeline sạch
#         time.sleep(0.05)
#         self._flush_image_buffer()
#         return MV_OK

#     def not_grabbing(self):
#         ret = self.obj_cam.MV_CC_StopGrabbing()
#         if ret != 0:
#             print("Stop grabbing fail! ret[0x%x]" % ret)
#             return ret
#         self.b_start_grabbing = False
#         return MV_OK

#     # ─────────────────────────────────────────────
#     # PIXEL FORMAT HELPER
#     # ─────────────────────────────────────────────
#     def IsImageColor(self, enPixelType):
#         mono_formats = [
#             PixelType_Gvsp_Mono8,
#             PixelType_Gvsp_Mono10,
#             PixelType_Gvsp_Mono12,
#         ]
#         return 'mono' if enPixelType in mono_formats else 'color'

#     # ─────────────────────────────────────────────
#     # LOAD USER SET PARAMS
#     # ─────────────────────────────────────────────
#     def load_params_user_selector(self, user_set_index=0):
#         print(f'[-] Loading UserSet{user_set_index} from MVS...')
#         if not self.b_open_device:
#             return -1

#         ret = self.obj_cam.MV_CC_SetEnumValue("UserSetSelector", user_set_index)
#         if ret != 0:
#             print(f"=> Failed to select user set {user_set_index}, error: {ret}")
#             return ret

#         ret = self.obj_cam.MV_CC_SetCommandValue("UserSetLoad")
#         if ret != 0:
#             print(f"=> Failed to load user set {user_set_index}, error: {ret}")
#             return ret

#         print(f"[-] Load UserSet{user_set_index} from MVS Successfully!")

#         # UserSetLoad có thể reset TriggerMode → cấu hình lại
#         ret = self.configure_software_trigger()
#         if ret != 0:
#             print("warning: re-configure software trigger after UserSetLoad fail!")
#             return ret

#         return self.Get_all_parameter()

#     # ─────────────────────────────────────────────
#     # ĐỌC TẤT CẢ PARAMS TỪ CAMERA
#     # ─────────────────────────────────────────────
#     def Get_all_parameter(self):
#         if not self.b_open_device:
#             return -1

#         self.camera_params = {}

#         float_params = ["AcquisitionFrameRate", "ExposureTime", "Gain", "Gamma"]
#         for name in float_params:
#             stVal = MVCC_FLOATVALUE()
#             memset(byref(stVal), 0, sizeof(MVCC_FLOATVALUE))
#             ret = self.obj_cam.MV_CC_GetFloatValue(name, stVal)
#             self.camera_params[name] = stVal.fCurValue if ret == 0 else None

#         bool_params = ["GammaEnable"]
#         for name in bool_params:
#             stVal = c_bool(False)
#             ret = self.obj_cam.MV_CC_GetBoolValue(name, stVal)
#             self.camera_params[name] = stVal.value if ret == 0 else None

#         enum_params = [
#             "BalanceWhiteAuto", "PixelFormat", "AcquisitionMode", "TriggerMode",
#             "TriggerSource", "ExposureAuto", "GainAuto", "BinningSelector", "TestPattern"
#         ]
#         for name in enum_params:
#             stVal = MVCC_ENUMVALUE()
#             memset(byref(stVal), 0, sizeof(MVCC_ENUMVALUE))
#             ret = self.obj_cam.MV_CC_GetEnumValue(name, stVal)
#             self.camera_params[name] = stVal.nCurValue if ret == 0 else None

#         int_params = [
#             "BinningHorizontal", "BinningVertical", "OffsetX", "OffsetY",
#             "WidthMax", "HeightMax", "Width", "Height", "BalanceRatio"
#         ]
#         for name in int_params:
#             stVal = MVCC_INTVALUE()
#             memset(byref(stVal), 0, sizeof(MVCC_INTVALUE))
#             ret = self.obj_cam.MV_CC_GetIntValue(name, stVal)
#             self.camera_params[name] = stVal.nCurValue if ret == 0 else None

#         # Cập nhật timeout tối ưu từ exposure thực tế đọc được
#         exposure_us = self.camera_params.get("ExposureTime")
#         if exposure_us:
#             self._retrieve_timeout_ms = self._calc_timeout_ms(exposure_us)
#             print(f"[Camera] ExposureTime = {exposure_us/1000:.2f} ms  "
#                   f"→ retrieve timeout = {self._retrieve_timeout_ms} ms")

#         return MV_OK

#     # ─────────────────────────────────────────────
#     # ĐÓNG THIẾT BỊ
#     # ─────────────────────────────────────────────
#     def Close_device(self):
#         if self.b_open_device:
#             if self.b_thread_closed:
#                 Stop_thread(self.h_thread_handle)
#                 self.b_thread_closed = False
#             ret = self.obj_cam.MV_CC_CloseDevice()
#             if ret != 0:
#                 return ret

#         self.obj_cam.MV_CC_DestroyHandle()
#         self.b_open_device    = False
#         self.b_start_grabbing = False
#         self.b_exit           = True
#         print("close device successfully!")



#_________________________________#____________________________________#__________________________________#___________________________________#_________________#



# from core.CameraParams_header import *
# from core.MvCameraControl_class import *
# import threading
# import time
# import numpy as np
# import sys
# from ctypes import *
# import inspect


# def Async_raise(tid, exctype):
#     tid = ctypes.c_long(tid)
#     if not inspect.isclass(exctype):
#         exctype = type(exctype)
#     res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
#     if res == 0:
#         raise ValueError("invalid thread id")
#     elif res != 1:
#         ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
#         raise SystemError("PyThreadState_SetAsyncExc failed")


# def Stop_thread(thread):
#     Async_raise(thread.ident, SystemExit)


# class CameraOperation:

#     def __init__(self, obj_cam, st_device_list, n_connect_num=0, b_open_device=False,
#                  b_start_grabbing=False, h_thread_handle=None, b_thread_closed=False,
#                  st_frame_info=None, b_exit=False, b_save_bmp=False, b_save_jpg=False,
#                  buf_save_image=None, n_save_image_size=0, n_win_gui_id=0,
#                  frame_rate=0, exposure_time=0, gain=0):

#         self.obj_cam             = obj_cam
#         self.st_device_list      = st_device_list
#         self.n_connect_num       = n_connect_num
#         self.b_open_device       = b_open_device
#         self.b_start_grabbing    = b_start_grabbing
#         self.b_thread_closed     = b_thread_closed
#         self.st_frame_info       = st_frame_info
#         self.b_exit              = b_exit
#         self.b_save_bmp          = b_save_bmp
#         self.b_save_jpg          = b_save_jpg
#         self.buf_grab_image      = None
#         self.buf_grab_image_size = 0
#         self.buf_save_image      = buf_save_image
#         self.n_save_image_size   = n_save_image_size
#         self.h_thread_handle     = h_thread_handle
#         self.frame_rate          = frame_rate
#         self.exposure_time       = exposure_time  # µs
#         self.gain                = gain

#         self.buf_lock = threading.Lock()

#         # Frame number của frame cuối đã trả về thành công.
#         # Dùng để phát hiện và bỏ qua frame cũ còn sót trong queue.
#         self._last_frame_num = -1

#         # Timeout GetImageBuffer = exposure_ms + overhead, tự cập nhật sau Get_all_parameter()
#         self._retrieve_timeout_ms = self._calc_timeout_ms(exposure_time)

#     def _calc_timeout_ms(self, exposure_us):
#         """
#         Tính timeout GetImageBuffer từ exposure time (µs).
#         Công thức: exposure_ms + 10ms overhead (tăng lên 10ms để chắc chắn
#         frame mới đã vào queue trước khi GetImageBuffer được gọi).
#         Tối thiểu 20ms.
#         """
#         if exposure_us and exposure_us > 0:
#             return max(20, int(exposure_us / 1000) + 10)
#         return 20

#     # ─────────────────────────────────────────────
#     # MỞ THIẾT BỊ
#     # ─────────────────────────────────────────────
#     def Open_device(self):
#         if not self.b_open_device:
#             if self.n_connect_num < 0:
#                 return MV_E_CALLORDER

#             nConnectionNum = int(self.n_connect_num)
#             stDeviceList = cast(
#                 self.st_device_list.pDeviceInfo[nConnectionNum],
#                 POINTER(MV_CC_DEVICE_INFO)
#             ).contents

#             self.obj_cam = MvCamera()
#             ret = self.obj_cam.MV_CC_CreateHandle(stDeviceList)
#             if ret != 0:
#                 self.obj_cam.MV_CC_DestroyHandle()
#                 return ret

#             ret = self.obj_cam.MV_CC_OpenDevice()
#             if ret != 0:
#                 return ret

#             self.b_open_device   = True
#             self.b_thread_closed = False

#             # Tối ưu packet size cho GigE
#             if stDeviceList.nTLayerType == MV_GIGE_DEVICE:
#                 nPacketSize = self.obj_cam.MV_CC_GetOptimalPacketSize()
#                 if int(nPacketSize) > 0:
#                     ret = self.obj_cam.MV_CC_SetIntValue("GevSCPSPacketSize", nPacketSize)
#                     if ret != 0:
#                         print("warning: set packet size fail! ret[0x%x]" % ret)
#                 else:
#                     print("warning: get packet size fail! ret[0x%x]" % nPacketSize)

#             ret = self.configure_software_trigger()
#             if ret != 0:
#                 print("warning: configure software trigger fail! ret[0x%x]" % ret)
#                 return ret

#             print("Open device & configure software trigger successfully")
#             return MV_OK

#     # ─────────────────────────────────────────────
#     # CẤU HÌNH SOFTWARE TRIGGER
#     # ─────────────────────────────────────────────
#     def configure_software_trigger(self):
#         ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
#         if ret != 0:
#             print("set trigger mode OFF fail! ret[0x%x]" % ret)
#             return ret

#         ret = self.obj_cam.MV_CC_SetEnumValue("TriggerSource", MV_TRIGGER_SOURCE_SOFTWARE)
#         if ret != 0:
#             print("set trigger source SOFTWARE fail! ret[0x%x]" % ret)
#             return ret

#         ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_ON)
#         if ret != 0:
#             print("set trigger mode ON fail! ret[0x%x]" % ret)
#             return ret

#         # Warm-up + flush: chỉ cần lúc configure, không cần trong mỗi lần chụp
#         time.sleep(0.05)
#         self._flush_image_buffer()

#         # Reset frame counter sau mỗi lần configure
#         self._last_frame_num = -1

#         print("Software trigger configured successfully")
#         return MV_OK

#     # ─────────────────────────────────────────────
#     # FLUSH BUFFER
#     # ─────────────────────────────────────────────
#     def _flush_image_buffer(self, max_flush=10):
#         """Xả hết frame cũ trong queue. Chỉ gọi lúc init/configure/grabbing."""
#         stOutFrame = MV_FRAME_OUT()
#         flushed = 0
#         for _ in range(max_flush):
#             memset(byref(stOutFrame), 0, sizeof(stOutFrame))
#             ret = self.obj_cam.MV_CC_GetImageBuffer(stOutFrame, 5)
#             if ret == 0 and stOutFrame.pBufAddr is not None:
#                 self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
#                 flushed += 1
#             else:
#                 break
#         if flushed:
#             print(f"Flushed {flushed} stale frame(s) from buffer")

#     # ─────────────────────────────────────────────
#     # SOFTWARE TRIGGER + LẤY ẢNH  ← CRITICAL PATH
#     # ─────────────────────────────────────────────
#     def Trigger_Camera_Software(self, max_retries=3):
#         """
#         Gửi trigger → lấy frame MỚI (frame_num > _last_frame_num).

#         Fix buffer-lag / frame-duplicate:
#           - Sau trigger, poll GetImageBuffer tối đa max_poll lần
#           - Mỗi lần lấy được frame thì kiểm tra nFrameNum
#           - Nếu nFrameNum <= _last_frame_num → frame cũ, giải phóng và poll tiếp
#           - Chỉ trả về khi nFrameNum > _last_frame_num (frame mới đúng)

#         Không có sleep() trong critical path.
#         """
#         for attempt in range(max_retries):
#             try:
#                 # ── Bước 1: Gửi trigger ─────────────────
#                 ret = self.obj_cam.MV_CC_SetCommandValue("TriggerSoftware")
#                 if ret != 0:
#                     print("Execute software trigger fail! ret[0x%x] (attempt %d/%d)"
#                           % (ret, attempt + 1, max_retries))
#                     # time.sleep(0.015)
#                     continue

#                 # ── Bước 2: Lấy frame MỚI ───────────────
#                 img = self._retrieve_new_frame(self._retrieve_timeout_ms)
#                 if img is not None:
#                     return img

#                 print("Trigger OK nhưng không lấy được frame mới (attempt %d/%d)"
#                       % (attempt + 1, max_retries))

#             except Exception as e:
#                 print(f"Trigger Error (attempt {attempt + 1}/{max_retries}): {e}")
#                 # time.sleep(0.015)

#         print("Trigger thất bại sau %d lần thử" % max_retries)
#         return None

#     # ─────────────────────────────────────────────
#     # LẤY FRAME MỚI — bỏ qua frame cũ trong queue
#     # ─────────────────────────────────────────────
#     def _retrieve_new_frame(self, timeout_ms, max_poll=5):
#         """
#         Poll GetImageBuffer tối đa max_poll lần.
#         Mỗi lần lấy được frame thì verify nFrameNum:
#           - nFrameNum > _last_frame_num  → frame mới đúng, trả về
#           - nFrameNum <= _last_frame_num → frame cũ còn sót, giải phóng, poll tiếp

#         Tại sao max_poll=5:
#           Trường hợp xấu nhất: queue chứa 1-2 frame cũ sót lại.
#           5 lần poll là quá đủ để bỏ qua hết frame cũ và lấy được frame mới.
#           Mỗi poll tốn đúng = thời gian frame thực sự về (không busy-wait).
#         """
#         stOutFrame = MV_FRAME_OUT()

#         for poll in range(max_poll):
#             memset(byref(stOutFrame), 0, sizeof(stOutFrame))

#             with self.buf_lock:
#                 ret = self.obj_cam.MV_CC_GetImageBuffer(stOutFrame, 50)
               

#                 if ret != 0 or stOutFrame.pBufAddr is None:
#                     # Không có frame nào trong timeout → thất bại luôn, không poll tiếp
#                     # (nếu frame chưa về trong timeout_ms = exposure+10ms thì có vấn đề phần cứng)
#                     print("Get image buffer fail! ret[0x%x] (poll %d/%d)"
#                           % (ret, poll + 1, max_poll))
#                     return None

#                 current_frame_num = stOutFrame.stFrameInfo.nFrameNum

#                 if current_frame_num > self._last_frame_num:
#                     try:
#                         img = self._convert_frame(stOutFrame)
#                         if img is not None:
#                             self._last_frame_num = current_frame_num
#                             return img
#                         else:
#                             return None
#                     finally:
#                         print('bi qua ha')
#                         self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)

#                 else:
#                     # Frame cũ còn sót trong queue (nFrameNum <= last)
#                     # Giải phóng và poll tiếp để lấy frame của trigger hiện tại
#                     print(f"[WARN] Frame cũ phát hiện: frame_num={current_frame_num} "
#                           f"<= last={self._last_frame_num}, bỏ qua, poll tiếp ({poll+1}/{max_poll})")
#                     self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
#                     # Không sleep — frame mới có thể đã vào queue ngay sau frame cũ

#         print(f"Không lấy được frame mới sau {max_poll} lần poll")
#         return None

#     # ─────────────────────────────────────────────
#     # CONVERT PIXEL FORMAT → NUMPY ARRAY
#     # ─────────────────────────────────────────────
#     def _convert_frame(self, stOutFrame):
#         pixel_type = stOutFrame.stFrameInfo.enPixelType
#         color_mode = self.IsImageColor(pixel_type)

#         stConvertParam = MV_CC_PIXEL_CONVERT_PARAM()
#         memset(byref(stConvertParam), 0, sizeof(stConvertParam))

#         if color_mode == 'mono':
#             stConvertParam.enDstPixelType = PixelType_Gvsp_Mono8
#             nConvertSize = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight
#         elif color_mode == 'color':
#             stConvertParam.enDstPixelType = PixelType_Gvsp_BGR8_Packed
#             nConvertSize = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight * 3
#         else:
#             print("Pixel type not supported!")
#             return None

#         stConvertParam.nWidth         = stOutFrame.stFrameInfo.nWidth
#         stConvertParam.nHeight        = stOutFrame.stFrameInfo.nHeight
#         stConvertParam.pSrcData       = cast(stOutFrame.pBufAddr, POINTER(c_ubyte))
#         stConvertParam.nSrcDataLen    = stOutFrame.stFrameInfo.nFrameLen
#         stConvertParam.enSrcPixelType = pixel_type
#         stConvertParam.pDstBuffer     = (c_ubyte * nConvertSize)()
#         stConvertParam.nDstBufferSize = nConvertSize

#         ret = self.obj_cam.MV_CC_ConvertPixelType(stConvertParam)
#         if ret != 0:
#             print("Convert pixel fail! ret[0x%x]" % ret)
#             return None

#         img_buff = (c_ubyte * stConvertParam.nDstLen)()
#         cdll.msvcrt.memcpy(byref(img_buff), stConvertParam.pDstBuffer, stConvertParam.nDstLen)
#         img = np.frombuffer(img_buff, dtype=np.uint8, count=stConvertParam.nDstLen)

#         if color_mode == 'color':
#             img = img.reshape(stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nWidth, 3)
#         else:
#             img = img.reshape(stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nWidth)

#         return img

#     # ─────────────────────────────────────────────
#     # START / STOP GRABBING
#     # ─────────────────────────────────────────────
#     def grabbing(self):
#         ret = self.obj_cam.MV_CC_StartGrabbing()
#         if ret != 0:
#             print("Start grabbing fail! ret[0x%x]" % ret)
#             return ret
#         self.b_start_grabbing = True
#         time.sleep(0.05)
#         self._flush_image_buffer()
#         self._last_frame_num = -1  # Reset sau mỗi lần StartGrabbing
#         return MV_OK

#     def not_grabbing(self):
#         ret = self.obj_cam.MV_CC_StopGrabbing()
#         if ret != 0:
#             print("Stop grabbing fail! ret[0x%x]" % ret)
#             return ret
#         self.b_start_grabbing = False
#         return MV_OK

#     # ─────────────────────────────────────────────
#     # PIXEL FORMAT HELPER
#     # ─────────────────────────────────────────────
#     def IsImageColor(self, enPixelType):
#         mono_formats = [
#             PixelType_Gvsp_Mono8,
#             PixelType_Gvsp_Mono10,
#             PixelType_Gvsp_Mono12,
#         ]
#         return 'mono' if enPixelType in mono_formats else 'color'

#     # ─────────────────────────────────────────────
#     # LOAD USER SET PARAMS
#     # ─────────────────────────────────────────────
#     def load_params_user_selector(self, user_set_index=0):
#         print(f'[-] Loading UserSet{user_set_index} from MVS...')
#         if not self.b_open_device:
#             return -1

#         ret = self.obj_cam.MV_CC_SetEnumValue("UserSetSelector", user_set_index)
#         if ret != 0:
#             print(f"=> Failed to select user set {user_set_index}, error: {ret}")
#             return ret

#         ret = self.obj_cam.MV_CC_SetCommandValue("UserSetLoad")
#         if ret != 0:
#             print(f"=> Failed to load user set {user_set_index}, error: {ret}")
#             return ret

#         print(f"[-] Load UserSet{user_set_index} from MVS Successfully!")

#         # UserSetLoad có thể reset TriggerMode → cấu hình lại
#         ret = self.configure_software_trigger()
#         if ret != 0:
#             print("warning: re-configure software trigger after UserSetLoad fail!")
#             return ret

#         return self.Get_all_parameter()

#     # ─────────────────────────────────────────────
#     # ĐỌC TẤT CẢ PARAMS TỪ CAMERA
#     # ─────────────────────────────────────────────
#     def Get_all_parameter(self):
#         if not self.b_open_device:
#             return -1

#         self.camera_params = {}

#         float_params = ["AcquisitionFrameRate", "ExposureTime", "Gain", "Gamma"]
#         for name in float_params:
#             stVal = MVCC_FLOATVALUE()
#             memset(byref(stVal), 0, sizeof(MVCC_FLOATVALUE))
#             ret = self.obj_cam.MV_CC_GetFloatValue(name, stVal)
#             self.camera_params[name] = stVal.fCurValue if ret == 0 else None

#         bool_params = ["GammaEnable"]
#         for name in bool_params:
#             stVal = c_bool(False)
#             ret = self.obj_cam.MV_CC_GetBoolValue(name, stVal)
#             self.camera_params[name] = stVal.value if ret == 0 else None

#         enum_params = [
#             "BalanceWhiteAuto", "PixelFormat", "AcquisitionMode", "TriggerMode",
#             "TriggerSource", "ExposureAuto", "GainAuto", "BinningSelector", "TestPattern"
#         ]
#         for name in enum_params:
#             stVal = MVCC_ENUMVALUE()
#             memset(byref(stVal), 0, sizeof(MVCC_ENUMVALUE))
#             ret = self.obj_cam.MV_CC_GetEnumValue(name, stVal)
#             self.camera_params[name] = stVal.nCurValue if ret == 0 else None

#         int_params = [
#             "BinningHorizontal", "BinningVertical", "OffsetX", "OffsetY",
#             "WidthMax", "HeightMax", "Width", "Height", "BalanceRatio"
#         ]
#         for name in int_params:
#             stVal = MVCC_INTVALUE()
#             memset(byref(stVal), 0, sizeof(MVCC_INTVALUE))
#             ret = self.obj_cam.MV_CC_GetIntValue(name, stVal)
#             self.camera_params[name] = stVal.nCurValue if ret == 0 else None

#         # Cập nhật timeout tối ưu từ exposure thực tế
#         exposure_us = self.camera_params.get("ExposureTime")
#         if exposure_us:
#             self._retrieve_timeout_ms = self._calc_timeout_ms(exposure_us)
#             print(f"[Camera] ExposureTime = {exposure_us/1000:.2f} ms  "
#                   f"→ retrieve timeout = {self._retrieve_timeout_ms} ms")

#         return MV_OK

#     # ─────────────────────────────────────────────
#     # ĐÓNG THIẾT BỊ
#     # ─────────────────────────────────────────────
#     def Close_device(self):
#         if self.b_open_device:
#             if self.b_thread_closed:
#                 Stop_thread(self.h_thread_handle)
#                 self.b_thread_closed = False
#             ret = self.obj_cam.MV_CC_CloseDevice()
#             if ret != 0:
#                 return ret

#         self.obj_cam.MV_CC_DestroyHandle()
#         self.b_open_device    = False
#         self.b_start_grabbing = False
#         self.b_exit           = True
#         print("close device successfully!")



#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++



# from core.CameraParams_header import *
# from core.MvCameraControl_class import *
# import threading
# import time
# import numpy as np
# import sys
# from ctypes import *
# import inspect



# def Async_raise(tid, exctype):
#     tid = ctypes.c_long(tid)
#     if not inspect.isclass(exctype):
#         exctype = type(exctype)
#     res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
#     if res == 0:
#         raise ValueError("invalid thread id")
#     elif res != 1:
#         ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
#         raise SystemError("PyThreadState_SetAsyncExc failed")


# def Stop_thread(thread):
#     Async_raise(thread.ident, SystemExit)


# class CameraOperation:

#     def __init__(self, obj_cam, st_device_list, n_connect_num=0, b_open_device=False,
#                  b_start_grabbing=False, h_thread_handle=None, b_thread_closed=False,
#                  st_frame_info=None, b_exit=False, b_save_bmp=False, b_save_jpg=False,
#                  buf_save_image=None, n_save_image_size=0, n_win_gui_id=0,
#                  frame_rate=0, exposure_time=0, gain=0):

#         self.obj_cam             = obj_cam
#         self.st_device_list      = st_device_list
#         self.n_connect_num       = n_connect_num
#         self.b_open_device       = b_open_device
#         self.b_start_grabbing    = b_start_grabbing
#         self.b_thread_closed     = b_thread_closed
#         self.st_frame_info       = st_frame_info
#         self.b_exit              = b_exit
#         self.b_save_bmp          = b_save_bmp
#         self.b_save_jpg          = b_save_jpg
#         self.buf_grab_image      = None
#         self.buf_grab_image_size = 0
#         self.buf_save_image      = buf_save_image
#         self.n_save_image_size   = n_save_image_size
#         self.h_thread_handle     = h_thread_handle
#         self.frame_rate          = frame_rate
#         self.exposure_time       = exposure_time  # µs
#         self.gain                = gain

#         self.buf_lock        = threading.Lock()
#         self._last_frame_num = -1

#         # ── Tính sẵn timeout tối ưu từ exposure_time ──
#         # exposure_time (µs) → ms, cộng thêm 5ms buffer
#         # Nếu chưa biết exposure lúc __init__, dùng 20ms mặc định,
#         # sẽ được cập nhật sau khi Get_all_parameter()
#         self._retrieve_timeout_ms = self._calc_timeout_ms(exposure_time)

#     def _calc_timeout_ms(self, exposure_us):
#         """
#         Tính timeout GetImageBuffer từ exposure time.
#         exposure_us : exposure time tính bằng µs (vd 8000–10000)
#         Công thức  : exposure_ms + 5ms overhead, tối thiểu 20ms
#         """
#         if exposure_us and exposure_us > 0:
#             return max(20, int(exposure_us / 1000) + 5)
#         return 20  # mặc định an toàn

#     # ─────────────────────────────────────────────
#     # MỞ THIẾT BỊ
#     # ─────────────────────────────────────────────
#     def Open_device(self):
#         if not self.b_open_device:
#             if self.n_connect_num < 0:
#                 return MV_E_CALLORDER

#             nConnectionNum = int(self.n_connect_num)
#             stDeviceList = cast(
#                 self.st_device_list.pDeviceInfo[nConnectionNum],
#                 POINTER(MV_CC_DEVICE_INFO)
#             ).contents

#             self.obj_cam = MvCamera()
#             ret = self.obj_cam.MV_CC_CreateHandle(stDeviceList)
#             if ret != 0:
#                 self.obj_cam.MV_CC_DestroyHandle()
#                 return ret

#             ret = self.obj_cam.MV_CC_OpenDevice()
#             if ret != 0:
#                 return ret

#             self.b_open_device   = True
#             self.b_thread_closed = False

#             # Tối ưu packet size cho GigE
#             if stDeviceList.nTLayerType == MV_GIGE_DEVICE:
#                 nPacketSize = self.obj_cam.MV_CC_GetOptimalPacketSize()
#                 if int(nPacketSize) > 0:
#                     ret = self.obj_cam.MV_CC_SetIntValue("GevSCPSPacketSize", nPacketSize)
#                     if ret != 0:
#                         print("warning: set packet size fail! ret[0x%x]" % ret)
#                 else:
#                     print("warning: get packet size fail! ret[0x%x]" % nPacketSize)

#             ret = self.configure_software_trigger()
#             if ret != 0:
#                 print("warning: configure software trigger fail! ret[0x%x]" % ret)
#                 return ret

#             print("Open device & configure software trigger successfully")
#             return MV_OK

#     # ─────────────────────────────────────────────
#     # CẤU HÌNH SOFTWARE TRIGGER
#     # ─────────────────────────────────────────────
#     def configure_software_trigger(self):
#         ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
#         if ret != 0:
#             print("set trigger mode OFF fail! ret[0x%x]" % ret)
#             return ret

#         ret = self.obj_cam.MV_CC_SetEnumValue("TriggerSource", MV_TRIGGER_SOURCE_SOFTWARE)
#         if ret != 0:
#             print("set trigger source SOFTWARE fail! ret[0x%x]" % ret)
#             return ret

#         ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_ON)
#         if ret != 0:
#             print("set trigger mode ON fail! ret[0x%x]" % ret)
#             return ret

#         # Warm-up nhỏ sau khi đổi trigger mode, sau đó xả buffer cũ.
#         # Chỉ cần ở đây (lúc cấu hình), KHÔNG cần trong mỗi lần chụp.
#         time.sleep(0.05)
#         self._flush_image_buffer()

#         print("Software trigger configured successfully")
#         return MV_OK

#     # ─────────────────────────────────────────────
#     # FLUSH BUFFER — chỉ gọi lúc init / configure
#     # ─────────────────────────────────────────────
#     def _flush_image_buffer(self, max_flush=10):
#         """Xả hết frame cũ còn sót trong buffer."""
#         stOutFrame = MV_FRAME_OUT()
#         flushed = 0
#         for _ in range(max_flush):
#             memset(byref(stOutFrame), 0, sizeof(stOutFrame))
#             ret = self.obj_cam.MV_CC_GetImageBuffer(stOutFrame, 5)
#             if ret == 0 and stOutFrame.pBufAddr is not None:
#                 self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
#                 flushed += 1
#             else:
#                 break
#         if flushed:
#             print(f"Flushed {flushed} stale frame(s) from buffer")

#     # ─────────────────────────────────────────────
#     # SOFTWARE TRIGGER + LẤY ẢNH  ← CRITICAL PATH
#     # Không có sleep, không có lock thừa,
#     # timeout = exposure_ms + 5ms overhead
#     # ─────────────────────────────────────────────
#     def Trigger_Camera_Software(self, max_retries=3):
#         """
#         Luồng tối ưu tốc độ (1 thread tuần tự):

#           1. Gửi TriggerSoftware
#           2. GetImageBuffer với timeout = exposure_ms + 5ms
#              → ảnh về sau đúng ~exposure_time, không chờ thêm
#           3. Convert → trả về numpy array

#         Không có sleep() trong critical path.
#         Retry chỉ xảy ra khi thực sự lỗi (hiếm).

#         max_retries: giảm xuống 3 vì tuần tự — nếu lỗi thật thì retry nhiều cũng không giúp được
#         """
#         for attempt in range(max_retries):
#             try:
#                 # ── Bước 1: Gửi trigger ─────────────────
#                 ret = self.obj_cam.MV_CC_SetCommandValue("TriggerSoftware")
#                 if ret != 0:
#                     # 0x80000206: camera chưa sẵn sàng
#                     # Vì tuần tự nên lỗi này rất hiếm — chờ ngắn rồi thử lại
#                     print("Execute software trigger fail! ret[0x%x] (attempt %d/%d)"
#                           % (ret, attempt + 1, max_retries))
#                     time.sleep(0.015)
#                     continue

#                 # ── Bước 2: Lấy ảnh ─────────────────────
#                 # timeout = exposure_ms + 5ms, không poll vòng lặp
#                 img = self._retrieve_new_frame(self._retrieve_timeout_ms)
#                 if img is not None:
#                     return img

#                 # Trigger OK nhưng buffer trống — rất hiếm khi timeout đúng
#                 print("Trigger OK nhưng không lấy được ảnh (attempt %d/%d)"
#                       % (attempt + 1, max_retries))

#             except Exception as e:
#                 print(f"Trigger Error (attempt {attempt + 1}/{max_retries}): {e}")
#                 time.sleep(0.015)

#         print("Trigger thất bại sau %d lần thử" % max_retries)
#         return None

#     # ─────────────────────────────────────────────
#     # LẤY ẢNH TỪ BUFFER
#     # ─────────────────────────────────────────────
#     def _retrieve_new_frame(self, timeout_ms, max_poll=5):
#         """
#         Poll GetImageBuffer với step nhỏ, return ngay khi lấy được frame mới.
#         Tổng timeout = poll_step_ms * max_steps (tự tính), đủ để frame về.
#         """
#         stOutFrame = MV_FRAME_OUT()
#         poll_step_ms = 10        # Mỗi lần chờ tối đa 10ms
#         max_steps = max(3, (timeout_ms + poll_step_ms - 1) // poll_step_ms)

#         with self.buf_lock:
#             for step in range(max_steps):
#                 memset(byref(stOutFrame), 0, sizeof(stOutFrame))
#                 ret = self.obj_cam.MV_CC_GetImageBuffer(stOutFrame, poll_step_ms)

#                 if ret != 0 or stOutFrame.pBufAddr is None:
#                     # Không có frame trong step này → poll tiếp, chưa về kịp
#                     continue

#                 current_frame_num = stOutFrame.stFrameInfo.nFrameNum

#                 if current_frame_num <= self._last_frame_num:
#                     # Frame cũ còn sót → giải phóng và poll tiếp
#                     print(f"[WARN] Frame cũ: {current_frame_num} <= last={self._last_frame_num}, bỏ qua")
#                     self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
#                     continue

#                 # Frame mới đúng → convert và return NGAY
#                 try:
#                     img = self._convert_frame(stOutFrame)
#                     if img is not None:
#                         self._last_frame_num = current_frame_num
#                     return img
#                 finally:
#                     self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)

#         print(f"[ERR] Không lấy được frame mới sau {max_steps} steps ({max_steps * poll_step_ms}ms)")
#         return None

#     # ─────────────────────────────────────────────
#     # CONVERT PIXEL FORMAT → NUMPY ARRAY
#     # ─────────────────────────────────────────────
#     def _convert_frame(self, stOutFrame):
#         pixel_type = stOutFrame.stFrameInfo.enPixelType
#         color_mode = self.IsImageColor(pixel_type)

#         stConvertParam = MV_CC_PIXEL_CONVERT_PARAM()
#         memset(byref(stConvertParam), 0, sizeof(stConvertParam))

#         if color_mode == 'mono':
#             stConvertParam.enDstPixelType = PixelType_Gvsp_Mono8
#             nConvertSize = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight
#         elif color_mode == 'color':
#             stConvertParam.enDstPixelType = PixelType_Gvsp_BGR8_Packed
#             nConvertSize = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight * 3
#         else:
#             print("Pixel type not supported!")
#             return None

#         stConvertParam.nWidth         = stOutFrame.stFrameInfo.nWidth
#         stConvertParam.nHeight        = stOutFrame.stFrameInfo.nHeight
#         stConvertParam.pSrcData       = cast(stOutFrame.pBufAddr, POINTER(c_ubyte))
#         stConvertParam.nSrcDataLen    = stOutFrame.stFrameInfo.nFrameLen
#         stConvertParam.enSrcPixelType = pixel_type
#         stConvertParam.pDstBuffer     = (c_ubyte * nConvertSize)()
#         stConvertParam.nDstBufferSize = nConvertSize

#         ret = self.obj_cam.MV_CC_ConvertPixelType(stConvertParam)
#         if ret != 0:
#             print("Convert pixel fail! ret[0x%x]" % ret)
#             return None

#         img_buff = (c_ubyte * stConvertParam.nDstLen)()
#         cdll.msvcrt.memcpy(byref(img_buff), stConvertParam.pDstBuffer, stConvertParam.nDstLen)
#         img = np.frombuffer(img_buff, dtype=np.uint8, count=stConvertParam.nDstLen)

#         if color_mode == 'color':
#             img = img.reshape(stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nWidth, 3)
#         else:
#             img = img.reshape(stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nWidth)

#         return img

#     # ─────────────────────────────────────────────
#     # START / STOP GRABBING
#     # ─────────────────────────────────────────────
#     def grabbing(self):
#         ret = self.obj_cam.MV_CC_StartGrabbing()
#         if ret != 0:
#             print("Start grabbing fail! ret[0x%x]" % ret)
#             return ret
#         self.b_start_grabbing = True
#         # Flush sau StartGrabbing để pipeline sạch
#         time.sleep(0.05)
#         self._flush_image_buffer()
#         return MV_OK

#     def not_grabbing(self):
#         ret = self.obj_cam.MV_CC_StopGrabbing()
#         if ret != 0:
#             print("Stop grabbing fail! ret[0x%x]" % ret)
#             return ret
#         self.b_start_grabbing = False
#         return MV_OK

#     # ─────────────────────────────────────────────
#     # PIXEL FORMAT HELPER
#     # ─────────────────────────────────────────────
#     def IsImageColor(self, enPixelType):
#         mono_formats = [
#             PixelType_Gvsp_Mono8,
#             PixelType_Gvsp_Mono10,
#             PixelType_Gvsp_Mono12,
#         ]
#         return 'mono' if enPixelType in mono_formats else 'color'

#     # ─────────────────────────────────────────────
#     # LOAD USER SET PARAMS
#     # ─────────────────────────────────────────────
#     def load_params_user_selector(self, user_set_index=0):
#         print(f'[-] Loading UserSet{user_set_index} from MVS...')
#         if not self.b_open_device:
#             return -1

#         ret = self.obj_cam.MV_CC_SetEnumValue("UserSetSelector", user_set_index)
#         if ret != 0:
#             print(f"=> Failed to select user set {user_set_index}, error: {ret}")
#             return ret

#         ret = self.obj_cam.MV_CC_SetCommandValue("UserSetLoad")
#         if ret != 0:
#             print(f"=> Failed to load user set {user_set_index}, error: {ret}")
#             return ret

#         print(f"[-] Load UserSet{user_set_index} from MVS Successfully!")

#         # UserSetLoad có thể reset TriggerMode → cấu hình lại
#         ret = self.configure_software_trigger()
#         if ret != 0:
#             print("warning: re-configure software trigger after UserSetLoad fail!")
#             return ret

#         return self.Get_all_parameter()

#     # ─────────────────────────────────────────────
#     # ĐỌC TẤT CẢ PARAMS TỪ CAMERA
#     # ─────────────────────────────────────────────
#     def Get_all_parameter(self):
#         if not self.b_open_device:
#             return -1

#         self.camera_params = {}

#         float_params = ["AcquisitionFrameRate", "ExposureTime", "Gain", "Gamma"]
#         for name in float_params:
#             stVal = MVCC_FLOATVALUE()
#             memset(byref(stVal), 0, sizeof(MVCC_FLOATVALUE))
#             ret = self.obj_cam.MV_CC_GetFloatValue(name, stVal)
#             self.camera_params[name] = stVal.fCurValue if ret == 0 else None

#         bool_params = ["GammaEnable"]
#         for name in bool_params:
#             stVal = c_bool(False)
#             ret = self.obj_cam.MV_CC_GetBoolValue(name, stVal)
#             self.camera_params[name] = stVal.value if ret == 0 else None

#         enum_params = [
#             "BalanceWhiteAuto", "PixelFormat", "AcquisitionMode", "TriggerMode",
#             "TriggerSource", "ExposureAuto", "GainAuto", "BinningSelector", "TestPattern"
#         ]
#         for name in enum_params:
#             stVal = MVCC_ENUMVALUE()
#             memset(byref(stVal), 0, sizeof(MVCC_ENUMVALUE))
#             ret = self.obj_cam.MV_CC_GetEnumValue(name, stVal)
#             self.camera_params[name] = stVal.nCurValue if ret == 0 else None

#         int_params = [
#             "BinningHorizontal", "BinningVertical", "OffsetX", "OffsetY",
#             "WidthMax", "HeightMax", "Width", "Height", "BalanceRatio"
#         ]
#         for name in int_params:
#             stVal = MVCC_INTVALUE()
#             memset(byref(stVal), 0, sizeof(MVCC_INTVALUE))
#             ret = self.obj_cam.MV_CC_GetIntValue(name, stVal)
#             self.camera_params[name] = stVal.nCurValue if ret == 0 else None

#         # Cập nhật timeout tối ưu từ exposure thực tế đọc được
#         exposure_us = self.camera_params.get("ExposureTime")
#         if exposure_us:
#             self._retrieve_timeout_ms = self._calc_timeout_ms(exposure_us)
#             print(f"[Camera] ExposureTime = {exposure_us/1000:.2f} ms  "
#                   f"→ retrieve timeout = {self._retrieve_timeout_ms} ms")

#         return MV_OK

#     # ─────────────────────────────────────────────
#     # ĐÓNG THIẾT BỊ
#     # ─────────────────────────────────────────────
#     def Close_device(self):
#         if self.b_open_device:
#             if self.b_thread_closed:
#                 Stop_thread(self.h_thread_handle)
#                 self.b_thread_closed = False
#             ret = self.obj_cam.MV_CC_CloseDevice()
#             if ret != 0:
#                 return ret

#         self.obj_cam.MV_CC_DestroyHandle()
#         self.b_open_device    = False
#         self.b_start_grabbing = False
#         self.b_exit           = True
#         print("close device successfully!")






#_________________________________#____________________________________#__________________________________#___________________________________#_________________#



from core.CameraParams_header import *
from core.MvCameraControl_class import *
import threading
import time
import numpy as np
import sys
from ctypes import *
import inspect


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

        # Frame number của frame cuối đã trả về thành công.
        # Dùng để phát hiện và bỏ qua frame cũ còn sót trong queue.
        self._last_frame_num = -1

        # Timeout GetImageBuffer = exposure_ms + overhead, tự cập nhật sau Get_all_parameter()
        self._retrieve_timeout_ms = self._calc_timeout_ms(exposure_time)

    def _calc_timeout_ms(self, exposure_us):
        """
        Tính timeout GetImageBuffer từ exposure time (µs).
        Công thức: exposure_ms + 10ms overhead (tăng lên 10ms để chắc chắn
        frame mới đã vào queue trước khi GetImageBuffer được gọi).
        Tối thiểu 20ms.
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

    # ─────────────────────────────────────────────
    # SOFTWARE TRIGGER + LẤY ẢNH  ← CRITICAL PATH
    # ─────────────────────────────────────────────
    def Trigger_Camera_Software(self, max_retries=3):
        """
        Gửi trigger → lấy frame MỚI (frame_num > _last_frame_num).

        Fix buffer-lag / frame-duplicate:
          - Sau trigger, poll GetImageBuffer tối đa max_poll lần
          - Mỗi lần lấy được frame thì kiểm tra nFrameNum
          - Nếu nFrameNum <= _last_frame_num → frame cũ, giải phóng và poll tiếp
          - Chỉ trả về khi nFrameNum > _last_frame_num (frame mới đúng)

        Không có sleep() trong critical path.
        """
        for attempt in range(max_retries):
            try:
                # ── Bước 1: Gửi trigger ─────────────────
                ret = self.obj_cam.MV_CC_SetCommandValue("TriggerSoftware")
                if ret != 0:
                    print("Execute software trigger fail! ret[0x%x] (attempt %d/%d)"
                          % (ret, attempt + 1, max_retries))
                    # time.sleep(0.015)
                    continue

                # ── Bước 2: Lấy frame MỚI ───────────────
                img = self._retrieve_new_frame(self._retrieve_timeout_ms)
                if img is not None:
                    return img

                print("Trigger OK nhưng không lấy được frame mới (attempt %d/%d)"
                      % (attempt + 1, max_retries))

            except Exception as e:
                print(f"Trigger Error (attempt {attempt + 1}/{max_retries}): {e}")
                # time.sleep(0.015)

        print("Trigger thất bại sau %d lần thử" % max_retries)
        return None

    # ─────────────────────────────────────────────
    # LẤY FRAME MỚI — bỏ qua frame cũ trong queue
    # ─────────────────────────────────────────────
    def _retrieve_new_frame(self, timeout_ms, max_poll=5):
        """
        Poll GetImageBuffer tối đa max_poll lần.
        Mỗi lần lấy được frame thì verify nFrameNum:
          - nFrameNum > _last_frame_num  → frame mới đúng, trả về
          - nFrameNum <= _last_frame_num → frame cũ còn sót, giải phóng, poll tiếp

        Tại sao max_poll=5:
          Trường hợp xấu nhất: queue chứa 1-2 frame cũ sót lại.
          5 lần poll là quá đủ để bỏ qua hết frame cũ và lấy được frame mới.
          Mỗi poll tốn đúng = thời gian frame thực sự về (không busy-wait).
        """
        stOutFrame = MV_FRAME_OUT()

        for poll in range(max_poll):
            memset(byref(stOutFrame), 0, sizeof(stOutFrame))

            with self.buf_lock:
                ret = self.obj_cam.MV_CC_GetImageBuffer(stOutFrame, 50)
               

                if ret != 0 or stOutFrame.pBufAddr is None:
                    # Không có frame nào trong timeout → thất bại luôn, không poll tiếp
                    # (nếu frame chưa về trong timeout_ms = exposure+10ms thì có vấn đề phần cứng)
                    print("Get image buffer fail! ret[0x%x] (poll %d/%d)"
                          % (ret, poll + 1, max_poll))
                    return None

                # current_frame_num = stOutFrame.stFrameInfo.nFrameNum

                # if current_frame_num > self._last_frame_num:
                try:
                    img = self._convert_frame(stOutFrame)
                    if img is not None:
                        # self._last_frame_num = current_frame_num
                        return img
                    else:
                        return None
                finally:
                    self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)

                # else:
                #     # Frame cũ còn sót trong queue (nFrameNum <= last)
                #     # Giải phóng và poll tiếp để lấy frame của trigger hiện tại
                #     print(f"[WARN] Frame cũ phát hiện: frame_num={current_frame_num} "
                #           f"<= last={self._last_frame_num}, bỏ qua, poll tiếp ({poll+1}/{max_poll})")
                #     self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
                #     # Không sleep — frame mới có thể đã vào queue ngay sau frame cũ

        print(f"Không lấy được frame mới sau {max_poll} lần poll")
        return None

    # ─────────────────────────────────────────────
    # CONVERT PIXEL FORMAT → NUMPY ARRAY
    # ─────────────────────────────────────────────
    # def _convert_frame(self, stOutFrame):
    #     # pixel_type = stOutFrame.stFrameInfo.enPixelType
    #     stEnumValue = MVCC_ENUMVALUE()
    #     memset(byref(stEnumValue),0,sizeof(MVCC_ENUMVALUE))
    #     self.obj_cam.MV_CC_GetEnumValue("PixelFormat",stEnumValue)
    #     pixel_type = stEnumValue.nCurValue
    #     color_mode = self.IsImageColor(pixel_type)
    #     print('pixel_type',hex(pixel_type))
    #     stConvertParam = MV_CC_PIXEL_CONVERT_PARAM()
    #     memset(byref(stConvertParam), 0, sizeof(stConvertParam))

    #     if color_mode == 'mono':
    #         stConvertParam.enDstPixelType = PixelType_Gvsp_Mono8
    #         nConvertSize = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight + 2048
    #     elif color_mode == 'color':
    #         stConvertParam.enDstPixelType = PixelType_Gvsp_BGR8_Packed
    #         nConvertSize = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight * 3 + 2048
    #     else:
    #         print("Pixel type not supported!")
    #         return None

    #     stConvertParam.nWidth         = stOutFrame.stFrameInfo.nWidth
    #     stConvertParam.nHeight        = stOutFrame.stFrameInfo.nHeight
    #     stConvertParam.pSrcData       = cast(stOutFrame.pBufAddr, POINTER(c_ubyte))
    #     stConvertParam.nSrcDataLen    = stConvertParam.nWidth * stConvertParam.nHeight
    #     stConvertParam.enSrcPixelType = pixel_type
    #     # nConvertSize = 2592*2048*3+2048
    #     stConvertParam.pDstBuffer     = (c_ubyte * nConvertSize)()
    #     stConvertParam.nDstBufferSize = nConvertSize
    #     print(hex(pixel_type),stConvertParam.nWidth,stConvertParam.nHeight)
    #     ret = self.obj_cam.MV_CC_ConvertPixelType(stConvertParam)
    #     if ret != 0:
    #         print("Convert pixel fail! ret[0x%x]" % ret)
    #         return None

    #     img_buff = (c_ubyte * stConvertParam.nDstLen)()
    #     ctypes.memmove(byref(img_buff), stConvertParam.pDstBuffer, stConvertParam.nDstLen)
    #     img = np.frombuffer(img_buff, dtype=np.uint8, count=stConvertParam.nDstLen)

    #     if color_mode == 'color':
    #         img = img.reshape(stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nWidth, 3)
    #     else:
    #         img = img.reshape(stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nWidth)

    #     return img
    def _convert_frame(self, stOutFrame):
        import ctypes
        import cv2
        import numpy as np
        
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

        # 2. Xử lý ảnh tuỳ theo Pixel Format
        if pixel_type == 0x01080008:
            # BayerGB8 (Thường dùng ở dòng VCS 60fps)
            img = cv2.cvtColor(raw_img, cv2.COLOR_BayerGB2BGR)
            img = cv2.flip(img, 0)
            return img

        elif pixel_type == 0x0108000b:
            # BayerBG8 (Thường dùng ở dòng 80fps)
            img = cv2.cvtColor(raw_img, cv2.COLOR_BayerRG2BGR)
            return img

        elif pixel_type == 0x01080001:
            # Mono8 (Trắng Đen)
            return raw_img

        elif pixel_type == 0x01080009:
            # BayerRG8
            img = cv2.cvtColor(raw_img, cv2.COLOR_BayerBG2BGR)
            return img

        elif pixel_type == 0x0108000a:
            # BayerGR8
            img = cv2.cvtColor(raw_img, cv2.COLOR_BayerGR2BGR)
            return img

        else:
            print(f"Chưa hỗ trợ định dạng PixelFormat này: {hex(pixel_type)}")
            # Thử convert dự phòng tránh crash
            try:
                return cv2.cvtColor(raw_img, cv2.COLOR_BayerBG2BGR)
            except:
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



#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
