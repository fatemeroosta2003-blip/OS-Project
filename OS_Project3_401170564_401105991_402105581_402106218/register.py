import socket
import json
import psutil
import platform

def get_system_specs():
    specs = {
        "node_name": socket.gethostname(),
        "ip_address": socket.gethostbyname(socket.gethostname()),
        "os": f"{platform.system()} {platform.release()}",
        "total_ram_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "available_ram_gb": round(psutil.virtual_memory().available / (1024**3), 2),
        "cpu_cores": psutil.cpu_count(logical=True),
        "status": "ready"
    }
    return specs

def register_node(server_ip, server_port):
    data = get_system_specs()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((server_ip, server_port))
            s.sendall(json.dumps(data).encode('utf-8'))
            print(f"Success: {data['total_ram_gb']}GB RAM reported.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    DEST_IP = "192.168.1.104"
    DEST_PORT = 5000
    register_node(DEST_IP, DEST_PORT)
