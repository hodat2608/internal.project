from module_6.omron.omronfins.finsudp import FinsUDP, datadef


class OmronClient:
    def __init__(self, ip_address: str, port: int, dst_node: int = 1):
        """
        Omron PLC FINS Client
        :param ip_address: IP của PLC
        :param port: cổng UDP của PLC (thường 9600 hoặc 9601)
        :param dst_node: Node number (thường trùng số cuối của IP, ví dụ 192.168.2.13 -> 13)
        """
        self.ip = ip_address
        self.port = int(port)
        self.dst_node = dst_node
        self.fins = None
        self.connected = False

    def connect(self) -> bool:
        print('[+] Kết nối tới Omron PLC qua pymcprotocol')
        # try:
        #     self.fins = FinsUDP(0, 170)
        #     ret = self.fins.open(self.ip, self.port)
        #     if ret < 0:
        #         print("[ERROR] Không mở được kết nối FINS")
        #         return False
        #     self.fins.set_destination(dst_net_addr=0,
        #                               dst_node_num=self.dst_node,
        #                               dst_unit_addr=0)
        #     self.connected = True
        #     print("✅ Kết nối Omron PLC thành công")
        #     return True
        # except Exception as e:
        #     print(f"[ERROR] Lỗi khi kết nối PLC Omron: {e}")
        #     self.connected = False
        #     return False
        return True

    def read_dm(self, address: int, points: int = 1):
        """
        Đọc dữ liệu từ DM area
        :param address: số DM (VD: 1000 -> DM1000)
        :param points: số lượng word cần đọc
        :return: list giá trị đọc được hoặc None
        """
        if not self.connected:
            print("❌ Chưa kết nối PLC")
            return None
        try:
            ret, values = self.fins.read_mem_area(
                datadef.DM_WORD, address, 0, points, datadef.USHORT
            )
            if ret == 0:
                if points == 1:
                    print(f"📥 DM{address} = {values[0]}")
                    return values[0]
                else:
                    print(f"📥 DM{address}..DM{address+points-1} = {values}")
                    return values
            else:
                print(f"[ERROR] Lỗi khi đọc DM{address}, ret={ret}")
                return None
        except Exception as e:
            print(f"[ERROR] Exception khi đọc DM{address}: {e}")
            return None

    def write_dm(self, address: int, values):
        """
        Ghi dữ liệu xuống DM area
        :param address: số DM (VD: 1000 -> DM1000)
        :param values: int hoặc list[int] cần ghi
        :return: True nếu thành công
        """
        if not self.connected:
            print("❌ Chưa kết nối PLC")
            return False
        try:
            if isinstance(values, int):
                values = [values]
            ret = self.fins.write_mem_area(
                datadef.DM_WORD, address, 0, len(values),
                [(v, datadef.USHORT) for v in values]
            )
            if ret == 0:
                print(f"📤 Write DM{address} <- {values}")
                return True
            else:
                print(f"[ERROR] Lỗi khi ghi DM{address}, ret={ret}")
                return False
        except Exception as e:
            print(f"[ERROR] Exception khi ghi DM{address}: {e}")
            return False


# ================== Example usage ==================
if __name__ == "__main__":
    plc = OmronClient("192.168.2.13", 9600, dst_node=13)
    if plc.connect():
        val = plc.read_dm(1000)       # đọc DM1000
        plc.write_dm(1005, 123)       # ghi 123 vào DM1005
        plc.write_dm(1010, [10, 20])  # ghi 2 word vào DM1010, DM1011