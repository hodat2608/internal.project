
"""
plc_handler_fixed.py  —  v3  (stability + max speed)
=====================================================
Fix list (so với bản gốc):

  FIX-1   Thread-safe counter per-key          (_increment_counter / _reset_counter)
  FIX-2   Per-key processing guard             (_try_acquire_key / _release_key)
  FIX-3   TOCTOU: write-OFF trước khi submit
  FIX-4   Data race _active_triggers/mode_kick (_mode_lock + snapshot)
  FIX-5   QMessageBox từ worker thread         (show_warning signal)
  FIX-6   return → continue trong _set_mode_reg_process
  FIX-7   list_size dùng chung → dict per key  (_label_sizes)
  FIX-8   Executor không shutdown khi stop
  FIX-9   set_index_user: device có thể None
  FIX-10  QMessageBox trong set_index_user

Speed optimisation list:

  OPT-1   Adaptive sleep thay polling cố định 10ms
            → giảm CPU idle, phản hồi trigger nhanh hơn
  OPT-2   image.copy() chỉ khi thực sự cần thiết
            → tránh copy thừa khi process_image_func không ghi đè
  OPT-3   as_completed thay map() để nhận kết quả ngay khi từng model xong
            → không phải chờ model chậm nhất
  OPT-4   RWLock (ReadWriteLock) cho dict_signal_complete
            → nhiều reader song song, không block nhau trong hot path
  OPT-5   Pre-allocate QImage buffer, tránh tạo lại mỗi frame
            → giảm GC pressure trên main thread
  OPT-6   np.ascontiguousarray thay copy() khi ảnh đã contiguous
            → tránh copy toàn bộ bộ nhớ ảnh không cần thiết
"""

from Administrator import hardware_key
from absl.flags import _flagvalues
from Administrator import scripts_editor
from app_logger.app_logger import get_logger as _get_logger, open_log_window
_log = _get_logger('module_3.main_core')

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSpinBox, QTableWidget,
    QTableWidgetItem, QComboBox
)
from PyQt5.QtWidgets import QMessageBox
import glob, random
from PyQt5 import QtCore, QtGui, QtWidgets, QtMultimedia
from PyQt5.QtCore import QTimer
from module_3.layout_option_model import Ui_MainWindow  as uicmain
from module_3.handle_option_models import Process_Model 
from module_3.signal_transmission import Ui_MainWindow as AutomationInterface
from module_3.signal_process import DataProcessSignal as signals 
from module_3.config_status_logger import PLCConfigStatusLogger 
from module_4.hik_vision.pyuic5.hik_mvs_setting_device_list import Ui_MainWindow as Camera_Device
from module_4.hik_vision.core.core_plus_manual import Initial_Device as Initial_Device_MVS_Manual
from module_4.hik_vision.core.core_plus_auto import Initial_Device_Auto as Initial_Device_MVS_Auto
from module_4.hik_vision.public_layer_class_auto import Layer_Initial_Device_Auto as hik_vision_auto
from module_4.hik_vision.public_layer_class_manual import Layer_Initial_Device_Manual as hik_vision_manual
from module_4.basler_pylon.public_layer_class_auto import Layer_Initial_Device_Auto as basler_vision_auto
from module_4.basler_pylon.public_layer_class_manual import Layer_Initial_Device_Manual as basler_vision_manual
from module_3.handle_option_models import Process_Camera_Device
from module_3.tab_detect_single import Ui_MainWindow as Single_Tab_Detect
from module_6.mitsubishi.initial import SocketClient as Mitsubishi_Socket_Client
from module_6.keyence.initial import KeyenceClient as Keyence_Socket_Client
from module_6.omron.initial import OmronClient as Omron_Socket_Client
import cv2,time,numpy as np
from functools import partial
# from module_3.layout_display_image import *
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from module_3.mirror_test import KiemGuong
from module_3.mirror_process import Process_Mirror_Device
from module_3.mirror_tab import Ui_MainWindow as Mirror_Tab_Detect
from module_3.auto_logging import Ui_MainWindow as Auto_Logging
from module_3.auto_logging_process import AutoLoggingProcess
from module_3.parent_interface import Ui_MainWindow as Ui_MainWindow_mother
from module_3.child_interface import Ui_MainWindow as Ui_MainWindow_child

DICT_DEVICE_MANUAL = {
   'HIK - MVS' : hik_vision_manual,
   'Basler - Pypylon' : basler_vision_manual
}

DICT_DEVICE_AUTO = {
   'HIK - MVS' : hik_vision_auto,
   'Basler - Pypylon' : basler_vision_auto
}

PLC_COLLECT = {
   'KEYENCE' : Keyence_Socket_Client,
   'OMRON' : Omron_Socket_Client,
   'MITSUBISHI': Mitsubishi_Socket_Client
}

import os
from module_1.root_path import get_trigger_file_path


from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import queue
import time,threading
import traceback
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread, QMetaObject, Qt, Q_ARG

#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
# ---------------------------------------------------------------------------
# ReadWriteLock
# ---------------------------------------------------------------------------

class ReadWriteLock:
    """Cho phép nhiều reader đồng thời, writer độc quyền."""

    def __init__(self):
        self._read_ready = threading.Condition(threading.Lock())
        self._readers = 0

    def acquire_read(self):
        with self._read_ready:
            self._readers += 1

    def release_read(self):
        with self._read_ready:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()

    def acquire_write(self):
        self._read_ready.acquire()
        while self._readers > 0:
            self._read_ready.wait()

    def release_write(self):
        self._read_ready.release()

    class _ReadCtx:
        def __init__(self, rw): self._rw = rw
        def __enter__(self):    self._rw.acquire_read();  return self
        def __exit__(self, *_): self._rw.release_read()

    class _WriteCtx:
        def __init__(self, rw): self._rw = rw
        def __enter__(self):    self._rw.acquire_write(); return self
        def __exit__(self, *_): self._rw.release_write()

    def read(self):  return self._ReadCtx(self)
    def write(self): return self._WriteCtx(self)


# ---------------------------------------------------------------------------
# UISignals
# ---------------------------------------------------------------------------

class UISignals(QObject):
    update_display   = pyqtSignal(list, str)
    show_warning     = pyqtSignal(str, str)
    set_user_index   = pyqtSignal(object, object, str, str)
    load_mode_params = pyqtSignal(str)


# ---------------------------------------------------------------------------
# PLCWorkerModeAuto1
# ---------------------------------------------------------------------------

class PLCWorkerModeAuto1(QThread):
    MIN_SLEEP_MS = 1
    MAX_SLEEP_MS = 5
    STEP_MS      = 1

    def __init__(self, plc_handler):
        super().__init__()
        self.plc_handler = plc_handler
        self.running     = True

    def run(self):
        _log.info("[PLCWorkerModeAuto1] Running in thread: %s", threading.current_thread().name)
        sleep_ms = self.MAX_SLEEP_MS

        while self.running:
            try:
                triggered = self.plc_handler._run_trigger_from_activated_mode()
                self.plc_handler._activate_mode()
                self.plc_handler.reset_counter_from_plc()
            except Exception:
                # Worker loop KHÔNG được chết — log rồi tiếp tục
                _log.exception("[PLCWorkerModeAuto1] Unhandled exception in main loop")

            if triggered:
                sleep_ms = self.MIN_SLEEP_MS
            else:
                sleep_ms = min(sleep_ms + self.STEP_MS, self.MAX_SLEEP_MS)

            self.msleep(sleep_ms)


# ---------------------------------------------------------------------------
# PLCWorkerAutoLogging
# ---------------------------------------------------------------------------

class PLCWorkerAutoLogging(QThread):
    MIN_SLEEP_MS = 10
    MAX_SLEEP_MS = 50

    def __init__(self, plc_handler):
        super().__init__()
        self.plc_handler = plc_handler
        self.running     = True

    def run(self):
        _log.info("[PLCWorkerAutoLogging] Running in thread: %s", threading.current_thread().name)
        while self.running:
            try:
                self.plc_handler.handle_auto_logging_process_image()
            except Exception:
                _log.exception("[PLCWorkerAutoLogging] Unhandled exception in main loop")
            self.msleep(self.MAX_SLEEP_MS)


# ---------------------------------------------------------------------------
# PLCHandler
# ---------------------------------------------------------------------------

class PLCHandler:
    """Xử lý tất cả các hoạt động liên quan đến PLC"""

    def __init__(self, max_workers=6, processor=None, layer_core=None):
        self.layer_core     = layer_core
        self.executor       = ThreadPoolExecutor(max_workers=max_workers)
        self.model_executor = ThreadPoolExecutor(max_workers=4)
        self.processor      = processor
        if self.processor is not None:
            self.processor.plc_handler = self

        self._counters: defaultdict[str, int]                 = defaultdict(int)
        self._counter_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)
        self._counters_meta_lock                              = threading.Lock()

        self._processing_keys: set = set()
        self._processing_lock      = threading.Lock()

        self._mode_lock = threading.RLock()

        self._signal_rwlock       = ReadWriteLock()
        self.dict_signal_complete: dict = {}

        self._pixmap_cache: dict = {}
        self._pixmap_cache_lock  = threading.Lock()

        self.signals = UISignals()
        self.signals.update_display.connect(self.update_ui_slot)
        self.signals.show_warning.connect(self._show_warning_slot)
        self.signals.set_user_index.connect(self._on_set_user_index)
        self.signals.load_mode_params.connect(self._on_load_mode_params)

        self.worker_thread    = PLCWorkerModeAuto1(self)
        self.built_in_objects = {}
        self.built_in_mapping_mode = {}
        self.ui_itemcode      = None
        self.mode_kick        = None  # được set từ mapping 'automatic' trong set_built_in_mapping_mode

        self._label_sizes: dict = {}
        self._last_results_map: dict = {}
        self._active_triggers   = []
        self._active_reg        = []
        
        self.font        = QtGui.QFont()
        self.font.setPointSize(12)
        self.font.setBold(True)

        self._register_store: defaultdict[str, dict]                 = defaultdict(dict)
        self._register_store_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)
        self._register_store_meta_lock = threading.Lock()

        self._flag_logging: defaultdict[str, bool] = defaultdict(bool)
        self.register_table_logging: dict = {}

        self._item_code_tick  = 0
        self._last_item_code: str | None = None
        self.ITEM_CODE_POLL_EVERY = 100

        self.mode_load_jumper = False

        self.register_table_logging = {}

    # -----------------------------------------------------------------------
    # FIX CHÍNH: _submit — wrapper cho ThreadPoolExecutor.submit()
    # Tự động log exception từ future thay vì nuốt lặng lẽ
    # -----------------------------------------------------------------------

    def _submit(self, executor: ThreadPoolExecutor, fn, *args, **kwargs):
        """
        Gửi task vào executor VÀ attach done-callback để log exception.
        Exception trong thread pool sẽ xuất hiện trên terminal.
        """
        future = executor.submit(fn, *args, **kwargs)

        def _on_done(f):
            exc = f.exception()
            if exc:
                _log.error(
                    "[ThreadPool] Unhandled exception in %s: %s\n%s",
                    fn.__name__,
                    exc,
                    "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                )

        future.add_done_callback(_on_done)
        return future

    # -----------------------------------------------------------------------
    # -----------------------------------------------------------------------
    # Safe PLC I/O helpers (Direct to PLC vs Indirect from Log Mode)
    # -----------------------------------------------------------------------

    def is_indirect_log_mode(self) -> bool:
        """
        Kiểm tra chế độ giao tiếp PLC được cấu hình:
        - True: Chế độ mô phỏng qua LOG (indirect_from_log = True hoặc direct_to_plc = False)
        - False: Chế độ kết nối trực tiếp thiết bị PLC (direct_to_plc = True)
        """
        # 1. Kiểm tra cấu hình lưu trên layer_core (module_2.main_core)
        if self.layer_core is not None:
            # Nếu chỉ định rõ direct_to_plc = True và indirect_from_log = False
            if bool(getattr(self.layer_core, 'direct_to_plc', False)) is True and not bool(getattr(self.layer_core, 'indirect_from_log', False)):
                return False
            if bool(getattr(self.layer_core, 'indirect_from_log', False)) is True:
                return True
            if hasattr(self.layer_core, 'direct_to_plc') and bool(getattr(self.layer_core, 'direct_to_plc')) is False:
                return True

        # 2. Kiểm tra từ CSDL DATA_IP_ADDRESS.INFOR_ADDRESS nếu có db_manager hoặc connection
        try:
            conn = getattr(self.layer_core, 'connection', None)
            if conn and hasattr(conn, 'cursor') and callable(conn.cursor):
                cursor = conn.cursor()
                cursor.execute("SELECT direct_to_plc, indirect_from_log FROM DATA_IP_ADDRESS.INFOR_ADDRESS LIMIT 1")
                row = cursor.fetchone()
                cursor.close()
                if row:
                    direct_to_plc, indirect_from_log = bool(row[0]), bool(row[1])
                    return indirect_from_log or (not direct_to_plc)
        except Exception:
            pass

        return False

    def _safe_read_plc(self, register: str):
        """
        Đọc PLC an toàn:
        - Nếu user chọn indirect_from_log: Sử dụng _safe_read_plc_log để đọc từ log mô phỏng.
        - Nếu user chọn direct_to_plc: Sử dụng đọc trực tiếp từ thiết bị PLC.
        """
        if self.is_indirect_log_mode():
            return self._safe_read_plc_log(register)

        if self.layer_core is None or self.layer_core.driver_loader is None:
            # _log.error("[PLCHandler] _safe_read_plc failed for register: %s", register)
            return None
        try:
            return self.layer_core.driver_loader.read_plc(register)
        except Exception:
            # _log.exception("[PLCHandler] _safe_read_plc failed for register: %s", register)
            return None

    def _safe_write_plc(self, register: str, value):
        """
        Ghi PLC an toàn:
        - Nếu value là None hoặc để trống (""): bỏ qua không ghi (thanh ghi chỉ đọc không cần ghi).
        - Nếu user chọn indirect_from_log: Sử dụng _safe_write_plc_log để ghi vào log mô phỏng.
        - Nếu user chọn direct_to_plc: Sử dụng ghi trực tiếp xuống thiết bị PLC.
        """
        if value is None:
            return None
        val_str = str(value).strip()
        if val_str == "" or val_str.lower() in ("none", "no value"):
            return None

        if self.is_indirect_log_mode():
            return self._safe_write_plc_log(register, value)

        if self.layer_core is None or self.layer_core.driver_loader is None:
            # _log.error("[PLCHandler] _safe_write_plc failed for register: %s", register)
            return None
        try:
            return self.layer_core.driver_loader.write_plc(register, value)
        except Exception:
            # _log.exception("[PLCHandler] _safe_write_plc failed: register=%s value=%s", register, value)
            return None

    def _safe_read_plc_log(self, register: str):
        """Đọc PLC từ file log mô phỏng (trigger_{register}.txt), log lỗi thay vì để exception âm thầm."""
        # 1. Nếu driver_loader có hàm read_plc_log thì ưu tiên gọi
        if self.layer_core is not None and self.layer_core.driver_loader is not None:
            if hasattr(self.layer_core.driver_loader, 'read_plc_log'):
                try:
                    return self.layer_core.driver_loader.read_plc_log(register)
                except Exception:
                    pass

        # 2. Fallback đọc trực tiếp file trigger_{register}.txt trong AppData / bundle
        try:
            file_path = get_trigger_file_path(register, for_writing=False)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    line = f.readline().strip()
                    if '=' in line:
                        reg, val = line.split('=')
                        if reg.strip().upper() == register.strip().upper():
                            return int(val.strip())
            return 0
        except Exception:
            return 0

    def _safe_write_plc_log(self, register: str, value):
        """Ghi PLC vào file log mô phỏng (trigger_{register}.txt), log lỗi thay vì để exception âm thầm."""
        if value is None:
            return False
        val_str = str(value).strip()
        if val_str == "" or val_str.lower() in ("none", "no value"):
            return False

        # 1. Nếu driver_loader có hàm write_plc_log thì ưu tiên gọi
        if self.layer_core is not None and self.layer_core.driver_loader is not None:
            if hasattr(self.layer_core.driver_loader, 'write_plc_log'):
                try:
                    return self.layer_core.driver_loader.write_plc_log(register, value)
                except Exception:
                    pass

        # 2. Fallback ghi trực tiếp file trigger_{register}.txt trong thư mục AppData
        try:
            file_path = get_trigger_file_path(register, for_writing=True)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"{register} = {value}\n")
            return True
        except Exception as e:
            _log.exception("[PLCHandler] _safe_write_plc_log fallback failed: register=%s value=%s: %s", register, value, e)
            return False


    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def time_to_name_file_image(self):
        return str(datetime.now()).replace(':', '-').replace(' ', '_').replace('.', '-')

    def start_monitoring(self):
        self.worker_thread.start()

    def stop_monitoring(self):
        self.worker_thread.running = False
        self.worker_thread.quit()
        self.worker_thread.wait()
        self.executor.shutdown(wait=True)
        self.model_executor.shutdown(wait=True)
        _log.info("[PLCHandler] Executors shut down.")


    def start_monitoring_auto_logging(self):
        if not hasattr(self, 'worker_auto_logging'):
            self.worker_auto_logging = PLCWorkerAutoLogging(self)
        if not self.worker_auto_logging.isRunning():
            self.worker_auto_logging.running = True
            self.worker_auto_logging.start()

    def stop_monitoring_auto_logging(self):
        if hasattr(self, 'worker_auto_logging') and self.worker_auto_logging.isRunning():
            self.worker_auto_logging.running = False
            self.worker_auto_logging.quit()
            self.worker_auto_logging.wait()

    # -----------------------------------------------------------------------
    # Warning
    # -----------------------------------------------------------------------

    def _show_warning_slot(self, title: str, message: str):
        QMessageBox.warning(None, title, message, QMessageBox.Ok)

    def _warn(self, title: str, message: str):
        _log.warning("[PLCHandler] WARN — %s: %s", title, message)
        self.signals.show_warning.emit(title, message)

    # -----------------------------------------------------------------------
    # Counter helpers
    # -----------------------------------------------------------------------

    def _get_counter_lock(self, key) -> threading.Lock:
        with self._counters_meta_lock:
            return self._counter_locks[key]

    def _increment_counter(self, key) -> int:
        with self._get_counter_lock(key):
            self._counters[key] += 1
            return self._counters[key]

    def _reset_counter(self, key):
        with self._get_counter_lock(key):
            self._counters[key] = 0

    def _get_counter(self, key) -> int:
        with self._get_counter_lock(key):
            return self._counters[key]

    # -----------------------------------------------------------------------
    # Per-key processing guard
    # -----------------------------------------------------------------------

    def _try_acquire_key(self, key) -> bool:
        with self._processing_lock:
            if key in self._processing_keys:
                return False
            self._processing_keys.add(key)
            return True

    def _release_key(self, key):
        with self._processing_lock:
            self._processing_keys.discard(key)

    # -----------------------------------------------------------------------
    # Register accumulator
    # -----------------------------------------------------------------------

    def _get_register_lock(self, key) -> threading.Lock:
        with self._register_store_meta_lock:
            return self._register_store_locks[key]

    def _accumulate_registers(self, key: str, registers: dict | list):
        if not registers:
            return
        with self._get_register_lock(key):
            if isinstance(registers, dict):
                self._register_store[key].update(registers)
            elif isinstance(registers, (list, tuple, set)):
                for r in registers:
                    if r and str(r).strip():
                        self._register_store[key][str(r).strip()] = 1
        _log.debug('[%s] Accumulated %s registers (total: %s)',
                   key, len(registers), len(self._register_store[key]))

    def _pop_registers(self, key: str) -> dict:
        with self._get_register_lock(key):
            registers = dict(self._register_store[key])
            self._register_store[key].clear()
        return registers

    # -----------------------------------------------------------------------
    # Built-in objects / config
    # -----------------------------------------------------------------------

    def set_built_in_config(self, objects, mapping):
        self.built_in_objects = objects
        self.built_in_mapping_mode = mapping
        if self.mode_kick is None:
            # Mặc định: mode đang map cho 'automatic' (lấy từ camera đầu tiên có cấu hình)
            self.mode_kick = next(
                (cam.get('mapping', {}).get('automatic', {}).get('mapping_mode')
                 for cam in mapping.values()
                 if cam.get('mapping', {}).get('automatic', {}).get('mapping_mode')),
                None
            )
        self._update_trigger_cache()
        self._set_mode_reg_process()
        # self._update_counter_settings()

    def _update_counter_settings(self,automation_ui):
        if automation_ui:
            if automation_ui.radioButton_counter_pc.isChecked():
                return 'PC'
            elif automation_ui.radioButton_counter_plc.isChecked():
                return 'PLC'
            elif automation_ui.radioButton_condition_plc_pc.isChecked():
                return 'PLC_TO_PC'
                
    def set_item_code_display(self, obj):
        self.ui_itemcode = obj


    # -----------------------------------------------------------------------
    # reset counter from PLC
    # -----------------------------------------------------------------------
    def reset_counter_from_plc(self):
        if not self.built_in_objects or not self.dict_signal_complete:
            pass

        for key, value in self.built_in_objects.items():
                automation_ui = value.get('automation_ui')
                if automation_ui and automation_ui.radioButton_reset.isChecked():
                    signals_selected = automation_ui.comboBox_reset_counter_signal_selected.currentText()
                    signals = dict(self.dict_signal_complete.get(key, {}))
                    if signals_selected not in signals:
                        return 
                    reg = signals.get(signals_selected, {}).get('reg')
                    if not reg:
                        return
                    
                    if self._safe_read_plc(reg) != 0 :
                        self._reset_counter(key)
                        _log.info("[PLCHandler] Reset counter %s", key)
                        off_val = signals.get(signals_selected, {}).get('off')
                        if off_val is not None and str(off_val).strip() != "" and str(off_val).strip().lower() not in ('none', 'no value'):
                            try:
                                self._safe_write_plc(reg, int(off_val))
                            except (ValueError, TypeError):
                                pass

    # -----------------------------------------------------------------------
    # Mode reg / trigger cache
    # -----------------------------------------------------------------------

    def _set_mode_reg_process(self):
        if not self.built_in_objects or not self.mode_kick:
            _log.error("[PLCHandler] _set_mode_reg_process failed for built_in_objects: %s", self.built_in_objects)
            _log.error("[PLCHandler] _set_mode_reg_process failed for mode_kick: %s", self.mode_kick)
            return

        new_dict: dict = {}
        try:
            for key, values in self.built_in_objects.items():
                signals = values.get('signals')
                if not isinstance(signals, dict) or not isinstance(signals.get(self.mode_kick), dict):
                    _log.warning("[PLCHandler] Signals not found or invalid for mode: %s", self.mode_kick)
                    continue

                values_signals = signals[self.mode_kick].get('values_signals')
                if not isinstance(values_signals, dict):
                    _log.warning("[PLCHandler] values_signals is missing or invalid for mode: %s", self.mode_kick)
                    continue
                for reg, target_reg in values_signals.items():
                    if target_reg.get('read_register'):
                        mode_reg = 'read'
                    elif target_reg.get('write_register'):
                        mode_reg = 'write'
                    else:
                        continue
                    
                    reg_addr   = f"{target_reg.get('address', '')}{target_reg.get(f'{mode_reg}_register', '')}"
                    new_dict.setdefault(key, {})[reg] = {
                        'reg': reg_addr,
                        'on' : target_reg.get(f'{mode_reg}_value_on'),
                        'off': target_reg.get(f'{mode_reg}_value_off'),
                    }
        except Exception:
            _log.exception("[PLCHandler] _set_mode_reg_process failed")
            return

        with self._signal_rwlock.write():
            self.dict_signal_complete = new_dict

        _log.info("[PLCHandler] Updated dict_signal_complete for mode: %s", self.mode_kick)

    def _find_mode_mapping(self, camera_key, mode_key):
        """Trả về (mode_name, config) của camera có mapping_mode == mode_key, hoặc (None, {})."""
        mapping = self.built_in_mapping_mode.get(camera_key, {}).get('mapping', {})
        for mode_name, cfg in mapping.items():
            if cfg.get('mapping_mode') == mode_key:
                return mode_name, cfg
        return None, {}

    def _resolve_signal(self, key, field):
        """Signal dict của `field` ('trigger_selected'/'component'/'completed') theo mapping
        của (key, self.mode_kick). Trả None nếu chưa cấu hình ('None'/rỗng).
        Gọi bên trong _signal_rwlock.read(); KeyError nếu signal không có trong dict_signal_complete."""
        name = self._find_mode_mapping(key, self.mode_kick)[1].get(field)
        if not name or name == 'None':
            return None
        if name in self.dict_signal_complete[key]:
            return dict(self.dict_signal_complete[key][name])
        else:
            return None

    def _update_trigger_cache(self, trigger_selected=None):
        """trigger_selected: dict {camera_key: tên trigger}. None -> tự tính theo self.mode_kick."""
        new_triggers = []
        mode_kick = self.mode_kick
        try:
            if self.built_in_objects and mode_kick:
                for key, values in self.built_in_objects.items():
                    signals = values.get('signals')
                    mode_signals = signals.get(mode_kick) if isinstance(signals, dict) else None
                    if not isinstance(mode_signals, dict):
                        _log.warning("[PLCHandler] Signals not found or invalid for mode: %s", mode_kick)
                        continue

                    if trigger_selected is None:
                        trigger = self._find_mode_mapping(key, mode_kick)[1].get('trigger_selected')
                    else:
                        trigger = trigger_selected.get(key)

                    vals_sig = mode_signals.get('values_signals')
                    target_reg = vals_sig.get(trigger) if isinstance(vals_sig, dict) else None
                    if not target_reg:
                        _log.warning("[PLCHandler] Target register not found for trigger: %s", trigger)
                        continue

                    read_value_on  = target_reg.get('read_value_on')
                    read_value_off = target_reg.get('read_value_off')
                    if read_value_on is None or str(read_value_on).strip() == "" or str(read_value_on).strip().lower() == 'none':
                        _log.warning("[PLCHandler] Target register ON value not found for key: %s", trigger)
                        continue

                    # Nếu read_value_off khác trống (có số) thì lưu int, nếu để trống thì lưu None (chỉ đọc không cần ghi)
                    off_val = None
                    if read_value_off is not None and str(read_value_off).strip() != "" and str(read_value_off).strip().lower() != 'none':
                        try:
                            off_val = int(read_value_off)
                        except (ValueError, TypeError):
                            off_val = None

                    new_triggers.append({
                        'reg' : f"{target_reg['address']}{target_reg['read_register']}",
                        'on'  : int(read_value_on),
                        'off' : off_val,
                        'key' : key,
                        'data': values,
                    })
        except Exception:
            _log.exception("[PLCHandler] _update_trigger_cache failed")

        with self._mode_lock:
            self._active_triggers = new_triggers

        _log.info("[PLCHandler] Trigger cache updated for mode: %s (Count: %s)",
                  mode_kick, len(new_triggers))

    # -----------------------------------------------------------------------
    # Node / mode switching
    # -----------------------------------------------------------------------

    def _activate_mode(self):
        try:
            if not self.layer_core.driver_loader:
                # _log.error("[PLCHandler] _activate_mode failed for driver_loader: %s", self.layer_core.driver_loader)
                return

            if not self.processor.built_in_modes:
                _log.error("[PLCHandler] _activate_mode failed for built_in_modes: %s", self.processor.built_in_modes)
                return

            for _k, values in self.processor.built_in_modes.items():
                for mode_key, value in values.get('modes', {}).items():
                    register = value.get('register')
                    value_bit_off = value.get('value_bit_off')
                    try:
                        current_value = self._safe_read_plc(register)
                        if current_value is None:
                            _log.error("[PLCHandler] _activate_mode failed for current_value: %s", current_value)
                            continue
                        if int(current_value) != value.get('value_bit_on'):
                            continue

                        with self._mode_lock:
                            self.mode_kick = mode_key

                        mode_name, _ = self._find_mode_mapping(_k, mode_key)
                        if mode_name:
                            _log.info('Mode Set Index: %s', f'{mode_name}_mode')

                        # Trigger của từng camera theo mode vừa kích hoạt
                        triggers = {
                            cam: self._find_mode_mapping(cam, mode_key)[1].get('trigger_selected')
                            for cam in self.built_in_mapping_mode
                        }
                        self._update_trigger_cache(triggers)
                        self._set_mode_reg_process()
                        self.load_user_set_selector_from_mode()
                        self.load_params_from_activated_mode(mode_key)
                        if value_bit_off is not None and str(value_bit_off).strip() != "" and str(value_bit_off).strip().lower() not in ('none', 'no value'):
                            try:
                                self._safe_write_plc(str(register), int(value_bit_off))
                            except (TypeError, ValueError):
                                pass
                    except (TypeError, ValueError) as e:
                        _log.debug("[PLCHandler] _activate_mode value error for register %s: %s", register, e)
                        continue
        except Exception:
            _log.exception("[PLCHandler] _activate_mode unexpected error")

    def load_params_from_activated_mode(self, mode_name=None):
        with self._mode_lock:
            current_mode = mode_name or self.mode_kick
        if current_mode:
            if threading.current_thread() is threading.main_thread():
                self._load_params_signals_mode(current_mode)
            else:
                self.signals.load_mode_params.emit(current_mode)

    def _on_load_mode_params(self, mode_name: str):
        self._load_params_signals_mode(mode_name)

    def _load_params_signals_mode(self, mode_name: str):
        if not mode_name or not self.built_in_objects:
            return

        cursor = None
        connect_db = None
        if self.processor and hasattr(self.processor, 'db_manager') and self.processor.db_manager:
            cursor = self.processor.db_manager.cursor
            connect_db = self.processor.db_manager.connect_db

        if cursor is None:
            _log.warning("[PLCHandler] Cannot load params for mode %s: db_manager cursor is None", mode_name)
            return

        for key, values in self.built_in_objects.items():
            automation_ui = values.get('automation_ui')
            signals_processor = values.get('signals_processor') or getattr(automation_ui, 'signals_processor', None)
            camera_id = values.get('camera_id') or getattr(automation_ui, 'camera_id', None)
            item_code_id = values.get('item_code_id') or getattr(automation_ui, 'item_code_id', None)
            models = values.get('models') or getattr(automation_ui, 'models', None)

            if not signals_processor:
                continue

            try:
                # 1. Tải mapping thông số tín hiệu của mode từ Database
                mode_auto_id = signals_processor.load_params_signals_from_gui_mapping_db(
                    cursor, camera_id, mode_name=mode_name, show_message=False
                )
                if mode_auto_id:
                    if connect_db:
                        num_models_str = str(len(models)) if models else "0"
                        signals_processor.load_shotxmodel_from_db(
                            cursor, connect_db, mode_auto_id, num_models_str
                        )
                    shot_complete, dict_shot = signals_processor.dict_shotxmodel()
                    values['shot'] = dict_shot
                    values['shot_complete'] = shot_complete
                    _log.info("[%s] Tải thành công mode '%s': %s shots, mapping=%s", key, mode_name, shot_complete, dict_shot)
                else:
                    _log.warning("[%s] Chế độ '%s' chưa được cấu hình tín hiệu trong CSDL cho camera_id=%s", key, mode_name, camera_id)

                # 2. Lưu bảng thông số tín hiệu an toàn vào dictionary 'signals'
                if hasattr(signals_processor, 'get_table_params'):
                    tbl_params = signals_processor.get_table_params()
                    if tbl_params:
                        if not isinstance(values.get('signals'), dict):
                            values['signals'] = {}
                        signals_dict = values['signals']

                        if not isinstance(signals_dict.get(mode_name), dict):
                            signals_dict[mode_name] = {}
                        signals_dict[mode_name]['values_signals'] = tbl_params
                        _log.debug("[%s] Đã cập nhật bảng thông số tín hiệu cho mode '%s'", key, mode_name)
                    else:
                        _log.warning("[%s] Bảng thông số tín hiệu (table_params) trống hoặc chưa cấu hình cho mode '%s'", key, mode_name)

                # 3. Kiểm tra Logger ban đầu
                if hasattr(automation_ui, 'config_logger') and automation_ui.config_logger:
                    item_code_text = automation_ui.comboBox_Itemcode.currentText() if hasattr(automation_ui, 'comboBox_Itemcode') else ""
                    automation_ui.config_logger.check_initial_db(
                        cursor,
                        camera_id,
                        item_code_id,
                        mode_name,
                        item_code_text
                    )
            except Exception as e:
                _log.warning("[%s] Không thể tải đầy đủ thông số cho mode '%s' (camera_id=%s): %s", key, mode_name, camera_id, e)

        self._update_trigger_cache()
        self._set_mode_reg_process()

    def load_user_set_selector_from_mode(self):
        with self._mode_lock:
            current_mode = self.mode_kick

        for camera, values in self.processor.built_in_modes.items():
            modes = values.get('modes', {}).get(current_mode, {})
            if modes:
                self.signals.set_user_index.emit(
                    values,
                    modes.get('index', {}),
                    current_mode,
                    camera,
                )

    def _on_set_user_index(self, values, index, current_mode, camera):
        self._submit(self.executor, self.set_index_user, values, index, current_mode, camera)

    def set_index_user(self, values, index, current_mode, camera):
        if not values:
            self._warn("Cảnh báo", "Không có thông tin thiết bị Camera")
            _log.error("[set_index_user] values is None/empty for mode=%s camera=%s", current_mode, camera)
            return

        device = values.get('device')
        if not device:
            self._warn("Cảnh báo", "Kiểm tra kết nối thiết bị Camera")
            _log.error("[set_index_user] device is None for mode=%s camera=%s", current_mode, camera)
            return

        camera = camera.removeprefix('built-in-')
        try:
            device.stop_grabbing_array_class()
            device.set_user_selector_class(user_index=index)
            device.start_grabbing_array_class()
            _log.info('UserSet%s from Mode: %s in %s loaded successfully', index, current_mode, camera)
        except Exception:
            _log.exception('[set_index_user] UserSet%s from Mode: %s in %s failed', index, current_mode, camera)
            self._warn("Lỗi Camera", f"Không thể set user selector: camera={camera} mode={current_mode}")

    # -----------------------------------------------------------------------
    # Main trigger loop
    # -----------------------------------------------------------------------

    def _run_trigger_from_activated_mode(self) -> int:
        with self._mode_lock:
            triggers     = list(self._active_triggers)
            current_mode = self.mode_kick

        any_camera_in_logging = False
        for k, v in self.built_in_mapping_mode.items():
            if v.get('mapping', {}).get('logging', {}).get('mapping_mode') == current_mode:
                any_camera_in_logging = True
                break

        if not any_camera_in_logging:
            self.stop_monitoring_auto_logging()

        if not triggers:
            # _log.error("[PLCHandler] _run_trigger_from_activated_mode failed for triggers: %s", triggers)
            return 0

        activated = 0
        for item in triggers:
            key = item['key']
            try:
                if not self._try_acquire_key(key):
                    # _log.debug('Key %s đang xử lý, bỏ qua trigger', key)
                    continue        
                current_value = self._safe_read_plc(str(item['reg']))
                if current_value is None or str(current_value).strip() == "":
                    self._release_key(key)
                    continue

                if int(current_value) == item['on']:
                    off_val = item.get('off')
                    if off_val is not None and str(off_val).strip() != "" and str(off_val).strip().lower() not in ('none', 'no value'):
                        try:
                            self._safe_write_plc(str(item['reg']), int(off_val))
                        except (ValueError, TypeError):
                            pass
                    
                    mapping = self.built_in_mapping_mode.get(key, {}).get('mapping', {})
                    automatic_mode = mapping.get('automatic', {}).get('mapping_mode')
                    mirror_mode    = mapping.get('mirror', {}).get('mapping_mode')
                    logging_mode   = mapping.get('logging', {}).get('mapping_mode')

                    if current_mode == logging_mode:
                        self.handle_auto_logging_table_ui(key, item['data'])
                        self.start_monitoring_auto_logging()
                        self._release_key(key)
                        activated += 1
                        continue

                    handler = None
                    if current_mode == automatic_mode:
                        handler = self.handle_result_mode_auto
                    elif current_mode == mirror_mode:
                        handler = self.handle_result_mode_geji

                    if handler:
                        self._submit(
                            self.executor,
                            self._run_handler_with_release,
                            handler, key, item['data'],
                        )
                        activated += 1
                    else:
                        _log.warning("[%s] No handler mapped for current mode: %s", key, current_mode)
                        self._release_key(key)
                else:
                    self._release_key(key)

            except Exception:
                _log.exception("[_run_trigger_from_activated_mode] Error processing key: %s", key)
                self._release_key(key)

        return activated

    def _run_handler_with_release(self, handler, key, data):
        try:
            handler(key, data)
        except Exception:
            # Log đầy đủ traceback — đây là lý do chính code chết không có lỗi
            _log.exception("[PLCHandler] Exception in handler %s for key %s", handler.__name__, key)
        finally:
            self._release_key(key)

    # -----------------------------------------------------------------------
    # Image capture
    # -----------------------------------------------------------------------

    @staticmethod
    def snapshot_capture_config(automation_ui) -> dict:
        """Snapshot toàn bộ trạng thái UI trên Main Thread thành dict thuần Python.
        Hàm này PHẢI được gọi từ main thread trước khi submit vào executor."""
        def _safe_float(text: str) -> float:
            try:
                return float(text.strip())
            except (ValueError, AttributeError):
                return 0.0

        return {
            'gate':  {
                'pre':  {
                    'enabled': automation_ui.checkBox_join_gate_2.isChecked(),
                    'value':   int(automation_ui.comboBox_value_gate_2.currentText()),
                    'ordinal': getattr(automation_ui.spinBox_Ordinal_gate_2, 'value', lambda: getattr(automation_ui.spinBox_Ordinal_gate_2, 'text', lambda: getattr(automation_ui.spinBox_Ordinal_gate_2, 'currentText', lambda: 0)())())(),
                    'before':  automation_ui.checkBox_before_gate_2.isChecked(),
                    'after':   automation_ui.checkBox_after_gate_2.isChecked(),
                    'delay':   _safe_float(automation_ui.lineEdit_timer_gate_2.text()),
                },
                'post': {
                    'enabled': automation_ui.checkBox_join_gate_3.isChecked(),
                    'value':   int(automation_ui.comboBox_value_gate_3.currentText()),
                    'ordinal': getattr(automation_ui.spinBox_Ordinal_gate_3, 'value', lambda: getattr(automation_ui.spinBox_Ordinal_gate_3, 'text', lambda: getattr(automation_ui.spinBox_Ordinal_gate_3, 'currentText', lambda: 0)())())(),
                    'before':  automation_ui.checkBox_before_gate_3.isChecked(),
                    'after':   automation_ui.checkBox_after_gate_3.isChecked(),
                    'delay':   _safe_float(automation_ui.lineEdit_timer_gate_3.text()),
                },
            },
            'busy':  {
                'pre':  {
                    'enabled': automation_ui.checkBox_join_busy_2.isChecked(),
                    'value':   int(automation_ui.comboBox_value_busy_2.currentText()),
                    'ordinal': getattr(automation_ui.spinBox_Ordinal_busy_2, 'value', lambda: getattr(automation_ui.spinBox_Ordinal_busy_2, 'text', lambda: getattr(automation_ui.spinBox_Ordinal_busy_2, 'currentText', lambda: 0)())())(),
                    'before':  automation_ui.checkBox_before_busy_2.isChecked(),
                    'after':   automation_ui.checkBox_after_busy_2.isChecked(),
                    'delay':   _safe_float(automation_ui.lineEdit_timer_busy_2.text()),
                },
                'post': {
                    'enabled': automation_ui.checkBox_join_busy_3.isChecked(),
                    'value':   int(automation_ui.comboBox_value_busy_3.currentText()),
                    'ordinal': getattr(automation_ui.spinBox_Ordinal_busy_3, 'value', lambda: getattr(automation_ui.spinBox_Ordinal_busy_3, 'text', lambda: getattr(automation_ui.spinBox_Ordinal_busy_3, 'currentText', lambda: 0)())())(),
                    'before':  automation_ui.checkBox_before_busy_3.isChecked(),
                    'after':   automation_ui.checkBox_after_busy_3.isChecked(),
                    'delay':   _safe_float(automation_ui.lineEdit_timer_busy_3.text()),
                },
            },
            'ready': {
                'pre':  {
                    'enabled': automation_ui.checkBox_join_ready_2.isChecked(),
                    'value':   int(automation_ui.comboBox_value_ready_2.currentText()),
                    'ordinal': getattr(automation_ui.spinBox_Ordinal_ready_2, 'value', lambda: getattr(automation_ui.spinBox_Ordinal_ready_2, 'text', lambda: getattr(automation_ui.spinBox_Ordinal_ready_2, 'currentText', lambda: 0)())())(),
                    'before':  automation_ui.checkBox_before_ready_2.isChecked(),
                    'after':   automation_ui.checkBox_after_ready_2.isChecked(),
                    'delay':   _safe_float(automation_ui.lineEdit_timer_ready_2.text()),
                },
                'post': {
                    'enabled': automation_ui.checkBox_join_ready_3.isChecked(),
                    'value':   int(automation_ui.comboBox_value_ready_3.currentText()),
                    'ordinal': getattr(automation_ui.spinBox_Ordinal_ready_3, 'value', lambda: getattr(automation_ui.spinBox_Ordinal_ready_3, 'text', lambda: getattr(automation_ui.spinBox_Ordinal_ready_3, 'currentText', lambda: 0)())())(),
                    'before':  automation_ui.checkBox_before_ready_3.isChecked(),
                    'after':   automation_ui.checkBox_after_ready_3.isChecked(),
                    'delay':   _safe_float(automation_ui.lineEdit_timer_ready_3.text()),
                },
            },
        }

    def _apply_signal_phase(self, cfg: dict, signals: dict, phase: str, sig_keys: list) -> None:
        """Gửi tín hiệu PLC theo cấu hình phase (pre/post), có delay trước hoặc sau.
        Thứ tự gửi được quyết định bởi tham số 'ordinal' (tăng dần).
        Chạy hoàn toàn trên background thread, không chạm Qt widget."""
        tasks = []
        for sig_key in sig_keys:
            phase_cfg = cfg.get(sig_key, {}).get(phase, {})
            if not phase_cfg.get('enabled'):
                continue
            sig = signals.get(sig_key)
            if not sig:
                continue
            try:
                ordinal = int(phase_cfg.get('ordinal', 0))
            except (ValueError, TypeError):
                ordinal = 0
            tasks.append((ordinal, sig_key, phase_cfg, sig))

        # Sắp xếp theo ordinal tăng dần
        tasks.sort(key=lambda x: x[0])

        for ordinal, sig_key, phase_cfg, sig in tasks:
            delay = phase_cfg.get('delay', 0.0)
            value = phase_cfg.get('value', 0)
            reg   = str(sig.get('reg', ''))
            if not reg:
                continue
            write = self._safe_write_plc
            
            if phase_cfg.get('before'):
                if delay > 0:
                    time.sleep(delay)
                write(reg, int(value))
            elif phase_cfg.get('after'):
                write(reg, int(value))
                if delay > 0:
                    time.sleep(delay)

    def take_image(self, device, key, capture_cfg: dict):
        """Lấy ảnh từ camera công nghiệp.
        capture_cfg là dict thuần Python đã được snapshot từ main thread
        bằng snapshot_capture_config(), KHÔNG chứa Qt widget."""
        with self._signal_rwlock.read():
            signals = dict(self.dict_signal_complete.get(key, {}))
        def grab_with_retry(max_attempts: int = 3, delay: float = 0.03):
            for attempt in range(max_attempts):
                t0  = time.perf_counter()
                img = device.Retrieve_Image_Buffer()
                _log.debug('[take_image] Retrieve latency (attempt %d): %.2fms',
                           attempt + 1, (time.perf_counter() - t0) * 1000)
                if img is not None:
                    return img
                if attempt < max_attempts - 1:
                    time.sleep(delay)
            return None

        # --- Phase PRE-grab: gửi tín hiệu gate/busy/ready trước khi chụp ---
        self._apply_signal_phase(capture_cfg, signals, 'pre', ['gate', 'busy', 'ready'])

        raw_image_rgb = grab_with_retry()

        # --- Soft-reset nếu grab thất bại ---
        if raw_image_rgb is None:
            _log.warning('[%s] First grab failed — attempting camera soft reset...', key)
            try:
                device.stop_grabbing_array_class()
                time.sleep(0.1)
                device.start_grabbing_array_class()
                time.sleep(0.1)
            except Exception as e:
                _log.error('[%s] Camera soft reset failed: %s', key, e)
            raw_image_rgb = grab_with_retry()

        # --- Phase POST-grab: gửi tín hiệu gate/busy/ready sau khi chụp ---
        self._apply_signal_phase(capture_cfg, signals, 'post', ['gate', 'busy', 'ready'])

        return raw_image_rgb

    # -----------------------------------------------------------------------
    # take_image_bk
    # -----------------------------------------------------------------------
    def take_image_bk(self, device, key, timer, current_count, timer1):
        with self._signal_rwlock.read():
            signals = dict(self.dict_signal_complete.get(key, {}))

        write = self._safe_write_plc

        def grab_with_retry(max_attempts=3, delay=0.03):
            for attempt in range(max_attempts):
                start_time = time.perf_counter()
                img = device.Retrieve_Image_Buffer()
                lapsed = (time.perf_counter() - start_time) * 1000
                _log.debug('[take_image] Retrieve latency (attempt %d): %.2fms', attempt + 1, lapsed)
                if img is not None:
                    return img
                time.sleep(delay)
            return None

        for sig_name, val_key in [('gate', 'on'), ('busy', 'on'), ('ready', 'off')]:
            if sig_name in signals:
                val = signals[sig_name].get(val_key)
                if val is not None and str(val).strip() != '' and str(val).strip().lower() != 'none':
                    write(str(signals[sig_name]['reg']), int(val))

        time.sleep(timer)
        raw_image_rgb = grab_with_retry()

        if raw_image_rgb is None:
            _log.warning('[%s] First grab phase failed. Attempting camera soft reset...', key)
            try:
                device.stop_grabbing_array_class()
                time.sleep(0.1)
                device.start_grabbing_array_class()
                time.sleep(0.1)
            except Exception as e:
                _log.error('[%s] Camera soft reset failed: %s', key, e)
                
            raw_image_rgb = grab_with_retry()

        for sig_name, val_key in [('gate', 'off'), ('busy', 'off'), ('ready', 'on')]:
            if sig_name in signals:
                val = signals[sig_name].get(val_key)
                if val is not None and str(val).strip() != '' and str(val).strip().lower() != 'none':
                    write(str(signals[sig_name]['reg']), int(val))

        time.sleep(timer1)
        
        return raw_image_rgb
    # -----------------------------------------------------------------------
    # handler counter shot
    # -----------------------------------------------------------------------

    def counter_shot(self,key, automation_ui):

        counter_mode = self._update_counter_settings(automation_ui)
        read = self._safe_read_plc
        signals = dict(self.dict_signal_complete.get(key, {}))
        current_count = 0
        if counter_mode == 'PC':
            current_count = self._increment_counter(key)
        elif counter_mode == 'PLC':
            reg = signals.get(automation_ui.comboBox_increment_counter_signal_selected.currentText(), {}).get('reg')
            if reg:
                current_count = read(str(reg))
        elif counter_mode == 'PLC_TO_PC':
            current_count_pc = self._increment_counter(key)
            reg = signals.get(automation_ui.comboBox_increment_counter_signal_selected.currentText(), {}).get('reg')
            if reg:
                current_count_plc = read(str(reg))
                if current_count_pc == current_count_plc:
                    current_count = current_count_plc
                else:
                    _log.warning("[%s] PC count (%s) and PLC count (%s) mismatch!", key, current_count_pc, current_count_plc)
                    current_count = current_count_plc
        
        return current_count

    # -----------------------------------------------------------------------
    # Mode handlers
    # -----------------------------------------------------------------------

    def handle_result_mode_auto(self, key: str, values: dict) -> None:
        start_time    = time.perf_counter()

        automation_ui = values.get('automation_ui')

        current_count = self.counter_shot(key, automation_ui)

        _log.info('[%s] Current count for: %s', key, current_count)
        
        num_model = values.get('shot', {}).get(str(current_count))
        if not num_model:
            _log.debug('[%s] No model for shot %s — skipping', key, current_count)
            return

        device = values.get('device')
        if not device:
            _log.error('[%s] device is None at shot %s', key, current_count)
            self._warn("Cảnh báo", "Kiểm tra kết nối thiết bị Camera")
            return

        camera        = key.removeprefix('built-in-')
        key_model     = (camera, f'model-{num_model}')
        model_loader  = values.get('model_loader', {}).get(key_model)
        pyuic         = values.get('pyuic', {}).get(key_model)
        
        if not model_loader:
            _log.error('[%s] model_loader missing for key_model=%s', key, key_model)
            return
        if not pyuic:
            _log.error('[%s] pyuic missing for key_model=%s', key, key_model)
            return
        if not automation_ui:
            _log.error('[%s] automation_ui missing', key)
            return

        # Snapshot UI state trên main thread trước khi chuyển sang background thread
        capture_cfg = self.snapshot_capture_config(automation_ui)

        try:
            raw_image = self.take_image(device, key, capture_cfg)
        except Exception:
            _log.exception('[%s] take_image failed at shot %s', key, current_count)
            self._warn("Cảnh báo", "Lỗi lấy ảnh từ camera")
            return

        if raw_image is None:
            _log.error('[%s] raw_image is None at shot %s', key, current_count)
            self._warn("Cảnh báo", "Kiểm tra kết nối thiết bị Camera")
            return

        if not raw_image.flags['C_CONTIGUOUS']:
            raw_image = np.ascontiguousarray(raw_image)

        model_processor = self.processor.dict_processors.get(key_model)
        if not model_processor or not model_processor.process_image_func:
            _log.error('[%s] process_image_func is missing for key_model=%s. Check model loading (e.g., YoloFactory result_model).', key, key_model)
            return

        try:
            result_img, flag, list_register, logo_text = model_processor.process_image_func(
                raw_image, model_loader, pyuic, camera, key_model, current_count,
                mode_load_jumper=self.mode_load_jumper,
            )
        except Exception:
            _log.exception('[%s] process_image_func failed at shot %s', key, current_count)
            return

        if automation_ui.radioButton_cycle_frame.isChecked():
            self._accumulate_registers(key, list_register or [])

            shot_complete = values.get('shot_complete', 0)

            if current_count >= shot_complete:
                all_registers = self._pop_registers(key)

                try:
                    with self._signal_rwlock.read():
                        comp_sig  = self._resolve_signal(key, 'completed')
                        reset_sig = self._resolve_signal(key, 'component')
                except KeyError:
                    _log.exception('[%s] Missing complete/reset signal in dict_signal_complete', key)
                    self._reset_counter(key)
                    return

                if all_registers:
                    _log.info('[%s] NG registers: %s', key, all_registers)
                    if isinstance(all_registers, dict):
                        for reg, val in all_registers.items():
                            if reg and str(reg).strip():
                                self._safe_write_plc(str(reg).strip(), val)
                    else:
                        for reg in all_registers:
                            if reg and str(reg).strip():
                                self._safe_write_plc(str(reg).strip(), 1)
                else:
                    if reset_sig:
                        _log.info(f'Send Reset Signal OK {reset_sig}')
                        self._safe_write_plc(str(reset_sig['reg']), int(reset_sig['on']))

                if comp_sig:
                    _log.info(f'Send Complete Signal {comp_sig}')
                    self._safe_write_plc(str(comp_sig['reg']), int(comp_sig['on']))
                self._reset_counter(key)
                _log.info('[%s] Complete Cycle Shot %s | registers: %s',key, current_count, len(all_registers))

        elif automation_ui.radioButton_single_frame.isChecked():
            try:
                with self._signal_rwlock.read():
                        comp_sig  = self._resolve_signal(key, 'completed')
                        reset_sig = self._resolve_signal(key, 'component')
            except KeyError:
                _log.exception('[%s] Missing complete/reset signal in dict_signal_complete', key)
                self._reset_counter(key)
                return

            if list_register:
                _log.info('[%s] NG registers: %s', key, list_register)
                if isinstance(list_register, dict):
                    for reg, val in list_register.items():
                        if reg and str(reg).strip():
                            self._safe_write_plc(str(reg).strip(), val)
                else:
                    for reg in list_register:
                        if reg and str(reg).strip():
                            self._safe_write_plc(str(reg).strip(), 1)
            else:
                if reset_sig:
                    _log.info(f'Send Reset Signal OK {reset_sig}')
                    self._safe_write_plc(str(reset_sig['reg']), int(reset_sig['on']))

            if comp_sig:
                _log.info(f'Send Complete Signal {comp_sig}')
                self._safe_write_plc(str(comp_sig['reg']), int(comp_sig['on']))

            _log.info('[%s] Complete Single frame %s | registers: %s',key, current_count, len(list_register))

        state_str = 'OK' if flag else 'NG'
        chk_orig = pyuic.checkBox_OK_image_original if flag else pyuic.checkBox_NG_image_original
        
        if chk_orig.isChecked():
            path_save = (pyuic.lineEdit_OK_image_original if flag else pyuic.lineEdit_NG_image_original).text().strip()
            if path_save:
                chk_det = pyuic.checkBox_OK_image_detected if flag else pyuic.checkBox_NG_image_detected
                save_det = chk_det.isChecked()
                image_format = pyuic.Image_format.currentText().strip() if hasattr(pyuic, 'Image_format') else 'PNG'
                
                self.executor.submit(
                    self._save_ng_image, 
                    raw_image.copy(), 
                    path_save, 
                    key, 
                    state_str, 
                    result_img.copy() if save_det else None, 
                    save_det,
                    image_format
                )
        elapsed = (time.perf_counter() - start_time) * 1000
        self.signals.update_display.emit(
            [(key_model, pyuic, result_img, flag, list_register, logo_text)],
            f"⏱️: {elapsed:.2f} ms",
        )

    # -----------------------------------------------------------------------
    # Mode handlers mode manual
    # -----------------------------------------------------------------------

    def handle_result_mode_auto_manual(self, key: str, values: dict) -> None:
        time_start = time.perf_counter()
        start_time    = time.perf_counter()

        automation_ui = values.get('automation_ui')

        current_count = self.counter_shot(key, automation_ui)
        
        num_model = values.get('shot', {}).get(str(current_count))
        if not num_model:
            _log.debug('[%s] No model for shot %s — skipping', key, current_count)
            return

        camera        = key.removeprefix('built-in-')
        key_model     = (camera, f'model-{num_model}')
        model_loader  = values.get('model_loader', {}).get(key_model)
        pyuic         = values.get('pyuic', {}).get(key_model)
        
        if not model_loader:
            _log.error('[%s] model_loader missing for key_model=%s', key, key_model)
            return
        if not pyuic:
            _log.error('[%s] pyuic missing for key_model=%s', key, key_model)
            return
        if not automation_ui:
            _log.error('[%s] automation_ui missing', key)
            return

        # Snapshot UI state trên main thread trước khi chuyển sang background thread
        capture_cfg = self.snapshot_capture_config(automation_ui)
        # time.sleep(30)
        import random
        folder_path = r'C:\Users\VDM\Documents\New folder'
        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
        images = [f for f in os.listdir(folder_path) if f.lower().endswith(image_extensions)]
        if images:
            random_image_name = random.choice(images)
            raw_image = os.path.join(folder_path, random_image_name) 
                
        raw_image = cv2.imread(raw_image)

        try:
            model_processor = self.processor.dict_processors.get(key_model)
            if not model_processor or not model_processor.process_image_func:
                _log.error('[%s] process_image_func is missing for key_model=%s', key, key_model)
                return
            result_img, flag, list_register,logo_text = model_processor.process_image_func(
                raw_image, model_loader, pyuic, camera, key_model, current_count,
                mode_load_jumper=self.mode_load_jumper,
            )
        except Exception:
            _log.exception('[%s] process_image_func failed at shot %s', key, current_count)
            return

        elapsed = (time.perf_counter() - start_time) * 1000

        self._accumulate_registers(key, list_register or [])

        shot_complete = values.get('shot_complete', 0)
        if current_count >= shot_complete:
            all_registers = self._pop_registers(key)

            try:
                with self._signal_rwlock.read():
                    comp_sig  = dict(self.dict_signal_complete[key]['complete'])
                    reset_sig = dict(self.dict_signal_complete[key]['reset_ok'])
            except KeyError:
                _log.exception('[%s] Missing complete/reset signal in dict_signal_complete', key)
                self._reset_counter(key)
                return

            if all_registers:
                _log.info('[%s] NG registers: %s', key, all_registers)
                if isinstance(all_registers, dict):
                    for reg, val in all_registers.items():
                        if reg and str(reg).strip():
                            self._safe_write_plc(str(reg).strip(), val)
            else:
                self._safe_write_plc(str(reset_sig['reg']), int(reset_sig['on']))

            self._safe_write_plc(str(comp_sig['reg']), int(comp_sig['on']))
            self._reset_counter(key)
            _log.info('[%s] Complete shot %s | registers: %s | %.2fms',
                      key, current_count, len(all_registers), elapsed)

        state_str = 'OK' if flag else 'NG'
        chk_orig = pyuic.checkBox_OK_image_original if flag else pyuic.checkBox_NG_image_original
        
        if chk_orig.isChecked():
            path_save = (pyuic.lineEdit_OK_image_original if flag else pyuic.lineEdit_NG_image_original).text().strip()
            if path_save:
                chk_det = pyuic.checkBox_OK_image_detected if flag else pyuic.checkBox_NG_image_detected
                save_det = chk_det.isChecked()
                image_format = pyuic.Image_format.currentText().strip() if hasattr(pyuic, 'Image_format') else 'PNG'
                
                self.executor.submit(
                    self._save_ng_image, 
                    raw_image.copy(), 
                    path_save, 
                    key, 
                    state_str, 
                    result_img.copy() if save_det else None, 
                    save_det,
                    image_format
                )
        
        self.signals.update_display.emit(
            [(key_model, pyuic, result_img, flag, list_register,logo_text)],
            f"⏱️: {elapsed:.2f} ms",
        )
        time_end = time.perf_counter()
        time_elapsed = (time_end - time_start) * 1000
        time_str = f"⏱️: {time_elapsed:.2f} ms"

    # -----------------------------------------------------------------------
    # Mode handlers mode_geji
    # -----------------------------------------------------------------------
    def handle_result_mode_geji(self, key, values):
        start_time = time.perf_counter()
        current_count = self._increment_counter(key)
        num_model = values.get('shot', {}).get(str(current_count))
        device = values.get('device')
        if not device:
            _log.error('[handle_result_mode_geji][%s] device is None', key)
            self._warn("Cảnh báo", "Kiểm tra kết nối thiết bị Camera")
            return

        camera    = key.removeprefix('built-in-')
        key_model     = (camera, f'model-{num_model}')
        pyuic     = values.get('pyuic', {}).get(key_model)
        mirror_dev = values.get('mirror_dev')

        if pyuic is None:
            _log.error('[handle_result_mode_geji][%s] pyuic missing for key_model=%s', key, key_model)
            return

        try:
            raw_image_rgb = device.Retrieve_Image_Buffer()
        except Exception:
            _log.exception('[handle_result_mode_geji][%s] Retrieve_Image_Buffer failed', key)
            return
        # CẢNH BÁO LỖI LUỒNG: KHÔNG ĐƯỢC CHẠY get_value_from_table() Ở ĐÂY VÌ ĐANG Ở BACKGROUND THREAD.
        # Chúng ta chỉ lấy biến dict đã được lưu trữ sẵn từ Main Thread.
        MIRROR_DATA_CAMERA1 = mirror_dev.MIRROR_DATA_CAMERA1
        CONFIG_CAMERA1 = mirror_dev.CONFIG_CAMERA1
        
        try:
            obj        = KiemGuong(MIRROR_DATA_CAMERA1, CONFIG_CAMERA1)
            img, check, dict_data = obj.run(raw_image_rgb)
        except Exception:
            _log.exception('[handle_result_mode_geji][%s] KiemGuong.run failed', key)
            return

        result_img = img
        flag       = check

        # NOTE: PLC write PHẢI ngoài read-lock để tránh deadlock
        try:
            with self._signal_rwlock.read():
                reset_ok_sig = self._resolve_signal(key, 'component')
                complete_sig = self._resolve_signal(key, 'completed')
        except KeyError:
            _log.exception('[handle_result_mode_geji][%s] Missing signal config', key)
            return

        if reset_ok_sig:
            self._safe_write_plc(str(reset_ok_sig['reg']), int(reset_ok_sig['on']))
        if complete_sig:
            self._safe_write_plc(str(complete_sig['reg']), int(complete_sig['on']))

        list_register = []
        elapsed       = (time.perf_counter() - start_time) * 1000
        self._reset_counter(key)
        self.signals.update_display.emit(
            [(key_model, pyuic, result_img, flag, list_register, "Mirror (Use Mirror Model)")],
            f"⏱️: {elapsed:.2f} ms",
        )


    # -----------------------------------------------------------------------
    # auto_logging_ui
    # -----------------------------------------------------------------------

    def handle_auto_logging_table_ui(self, key: str, values: dict) -> None:
        camera        = key.removeprefix('built-in-')
        auto_log_ui = values.get('auto_logging_ui')
        if not auto_log_ui: return

        table_logging = auto_log_ui.tableWidget
        
        from PyQt5.QtWidgets import QCheckBox

        if not hasattr(self, 'register_table_logging') or not isinstance(self.register_table_logging, dict):
            self.register_table_logging = {}

        # Dọn dẹp các cấu hình cũ của key này để tránh duplicate khi gọi lại hàm
        for reg in list(self.register_table_logging.keys()):
            self.register_table_logging[reg] = [
                item for item in self.register_table_logging[reg] if item.get('key') != key
            ]
            if not self.register_table_logging[reg]:
                del self.register_table_logging[reg]

        for row in range(table_logging.rowCount()):
            container = table_logging.cellWidget(row, 0)
            if container is not None:
                chk = container.findChild(QCheckBox)
                if chk and chk.isChecked():
                    reg_item = table_logging.item(row, 6)
                    val_on_item = table_logging.item(row, 7)
                    val_off_item = table_logging.item(row, 8)
                    path_item = table_logging.item(row, 1)
                    desc_item = table_logging.item(row, 2)
                    
                    register = reg_item.text().strip() if reg_item else ""
                    val_on = val_on_item.text().strip() if val_on_item else ""
                    val_off = val_off_item.text().strip() if val_off_item else ""
                    path = path_item.text().strip() if path_item else ""
                    desc = desc_item.text().strip() if desc_item else ""
                    
                    cam_combo = table_logging.cellWidget(row, 3)
                    model_combo = table_logging.cellWidget(row, 4)
                    
                    sel_cam = cam_combo.currentText() if cam_combo else ""
                    sel_model = model_combo.currentText() if model_combo else ""

                    if register:
                        self.register_table_logging.setdefault(register, []).append({
                            'path_image': path,
                            'description': desc,
                            'selected_camera': sel_cam,
                            'selected_model': sel_model,
                            'value_on': val_on,
                            'value_off': val_off,
                            'values': values,
                            'key': key
                        })

    def handle_auto_logging_process_image(self):
        if not getattr(self, 'register_table_logging', None):
            return

        for register, list_configs in list(self.register_table_logging.items()):
            try:
                plc_raw = self._safe_read_plc(register)
                if plc_raw is None or str(plc_raw).strip() == "":
                    continue
                plc_val = int(plc_raw)
            except (ValueError, TypeError):
                continue
            
            for data_info in list_configs:
                try:
                    target_val = int(data_info.get('value_on', data_info.get('value', 1)))
                    value_off = int(data_info.get('value_off', 0))
                except (ValueError, TypeError):
                    continue

                if plc_val == target_val:
                    key = data_info['key']
                    if self._flag_logging[key]:
                        continue  # Already logging for this key
                    self._flag_logging[key] = True

                    try:
                        start_time = time.perf_counter()
                        values = data_info['values']
                        camera        = key.removeprefix('built-in-')
                        key_model = (data_info['selected_camera'], data_info['selected_model'])
                        path = data_info['path_image']
                        model_loader  = values.get('model_loader', {}).get(key_model)
                        pyuic         = values.get('pyuic', {}).get(key_model) 
                        current_count = 1
                        
                        #kiểm tra xem đường dãn có tồn tại không
                        if not os.path.exists(path):
                            _log.error('[%s] Đường dẫn không tồn tại: %s', key, path)
                            continue

                        if not pyuic:
                            _log.error('[%s] pyuic is None', key)
                            continue
                        
                        if not model_loader:
                            _log.error('[%s] model_loader is None', key)
                            continue

                        _log.info('[%s] handle_image_logging — processing %s images', key, path)
                        raw_image = cv2.imread(path)
                        if raw_image is None:
                            _log.error('[%s] cv2.imread returned None for: %s', key, path)
                            continue

                        # raw_image = cv2.cvtColor(raw_image, cv2.COLOR_BGR2RGB)

                        result_img, flag, list_register,_ = self.processor.processor.process_image_func(
                            raw_image, model_loader, pyuic, camera, key_model, current_count,
                        )
                        elapsed     = (time.perf_counter() - start_time) * 1000

                        self._accumulate_registers(key, list_register or [])
                        all_registers = self._pop_registers(key)

                        if all_registers:
                            _log.info('[%s] NG registers: %s', key, all_registers)
                            if isinstance(all_registers, dict):
                                for reg, val in all_registers.items():
                                    if reg and str(reg).strip():
                                        self._safe_write_plc(str(reg).strip(), val)
                            else:
                                for reg in all_registers:
                                    if reg and str(reg).strip():
                                        self._safe_write_plc(str(reg).strip(), 1)

                        self._safe_write_plc(register, value_off)

                        self.signals.update_display.emit(
                            [(key_model, pyuic, result_img, flag, list_register, "Logging (Model Representation Mapping)")],
                            f"⏱️: {elapsed:.2f} ms",
                        )

                        if not flag:
                            _log.info('[%s] NG detected for image: %s', key, path)
                    finally:
                        self._flag_logging[key] = False
                    
                    # NOTE: PLC write PHẢI ngoài read-lock để tránh deadlock
                    try:
                        with self._signal_rwlock.read():
                            reset_ok_sig = self._resolve_signal(key, 'component')
                            complete_sig = self._resolve_signal(key, 'completed')
                    except KeyError:
                        _log.exception('[handle_result_mode_logging][%s] Missing signal config', key)
                        return

                    if reset_ok_sig:
                        self._safe_write_plc(str(reset_ok_sig['reg']), int(reset_ok_sig['on']))
                    if complete_sig:
                        self._safe_write_plc(str(complete_sig['reg']), int(complete_sig['on']))


    # -----------------------------------------------------------------------
    # UI update slot (main thread)
    # -----------------------------------------------------------------------

    def clear_ui_caches(self):
        """Xóa cache kích thước label và pixmap khi thay đổi layout mode."""
        self._label_sizes.clear()
        with self._pixmap_cache_lock:
            self._pixmap_cache.clear()

    def re_render_latest_ui(self):
        """Hiển thị lại ảnh kết quả gần nhất khớp với kích thước layout mới."""
        if not getattr(self, '_last_results_map', None):
            return
        for key_model, (item, time_str) in list(self._last_results_map.items()):
            self.update_ui_slot([item], time_str)

    def update_ui_slot(self, results, time_str):
        if not hasattr(self, '_last_results_map'):
            self._last_results_map = {}
        for key_model, _pyuic5, result_img, flag, list_register, logo_text in results:
            try:
                set_style = 'background-color:#2e7d32; color:white' if flag else 'background-color:#c62828; color:white'
                result_text = "OK" if flag else "NG"
                
                # --- Watermark Logic ---
                if logo_text:
                    font = cv2.FONT_HERSHEY_DUPLEX
                    font_scale = 1.5
                    thickness = 2
                    (tw, th), _ = cv2.getTextSize(logo_text, font, font_scale, thickness)
                    margin = 30
                    img_h, img_w = result_img.shape[:2]
                    
                    x_text = img_w - tw - margin
                    y_text = img_h - margin
                    
                    x1 = max(0, x_text - 15)
                    y1 = max(0, y_text - th - 15)
                    x2 = min(img_w, x_text + tw + 15)
                    y2 = min(img_h, y_text + 15)
                    
                    if x2 > x1 and y2 > y1:
                        roi = result_img[y1:y2, x1:x2]
                        overlay_roi = roi.copy()
                        
                        # Nền đen bán trong suốt cho watermark
                        cv2.rectangle(overlay_roi, (0, 0), (x2 - x1, y2 - y1), (30, 30, 30), -1)
                        # Chữ watermark màu xám nhạt
                        cv2.putText(overlay_roi, logo_text, (15, y2 - y1 - 15), font, font_scale, (220, 220, 220), thickness, cv2.LINE_AA)
                        
                        # Blend overlay với ROI gốc (60% độ đậm cho chữ, 40% giữ lại nền ảnh)
                        cv2.addWeighted(overlay_roi, 0.6, roi, 0.4, 0, roi)
                        result_img[y1:y2, x1:x2] = roi
                # -----------------------
                
                # Lưu lại kết quả gần nhất (đã có watermark, để rỗng logo_text tránh vẽ lặp khi re-render)
                self._last_results_map[key_model] = (
                    (key_model, _pyuic5, result_img, flag, list_register, ""),
                    time_str
                )
                
                child = self.processor.dict_child.get(key_model) if self.processor and hasattr(self.processor, 'dict_child') else None
                if not child:
                    continue
                label_image = child['ldi']
                label_okng  = child['ldr']
                label_time  = child['ldt']

                # Lấy kích thước thực tế hiện tại của label_image (thay đổi theo layout mode)
                w, h = label_image.width(), label_image.height()
                if w > 10 and h > 10:
                    self._label_sizes[key_model] = (w, h)

                target_w, target_h = self._label_sizes.get(key_model, (w, h))

                h_img, w_img = result_img.shape[:2]
                if target_w > 0 and target_h > 0:
                    aspect = w_img / h_img
                    if target_w / target_h > aspect:
                        new_h = target_h
                        new_w = int(new_h * aspect)
                    else:
                        new_w = target_w
                        new_h = int(new_w / aspect)
                    resized = cv2.resize(result_img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                else:
                    resized = result_img

                h_r, w_r  = resized.shape[:2]
                cache_key = (key_model, w_r, h_r)
                cached    = self._pixmap_cache.get(cache_key)

                if cached is None or cached[0].shape != resized.shape:
                    buf  = np.ascontiguousarray(resized)
                    qimg = QtGui.QImage(buf.data, w_r, h_r, buf.strides[0],
                                        QtGui.QImage.Format_RGB888)
                    pix  = QtGui.QPixmap.fromImage(qimg)
                    self._pixmap_cache[cache_key] = (buf, pix)
                else:
                    buf, pix = cached
                    np.copyto(buf, resized)
                    qimg = QtGui.QImage(buf.data, w_r, h_r, buf.strides[0],
                                        QtGui.QImage.Format_RGB888)
                    pix  = QtGui.QPixmap.fromImage(qimg)
                    self._pixmap_cache[cache_key] = (buf, pix)

                invoke = QtCore.QMetaObject.invokeMethod
                Q      = QtCore.Qt.QueuedConnection

                if label_image:
                    invoke(label_image, "setPixmap", Q, QtCore.Q_ARG(QtGui.QPixmap, pix))
                if label_okng:
                    invoke(label_okng,  "setText",   Q, QtCore.Q_ARG(str, result_text))
                    invoke(label_okng,  "setStyleSheet",   Q, QtCore.Q_ARG(str, set_style))
                if label_time:
                    invoke(label_time,  "setText",   Q, QtCore.Q_ARG(str, time_str))
            
            except Exception:
                # Log đầy đủ — không nuốt lỗi nữa
                _log.exception("[update_ui_slot] Error rendering key_model=%s", key_model)

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------
    def cleanup(self):
        self.stop_monitoring()

        # Turn off PLC ready & run signals upon exit
        with self._mode_lock:
            current_mode = self.mode_kick

        if self.processor and hasattr(self.processor, 'built_in_dict_device'):
            for key in list(self.processor.built_in_dict_device.keys()):
                camera_name = key.replace('built-in-camera-', '')
                for sig in ['run', 'ready']:
                    try:
                        addr, _, _, _, write_reg, val_on, val_off = self.processor.return_reg(camera_name, name_signal=sig, mode_name=current_mode)
                        if addr is not None and write_reg is not None and val_off is not None:
                            val_off_str = str(val_off).strip()
                            if val_off_str != "" and val_off_str.lower() not in ('none', 'no value'):
                                reg_addr = f"{addr}{write_reg}"
                                _log.info("Cleanup PLC: writing OFF to %s signal %s on reg %s value %s", camera_name, sig, reg_addr, val_off)
                                try:
                                    self._safe_write_plc(reg_addr, int(val_off))
                                except (ValueError, TypeError):
                                    pass
                    except Exception:
                        _log.exception("Cleanup PLC: Error resetting signal %s for camera %s", sig, camera_name)

        self.executor.shutdown(wait=True)
        if self.processor and hasattr(self.processor, 'built_in_objects'):
            for key, data in self.processor.built_in_objects.items():
                device = data.get('device')
                if device:
                    try:
                        _log.info("Cleanup: Closing camera %s", key)
                        device.stop_grabbing_array_class()
                        device.close_device()
                    except Exception:
                        _log.exception("Cleanup: Error closing camera %s", key)
                        pass


    # -----------------------------------------------------------------------
    # Save image
    # -----------------------------------------------------------------------

    def _save_ng_image(self, image: np.ndarray, path_save_image: str,
                       key: str, state: str, image_result: np.ndarray, save_detected: bool,
                       image_format: str = 'PNG') -> None:
        if not path_save_image:
            _log.warning('[%s] path_save_image rỗng, bỏ qua lưu ảnh.', key)
            return

        try:
            today = datetime.now().strftime('%Y-%m-%d')
            folder = os.path.join(path_save_image, state, today)
            os.makedirs(folder, exist_ok=True)

            fmt = (image_format or 'PNG').strip().lower()
            ext = fmt if fmt in ['png', 'jpg', 'jpeg', 'bmp', 'tiff', 'tif', 'raw'] else 'png'
            filename = f'{self.time_to_name_file_image()}.{ext}'
            filepath = os.path.join(folder, filename)
            
            bgr_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            if ext == 'raw':
                bgr_image.tofile(filepath)
            else:
                cv2.imwrite(filepath, bgr_image)

            if save_detected and image_result is not None:
                folder_detect = os.path.join(folder, 'Image_Detect')
                os.makedirs(folder_detect, exist_ok=True)
                filepath_detect = os.path.join(folder_detect, filename)
                bgr_detect = cv2.cvtColor(image_result, cv2.COLOR_RGB2BGR)
                if ext == 'raw':
                    bgr_detect.tofile(filepath_detect)
                else:
                    cv2.imwrite(filepath_detect, bgr_detect)

            _log.info('[%s] %s image saved: %s', key, state, filepath)

        except Exception:
            _log.exception('[%s] _save_ng_image failed (state=%s)', key, state)

#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$


class DatabaseManager:
    
    def __init__(self, database,connect_db):
        self.db = database
        self.connect_db = connect_db
        self.cursor = self.connect_db.connection.cursor()

    def ensure_schema_compatibility(self):
        """Tự động nâng cấp cấu trúc bảng nếu database cũ chưa có:
        - ITEMS_CODE.value_bit_off -> VARCHAR(255)
        - MODE_AUTO.value_bit_off -> VARCHAR(255)
        - SHOTXMODEL.Discription -> VARCHAR(255)
        """
        try:
            self.cursor.execute(f"ALTER TABLE `{self.db}`.ITEMS_CODE MODIFY COLUMN value_bit_off VARCHAR(255) NOT NULL DEFAULT '0'")
            self.connect_db.connection.commit()
        except Exception as e:
            _log.debug("ITEMS_CODE modify value_bit_off check: %s", e)

        try:
            self.cursor.execute(f"ALTER TABLE `{self.db}`.MODE_AUTO MODIFY COLUMN value_bit_off VARCHAR(255) NOT NULL DEFAULT '0'")
            self.connect_db.connection.commit()
        except Exception as e:
            _log.debug("MODE_AUTO modify value_bit_off check: %s", e)

        try:
            self.cursor.execute(f"""
                SELECT COUNT(*) FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'SHOTXMODEL' AND COLUMN_NAME = 'Discription'
            """, (self.db,))
            row = self.cursor.fetchone()
            if not row or row[0] == 0:
                self.cursor.execute(f"ALTER TABLE `{self.db}`.SHOTXMODEL ADD COLUMN Discription VARCHAR(255) DEFAULT '' AFTER no_of_model")
                self.connect_db.connection.commit()
                _log.info("Added column Discription to `%s`.SHOTXMODEL", self.db)
        except Exception as e:
            _log.debug("SHOTXMODEL add Discription check: %s", e)

    def select_database(self):
        """Chọn database làm việc cho phiên kiểm tra"""
        try:
            self.cursor.execute(f"USE `{self.db}`")
            _log.info(f'Select database: {self.db}')
            self.ensure_schema_compatibility()
        except Exception as e:
            _log.error(f'Failed to select database {self.db}: {e}')
        
    def get_item_code_id(self, item_code):
        """Lấy item code ID từ database"""
        self.cursor.execute(
            f"SELECT id FROM `{self.db}`.ITEMS_CODE WHERE name_line_code = %s",
            (item_code,)
        )
        _log.info(f'Get item code id: {item_code}')
        result = self.cursor.fetchone()
        return result[0] if result else None
        
    def get_camera_records(self, item_code_id):
        """Lấy danh sách camera records cho item code"""
        self.cursor.execute(
            f"SELECT * FROM `{self.db}`.NUMS_CAMERA WHERE item_code_id = %s",
            (item_code_id,)
        )
        _log.info(f'Get camera records for item code: {item_code_id}')
        return self.cursor.fetchall()
        
    def get_models_for_camera(self, camera_id):
        """Lấy danh sách models cho camera cụ thể"""
        self.cursor.execute(
            f"SELECT * FROM `{self.db}`.NUMS_MODEL WHERE camera_id = %s",
            (camera_id,)
        )
        _log.info(f'Get models for camera: {camera_id}')
        return self.cursor.fetchall()


class CameraTabManager:
    
    def __init__(self, db_manager, i_code,connect_db,database):
        self.database=database
        self.db_manager = db_manager
        self.i_code = i_code
        self.connect_plc = connect_db
        self.built_in_objects = {}
        self.built_in_modes = {}
        self.built_in_dict_device = {}
        self.built_in_mapping_mode = {}
        self.dict_child = {}
        self.dict_processors = {}
        self.frame_count = 0
        self.set_list_model = []
        self.total_key = []
        self.device = None
        self.camera_colors = {}

    def get_camera_frame_style(self, camera_id):
        """Trả về stylesheet màu nền sáng, nhạt, dịu mắt đồng bộ cho các frame cùng camera."""
        if not hasattr(self, 'camera_colors'):
            self.camera_colors = {}

        cam_key = str(camera_id).strip()
        if cam_key not in self.camera_colors:
            # Danh sách các tone màu hơi trầm nhã nhặn, dịu mắt, không quá nổi bật nhưng phân biệt rõ ràng giữa các camera
            palette = [
                {"bg": "#CAD2DA", "border": "#364554"},  # Xanh xám thép (Slate Blue)
                {"bg": "#CAD4CB", "border": "#354A3A"},  # Xanh rêu xám (Sage Green)
                {"bg": "#D3CCC5", "border": "#4D423B"},  # Nâu xám ấm (Warm Taupe)
                {"bg": "#C6D2D4", "border": "#284449"},  # Xanh cổ vịt trầm (Petrol Teal)
                {"bg": "#CBCDE0", "border": "#373C54"},  # Xanh chàm tro (Dusk Indigo)
                {"bg": "#CCD0C2", "border": "#424A35"},  # Rêu đá trầm (Muted Olive)
                {"bg": "#D0D4D8", "border": "#3D464F"},  # Xám than chì (Charcoal Slate)
                {"bg": "#CFC7CF", "border": "#443743"},  # Xám tro ánh tím trầm (Dusk Plum)
                {"bg": "#C4CDD3", "border": "#2D3E49"},  # Xanh xám bão trầm (Storm Slate)
                {"bg": "#C8CDD0", "border": "#343E43"},  # Xám thép kim loại (Pewter Steel)
            ]
            used_bgs = {v.get("bg") for v in self.camera_colors.values() if isinstance(v, dict)}
            available = [c for c in palette if c["bg"] not in used_bgs]
            if not available:
                available = palette

            # Ưu tiên gán màu cố định theo camera_id để nhất quán và phân biệt tối ưu giữa các camera
            try:
                digits = ''.join(filter(str.isdigit, cam_key))
                if digits:
                    cam_idx = (int(digits) - 1) % len(palette)
                    if palette[cam_idx]["bg"] not in used_bgs:
                        chosen = palette[cam_idx]
                    else:
                        chosen = available[0]
                else:
                    chosen = random.choice(available)
            except Exception:
                chosen = random.choice(available)

            self.camera_colors[cam_key] = chosen

        entry = self.camera_colors[cam_key]
        bg = entry["bg"]
        border = entry["border"]
        return f"QFrame#frame {{ background-color: {bg}; border: 2px solid {border}; border-radius: 6px; }}"

    def get_camera_label_style(self, camera_id):
        """Trả về stylesheet cho label_4 nổi bật đồng bộ với màu của camera."""
        if not hasattr(self, 'camera_colors'):
            self.camera_colors = {}

        cam_key = str(camera_id).strip()
        if cam_key not in self.camera_colors:
            self.get_camera_frame_style(camera_id)

        entry = self.camera_colors.get(cam_key, {})
        border = entry.get("border", "#364554")
        return f"QLabel {{ background-color: {border}; color: #ffffff; border: 1px solid {border}; border-radius: 4px; padding: 4px; font-weight: bold; }}"

    def create_camera_tab(self):

        tab = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(tab)
        inner_tab = QtWidgets.QTabWidget()
        layout.addWidget(inner_tab)
        return tab

    def add_child_window_follow_on_cameras(self,ui_mother,camera_id,model_id,total_cameras):
        ui_mother.label_3.setText(f"{self.i_code.upper()}")
        ui_mother.label.setText(f"{self.database.upper()}")
        num_cameras = total_cameras
        max_columns = 4
        screen_geo = QtWidgets.QApplication.primaryScreen().availableGeometry()
        screen_w = screen_geo.width()
        screen_h = screen_geo.height()
        if not hasattr(self, 'dict_camera_ui'):
            self.dict_camera_ui = {}

        if camera_id not in self.dict_camera_ui:
            child_window = QtWidgets.QMainWindow()
            ui_child = Ui_MainWindow_child()
            ui_child.setupUi(child_window)
            ui_child.label_4.setText(f"CAMERA [{camera_id}]")
            ui_child.label_4.setStyleSheet(self.get_camera_label_style(camera_id))
        
            child_frame = ui_child.frame
            child_frame.setStyleSheet(self.get_camera_frame_style(camera_id))
            child_frame.setParent(ui_mother.scrollAreaWidgetContents_display)
            
            child_frame.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            # Áp dụng chung 1 kích thước tối thiểu cho tất cả các khối để đảm bảo sự đồng đều
            child_frame.setMinimumHeight(int(screen_h * 0.4))

            old_layout = ui_mother.scrollAreaWidgetContents_display.layout()
            if old_layout is not None and not isinstance(old_layout, QtWidgets.QGridLayout):
                QtWidgets.QWidget().setLayout(old_layout)

            if not ui_mother.scrollAreaWidgetContents_display.layout():
                layout = QtWidgets.QGridLayout()
                layout.setContentsMargins(10, 10, 10, 10)
                layout.setSpacing(10)
                ui_mother.scrollAreaWidgetContents_display.setLayout(layout)
            frame_layout = ui_mother.scrollAreaWidgetContents_display.layout()
            row = self.frame_count // max_columns
            col = self.frame_count % max_columns
            frame_layout.addWidget(child_frame, row, col)
            self.frame_count += 1
            num_rows = (num_cameras - 1) // max_columns + 1
            for c in range(min(num_cameras, max_columns)):
                frame_layout.setColumnStretch(c, 1)
            for r in range(num_rows):
                frame_layout.setRowStretch(r, 1)
            self.dict_camera_ui[camera_id] = ui_child

        ui_child = self.dict_camera_ui[camera_id]
        self.dict_child[(f'camera-{camera_id}', f'model-{model_id}')] = {
            'ldi': ui_child.label_display_image,
            'ldr': ui_child.label_display_okng,
            'ldt': ui_child.label_display_time
        }
        
    def change_layout_mode(self):
        if not hasattr(self, 'ui_mother'): return
        display_mode = self.ui_mother.comboBox_display_mode.currentText()
        layout_mode = self.ui_mother.comboBox_layout_mode_by.currentText()
        show_layout = self.ui_mother.comboBox_show_ui.currentText()
        self.processor.save_display_mode(self.db_manager.cursor, self.db_manager.connect_db, self.item_code_id, display_mode, layout_mode,show_layout)
        keys = list(self.dict_child.keys())
        if not keys: return
        
        layout = self.ui_mother.scrollAreaWidgetContents_display.layout()
        if layout is not None:
            # Xóa các item cũ thay vì gọi deleteLater ngay lập tức cho an toàn
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()
            QtWidgets.QWidget().setLayout(layout)
            
        self.frame_count = 0
        self.dict_camera_ui = {}
        self.dict_child.clear()
        
        unique_cameras = list(set([k[0] for k in keys]))
        total_cameras = len(unique_cameras)
        total_models = len(keys)
        
        # Sort keys để tạo UI theo đúng thứ tự Camera và Model
        keys.sort(key=lambda x: (x[0], int(x[1].split('-')[1])))

        for cam_key, mod_key in keys:

            camera_name = cam_key.split('-')[1]
            model_number = int(mod_key.split('-')[1])

            if layout_mode == 'Layout Models':
                self.add_child_window_follow_on_models(self.ui_mother, camera_name, model_number, total_models)
            elif layout_mode == 'Layout Camera':
                self.add_child_window_follow_on_cameras(self.ui_mother, camera_name, model_number, total_cameras)

        QtWidgets.QApplication.processEvents()

        if hasattr(self, 'plc_handler') and self.plc_handler:
            self.plc_handler.clear_ui_caches()
            QtCore.QTimer.singleShot(60, self.plc_handler.re_render_latest_ui)

    
    def add_child_window_follow_on_models(self,ui_mother,camera_id,model_id,total_models):
        ui_mother.label_3.setText(f"{self.i_code.upper()}")
        ui_mother.label.setText(f"{self.database.upper()}")
        num_models = total_models
        max_columns = 4

        # Dùng màn hình hiện tại để tính toán kích thước động
        screen_geo = QtWidgets.QApplication.primaryScreen().availableGeometry()
        screen_w = screen_geo.width()
        screen_h = screen_geo.height()

        child_window = QtWidgets.QMainWindow()
        self.ui_child = Ui_MainWindow_child()
        self.ui_child.setupUi(child_window)

        self.ui_child.label_4.setText(f"CAMERA [{camera_id}] 🔗 MODEL [{model_id}]")
        self.ui_child.label_4.setStyleSheet(self.get_camera_label_style(camera_id))
        self.dict_child[(f'camera-{camera_id}', f'model-{model_id}')] = {
            'ldi': self.ui_child.label_display_image,
            'ldr': self.ui_child.label_display_okng,
            'ldt': self.ui_child.label_display_time
        }
    
        self.child_frame = self.ui_child.frame
        self.child_frame.setStyleSheet(self.get_camera_frame_style(camera_id))
        self.child_frame.setParent(ui_mother.scrollAreaWidgetContents_display)
        
        # Thiết lập policy thành Expanding ở cả hai chiều để layout tự quản lý độ co giãn
        self.child_frame.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        
        # Áp dụng chung 1 kích thước tối thiểu cho tất cả các khối để đảm bảo sự đồng đều
        self.child_frame.setMinimumHeight(int(screen_h * 0.5))

        old_layout = ui_mother.scrollAreaWidgetContents_display.layout()
        if old_layout is not None and not isinstance(old_layout, QtWidgets.QGridLayout):
            QtWidgets.QWidget().setLayout(old_layout)

        if not ui_mother.scrollAreaWidgetContents_display.layout():
            layout = QtWidgets.QGridLayout()
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(10)
            ui_mother.scrollAreaWidgetContents_display.setLayout(layout)

        frame_layout = ui_mother.scrollAreaWidgetContents_display.layout()

        row = self.frame_count // max_columns
        col = self.frame_count % max_columns

        frame_layout.addWidget(self.child_frame, row, col)
        self.frame_count += 1

        # Setup tỷ lệ dãn đều cho các cột và hàng
        num_rows = (num_models - 1) // max_columns + 1
        for c in range(min(num_models, max_columns)):
            frame_layout.setColumnStretch(c, 1)
        for r in range(num_rows):
            frame_layout.setRowStretch(r, 1)

    def apply_window_state(self, show_mode: str):
        """Áp dụng trạng thái cửa sổ hiển thị: Full Screen, Maximize, Minimize."""
        if not hasattr(self, 'MainWindoww') or self.MainWindoww is None:
            return
        mode_str = str(show_mode).strip()
        if mode_str == "Full Screen":
            self.MainWindoww.showFullScreen()
        elif mode_str == "Minimize":
            self.MainWindoww.showMinimized()
        elif mode_str == "Maximize":
            if self.MainWindoww.isFullScreen():
                self.MainWindoww.showNormal()
            self.MainWindoww.showMaximized()
        self.MainWindoww.raise_()
        self.MainWindoww.activateWindow()

    def save_show_ui_mode(self, show_mode: str):
        """Lưu trạng thái hiển thị vào database mode_display."""
        if not hasattr(self, 'ui_mother'):
            return
        display_mode = self.ui_mother.comboBox_display_mode.currentText()
        layout_mode = self.ui_mother.comboBox_layout_mode_by.currentText()
        try:
            if hasattr(self, 'processor') and hasattr(self.processor, 'save_display_mode'):
                self.processor.save_display_mode(
                    self.db_manager.cursor,
                    self.db_manager.connect_db,
                    self.item_code_id,
                    display_mode,
                    layout_mode,
                    str(show_mode).strip()
                )
        except Exception as e:
            _log.warning("Could not save show_ui_mode to database: %s", e)

    def toggle_fullscreen(self):
        """Phím tắt F11: Chuyển đổi qua lại giữa Full Screen và Maximize."""
        if not hasattr(self, 'MainWindoww') or self.MainWindoww is None:
            return
        if self.MainWindoww.isFullScreen():
            new_mode = "Maximize"
        else:
            new_mode = "Full Screen"
        self.apply_window_state(new_mode)
        if hasattr(self, 'ui_mother') and hasattr(self.ui_mother, 'comboBox_show_ui'):
            self.ui_mother.comboBox_show_ui.setCurrentText(new_mode)
        self.save_show_ui_mode(new_mode)

    def exit_fullscreen_on_esc(self):
        """Phím tắt Escape: Nếu đang ở Full Screen thì trở về Maximize."""
        if not hasattr(self, 'MainWindoww') or self.MainWindoww is None:
            return
        if self.MainWindoww.isFullScreen():
            new_mode = "Maximize"
            self.apply_window_state(new_mode)
            if hasattr(self, 'ui_mother') and hasattr(self.ui_mother, 'comboBox_show_ui'):
                self.ui_mother.comboBox_show_ui.setCurrentText(new_mode)
            self.save_show_ui_mode(new_mode)

    def on_show_ui_activated(self):
        """Xử lý khi người dùng tương tác chọn mục trên comboBox_show_ui."""
        if not hasattr(self, 'ui_mother') or not hasattr(self, 'MainWindoww'):
            return
        selected_mode = self.ui_mother.comboBox_show_ui.currentText()
        self.apply_window_state(selected_mode)
        self.save_show_ui_mode(selected_mode)

    def on_display_mode_activated(self):
        """Xử lý khi người dùng chọn Show/Hide Bounding Boxes."""
        if not hasattr(self, 'ui_mother'):
            return
        display_mode = self.ui_mother.comboBox_display_mode.currentText()
        layout_mode = self.ui_mother.comboBox_layout_mode_by.currentText()
        show_layout = self.ui_mother.comboBox_show_ui.currentText()
        try:
            if hasattr(self, 'processor') and hasattr(self.processor, 'save_display_mode'):
                self.processor.save_display_mode(
                    self.db_manager.cursor,
                    self.db_manager.connect_db,
                    self.item_code_id,
                    display_mode,
                    layout_mode,
                    show_layout
                )
        except Exception as e:
            _log.warning("Could not save display_mode to database: %s", e)

    def create_model_tabs(self, models, camera_name, camera_id, tab_widget_2, product_code_forms,total_models,total_cameras,item_code_id,progress_callback=None, base_progress=0, step_progress=0):

        ui_instances = {}
        ui_modelloader = {}
        path_instances = {}
        parameter_models = {}

        if not hasattr(self, 'MainWindoww'):
            self.MainWindoww = QtWidgets.QMainWindow()
            self.ui_mother = Ui_MainWindow_mother()
            self.ui_mother.setupUi(self.MainWindoww)

            # Đăng ký phím tắt F11 (toggle Full Screen <-> Maximize)
            self.shortcut_f11 = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_F11), self.MainWindoww)
            self.shortcut_f11.setContext(QtCore.Qt.ApplicationShortcut)
            self.shortcut_f11.activated.connect(self.toggle_fullscreen)

            # Đăng ký phím tắt Escape (thoát Full Screen về Maximize)
            self.shortcut_esc = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Escape), self.MainWindoww)
            self.shortcut_esc.setContext(QtCore.Qt.WindowShortcut)
            self.shortcut_esc.activated.connect(self.exit_fullscreen_on_esc)

            show_ui_default = "Maximize"
            try:
                self.db_manager.cursor.execute(
                    f"SELECT display_mode, layout_mode, show_layout FROM `{self.db_manager.db}`.mode_display WHERE item_code_id = %s",
                    (item_code_id,)
                )
                result_cursor = self.db_manager.cursor.fetchone()
                if result_cursor:
                    if result_cursor[0]:
                        self.ui_mother.comboBox_display_mode.setCurrentText(str(result_cursor[0]))
                    if result_cursor[1]:
                        self.ui_mother.comboBox_layout_mode_by.setCurrentText(str(result_cursor[1]))
                    if result_cursor[2]:
                        show_ui_default = str(result_cursor[2]).strip()
                        self.ui_mother.comboBox_show_ui.setCurrentText(show_ui_default)
                else:
                    self.ui_mother.comboBox_show_ui.setCurrentText(show_ui_default)
            except Exception as e:
                _log.warning("Could not read mode_display: %s", e)
                self.ui_mother.comboBox_show_ui.setCurrentText(show_ui_default)

            # Áp dụng trạng thái hiển thị ban đầu từ cấu hình đã lưu
            self.apply_window_state(show_ui_default)

            try:
                self.ui_mother.comboBox_layout_mode_by.currentIndexChanged.disconnect(self.change_layout_mode)
            except (TypeError, RuntimeError):
                pass
            self.ui_mother.comboBox_layout_mode_by.currentIndexChanged.connect(self.change_layout_mode)

            try:
                self.ui_mother.comboBox_show_ui.activated.disconnect(self.on_show_ui_activated)
            except (TypeError, RuntimeError):
                pass
            self.ui_mother.comboBox_show_ui.activated.connect(self.on_show_ui_activated)

            try:
                self.ui_mother.comboBox_display_mode.activated.disconnect(self.on_display_mode_activated)
            except (TypeError, RuntimeError):
                pass
            self.ui_mother.comboBox_display_mode.activated.connect(self.on_display_mode_activated)

        self.item_code_id = item_code_id
        layout_mode = self.ui_mother.comboBox_layout_mode_by.currentText()
        total_m = len(models)
        for model_index, _ in enumerate(models):
            if progress_callback and total_m > 0:
                cur_val = base_progress + int(step_progress * (model_index / total_m))
                progress_callback(cur_val, f"Đang tải giao diện (Model {model_index+1}/{total_m}) cho camera {camera_name}...")
                
            model_number = model_index + 1
            new_tab = QtWidgets.QMainWindow()
            
            ui_child = uicmain()
            ui_child.setupUi(new_tab)
            
            if progress_callback and total_m > 0:
                cur_val = base_progress + int(step_progress * ((model_index + 0.3) / total_m))
                progress_callback(cur_val, f"Đang gán giá trị (Model {model_index+1}/{total_m}) cho camera {camera_name}...")
        
            self.processor = Process_Model(ui_child)
            self.processor.assign_values(model_number, camera_name, self.i_code)
            self.processor.collect_device()
            
            if progress_callback and total_m > 0:
                cur_val = base_progress + int(step_progress * ((model_index + 0.6) / total_m))
                
                progress_callback(cur_val, f"Đang thêm cửa sổ phụ (Model {model_index+1}/{total_m}) cho camera {camera_name}...")
            
            if layout_mode == 'Layout Models':
                self.add_child_window_follow_on_models(self.ui_mother,camera_name,model_number,total_models)
            elif layout_mode == 'Layout Camera':
                self.add_child_window_follow_on_cameras(self.ui_mother,camera_name,model_number,total_cameras)
            
            if progress_callback and total_m > 0:
                cur_val = base_progress + int(step_progress * ((model_index + 0.8) / total_m))
                progress_callback(cur_val, f"Đang tải parameters & weight (Model {model_index+1}/{total_m}) cho camera {camera_name}...")
                
            self.processor.load_parameter_injection_safe(
                camera_id, model_number, 
                self.db_manager.cursor, self.db_manager.connect_db, 
                None, ui_instances
            )
            
            key = (f'camera-{camera_name}', f'model-{model_number}')
            self.total_key.append(key)
            ui_instances[key] = ui_child
            ui_modelloader[key] = self.processor.model_loader
            path_instances[key] = self.processor.path_object
            parameter_models[key] = self.processor.parametes_model
            self.dict_processors[key] = self.processor
            
            self._connect_model_signals(ui_child, self.processor)
            
            tab_widget_2.addTab(new_tab, f"Model {model_number}")
            product_code_forms.append(new_tab)

        return ui_instances, ui_modelloader, path_instances, parameter_models
    
        
    def _connect_model_signals(self, ui_child, processor):
        ui_child.pushButton_weight_pytorch.clicked.connect(lambda _: processor.browse_file())
        ui_child.pushButton_weight_pytorch_2.clicked.connect(lambda _: processor.load_model())
        ui_child.pushButton_save_data.clicked.connect(lambda _: processor.save_values_injection_safe(self.db_manager.cursor, self.db_manager.connect_db))
        ui_child.pushButton_edit_params.clicked.connect(lambda _: processor.toggle_lock(self.db_manager.cursor, self.db_manager.connect_db))
        ui_child.pushButton_load_parameters.clicked.connect(lambda _: processor.load_data_injection_safe())
        ui_child.pushButton_data_change.clicked.connect(lambda _: processor.browse_folder_activity_history())
        ui_child.pushButton_broswer_tensort.clicked.connect(lambda _: processor.browse_file_engine_tensorrt())
        ui_child.pushButton_classes_txt.clicked.connect(lambda _: processor.browse_file_classes())
        ui_child.pushButton_NG_image_original.clicked.connect(lambda _: processor.browse_folder_ng_img_original())
        ui_child.pushButton_NG_image_detected.clicked.connect(lambda _: processor.browse_folder_ng_img_detected())
        ui_child.pushButton_OK_image_original.clicked.connect(lambda _: processor.browse_folder_ok_img_original())
        ui_child.pushButton_OK_image_detected.clicked.connect(lambda _: processor.browse_folder_ok_img_detected())
        ui_child.pushButton_logging_image.clicked.connect(lambda _: processor.browse_folder_image_logging())
        if hasattr(ui_child, 'pushButton_add_tasks'):
            ui_child.pushButton_add_tasks.clicked.connect(lambda _: processor.open_task_workspace())
        if hasattr(ui_child, 'pushButton_data_calculator'):
            ui_child.pushButton_data_calculator.clicked.connect(lambda _: processor.open_task_workspace())
        
        def _update_runtime_ui(text):
            if text == 'PyTorch':
                ui_child.lineEdit_weight_tensorrt.setEnabled(False)
                ui_child.pushButton_broswer_tensort.setEnabled(False)
                ui_child.pushButton_model_tensorrt.setEnabled(False)
                ui_child.lineEdit_classes_txt.setEnabled(False)
                ui_child.pushButton_classes_txt.setEnabled(False)
                ui_child.pushButton_class_file.setEnabled(False)
                ui_child.lineEdit_weight_pytorch.setEnabled(True)
                ui_child.pushButton_weight_pytorch.setEnabled(True)
                ui_child.pushButton_weight_pytorch_2.setEnabled(True)
            elif text == 'TensorRT':
                ui_child.lineEdit_weight_tensorrt.setEnabled(True)
                ui_child.pushButton_broswer_tensort.setEnabled(True)
                ui_child.pushButton_model_tensorrt.setEnabled(True)
                ui_child.lineEdit_classes_txt.setEnabled(True)
                ui_child.pushButton_classes_txt.setEnabled(True)
                ui_child.pushButton_class_file.setEnabled(True)
                ui_child.lineEdit_weight_pytorch.setEnabled(False)
                ui_child.pushButton_weight_pytorch.setEnabled(False)
                ui_child.pushButton_weight_pytorch_2.setEnabled(False)
                
        ui_child.comboBox_model_runtime.currentTextChanged.connect(_update_runtime_ui)
        _update_runtime_ui(ui_child.comboBox_model_runtime.currentText())
        
    def create_automation_interface(self, camera_id, camera_name, item_code_id, models, tab_widget_2, product_code_forms):
        _translate = QtCore.QCoreApplication.translate
        automation_tab = QtWidgets.QMainWindow()
        self.automation_ui = AutomationInterface()
        self.automation_ui.setupUi(automation_tab)
        tab_widget_2.addTab(automation_tab, "PLC Settings")
        
        _signals_processor = signals(self.automation_ui)
        self.automation_ui.signals_processor = _signals_processor
        self.automation_ui.camera_id = camera_id
        self.automation_ui.camera_name = camera_name
        self.automation_ui.item_code_id = item_code_id
        self.automation_ui.models = models
        _automation_ui = self.automation_ui
        _automation_ui.comboBox_camera.setItemText(0, _translate("MainWindow", str(camera_name)))
        _automation_ui.comboBox_n_model.setItemText(0, _translate("MainWindow", str(len(models))))
        _automation_ui.comboBox_Itemcode.setItemText(0, _translate("MainWindow", str(self.i_code)))
        _automation_ui.spinBox_num_shot.valueChanged.connect(lambda _, processor=_signals_processor: processor.generate_table())
        _automation_ui.pushButton_admin.clicked.connect(lambda _, processor=_signals_processor: processor.toggle_lock(self.db_manager.cursor, self.db_manager.connect_db))
        dict_signals = _signals_processor.get_dict_mode_params(self.db_manager.cursor, camera_id)
        _signals_processor.load_data_plc(self.connect_plc.connection.cursor())
        mode_auto_id = _signals_processor.load_values_signal_default_mode_from_db_up_to_gui(self.db_manager.cursor, camera_id)
        _signals_processor.load_shotxmodel_from_db(self.db_manager.cursor, self.db_manager.connect_db, mode_auto_id,str(len(models)))
        _signals_processor.load_register_name_line_code(self.db_manager.cursor)
        shot_complete, dict_shot = _signals_processor.dict_shotxmodel()
        self.automation_ui.pushButton_applyshotxmodel.clicked.connect(lambda _: _signals_processor.save_shotxmodel_to_db(self.db_manager.cursor, self.db_manager.connect_db, item_code_id))
        self.automation_ui.pushButton_applysignalplc.clicked.connect(lambda _: _signals_processor.save_values_signal_to_db_from_gui(self.db_manager.cursor, self.db_manager.connect_db, item_code_id))
        self.automation_ui.pushButton_set_save_mode.clicked.connect(lambda _: _signals_processor.save_mode_auto(self.db_manager.cursor, self.db_manager.connect_db, item_code_id))
        def _on_load_mode(_=None, show_message=False):
            mode_name = _automation_ui.comboBox_mode_auto.currentText()
            mode_auto_id = _signals_processor.load_params_signals_from_gui_mapping_db(
                self.db_manager.cursor, camera_id, mode_name=mode_name, show_message=show_message
            )
            if mode_auto_id:
                _signals_processor.load_shotxmodel_from_db(
                    self.db_manager.cursor, self.db_manager.connect_db, mode_auto_id, str(len(models))
                )
                shot_complete, dict_shot = _signals_processor.dict_shotxmodel()
                cam_key = f'built-in-camera-{camera_name}'
                if hasattr(self, 'built_in_objects') and cam_key in self.built_in_objects:
                    self.built_in_objects[cam_key]['shot'] = dict_shot
                    self.built_in_objects[cam_key]['shot_complete'] = shot_complete
            if hasattr(_automation_ui, 'config_logger') and _automation_ui.config_logger:
                _automation_ui.config_logger.check_initial_db(
                    self.db_manager.cursor,
                    camera_id,
                    item_code_id,
                    _automation_ui.comboBox_mode_auto.currentText(),
                    _automation_ui.comboBox_Itemcode.currentText()
                )
        _on_load_mode(show_message=False)
        self.automation_ui.pushButton_load_params_from_mode.clicked.connect(lambda _: _on_load_mode(show_message=True))
        self.automation_ui.pushButton_apply_itemcode_assign.clicked.connect(lambda _: _signals_processor.save_register_name_line_code(self.db_manager.cursor, self.db_manager.connect_db))
        mode_dict = self.get_mode(_signals_processor,camera_id)

        #setup_counter_shot
        def apply_counter_shot_setup():
            _signals_processor.setup_counter_shot(self.db_manager.cursor, self.db_manager.connect_db, camera_id)

        self.automation_ui.pushButton_apply_setting_for_counter.clicked.connect(apply_counter_shot_setup)
        self.automation_ui.pushButton_load_setting_for_counter.clicked.connect(lambda _: _signals_processor.load_counter_shot(self.db_manager.cursor, camera_id))
        _signals_processor.load_counter_shot(self.db_manager.cursor, camera_id)
        
        #setup_mapping_mode
        self.automation_ui.pushButton_apply_Set_mode.clicked.connect(lambda _: _signals_processor.save_mapping_mode(self.db_manager.cursor, self.db_manager.connect_db, camera_id))
        self.automation_ui.pushButton_load_Set_mode.clicked.connect(lambda _: _signals_processor.load_mapping_mode(self.db_manager.cursor, camera_id))
        list_mode = _signals_processor.load_mapping_mode(self.db_manager.cursor, camera_id)
        #save_signal_transmission_and_receptions
        self.automation_ui.pushButton_apply_tranmission_reception.clicked.connect(lambda _: _signals_processor.save_all_data(self.db_manager.cursor, self.db_manager.connect_db,camera_id))
        self.automation_ui.pushButton_load_tranmission_reception.clicked.connect(lambda _: _signals_processor.load_all_data(self.db_manager.cursor, camera_id))
        _signals_processor.load_all_data(self.db_manager.cursor,camera_id)

        # Quét trạng thái CSDL ban đầu và hiển thị lên log realtime
        self.automation_ui.config_logger.check_initial_db(
            self.db_manager.cursor,
            camera_id,
            item_code_id,
            self.automation_ui.comboBox_mode_auto.currentText(),
            self.automation_ui.comboBox_Itemcode.currentText()
        )

        def _on_mode_combo_changed(mode_name):
            if hasattr(self.automation_ui, 'config_logger') and self.automation_ui.config_logger:
                self.automation_ui.config_logger.check_initial_db(
                    self.db_manager.cursor,
                    camera_id,
                    item_code_id,
                    mode_name,
                    self.automation_ui.comboBox_Itemcode.currentText()
                )
        self.automation_ui.comboBox_mode_auto.currentTextChanged.connect(_on_mode_combo_changed)

        product_code_forms.append(automation_tab)
        return dict_signals, shot_complete, dict_shot,mode_dict,self.automation_ui,list_mode
        
    def create_camera_device_interface_manual(self, camera_id, camera_name, item_code_id, tab_widget_2, product_code_forms):
        _translate = QtCore.QCoreApplication.translate
        device_tab = QtWidgets.QMainWindow()
        _device_tab_ui = Camera_Device()
        _device_tab_ui.setupUi(device_tab)
        tab_widget_2.addTab(device_tab, "Camera Device Setting")
        _mirror_tab_widget,dev = self.create_mirror_gui(tab_widget_2)
        driver = Process_Camera_Device(self.db_manager.connect_db, self.db_manager.cursor,self.automation_ui)
        device_launch = DICT_DEVICE_MANUAL[driver.query_camera_type(item_code_id, camera_name)[0]]
        device_camera = device_launch(device_tab, _device_tab_ui,_mirror_tab_widget)
        
        #auto action
        _device_tab_ui.comboBox_camera_id.setItemText(0, _translate("MainWindow", str({camera_name})))
        _device_tab_ui.pushButton_find_device.clicked.connect(partial(device_camera.enum_devices_public_class))
        _device_tab_ui.pushButton_Connect_Device.clicked.connect(partial(device_camera.open_device_camera_public_class))
        _device_tab_ui.pushButton_disconnect_dev.clicked.connect(partial(device_camera.close_device_public_class))
        _device_tab_ui.pushButton_set_load.clicked.connect(partial(device_camera.user_set_load_public_class))
        _device_tab_ui.pushButton_set_save.clicked.connect(partial(device_camera.set_param_public_class))
        _device_tab_ui.radioButton_check_continous.clicked.connect(partial(device_camera.set_continue_mode_public_class))
        _device_tab_ui.radioButton_triggermode.clicked.connect(partial(device_camera.set_software_trigger_mode_public_class))
        _device_tab_ui.pushButton_start_stream.clicked.connect(partial(device_camera.start_grabbing_public_class))
        _device_tab_ui.pushButton_stop_stream.clicked.connect(partial(device_camera.stop_grabbing_public_class))
        _device_tab_ui.pushButton_start_grab.clicked.connect(partial(device_camera.start_grabbing_public_class))
        _device_tab_ui.pushButton_stop_grab.clicked.connect(partial(device_camera.stop_grabbing_public_class))
        _device_tab_ui.radioButton_free_run.clicked.connect(partial(device_camera.start_grabbing_array_public_class))
        _device_tab_ui.pushButton_trigger_software.clicked.connect(partial(device_camera.trigger_once_public_class))
        _device_tab_ui.pushButton_trigger_get_img_buffer.clicked.connect(partial(device_camera.GetImgArayBuffer_public_class))
        _device_tab_ui.pushButton.clicked.connect(lambda _: driver.query_mode_id_to_user_index(item_code_id,_device_tab_ui))
        # device_camera.user_set_load_public_class()
        #mirror action
        _mirror_tab_widget.pushButton_streaming.clicked.connect(lambda _: dev.set_live_stream(True))
        if hasattr(device_camera, 'start_grabbing_public_class_mirror'):
            _mirror_tab_widget.pushButton_streaming.clicked.connect(partial(device_camera.start_grabbing_public_class_mirror))
            
        _mirror_tab_widget.pushButton_stop_grab.clicked.connect(lambda _: dev.set_live_stream(False))
        if hasattr(device_camera, 'stop_grabbing_public_class_mirror'):
            _mirror_tab_widget.pushButton_stop_grab.clicked.connect(partial(device_camera.stop_grabbing_public_class_mirror))
            
        if hasattr(device_camera, 'start_grabbing_array_public_class_mirror'):
            _mirror_tab_widget.pushButton_start_grab.clicked.connect(partial(device_camera.start_grabbing_array_public_class_mirror))
            
        if hasattr(device_camera, 'GetImgArayBuffer_public_class_mirror'):
            _mirror_tab_widget.pushButton_capture.clicked.connect(partial(device_camera.GetImgArayBuffer_public_class_mirror))

        #mirror action with line
        _mirror_tab_widget.pushButton_show_crossline.setCheckable(True)
        _mirror_tab_widget.pushButton_drag_crossline.setCheckable(True)
        _mirror_tab_widget.pushButton_show_gridline.setCheckable(True)
        _mirror_tab_widget.pushButton_broswer_file_img.clicked.connect(partial(dev.browse_file))
        _mirror_tab_widget.pushButton_show_crossline.toggled.connect(partial(dev.on_toggle_show_cross))
        _mirror_tab_widget.pushButton_drag_crossline.toggled.connect(partial(dev.on_toggle_drag_cross))
        _mirror_tab_widget.pushButton_show_gridline.toggled.connect(partial(dev.on_toggle_show_grid))
        _mirror_tab_widget.pushButton_reset_cross.clicked.connect(partial(dev.reset_center))
        _mirror_tab_widget.pushButton_run_check.clicked.connect(lambda: dev.run_check(dev.image))
        _mirror_tab_widget.pushButton_streaming.clicked.connect(lambda _: dev.start_stream_detect())
        _mirror_tab_widget.pushButton_stop_grab.clicked.connect(lambda _: dev.stop_stream_detect())
        _mirror_tab_widget.pushButton_load_setting.clicked.connect(lambda _: dev.load_params(item_code_id,camera_name))
        _mirror_tab_widget.pushButton_appl_setting.clicked.connect(lambda _: dev.save_params(item_code_id,camera_name))
        dev.load_params(item_code_id,camera_name)
        product_code_forms.append(device_tab)
        return device_camera,dev

    def create_mirror_gui(self,tab_widget_2):
        _translate = QtCore.QCoreApplication.translate
        mirror_tab_widget = QtWidgets.QMainWindow()
        self._mirror_tab_widget = Mirror_Tab_Detect()
        self._mirror_tab_widget.setupUi(mirror_tab_widget)
        tab_widget_2.addTab(mirror_tab_widget, "Mirror Settings")
        dev = Process_Mirror_Device(self._mirror_tab_widget,self.db_manager.connect_db,self.db_manager.cursor)
        tab_widget_2.mirror_device = dev
        self._mirror_tab_widget.mirror_device = dev

        return self._mirror_tab_widget,dev
    
    def auto_initial_device(self, camera_id, camera_name, item_code_id, tab_widget_2, product_code_forms, dict_signals, progress_callback=None):
        driver = Process_Camera_Device(self.db_manager.connect_db, self.db_manager.cursor, self.automation_ui)
        device_type, serial, conn_type, ip_address = driver.query_camera_type(item_code_id, camera_name)
        device_launch = DICT_DEVICE_AUTO[device_type]
        identifier = ip_address if conn_type == 'GigE' else serial
        conn_mode = 'GigE' if conn_type == 'GigE' else 'USB'
        plc_signals = {}
        for sig in ['run', 'ready', 'busy']:
            addr, _, _, _, write_reg, val_on, val_off = self.return_reg(camera_name, name_signal=sig, mode_name='Auto 1')
            if addr is None or write_reg is None:
                _log.warning(
                    "[auto_initial_device] Camera %s: signal '%s' chưa được cấu hình trong DB — "
                    "bỏ qua việc đọc/ghi PLC signal. Hãy setup MODE_AUTO trước.",
                    camera_name, sig
                )
                return
            plc_signals[sig] = {
                'reg': f"{addr}{write_reg}",
                'on': val_on,
                'off': val_off
            }
        retry_interval = 1
        attempt = 0

        while True:
            attempt += 1
            plc = self.connect_plc.driver_loader
            
            if plc:
                try:
                    _log.info("[Camera %s] Lần thử %s: Đang kết nối (%s - %s)...", camera_name, attempt, conn_mode, identifier)
                    self.device = device_launch(identifier, conn_mode)
                    self.device.enum_devices_class()
                    self.device.open_device_camera_class()
                    self.device.start_grabbing_array_class()
                    if plc_signals['ready']['reg'] and plc_signals['ready']['on']:
                        plc.write_plc(str(plc_signals['ready']['reg']), int(plc_signals['ready']['on']))
                    if plc_signals['run']['reg'] and plc_signals['run']['on']:
                        plc.write_plc(str(plc_signals['run']['reg']),   int(plc_signals['run']['on']))
                    if plc_signals['busy']['reg'] and plc_signals['busy']['off']:
                        plc.write_plc(str(plc_signals['busy']['reg']),   int(plc_signals['busy']['off']))
                    
                    _log.info("[Camera %s] ✅ Kết nối thành công sau %s lần thử!", camera_name, attempt)
                    return self.device
                    
                except Exception as e:
                    _log.warning("[Camera %s] ❌ Lần thử %s thất bại: %s", camera_name, attempt, e)
                    if progress_callback:
                        progress_callback(None, f"Camera {camera_name} kết nối thất bại (Lần {attempt}). Đang thử lại...")
                    if plc_signals['ready']['reg'] and plc_signals['ready']['off']:
                        plc.write_plc(str(plc_signals['ready']['reg']), int(plc_signals['ready']['off']))
                    if plc_signals['run']['reg'] and plc_signals['run']['off']:
                        plc.write_plc(str(plc_signals['run']['reg']),   int(plc_signals['run']['off']))
                    if plc_signals['busy']['reg'] and plc_signals['busy']['off']:
                        plc.write_plc(str(plc_signals['busy']['reg']),   int(plc_signals['busy']['on']))
                    _log.info("[Camera %s] Thử lại sau %s giây...", camera_name, retry_interval)
                    time.sleep(retry_interval)
                    if attempt == 3:
                        _log.error("[Camera %s] Kết nối thất bại sau %s lần thử!", camera_name, attempt)
                        return
            else:
                _log.warning("[Camera %s] PLC Driver chưa sẵn sàng...", camera_name)
                if progress_callback:
                    progress_callback(None, f"PLC Driver chưa sẵn sàng (Lần {attempt}). Đang đợi...")
                if attempt == 3:
                    _log.error("[Camera %s] PLC Driver chưa sẵn sàng sau %s lần thử!", camera_name, attempt)
                    return
    
    def get_mode(self,signals_processor,camera_id):
        return signals_processor.collect_dict_from_mode_auto(self.db_manager.cursor, camera_id)
    
    def create_auto_log_tab(self,tab_widget_2,built_in_objects,camera_id,camera_name,item_code_id,total_key,product_code_forms,process):
        _translate = QtCore.QCoreApplication.translate
        auto_log_tab = QtWidgets.QMainWindow()
        auto_log_tab_ui = Auto_Logging()
        auto_log_tab_ui.setupUi(auto_log_tab)
        tab_widget_2.addTab(auto_log_tab, "Auto Logging")
        product_code_forms.append(auto_log_tab)
        auto_log_tab_ui.comboBox_item_code.clear()
        auto_log_tab_ui.comboBox_item_code.addItem(str(self.i_code))

        logging_process = AutoLoggingProcess(auto_log_tab_ui,self.connect_plc.connection.cursor(),process,built_in_objects)
        # Giữ tham chiếu mạnh cho từng camera, không bị GC khi camera sau tạo tab
        if not hasattr(self, 'logging_processes'):
            self.logging_processes = {}
        self.logging_processes[(camera_id, camera_name)] = logging_process
        self.logging_process = logging_process  # giữ tương thích code cũ

        logging_process.load_data_from_db(camera_id,self.connect_plc.connection)
        auto_log_tab_ui.pushButton_broswer_folder.clicked.connect(logging_process.broswer_folder)
        auto_log_tab_ui.pushButton_import.clicked.connect(lambda _=False, lp=logging_process, cn=camera_name: lp.generate_table([k for k in self.total_key if k[0] == f'camera-{cn}']))
        auto_log_tab_ui.tableWidget.itemSelectionChanged.connect(logging_process.show_image_preview)
        auto_log_tab_ui.pushButton_set_save.clicked.connect(lambda _=False, lp=logging_process: lp.save_values_auto_log_to_db(camera_id,self.connect_plc.connection))
        auto_log_tab_ui.pushButton_set_load.clicked.connect(lambda _=False, lp=logging_process: lp.load_data_from_db(camera_id,self.connect_plc.connection))

        return auto_log_tab_ui


    def set_camera_data(self, camera_name, ui_instances, ui_modelloader, path_instances, 
        dict_signals, shot_complete, dict_shot, parameter_models,automation_ui,device=None,dev=None,auto_logging_ui=None):
        key = f'built-in-camera-{camera_name}'
        self.built_in_objects[key] = {
            'pyuic': ui_instances,
            'model_loader': ui_modelloader,
            'path_instances': path_instances,
            'signals': dict_signals if isinstance(dict_signals, dict) else {},
            'shot': dict_shot,
            'shot_complete': shot_complete,
            'parameter_models_x': parameter_models,
            'device': device,
            'automation_ui': automation_ui,
            'mirror_dev': dev,
            'auto_logging_ui': auto_logging_ui,
            'signals_processor': getattr(automation_ui, 'signals_processor', None),
            'camera_id': getattr(automation_ui, 'camera_id', None),
            'camera_name': camera_name,
            'item_code_id': getattr(automation_ui, 'item_code_id', None),
            'models': getattr(automation_ui, 'models', None),
        }

    def set_signals_device_camera(self, camera_name,dict_signals):
        key = f'built-in-camera-{camera_name}'
        self.built_in_dict_device[key] = {
            'signals': dict_signals,
        }
    
    def set_mode_data(self, camera_name, mode_dict, device=None):
        key = f'built-in-camera-{camera_name}'
        self.built_in_modes[key] = {
            'modes': mode_dict,
            'device': device
        }

    def set_list_mapping_mode(self,camera_name,list_mode):
        key = f'built-in-camera-{camera_name}'
        self.built_in_mapping_mode[key] = {
            'mapping': list_mode,
        }

    def return_reg(self,name_camera,name_signal=None,mode_name=None):
        try:
            cam_data = self.built_in_dict_device.get(f'built-in-camera-{name_camera}', {})
            signals = cam_data.get('signals', {}) if cam_data else {}
            mode_data = signals.get(mode_name, {}) if signals else {}
            values_signals = mode_data.get('values_signals', {}) if mode_data else {}
            reg = values_signals.get(name_signal, {}) if values_signals else {}
            
            if not reg:
                return None, None, None, None, None, None, None

            address = reg.get('address')
            read_register = reg.get('read_register')
            read_value_on = reg.get('read_value_on')
            read_value_off = reg.get('read_value_off')
            write_register = reg.get('write_register')
            write_value_on = reg.get('write_value_on')
            write_value_off = reg.get('write_value_off')
            return address, read_register, read_value_on, read_value_off, write_register, write_value_on, write_value_off
        except Exception as e:
            _log.error("Error in return_reg: %s", e)
            return None, None, None, None, None, None, None

