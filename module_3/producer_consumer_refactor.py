"""
producer_consumer_refactor.py
==============================
Refactor theo pattern Producer / Consumer:

  TRƯỚC (tuần tự — chậm):
      trigger → take_image() → process_image_func() → emit
                [camera chờ model xong mới chụp tiếp]

  SAU (song song — nhanh hơn):
      trigger → take_image() → queue_image.put()     ← Producer (camera thread)
                                    ↓
                              ImageConsumerWorker     ← Consumer (thread riêng)
                                    ↓
                              process_image_func()
                                    ↓
                              emit update_display

  Lợi ích:
    - Camera sẵn sàng chụp shot tiếp theo ngay sau khi put vào queue
    - Model inference chạy trên thread riêng, không block camera
    - Nhiều camera vẫn song song qua self.executor như cũ
"""

import time
import queue
import logging
import threading
import traceback
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

_log = logging.getLogger(__name__)


# ===========================================================================
# Data class — gói toàn bộ context cần thiết để xử lý 1 ảnh
# ===========================================================================

@dataclass
class ImageTask:
    """Đơn vị dữ liệu đưa vào queue — chứa đủ thông tin để Consumer xử lý."""
    key         : str
    key_model   : tuple
    raw_image   : np.ndarray
    model_loader: Any
    pyuic       : Any
    values      : dict
    current_count: int
    start_time  : float = field(default_factory=time.perf_counter)


# ===========================================================================
# Consumer Worker — chạy trên thread riêng, lấy ImageTask từ queue xử lý
# ===========================================================================

class ImageConsumerWorker:
    """
    Chạy vòng lặp lấy ImageTask từ queue → xử lý model → emit kết quả.
    Mỗi key (camera) có 1 consumer riêng để tránh lẫn lộn thứ tự shot.
    """

    def __init__(self, plc_handler, key: str):
        self.plc_handler = plc_handler
        self.key         = key
        self.running     = True
        self._thread     = threading.Thread(
            target=self._loop,
            name=f"ImageConsumer-{key}",
            daemon=True,
        )

    def start(self): self._thread.start()

    def stop(self):
        self.running = False
        # Đẩy sentinel None để unblock queue.get()
        self.plc_handler.queue_image.put(None)

    def _loop(self):
        _log.info("[Consumer-%s] Started", self.key)
        while self.running:
            try:
                task: ImageTask | None = self.plc_handler.queue_image.get(timeout=1.0)
                if task is None:          # sentinel → dừng
                    break
                if task.key != self.key:  # không phải task của camera này
                    self.plc_handler.queue_image.put(task)  # trả lại queue
                    continue
                self._process(task)
            except queue.Empty:
                continue
            except Exception as e:
                _log.error("[Consumer-%s] Exception: %s", self.key, e)
                traceback.print_exc()

    def _process(self, task: ImageTask):
        h = self.plc_handler

        if not task.raw_image.flags['C_CONTIGUOUS']:
            task.raw_image = np.ascontiguousarray(task.raw_image)

        result_img, flag, list_register = h.processor.processor.process_image_func(
            task.raw_image, task.model_loader, task.pyuic
        )

        result_text = f'RESULT: {"OK" if flag else "NG"}'
        cv2.putText(result_img, result_text, (25, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 5,
                    (0, 255, 0) if flag else (0, 0, 255), 10)

        elapsed = (time.perf_counter() - task.start_time) * 1000
        h.signals.update_display.emit(
            [(task.key_model, task.pyuic, result_img, flag, result_text, list_register)],
            f"Time : {elapsed:.2f} ms"
        )

        h._accumulate_registers(task.key, list_register or [])

        shot_complete = task.values.get('shot_complete', 0)
        if task.current_count >= shot_complete:
            all_registers = h._pop_registers(task.key)
            try:
                with h._signal_rwlock.read():
                    comp_sig = dict(h.dict_signal_complete[task.key]['complete'])
                if isinstance(all_registers, dict):
                    for reg, val in all_registers.items():
                        if reg and str(reg).strip():
                            h.layer_core.driver_loader.write_plc(str(reg).strip(), val)
                else:
                    for reg in all_registers:
                        if reg and str(reg).strip():
                            h.layer_core.driver_loader.write_plc(str(reg).strip(), 1)
                h.layer_core.driver_loader.write_plc(
                    str(comp_sig['reg']), int(comp_sig['on'])
                )
            except KeyError:
                pass
            h._reset_counter(task.key)
            _log.info('[%s] Complete shot %s | registers: %s | %.2fms',
                      task.key, task.current_count, len(all_registers), elapsed)


# ===========================================================================
# Thay đổi trong PLCHandler
# ===========================================================================

class PLCHandlerChanges:
    """
    Chỉ liệt kê những chỗ cần thêm/sửa trong PLCHandler gốc.
    Không phải class độc lập — paste từng phần vào đúng chỗ.
    """

    # -----------------------------------------------------------------------
    # [THÊM VÀO __init__] — sau các dòng attribute hiện tại
    # -----------------------------------------------------------------------
    def __init_additions__(self):
        # Queue dùng chung cho tất cả camera
        # maxsize=0 → không giới hạn; đặt maxsize=N để tránh tích lũy quá nhiều
        self.queue_image: queue.Queue = queue.Queue(maxsize=0)

        # Dict consumer theo key — mỗi camera 1 consumer
        self._consumers: dict[str, ImageConsumerWorker] = {}

    # -----------------------------------------------------------------------
    # [SỬA] start_monitoring — khởi động consumer khi biết danh sách camera
    # -----------------------------------------------------------------------
    def start_monitoring(self):
        self.worker_thread.start()
        # Consumer sẽ được tạo lazily trong take_image khi camera đầu tiên kích hoạt
        # hoặc tạo sẵn ở đây nếu đã biết danh sách key:
        #
        # for key in self.built_in_objects:
        #     self._start_consumer(key)

    # -----------------------------------------------------------------------
    # [THÊM VÀO CLASS] — helper tạo consumer lazily
    # -----------------------------------------------------------------------
    def _ensure_consumer(self, key: str):
        """Tạo và start consumer cho key nếu chưa có."""
        if key not in self._consumers:
            consumer = ImageConsumerWorker(self, key)
            self._consumers[key] = consumer
            consumer.start()
            _log.info("[PLCHandler] Consumer started for key: %s", key)

    # -----------------------------------------------------------------------
    # [SỬA] stop_monitoring — dừng tất cả consumer
    # -----------------------------------------------------------------------
    def stop_monitoring(self):
        self.worker_thread.running = False
        self.worker_thread.quit()
        self.worker_thread.wait()

        # Dừng tất cả consumer
        for key, consumer in self._consumers.items():
            consumer.stop()
            _log.info("[PLCHandler] Consumer stopped for key: %s", key)
        self._consumers.clear()

        self.executor.shutdown(wait=True)

    # -----------------------------------------------------------------------
    # [THAY THẾ] take_image — Producer: chụp ảnh → put vào queue, không return
    # -----------------------------------------------------------------------
    def take_image(self, device, key: str, timer: float,
                   key_model=None, model_loader=None, pyuic=None,
                   values=None, current_count=0):
        """
        Producer: chụp ảnh → đóng gói thành ImageTask → put vào queue_image.
        Không return ảnh — Consumer sẽ lấy từ queue để xử lý.
        """
        # Đảm bảo consumer đã chạy cho key này
        self._ensure_consumer(key)

        with self._signal_rwlock.read():
            signals = dict(self.dict_signal_complete.get(key, {}))

        write = self.layer_core.driver_loader.write_plc

        if signals:
            if 'gate'  in signals: write(str(signals['gate']['reg']),  int(signals['gate']['on']))
            if 'busy'  in signals: write(str(signals['busy']['reg']),  int(signals['busy']['on']))
            if 'ready' in signals: write(str(signals['ready']['reg']), int(signals['ready']['off']))

        time.sleep(timer)

        raw_image = device.Retrieve_Image_Buffer()

        if signals:
            if 'gate'  in signals: write(str(signals['gate']['reg']),  int(signals['gate']['off']))
            if 'busy'  in signals: write(str(signals['busy']['reg']),  int(signals['busy']['off']))
            if 'ready' in signals: write(str(signals['ready']['reg']), int(signals['ready']['on']))

        if raw_image is None:
            _log.warning("[%s] Retrieve_Image_Buffer returned None", key)
            return

        # Đóng gói context → đưa vào queue cho Consumer xử lý
        task = ImageTask(
            key          = key,
            key_model    = key_model,
            raw_image    = raw_image,
            model_loader = model_loader,
            pyuic        = pyuic,
            values       = values,
            current_count= current_count,
            start_time   = time.perf_counter(),
        )
        self.queue_image.put(task)
        _log.debug("[%s] ImageTask queued (shot %s)", key, current_count)

    # -----------------------------------------------------------------------
    # [THAY THẾ] handle_result_mode_auto — chỉ còn nhiệm vụ Producer
    # Xử lý model đã chuyển sang Consumer
    # -----------------------------------------------------------------------
    def handle_result_mode_auto(self, key: str, values: dict) -> None:
        try:
            start_time = time.perf_counter()

            current_count = self._increment_counter(key)
            _log.info('Counter Shot [%s]: %s', key, current_count)

            num_model = values.get('shot', {}).get(str(current_count))
            if not num_model:
                return

            device = values.get('device')
            if not device:
                self._warn("Cảnh báo", "Kiểm tra kết nối thiết bị Camera")
                return

            camera       = key.removeprefix('built-in-')
            key_model    = (camera, f'model-{num_model}')
            model_loader = values.get('model_loader', {}).get(key_model)
            pyuic        = values.get('pyuic', {}).get(key_model)
            automation_ui= values.get('automation_ui')

            if not model_loader or not pyuic or not automation_ui:
                _log.warning('[%s] Missing model_loader or pyuic for %s', key, key_model)
                return

            timer = values.get('timer', 0.0)

            # Chụp ảnh → put vào queue → return ngay
            # Consumer sẽ xử lý tiếp trên thread riêng
            self.take_image(
                device        = device,
                key           = key,
                timer         = timer,
                key_model     = key_model,
                model_loader  = model_loader,
                pyuic         = pyuic,
                values        = values,
                current_count = current_count,
            )

            _log.debug('[%s] take_image done in %.2fms, handed to consumer',
                       key, (time.perf_counter() - start_time) * 1000)

        except Exception as e:
            _log.error("[%s] Exception: %s", key, e)
            traceback.print_exc()
