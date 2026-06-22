import socket
import json
import os
import psutil
import time
import threading
import manager 

HOST_CID = 2 
REG_PORT = 8888
CMD_PORT = 9999

def get_stats():
    total_m = psutil.virtual_memory().total // (1024 * 1024)
    total_c = psutil.cpu_count()
    states = manager.get_all_container_states()
    alloc_m = 0
    for s in states:
        if s.get('status') == 'running':
            alloc_m += s.get('limits', {}).get('memory', 0)
    return {
        "total_mem": total_m, 
        "alloc_mem": alloc_m,
        "total_cpu": total_c,
        "alloc_cpu": 0 
    }

def listen():
    server = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    server.bind((socket.VMADDR_CID_ANY, CMD_PORT))
    server.listen(5)
    print(f"[*] Agent is listening for commands on VSOCK port {CMD_PORT}...")
    
    while True:
        conn, addr = server.accept()
        client_cid = addr[0] 
        try:
            raw = conn.recv(16384).decode('utf-8')
            req = json.loads(raw)
            cmd = req.get('cmd')

            print(f"[#] Received command: '{cmd}' from Host (CID {client_cid})")

            if cmd == "get_stats":
                conn.sendall(json.dumps(get_stats()).encode('utf-8'))

            elif cmd == "run":
                u_id = req['uuid']
                print(f"[*] Starting container creation: {u_id[:12]}")
                
                c_dir = os.path.join(manager.BASE_PATH, u_id)
                os.makedirs(c_dir, exist_ok=True)
                
                state = {
                    "id": u_id, "status": "creating", "pid": 0,
                    "bundle": c_dir, "limits": req['limits'],
                    "annotations": {"name": f"zocker-{u_id[:4]}"}
                }
                with open(os.path.join(c_dir, "config.json"), 'w') as f: json.dump(req['config'], f)
                with open(os.path.join(c_dir, "state.json"), 'w') as f: json.dump(state, f)
                
                manager.create_and_start_service(u_id)
                print(f"[+] Container {u_id[:12]} service started successfully.")
                conn.sendall(b"OK: Service Started")

            elif cmd == "ps":
                all_states = manager.get_all_container_states()
                now = time.time()
                for s in all_states:
                    created_at = s.get('created_at') or now
                    age_seconds = int(now - created_at)
                    
                    if age_seconds < 60: s['age'] = f"{age_seconds}s"
                    else: s['age'] = f"{age_seconds // 60}m {age_seconds % 60}s"
                
                conn.sendall(json.dumps(all_states).encode('utf-8'))

            elif cmd == "stop":
                u_id = req.get('uuid')
                print(f"[*] Stopping container: {u_id[:12]}")
                os.system(f"sudo systemctl stop zocker-{u_id}")
                conn.sendall(b"OK: Container Stopped")

            elif cmd == "rm":
                u_id = req.get('uuid')
                print(f"[*] Removing container files: {u_id[:12]}")
                result = manager.remove_container(u_id, req.get('force', False))
                conn.sendall(str(result).encode('utf-8'))

            elif cmd == "exec":
                u_id = req.get('uuid')
                shell_cmd = req.get('shell_cmd')
                print(f"[*] Executing command inside {u_id[:12]}: {shell_cmd}")
                result = manager.exec_in_container_V2(u_id, shell_cmd)
                conn.sendall(str(result).encode('utf-8'))

            elif cmd == "connect":
                u_id1 = req.get('uuid1')
                u_id2 = req.get('uuid2')
                print(f"[*] Connecting {u_id1[:8]} and {u_id2[:8]}")
                success, msg = manager.connect_containers(u_id1, u_id2)
                conn.sendall(msg.encode('utf-8'))
                
        except Exception as e:
            print(f"[!] Error during command execution: {str(e)}")
            conn.sendall(f"Error: {str(e)}".encode('utf-8'))
        finally:
            conn.close()

if __name__ == "__main__":
    print("--- Zocker Agent Starting ---")
    threading.Thread(target=listen, daemon=True).start()
    
    print(f"[*] Trying to register at Proxy (Host CID {HOST_CID})...")
    while True:
        try:
            s = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
            s.connect((HOST_CID, REG_PORT))
            s.sendall(json.dumps(get_stats()).encode('utf-8'))
            if s.recv(1024) == b"ACK":
                print("[+] Successfully registered at Proxy!")
                break
        except:
            time.sleep(2)
            
    while True: 
        time.sleep(1)