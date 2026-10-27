import socket
import time
import threading
from module_1.root_path import resource_path, get_trigger_file_path
from app_logger.app_logger import get_logger as _get_logger
_log = _get_logger('module_6.keyence.initial')
class KeyenceClient:
    def __init__(self, ip: str, port: int, mode: str = "binary", timeout: float = 3.0):
        """
        :param ip: Địa chỉ IP của PLC
        :param port: Cổng PLC (mặc định 5000 cho Keyence KV)
        :param mode: "ascii" hoặc "binary"
        :param timeout: timeout cho socket
        """
        assert mode in ("ascii", "binary"), "Mode phải là 'ascii' hoặc 'binary'"
        self.ip = ip
        self.port = int(port)
        self.mode = mode
        self.timeout = float(timeout)
        self.sock = None
        self.locked = threading.Lock()
        self.trigger_file_path = get_trigger_file_path("trigger")
        self.last_bytes_recv = 0
        self.last_bytes_sent = 0
        self.last_speed_time = 0
        self.current_adapter_desc = ""

    def get_network_adapter_info(self):
        """Trả về (adapter_name, description, ipv4, ipv6) của giao diện mạng dùng để kết nối PLC."""
        if not self.sock:
            return "", "", "", ""
        try:
            # Dùng UDP socket ảo để ép hệ điều hành dò bảng định tuyến tới IP của PLC
            # Cách này luôn lấy được IP đúng kể cả khi PLC đang tắt mạng
            dummy_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            dummy_sock.connect((self.ip, self.port))
            local_ip = dummy_sock.getsockname()[0]
            dummy_sock.close()
        except Exception:
            return "", "", "", ""

        import subprocess
        import re
        try:
            output = subprocess.check_output("ipconfig /all", text=True, encoding='oem', creationflags=subprocess.CREATE_NO_WINDOW)
            current_adapter, current_desc, current_ipv6, current_ipv4 = "", "", "", ""
            adapter_pattern = re.compile(r'^.* adapter (.*):$')

            for line in output.splitlines():
                line = line.strip()
                if not line: continue
                print(f"line : {line}")
                match = adapter_pattern.match(line)
                if match:
                    current_adapter = match.group(1).strip()
                    current_desc, current_ipv6, current_ipv4 = "", "", ""
                    continue
                print(f"current_adapter : {current_adapter}")
                print(f"current_desc : {current_desc}")
                print(f"current_ipv6 : {current_ipv6}")
                print(f"current_ipv4 : {current_ipv4}")
                if "Description" in line:
                    current_desc = line.split(":", 1)[1].strip()
                elif "IPv6" in line:
                    ip = line.split(":", 1)[1].strip()
                    current_ipv6 = ip.replace("(Preferred)", "").strip()
                elif "IPv4" in line or "IP Address" in line:
                    ip = line.split(":", 1)[1].strip()
                    current_ipv4 = ip.replace("(Preferred)", "").strip()
                    if current_ipv4 == local_ip:
                        self.current_adapter_desc = current_desc
                        return current_adapter, current_desc, current_ipv4, current_ipv6
        except Exception as e:
            _log.error(f"Error getting network info: {e}")
        return "", "", "", ""

    def get_network_speed(self):
        """Trả về (recv_kbps, sent_kbps) riêng biệt cho cổng mạng đang dùng. (Dùng GetIfTable API Windows)"""
        import ctypes
        from ctypes import wintypes
        import time

        if not self.current_adapter_desc:
            return 0.0, 0.0

        try:
            class MIB_IFROW(ctypes.Structure):
                _fields_ = [
                    ('wszName', ctypes.c_wchar * 256),
                    ('dwIndex', wintypes.DWORD),
                    ('dwType', wintypes.DWORD),
                    ('dwMtu', wintypes.DWORD),
                    ('dwSpeed', wintypes.DWORD),
                    ('dwPhysAddrLen', wintypes.DWORD),
                    ('bPhysAddr', ctypes.c_byte * 8),
                    ('dwAdminStatus', wintypes.DWORD),
                    ('dwOperStatus', wintypes.DWORD),
                    ('dwLastChange', wintypes.DWORD),
                    ('dwInOctets', wintypes.DWORD),
                    ('dwInUcastPkts', wintypes.DWORD),
                    ('dwInNUcastPkts', wintypes.DWORD),
                    ('dwInDiscards', wintypes.DWORD),
                    ('dwInErrors', wintypes.DWORD),
                    ('dwInUnknownProtos', wintypes.DWORD),
                    ('dwOutOctets', wintypes.DWORD),
                    ('dwOutUcastPkts', wintypes.DWORD),
                    ('dwOutNUcastPkts', wintypes.DWORD),
                    ('dwOutDiscards', wintypes.DWORD),
                    ('dwOutErrors', wintypes.DWORD),
                    ('dwOutQLen', wintypes.DWORD),
                    ('dwDescrLen', wintypes.DWORD),
                    ('bDescr', ctypes.c_char * 256),
                ]
            
            iphlpapi = ctypes.windll.Iphlpapi
            dwSize = wintypes.DWORD(0)
            iphlpapi.GetIfTable(None, ctypes.byref(dwSize), 0)
            
            buffer = ctypes.create_string_buffer(dwSize.value)
            if iphlpapi.GetIfTable(ctypes.byref(buffer), ctypes.byref(dwSize), 0) == 0:
                dwNumEntries = wintypes.DWORD.from_buffer_copy(buffer[:4]).value
                offset = 4
                target_in = 0
                target_out = 0
                found = False
                for i in range(dwNumEntries):
                    row = MIB_IFROW.from_buffer_copy(buffer[offset : offset + ctypes.sizeof(MIB_IFROW)])
                    desc = row.bDescr[:row.dwDescrLen].decode('ascii', errors='ignore')
                    if desc == self.current_adapter_desc:
                        target_in = row.dwInOctets
                        target_out = row.dwOutOctets
                        found = True
                        break
                    offset += ctypes.sizeof(MIB_IFROW)
                
                if not found:
                    return 0.0, 0.0
                    
                current_time = time.time()
                
                if self.last_bytes_recv == 0:
                    self.last_bytes_recv = target_in
                    self.last_bytes_sent = target_out
                    self.last_speed_time = current_time
                    return 0.0, 0.0
                    
                time_diff = current_time - self.last_speed_time
                if time_diff <= 0:
                    return 0.0, 0.0
                
                recv_diff = target_in - self.last_bytes_recv
                sent_diff = target_out - self.last_bytes_sent
                
                # Xử lý tràn số 32-bit của Windows Counter
                if recv_diff < 0: recv_diff += (1 << 32)
                if sent_diff < 0: sent_diff += (1 << 32)
                    
                # Task Manager đo tốc độ mạng dùng Kbps (1000 bps) chứ không phải 1024 bps
                recv_kbps = (recv_diff * 8) / (1000 * time_diff)
                sent_kbps = (sent_diff * 8) / (1000 * time_diff)
                
                self.last_bytes_recv = target_in
                self.last_bytes_sent = target_out
                self.last_speed_time = current_time
                return round(recv_kbps, 2), round(sent_kbps, 2)
        except Exception:
            pass
        return 0.0, 0.0

    def connect(self):
        _log.info(f'[+] Kết nối tới Keyence PLC {self.ip}:{self.port} qua pymcprotocol')
        for i in range(3):
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(self.timeout)
                self.sock.connect((self.ip, self.port))
                _log.info(f"Connected to Keyence PLC ({self.mode} mode)")
                return True
            except Exception as e:
                _log.warning(f"Cannot connect to PLC {self.ip}:{self.port} (Attempt {i+1}/3) -> {e}")
                if i < 2:
                    time.sleep(1)
        _log.error(f"Connection failed after 3 attempts to Keyence PLC {self.ip}:{self.port}")
        return False

    def read_plc_log(self, register_trigger):
        import time
        import os
        
        file_path = get_trigger_file_path(register_trigger, for_writing=False)
        
        for _ in range(10):
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    line = file.readline().strip()
                    if '=' not in line:
                        return 0
                    register, value = line.split('=')
                    register = register.strip()
                    value = int(value.strip())
                    return value if register.upper() == str(register_trigger).strip().upper() else 0
            except FileNotFoundError:
                # File chưa tồn tại, mặc định là 0
                return 0
            except (IOError, PermissionError):
                time.sleep(0.01)
        
        return 0
                
    def write_plc_log(self, register, value):
        import time
        import os
        file_path = get_trigger_file_path(register, for_writing=True)
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
        except Exception:
            pass
        for _ in range(10):
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(f"{register} = {value}\n")
                return True
            except (IOError, PermissionError) as e:
                time.sleep(0.01)
        print(f"Error writing to trigger file {file_path} after retries")
        return False


    def close(self):
        """Đóng kết nối"""
        if self.sock:
            self.sock.close()
            self.sock = None
            print("🔌 Disconnected from PLC")

    def _send(self, data: bytes) -> bytes:
        """Gửi dữ liệu (binary)"""
        self.sock.sendall(data)
        return self.sock.recv(4096)

    def _send_ascii(self, cmd: str) -> str:
        """Gửi dữ liệu (ASCII)"""
        self.sock.sendall(cmd.encode("utf-8"))
        resp = self.sock.recv(4096).decode("utf-8").strip()
        return resp

    # ---------------- ASCII MODE ----------------
    def read_dm_ascii(self, addr: int) -> int:
        cmd = f"RD DM{addr}\r"
        resp = self._send_ascii(cmd)
        return int(resp)

    def write_dm_ascii(self, addr: int, value: int):
        cmd = f"WR DM{addr} {value}\r"
        resp = self._send_ascii(cmd)
        if resp != "OK":
            print(f"[WARN] Write response = {resp}")

    # ---------------- BINARY MODE (MC 3E) ----------------
    def read_dm_binary(self, addr: int, points: int = 1):
        # Header
        header = b"\x50\x00\x00\xFF\xFF\x03\x00\x00"
        monitoring_timer = b"\x10\x00"

        command = b"\x01\x04"      # Batch Read
        subcommand = b"\x00\x00"

        device_code = 0xA8         # DM code
        dev_bytes = addr.to_bytes(3, "little") + bytes([device_code])
        req_data = dev_bytes + points.to_bytes(2, "little")

        length = (len(monitoring_timer) + len(command) +
                  len(subcommand) + len(req_data)).to_bytes(2, "little")

        frame = header + length + monitoring_timer + command + subcommand + req_data
        resp = self._send(frame)

        end_code = int.from_bytes(resp[9:11], "little")
        if end_code != 0x0000:
            raise Exception(f"PLC returned error code {end_code}")

        body = resp[11:]
        data = [int.from_bytes(body[i:i+2], "little")
                for i in range(0, len(body), 2)]
        return data[0] if points == 1 else data

    def write_dm_binary(self, addr: int, values):
        if isinstance(values, int):
            values = [values]

        header = b"\x50\x00\x00\xFF\xFF\x03\x00\x00"
        monitoring_timer = b"\x10\x00"

        command = b"\x01\x14"  # Batch Write
        subcommand = b"\x00\x00"

        device_code = 0xA8
        dev_bytes = addr.to_bytes(3, "little") + bytes([device_code])

        data_bytes = b''.join([v.to_bytes(2, "little") for v in values])
        req_data = dev_bytes + len(values).to_bytes(2, "little") + data_bytes

        length = (len(monitoring_timer) + len(command) +
                  len(subcommand) + len(req_data)).to_bytes(2, "little")

        frame = header + length + monitoring_timer + command + subcommand + req_data
        resp = self._send(frame)

        end_code = int.from_bytes(resp[9:11], "little")
        if end_code != 0x0000:
            raise Exception(f"PLC returned error code {end_code}")

    # # ---------------- API CHUNG ----------------
    # def read_dm(self, addr: int, points: int = 1):
    #     if self.mode == "ascii":
    #         if points != 1:
    #             raise NotImplementedError("ASCII mode chỉ đọc từng word 1")
    #         return self.read_dm_ascii(addr)
    #     else:
    #         return self.read_dm_binary(addr, points)

    # def write_dm(self, addr: int, values):
    #     if self.mode == "ascii":
    #         if isinstance(values, list):
    #             raise NotImplementedError("ASCII mode chỉ ghi 1 word")
    #         return self.write_dm_ascii(addr, values)
    #     else:
    #         return self.write_dm_binary(addr, values)

    def read_plc(self,data):
        try:
            with self.locked:
                a = 'RD '
                c = '\x0D'
                d = a+ data +c
                datasend = d.encode("UTF-8")
                self.sock.sendall(datasend)
                data = self.sock.recv(1024)
                datadeco = data.decode("UTF-8")
                data1 = int(datadeco)
                return data1
        except:
            pass

    def write_plc(self,register, data):
        try:
            with self.locked:
                a = 'WR '
                b = ' '
                c = '\x0D'
                d = a+ register + b + str(data) + c
                datasend  = d.encode("UTF-8")
                self.sock.sendall(datasend)
                datares = self.sock.recv(1024)
        except:
            pass



# # ---------------- Example ----------------
# if __name__ == "__main__":
#     plc = KeyenceClient("192.168.0.10", 5000, mode="ascii")
#     plc.connect()

#     # Đọc DM100
#     val = plc.read_dm(100)
#     print("Read:", val)

#     # Ghi DM105 = 123
#     plc.write_dm(105, 123)
#     print("Write OK")

#     plc.close()
