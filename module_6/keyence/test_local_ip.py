import socket

ip='192.168.42.36'
port=8501

dummy_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
dummy_sock.connect((ip, port))
local_ip = dummy_sock.getsockname()[0]
dummy_sock.close()
print(local_ip)