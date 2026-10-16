"""
Logic cho tab "PLC Signal Test" (tab_3 trong auto_init_.ui).

Cách dùng
---------
1) Cho class cửa sổ kế thừa PlcTestTabMixin:

       class MainWindow(QMainWindow, PlcTestTabMixin):
           def __init__(self):
               super().__init__()
               uic.loadUi("auto_init_.ui", self)      # giữ nguyên các object name cũ
               self.setup_plc_test_tab()

2) Trong hàm xử lý kết nối ở tab "Auto Connect Device Control":

       self.set_plc_test_connected(True,  "KEYENCE", "192.168.1.10", 8051)   # khi kết nối OK
       self.set_plc_test_connected(False)                                    # khi ngắt kết nối

3) Nối driver PLC thật bằng cách override 2 hàm (hoặc sửa trực tiếp):

       def plc_read_register(self, register, data_type):  ->  trả về giá trị
       def plc_write_register(self, register, data_type, value)

   Mặc định 2 hàm này chạy chế độ DEMO (lưu giá trị trong bộ nhớ) để bạn thử giao diện
   ngay mà chưa cần PLC. Ném Exception khi lỗi, giao diện sẽ tự hiện trạng thái ERROR.
"""
import struct
import time

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

# (min, max) cho từng kiểu số nguyên
_INT_RANGES = {
    "UINT16": (0, 0xFFFF),
    "INT16": (-0x8000, 0x7FFF),
    "UINT32": (0, 0xFFFFFFFF),
    "INT32": (-0x80000000, 0x7FFFFFFF),
}

_LOG_COLORS = {"SYS": "#94A3B8", "TX": "#38BDF8", "RX": "#34D399", "ERR": "#F87171"}


class PlcTestTabMixin:

    # ------------------------------------------------------------------ setup
    def setup_plc_test_tab(self):
        self._plc_connected = False
        self._plc_sim = {}                                   # bộ nhớ giả lập (DEMO)
        self._plc_poll_timer = QTimer(self)
        self._plc_poll_timer.timeout.connect(self.on_plc_receive_clicked)

        self.pushButton_plc_receive.clicked.connect(self.on_plc_receive_clicked)
        self.pushButton_plc_send.clicked.connect(self.on_plc_send_clicked)
        self.pushButton_plc_clear_log.clicked.connect(self.textEdit_plc_log.clear)
        self.pushButton_plc_copy_log.clicked.connect(self._plc_copy_log)
        self.checkBox_read_continuous.toggled.connect(self._plc_toggle_polling)
        self.spinBox_read_interval.valueChanged.connect(self._plc_interval_changed)
        # Enter trong ô nhập = bấm nút
        self.lineEdit_read_register.returnPressed.connect(self.on_plc_receive_clicked)
        self.lineEdit_write_value.returnPressed.connect(self.on_plc_send_clicked)
        self.lineEdit_write_register.returnPressed.connect(self.lineEdit_write_value.setFocus)

        self.set_plc_test_connected(False)

    # ------------------------------------------------- kết nối / trạng thái chung
    def set_plc_test_connected(self, connected, module="", ip="", port=""):
        """Gọi từ tab Auto Connect Device Control khi kết nối / ngắt kết nối PLC."""
        self._plc_connected = bool(connected)
        self.groupBox_plc_read.setEnabled(self._plc_connected)
        self.groupBox_plc_write.setEnabled(self._plc_connected)

        if self._plc_connected:
            self._plc_set_property(self.label_plc_conn_status, "state", "connected")
            self.label_plc_conn_status.setText("\u25CF  CONNECTED")
            self.label_plc_conn_target.setText(f"{module}  \u00B7  {ip}:{port}")
            self._plc_log("SYS", f"Connected to {module} at {ip}:{port}")
        else:
            self._plc_stop_polling()
            self._plc_set_property(self.label_plc_conn_status, "state", "disconnected")
            self.label_plc_conn_status.setText("\u25CF  DISCONNECTED")
            self.label_plc_conn_target.setText(
                "Connect a PLC in \u201CAuto Connect Device Control\u201D first")
            if self.textEdit_plc_log.toPlainText():
                self._plc_log("SYS", "PLC disconnected")

    # ------------------------------------------------------ hook driver PLC thật
    def plc_read_register(self, register, data_type):
        """TODO: thay bằng lệnh đọc PLC thật. Trả về giá trị (int/float/bool)."""
        return self._plc_sim.get(register.upper(), 0)

    def plc_write_register(self, register, data_type, value):
        """TODO: thay bằng lệnh ghi PLC thật. Ném Exception nếu thất bại."""
        self._plc_sim[register.upper()] = value

    # ------------------------------------------------------------------- READ
    def on_plc_receive_clicked(self):
        if not self._plc_connected:
            return
        register = self.lineEdit_read_register.text().strip()
        dtype = self.comboBox_read_data_type.currentText()
        if not register:
            self._plc_set_badge(self.label_read_status, "error", "ENTER A REGISTER")
            self.lineEdit_read_register.setFocus()
            return

        self._plc_set_badge(self.label_read_status, "pending", "READING\u2026")
        t0 = time.perf_counter()
        try:
            value = self.plc_read_register(register, dtype)
            ms = (time.perf_counter() - t0) * 1000
        except Exception as exc:                              # noqa: BLE001
            self.lineEdit_read_value.setText("\u2014")
            self._plc_set_badge(self.label_read_status, "error", "READ FAILED")
            self._plc_log("ERR", f"READ {register} [{dtype}] -> {exc}")
            self._plc_stop_polling()
            return

        text = self._plc_format_value(value, dtype)
        self.lineEdit_read_value.setText(text)
        stamp = time.strftime("%H:%M:%S")
        self._plc_set_badge(self.label_read_status, "ok", f"OK  \u00B7  {ms:.0f} ms  \u00B7  {stamp}")
        # khi polling chỉ ghi log lúc giá trị thay đổi để log không bị tràn
        if not self._plc_poll_timer.isActive() or text != getattr(self, "_plc_last_poll_text", None):
            self._plc_log("RX", f"READ  {register} [{dtype}] = {text}   ({ms:.0f} ms)")
        self._plc_last_poll_text = text

    # ------------------------------------------------------------------ WRITE
    def on_plc_send_clicked(self):
        if not self._plc_connected:
            return
        register = self.lineEdit_write_register.text().strip()
        dtype = self.comboBox_write_data_type.currentText()
        raw = self.lineEdit_write_value.text().strip()

        if not register:
            self._plc_set_badge(self.label_write_result, "error", "ENTER A REGISTER")
            self.lineEdit_write_register.setFocus()
            return
        try:
            value = self._plc_parse_value(raw, dtype)
        except ValueError as exc:
            self._plc_set_badge(self.label_write_result, "error", f"INVALID VALUE")
            self._plc_log("ERR", f"WRITE {register} [{dtype}] rejected: {exc}")
            self.lineEdit_write_value.setFocus()
            return

        self._plc_set_badge(self.label_write_result, "pending", "SENDING\u2026")
        QApplication.processEvents()
        t0 = time.perf_counter()
        try:
            self.plc_write_register(register, dtype, value)
            ms = (time.perf_counter() - t0) * 1000
        except Exception as exc:                              # noqa: BLE001
            self._plc_set_badge(self.label_write_result, "error", "SEND FAILED")
            self._plc_log("ERR", f"WRITE {register} [{dtype}] = {raw} -> {exc}")
            return

        self._plc_log("TX", f"WRITE {register} [{dtype}] = {self._plc_format_value(value, dtype)}   ({ms:.0f} ms)")

        if self.checkBox_write_verify.isChecked():
            try:
                back = self.plc_read_register(register, dtype)
            except Exception as exc:                          # noqa: BLE001
                self._plc_set_badge(self.label_write_result, "error", "VERIFY FAILED")
                self._plc_log("ERR", f"VERIFY {register} -> {exc}")
                return
            if self._plc_values_equal(back, value, dtype):
                self._plc_set_badge(self.label_write_result, "ok", "SENT  \u00B7  VERIFIED")
                self._plc_log("RX", f"VERIFY {register} = {self._plc_format_value(back, dtype)}  OK")
            else:
                self._plc_set_badge(self.label_write_result, "error", "MISMATCH")
                self._plc_log("ERR", f"VERIFY {register}: wrote {value}, read back {back}")
        else:
            self._plc_set_badge(self.label_write_result, "ok", f"SENT  \u00B7  {time.strftime('%H:%M:%S')}")

    # ---------------------------------------------------------------- polling
    def _plc_toggle_polling(self, on):
        if on and self._plc_connected:
            self._plc_poll_timer.start(self.spinBox_read_interval.value())
            self.on_plc_receive_clicked()
        else:
            self._plc_poll_timer.stop()

    def _plc_interval_changed(self, ms):
        if self._plc_poll_timer.isActive():
            self._plc_poll_timer.start(ms)

    def _plc_stop_polling(self):
        self._plc_poll_timer.stop()
        if self.checkBox_read_continuous.isChecked():
            self.checkBox_read_continuous.blockSignals(True)
            self.checkBox_read_continuous.setChecked(False)
            self.checkBox_read_continuous.blockSignals(False)

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _plc_set_property(widget, name, value):
        widget.setProperty(name, value)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _plc_set_badge(self, label, state, text):
        label.setText(text)
        self._plc_set_property(label, "state", state)

    def _plc_log(self, level, message):
        color = _LOG_COLORS.get(level, "#CBD5E1")
        stamp = time.strftime("%H:%M:%S")
        self.textEdit_plc_log.append(
            f'<span style="color:#64748B">{stamp}</span>&nbsp;&nbsp;'
            f'<span style="color:{color}"><b>{level:<3}</b></span>&nbsp;&nbsp;'
            f'<span style="color:#E2E8F0">{message}</span>')

    def _plc_copy_log(self):
        QApplication.clipboard().setText(self.textEdit_plc_log.toPlainText())

    @staticmethod
    def _plc_parse_value(raw, dtype):
        if raw == "":
            raise ValueError("value is empty")
        if dtype == "BOOL":
            low = raw.lower()
            if low in ("1", "true", "on"):
                return True
            if low in ("0", "false", "off"):
                return False
            raise ValueError("BOOL accepts 0/1, ON/OFF, TRUE/FALSE")
        if dtype == "FLOAT32":
            try:
                return struct.unpack("<f", struct.pack("<f", float(raw)))[0]
            except (ValueError, OverflowError, struct.error):
                raise ValueError("not a valid float") from None
        try:
            number = int(raw, 0)                              # hỗ trợ 123, 0x1F, 0b101
        except ValueError:
            raise ValueError("not a valid integer") from None
        lo, hi = _INT_RANGES[dtype]
        if not lo <= number <= hi:
            raise ValueError(f"{dtype} range is {lo} .. {hi}")
        return number

    @staticmethod
    def _plc_format_value(value, dtype):
        if dtype == "BOOL":
            return "ON  (1)" if value else "OFF (0)"
        if dtype == "FLOAT32":
            return f"{float(value):.6g}"
        width = 4 if dtype.endswith("16") else 8
        return f"{int(value)}   (0x{int(value) & ((1 << (width * 4)) - 1):0{width}X})"

    @staticmethod
    def _plc_values_equal(a, b, dtype):
        if dtype == "FLOAT32":
            return abs(float(a) - float(b)) < 1e-6 * max(1.0, abs(float(b)))
        return bool(a) == bool(b) if dtype == "BOOL" else int(a) == int(b)
