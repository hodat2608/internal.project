import sys,os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread, QMetaObject, Qt, Q_ARG
from core.CamOperation_class_new import *
from core.MvCameraControl_class import *
from core.MvErrorDefine_const import *
from core.CameraParams_header import *
from app_logger.app_logger import get_logger as _get_logger
_log = _get_logger('module_4.hik_vision.core.core_plus_auto')
import ctypes,cv2

class Initial_Device_Auto(QObject):
    def __init__(self, port_gige, port):
        super().__init__()
        self.deviceList = MV_CC_DEVICE_INFO_LIST()
        self.cam = MvCamera()
        self.obj_cam_operation = None
        self.port_GigE = port_gige          # Đóng vai trò là ID định danh cần mở (IP của camera GigE hoặc Serial của USB)
        self.port_connect = port            # Mã cổng quản lý nội bộ của ứng dụng của bạn
        self.user_set_selector = 0
        self.dict_device = {}

    # Quét mạng và các cổng kết nối vật lý để lập danh sách camera sẵn có
    def enum_devices(self):
        ret = MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE | MV_USB_DEVICE, self.deviceList)
        devList = []
        self.dict_device.clear() # Làm sạch từ điển lưu trữ trước khi quét lại
        
        for index in range(0, self.deviceList.nDeviceNum):
            mvcc_dev_info = ctypes.cast(self.deviceList.pDeviceInfo[index], ctypes.POINTER(MV_CC_DEVICE_INFO)).contents
            
            # Xử lý nếu thiết bị là loại Camera cáp mạng GigE
            if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE:
                chModelName = ''.join(chr(b) for b in mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName if b != 0)
                nip = mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp
                ip_str = '.'.join(str((nip >> offset) & 0xFF) for offset in [24, 16, 8, 0])
                
                devList.append(f"[{index}]%{self.port_connect}%{chModelName}%{ip_str}")
                self.dict_device[ip_str] = [{
                    'index': index,
                    'PORT': self.port_connect
                }]
                
            # Xử lý nếu thiết bị là loại Camera cáp USB 3.0
            elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
                chModelName = ''.join(chr(b) for b in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName if b != 0)
                serial = ''.join(chr(b) for b in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber if b != 0)
                
                devList.append(f'[{index}]%{self.port_connect}%{chModelName}%{serial}')
                self.dict_device[serial] = [{
                    'index': index,
                    'PORT': self.port_connect
                }]
        return devList

    # Khởi tạo tiến trình kết nối mở camera dựa trên thông tin định danh IP hoặc Serial nhận vào
    def open_device_camera(self):
        if self.port_GigE not in self.dict_device:
            print(f"[-] Lỗi: Không tìm thấy thiết bị nào khớp với định danh '{self.port_GigE}' trong hệ thống!")
            return False

        nSelCamIndex = self.dict_device[self.port_GigE][0]['index']
        self.obj_cam_operation = CameraOperation(self.cam, self.deviceList, int(nSelCamIndex))
        
        ret = self.obj_cam_operation.Open_device()
        if ret != 0:
            strError = "[-] Open device failed ret:" + hex(ret)
            print(f'[-] Open camera HIK Failed, Please try again! Error: {strError}')
            return False
        else:
            print(f'[+] Open camera HIK successfully from Port/Key: {self.port_GigE}')
            return True

    # Kích hoạt chế độ lắng nghe Trigger mạng
    def start_grabbing_array(self):
        if self.obj_cam_operation is None:
            print('[-] Khởi tạo Start Grabbing thất bại: Camera chưa được mở.')
            return
        
        ret = self.obj_cam_operation.grabbing()
        if ret != 0:
            print(f'[-] Start Grabbing MVS DRIVER has been Failed! Mã lỗi: {hex(ret)}')
            return
        print('[+] Start Grabbing MVS DRIVER Successfully!')
    
    # Hủy kích hoạt chế độ lắng nghe dữ liệu
    def stop_grabbing_array(self):
        if self.obj_cam_operation is None:
            return
            
        ret = self.obj_cam_operation.not_grabbing()
        if ret != 0:
            print(f'[-] Stop Grabbing MVS DRIVER has been Failed! Mã lỗi: {hex(ret)}')
            return
        print('[+] Stop Grabbing MVS DRIVER Successfully!')

    def GetImgArayBuffer(self):
        if self.obj_cam_operation is None:
            print('[-] Thất bại: CameraOperation chưa được khởi tạo.')
            return None
        img = self.obj_cam_operation.Trigger_Camera_Software(max_retries=5)
        return img
    
    def flush_buffer_ne(self):
        self.obj_cam_operation.flush_buffer()

    def close_device(self):
        self.obj_cam_operation.Close_device()
        _log.info('Close device camera HIK successfully')

    def set_user_selector(self,user_index=None):
        ret = self.obj_cam_operation.load_params_user_selector(user_set_index = user_index if user_index else self.user_set_selector) 
        self.obj_cam_operation.configure_software_trigger()
        _log.info('Set user selector HIK successfully')
        return ret


# def main():
#     # 1. Khởi tạo đối tượng quản lý với IP và Port của bạn
#     ip_camera = "192.168.4.3"
#     port_type = "GigE"
    
#     print(f"[*] Đang khởi tạo bộ quản lý Camera HIK (IP: {ip_camera})...")
#     camera_manager = Initial_Device_Auto(port_gige=ip_camera, port=port_type)
    
#     # 2. Quét danh sách thiết bị trong mạng
#     print("[*] Đang quét các camera kết nối hệ thống...")
#     camera_manager.enum_devices()
    
#     # 3. Kiểm tra xem IP camera có tồn tại trong danh sách quét được không
#     if ip_camera not in camera_manager.dict_device:
#         print(f"[-] Thất bại: Không tìm thấy camera nào có IP {ip_camera} trên đường truyền!")
#         print("[*] Vui lòng kiểm tra lại dây cáp mạng hoặc cấu hình IP tĩnh của máy tính.")
#         return

#     # 4. Mở kết nối tới Camera
#     print(f"[*] Đang tiến hành kết nối tới Camera {ip_camera}...")
#     if not camera_manager.open_device_camera():
#         print("[-] Không thể mở thiết bị.")
#         return
        
#     # try:
#         # 5. Bắt đầu truyền luồng dữ liệu (Cấu hình tự động sang chế độ Trigger Software)
#     camera_manager.start_grabbing_array()
#     while True: 
#         print("\n=== HỆ THỐNG SẴN SÀNG ===")
#         print("Nhấn phím [ENTER] trên bàn phím để gửi lệnh Trigger Software chụp ảnh...")
#         input()  # Chờ người dùng nhấn nút Enter trên terminal
        
#         # 6. Gửi lệnh kích hoạt phần mềm và nhận về mảng ảnh Numpy Array
#         print("[*] Đang gửi tín hiệu chụp ảnh...")
#         frame = camera_manager.GetImgArayBuffer()
        
#         if frame is not None:
#             # Lưu hình ảnh xuống máy tính bằng OpenCV
#             filename = f"capture_{int(time.time())}.jpg"
#             cv2.imwrite(filename, frame)
#             print(f"[+] Đã chụp và lưu ảnh thành công: {filename}")
            
#             # Hiển thị cửa sổ xem trước (Preview) ảnh vừa chụp
#             print("[*] Đang hiển thị ảnh. Nhấn phím bất kỳ trên cửa sổ ảnh để thoát...")
#             cv2.imshow("HIK Robot - Captured Image", cv2.resize(frame, (800, 600)))
#             cv2.waitKey(0)
#             cv2.destroyAllWindows()
#         else:
#             print("[-] Lỗi: Bộ đệm không trả về dữ liệu hình ảnh (Timeout).")
       
# if __name__ == "__main__":
#     main()
