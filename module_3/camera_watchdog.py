# -*- coding: utf-8 -*-
"""
module_3/camera_watchdog.py
===========================
Tiến trình giám sát và khôi phục kết nối Camera tự động (Watchdog & Auto-Reconnect):
- Liên tục giám sát trạng thái kết nối phần cứng của từng Camera đang hoạt động.
- Phát hiện kịp thời sự cố mất kết nối (rút cáp Ethernet/USB, mất nguồn camera, lỗi switch).
- Gửi tín hiệu báo lỗi cho PLC ngay lập tức qua set_camera_continuous_status(status=False).
- Tự động thăm dò và kết nối lại camera trong nền (thử lại định kỳ mà không làm treo UI).
- Khi khôi phục kết nối:
  + Mở lại thiết bị camera và khởi động lại luồng lấy ảnh (grabbing).
  + Cập nhật lại đối tượng camera mới vào built_in_objects, built_in_modes, UI.
  + Gửi lại tín hiệu sẵn sàng (status=True) cho PLC.
  + Phục hồi hoàn toàn khả năng chụp ảnh tự động mà không cần khởi động lại phần mềm!
"""

import time
import threading
from PyQt5 import QtCore
from app_logger.app_logger import get_logger as _get_logger
from module_3.camera_alert_ui import CameraWatchdogSignals

_log = _get_logger('module_3.camera_watchdog')


def is_camera_alive(device, conn_mode: str = 'USB', ip_address: str = None) -> bool:
    """
    Kiểm tra xem thiết bị camera còn kết nối và hoạt động bình thường hay không.
    Hỗ trợ Hikvision (MVS) và Basler (Pypylon).
    """
    if device is None:
        return False

    # 1. Gọi is_connected_class hoặc is_connected nếu lớp bọc hỗ trợ
    if hasattr(device, 'is_connected_class'):
        try:
            return bool(device.is_connected_class())
        except Exception:
            pass

    if hasattr(device, 'is_connected'):
        try:
            return bool(device.is_connected())
        except Exception:
            pass

    # 2. Kiểm tra trực tiếp SDK Hikvision (MV_CC_IsDeviceConnected hoặc b_open_device)
    try:
        op = getattr(device, 'obj_cam_operation', None)
        if op is not None:
            cam = getattr(op, 'obj_cam', None) or getattr(op, 'cam', None)
            if cam is not None and getattr(cam, 'handle', None) is not None:
                if hasattr(cam, 'MV_CC_IsDeviceConnected'):
                    return bool(cam.MV_CC_IsDeviceConnected())
            if getattr(op, 'b_open_device', False):
                return True

        cam = getattr(device, 'cam', None)
        if cam is not None and getattr(cam, 'handle', None) is not None:
            if hasattr(cam, 'MV_CC_IsDeviceConnected'):
                return bool(cam.MV_CC_IsDeviceConnected())
    except Exception:
        pass

    # 3. Kiểm tra trực tiếp SDK Basler (pypylon InstantCamera)
    try:
        b_cam = getattr(device, 'camera', None)
        if b_cam is not None:
            if hasattr(b_cam, 'IsCameraDeviceRemoved') and b_cam.IsCameraDeviceRemoved():
                return False
            if hasattr(b_cam, 'IsOpen'):
                return bool(b_cam.IsOpen())
            return True
    except Exception:
        pass

    return True


def cleanup_camera_device(device):
    """Đóng và giải phóng tài nguyên thiết bị camera cũ."""
    if device is None:
        return
    try:
        if hasattr(device, 'stop_grabbing_array_class'):
            device.stop_grabbing_array_class()
    except Exception:
        pass
    try:
        if hasattr(device, 'close_device_class'):
            device.close_device_class()
    except Exception:
        pass
    try:
        # Hik MVS: Đóng và hủy handle C ctypes nếu còn tồn tại
        cam = getattr(device, 'cam', None)
        if cam is None and hasattr(device, 'obj_cam_operation'):
            cam = getattr(device.obj_cam_operation, 'cam', None)
        if cam is not None and getattr(cam, 'handle', None) is not None:
            if hasattr(cam, 'MV_CC_CloseDevice'):
                cam.MV_CC_CloseDevice()
            if hasattr(cam, 'MV_CC_DestroyHandle'):
                cam.MV_CC_DestroyHandle()
            cam.handle = None
    except Exception:
        pass
    try:
        # Basler Pypylon
        b_cam = getattr(device, 'camera', None)
        if b_cam is not None:
            if hasattr(b_cam, 'StopGrabbing'):
                b_cam.StopGrabbing()
            if hasattr(b_cam, 'Close'):
                b_cam.Close()
            if hasattr(b_cam, 'DestroyDevice'):
                b_cam.DestroyDevice()
            device.camera = None
    except Exception:
        pass


class CameraWatchdogThread(QtCore.QThread):
    """
    Luồng giám sát trạng thái kết nối của tất cả các Camera liên tục.
    Tự động kích hoạt lỗi PLC khi mất kết nối và tự động kết nối lại.
    """
    def __init__(self, manager_instance, check_interval_ms: int = 1000):
        super().__init__()
        self.manager = manager_instance
        self.check_interval_ms = check_interval_ms
        self.running = True
        self.signals = getattr(self.manager, 'camera_signals', None) or CameraWatchdogSignals()
        self.camera_states = {}  # {cam_name: {'is_connected': bool, 'consecutive_errors': int, 'reconnect_attempts': int}}
        self._lock = threading.RLock()

    def run(self):
        _log.info("[CameraWatchdog] Bắt đầu tiến trình giám sát kết nối Camera...")

        while self.running:
            try:
                camera_configs = getattr(self.manager, 'camera_configs', {})
                if not camera_configs:
                    self.msleep(self.check_interval_ms)
                    continue

                for cam_name, cam_cfg in list(camera_configs.items()):
                    if not self.running:
                        break

                    key = cam_cfg.get('key', f'built-in-camera-{cam_name}')

                    # Khởi tạo state nếu chưa có
                    with self._lock:
                        is_new_cam = (cam_name not in self.camera_states)
                        if is_new_cam:
                            current_dev = self.manager.built_in_objects.get(key, {}).get('device')
                            is_conn = is_camera_alive(current_dev, cam_cfg.get('conn_mode', 'USB'), cam_cfg.get('ip_address'))
                            self.camera_states[cam_name] = {
                                'is_connected': is_conn,
                                'consecutive_errors': 0 if is_conn else 2,
                                'reconnect_attempts': 0,
                                'is_reconnecting': False
                            }

                        state = self.camera_states[cam_name]

                    # Trường hợp camera thực sự chưa được kết nối ngay từ khi khởi động phần mềm (không có device)
                    if is_new_cam and not state['is_connected'] and (current_dev is None):
                        _log.warning(
                            "[CameraWatchdog] ⚠️ Camera %s (%s - %s) không có kết nối ngay từ đầu! Kích hoạt hiển thị cảnh báo...",
                            cam_name, cam_cfg.get('conn_mode'), cam_cfg.get('identifier')
                        )
                        self._trigger_disconnect(cam_name, cam_cfg)

                    # 1. Nếu camera đang ở trạng thái KẾT NỐI: kiểm tra tính khả dụng
                    if state['is_connected']:
                        current_dev = self.manager.built_in_objects.get(key, {}).get('device')
                        alive = is_camera_alive(current_dev, cam_cfg.get('conn_mode', 'USB'), cam_cfg.get('ip_address'))

                        if not alive:
                            state['consecutive_errors'] += 1
                        else:
                            state['consecutive_errors'] = 0

                        # Nếu phát hiện lỗi: 2 lần kiểm tra liên tiếp (hoặc nếu current_dev đã là None)
                        if (current_dev is None) or (state['consecutive_errors'] >= 2):
                            _log.warning(
                                "[CameraWatchdog] ⚠️ Phát hiện MẤT KẾT NỐI tới Camera %s (%s - %s)! Lập tức gửi tín hiệu lỗi cho PLC...",
                                cam_name, cam_cfg.get('conn_mode'), cam_cfg.get('identifier')
                            )
                            self._trigger_disconnect(cam_name, cam_cfg)

                    # 2. Nếu camera đang ở trạng thái MẤT KẾT NỐI: tự động thử kết nối lại
                    else:
                        self._attempt_reconnect(cam_name, cam_cfg)

            except Exception as e:
                _log.debug("[CameraWatchdog] Ngoại lệ trong vòng lặp watchdog: %s", e)

            self.msleep(self.check_interval_ms)

        _log.info("[CameraWatchdog] Dừng tiến trình giám sát kết nối Camera.")

    def _trigger_disconnect(self, cam_name: str, cam_cfg: dict):
        """Xử lý ngắt kết nối: OFF tín hiệu PLC và chuẩn bị thử kết nối lại."""
        with self._lock:
            state = self.camera_states.get(cam_name)
            if state:
                state['is_connected'] = False
                state['consecutive_errors'] = 0
                state['reconnect_attempts'] = 0

        # Lập tức OFF tín hiệu PLC
        plc_signals = cam_cfg.get('plc_signals')
        if not plc_signals and hasattr(self.manager, 'get_camera_program_signals'):
            plc_signals = self.manager.get_camera_program_signals(cam_name, cam_cfg.get('camera_id'))
            cam_cfg['plc_signals'] = plc_signals

        if plc_signals and hasattr(self.manager, 'set_camera_continuous_status'):
            self.manager.set_camera_continuous_status(cam_name, plc_signals, status=False)

        # Dọn dẹp device cũ
        key = cam_cfg.get('key', f'built-in-camera-{cam_name}')
        old_dev = self.manager.built_in_objects.get(key, {}).get('device')
        cleanup_camera_device(old_dev)

        # Phát tín hiệu ra UI cảnh báo
        device_type = cam_cfg.get('device_type', 'Camera')
        identifier = cam_cfg.get('identifier', 'N/A')
        conn_mode = cam_cfg.get('conn_mode', 'N/A')
        attempt = state.get('reconnect_attempts', 1) if state else 1

        if hasattr(self.signals, 'camera_lost'):
            self.signals.camera_lost.emit(
                str(cam_name), str(device_type), str(identifier), str(conn_mode), int(attempt)
            )
        if hasattr(self.signals, 'camera_disconnected'):
            self.signals.camera_disconnected.emit(cam_name)

    def _attempt_reconnect(self, cam_name: str, cam_cfg: dict):
        """Thử kết nối lại camera trong nền."""
        with self._lock:
            state = self.camera_states.get(cam_name)
            if not state or state['is_connected']:
                return
            state['reconnect_attempts'] += 1
            attempt = state['reconnect_attempts']

        if hasattr(self.signals, 'reconnect_attempt'):
            self.signals.reconnect_attempt.emit(str(cam_name), int(attempt))
        if hasattr(self.signals, 'camera_reconnecting'):
            self.signals.camera_reconnecting.emit(cam_name, attempt)

        # Đảm bảo Alert UI hiển thị nếu đang ngắt kết nối (trừ khi người dùng chủ động bấm Đóng để kiểm tra cài đặt)
        overlay = getattr(self.manager, '_camera_alert_overlay', None)
        user_dismissed = getattr(overlay, 'user_dismissed', False)
        if (overlay is None or not overlay.isVisible()) and not user_dismissed:
            dev_t = cam_cfg.get('device_type', 'Camera')
            ident = cam_cfg.get('identifier', 'N/A')
            c_mode = cam_cfg.get('conn_mode', 'N/A')
            if hasattr(self.signals, 'camera_lost'):
                self.signals.camera_lost.emit(
                    str(cam_name), str(dev_t), str(ident), str(c_mode), int(attempt)
                )

        device_type = cam_cfg.get('device_type')
        identifier = cam_cfg.get('identifier')
        conn_mode = cam_cfg.get('conn_mode')
        device_launch = cam_cfg.get('device_launch')

        if not device_launch:
            from module_3.main_core import DICT_DEVICE_AUTO
            device_launch = DICT_DEVICE_AUTO.get(device_type)
            cam_cfg['device_launch'] = device_launch

        if not device_launch or not identifier:
            return

        try:
            _log.info("[CameraWatchdog] [⚠️ Camera %s] Đang tự động kết nối lại (Lần %d) [%s - %s]...",
                      cam_name, attempt, conn_mode, identifier)
            new_device = device_launch(identifier, conn_mode)
            new_device.enum_devices_class()
            new_device.open_device_camera_class()
            new_device.start_grabbing_array_class()

            # Kiểm tra xem camera đã thực sự kết nối và sẵn sàng chưa
            if not is_camera_alive(new_device, conn_mode, cam_cfg.get('ip_address')):
                cleanup_camera_device(new_device)
                return

            # Cập nhật thông tin Model Name nếu có
            model_name = getattr(new_device, 'chModelName', None) or getattr(new_device, 'PartNo', None)
            if not model_name and hasattr(new_device, 'dict_device'):
                try:
                    for dev_entries in new_device.dict_device.values():
                        if dev_entries and isinstance(dev_entries, list) and 'model_name' in dev_entries[0]:
                            model_name = dev_entries[0]['model_name']
                            break
                except Exception:
                    pass
            if model_name:
                cam_cfg['PartNo'] = str(model_name).strip()
                self.manager.PartNo = str(model_name).strip()

            # Khôi phục đối tượng device vào built_in_objects và built_in_modes
            key = cam_cfg.get('key', f'built-in-camera-{cam_name}')
            if key in self.manager.built_in_objects:
                self.manager.built_in_objects[key]['device'] = new_device
            if key in self.manager.built_in_modes:
                self.manager.built_in_modes[key]['device'] = new_device
            self.manager.device = new_device

            # Cập nhật lại UI Camera Device tab nếu có
            dev_ui = cam_cfg.get('device_tab_ui')
            if dev_ui:
                try:
                    dev_ui.label_dev_name.setText(str(device_type))
                    dev_ui.label_PartNo.setText(str(cam_cfg.get('PartNo', '#N/A')))
                    dev_ui.label_SerialNo.setText(str(identifier))
                    dev_ui.label_Port.setText(str(conn_mode))
                    dev_ui.label_IP.setText(str(cam_cfg.get('ip_address', '#N/A')))
                except Exception:
                    pass

            # Khôi phục trạng thái sẵn sàng cho PLC
            plc_signals = cam_cfg.get('plc_signals')
            if not plc_signals and hasattr(self.manager, 'get_camera_program_signals'):
                plc_signals = self.manager.get_camera_program_signals(cam_name, cam_cfg.get('camera_id'))
                cam_cfg['plc_signals'] = plc_signals

            if plc_signals and hasattr(self.manager, 'set_camera_continuous_status'):
                self.manager.set_camera_continuous_status(cam_name, plc_signals, status=True)

            with self._lock:
                state['is_connected'] = True
                state['consecutive_errors'] = 0
                state['reconnect_attempts'] = 0

            _log.info("[CameraWatchdog] ✅ Khôi phục kết nối thành công tới Camera %s (%s - %s) sau %d lần thử!",
                      cam_name, conn_mode, identifier, attempt)
            if hasattr(self.signals, 'camera_restored'):
                self.signals.camera_restored.emit(
                    str(cam_name), str(device_type), str(identifier), str(conn_mode)
                )
            if hasattr(self.signals, 'camera_reconnected'):
                self.signals.camera_reconnected.emit(cam_name, new_device)

        except Exception as e:
            _log.debug("[CameraWatchdog] [Camera %s] Lần thử kết nối lại %d thất bại: %s", cam_name, attempt, e)
            # Tiếp tục duy trì trạng thái OFF cho PLC
            plc_signals = cam_cfg.get('plc_signals')
            if plc_signals and hasattr(self.manager, 'set_camera_continuous_status'):
                self.manager.set_camera_continuous_status(cam_name, plc_signals, status=False)

    def notify_camera_disconnected(self, camera_name: str):
        """Được gọi từ bên ngoài (ví dụ take_image bị lỗi) để lập tức đánh dấu mất kết nối."""
        cam_name = str(camera_name).replace('built-in-camera-', '').replace('built-in-', '').replace('camera-', '')
        camera_configs = getattr(self.manager, 'camera_configs', {})
        cam_cfg = camera_configs.get(cam_name, {})
        _log.warning("[CameraWatchdog] Nhận thông báo mất kết nối trực tiếp cho Camera %s", cam_name)
        self._trigger_disconnect(cam_name, cam_cfg)

    def notify_camera_connected(self, camera_name: str):
        """Được gọi từ bên ngoài để xác nhận camera đã kết nối lại và chụp thành công."""
        cam_name = str(camera_name).replace('built-in-camera-', '').replace('built-in-', '').replace('camera-', '')
        with self._lock:
            state = self.camera_states.get(cam_name)
            if state:
                state['is_connected'] = True
                state['consecutive_errors'] = 0
                state['reconnect_attempts'] = 0
            else:
                self.camera_states[cam_name] = {
                    'is_connected': True,
                    'consecutive_errors': 0,
                    'reconnect_attempts': 0,
                    'is_reconnecting': False
                }

    def stop(self):
        """Dừng tiến trình giám sát an toàn."""
        self.running = False
        self.quit()
        self.wait(2000)

