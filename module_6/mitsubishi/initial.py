# mitsubishi/client.py
import socket

from module_6.mitsubishi.pymcprotocol.type3e import Type3E
from app_logger.app_logger import get_logger as _get_logger
_log = _get_logger('module_6.mitsubishi.initial')
import threading
from module_1.root_path import resource_path

class SocketClient:
    def __init__(self, ip_address, port):
        self.ipv4 = ip_address
        self.port = port
        self.client = None 
        self.trigger_file_path = resource_path("module_3\trigger.txt")
        self.locked = threading.Lock()

    def test_connection(self, ip: str, port: int, timeout: float = 3.0) -> bool:
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return True
        except Exception as e:
            # _log.error('[ERROR] Cannot connect to PLC at {ip}:{port} -> {e}', ip, port, e)
            return False

    def connect(self):
        _log.info('[+] Kết nối tới Mitsubishi PLC qua pymcprotocol')
        if self.test_connection(self.ipv4, self.port):
            _log.info("✅ Socket connection to Mitsubishi PLC successful")
            self.client = Type3E()
            self.client.connect(self.ipv4, self.port)
            _log.info("✅ pymcprotocol connected (ready for read/write)")
            return True
        else:
            _log.error("❌ Cannot connect to Mitsubishi PLC")
            return True

    
    def read_plc_log(self, register_trigger):
        import time
        import os
        
        dir_name = os.path.dirname(self.trigger_file_path)
        file_path = os.path.join(dir_name, f"trigger_{register_trigger}.txt")
        
        for _ in range(10):
            try:
                with open(file_path, 'r') as file:
                    line = file.readline().strip()
                    if '=' not in line:
                        return 0
                    register, value = line.split('=')
                    register = register.strip()
                    value = int(value.strip())
                    return value if register == register_trigger else 0
            except FileNotFoundError:
                # File chưa tồn tại, mặc định là 0
                return 0
            except (IOError, PermissionError):
                time.sleep(0.01)
        
        return 0
                
    def write_plc_log(self, register, value):
        import time
        import os
        
        dir_name = os.path.dirname(self.trigger_file_path)
        file_path = os.path.join(dir_name, f"trigger_{register}.txt")
        
        for _ in range(10):
            try:
                with open(file_path, 'w') as file:
                    file.write(f"{register} = {value}\n")
                return True
            except (IOError, PermissionError) as e:
                time.sleep(0.01)
        print(f"Error writing to trigger file {file_path} after retries")
        return False

    def read_dm(self, device: str, points: int = 1):
        """
        Đọc dữ liệu từ PLC
        :param device: tên device (VD: "D100", "M0")
        :param points: số lượng giá trị cần đọc
        :return: list giá trị đọc được
        """
        if not self.client:
            print("❌ Chưa kết nối PLC, hãy gọi connect() trước")
            return None
        try:
            data = self.client.batchread_wordunits(headdevice=device, readsize=points)
            _log.info(f"📥 Read {device} -> {data}")
            return data
        except Exception as e:
            _log.error('[ERROR] Cannot read from %s -> %s', device, e)
            return None

    def write_dm(self, device: str, values):
        """
        Ghi dữ liệu xuống PLC
        :param device: tên device (VD: "D100", "M0")
        :param values: giá trị cần ghi (int hoặc list int)
        """
        if not self.client:
            _log.error("❌ Chưa kết nối PLC, hãy gọi connect() trước")
            return False
        try:
            if isinstance(values, int):
                values = [values]
            self.client.batchwrite_wordunits(headdevice=device, values=values)
            _log.info(f"📤 Write {device} <- {values}")
            return True
        except Exception as e:
            _log.error('[ERROR] Cannot write to %s -> %s', device, e)
            return False

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
