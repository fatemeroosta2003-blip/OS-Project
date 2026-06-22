import socket
import json
import threading
import uuid
import argparse
import shlex
import time

REG_PORT = 8888
CMD_PORT = 9999
HOST_CID = socket.VMADDR_CID_ANY

class ZockerProxy:
    def __init__(self):
        self.nodes = {}  # {cid: {total_mem, alloc_mem, total_cpu...}}
        self.lock = threading.Lock()

    def start_discovery(self):
        sock = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
        sock.bind((HOST_CID, REG_PORT))
        sock.listen(10)
        print(f"[*] Discovery service started on port {REG_PORT}...")
        while True:
            conn, addr = sock.accept()
            try:
                data = conn.recv(2048).decode('utf-8')
                if data:
                    with self.lock:
                        self.nodes[addr[0]] = json.loads(data)
                        print(f"\n[+] Node Registered/Updated: CID {addr[0]}")
                conn.sendall(b"ACK")
            except Exception as e:
                print(f"Discovery Error: {e}")
            finally:
                conn.close()

    def send_command(self, cid, payload):
        sock = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
        try:
            sock.settimeout(5)
            sock.connect((cid, CMD_PORT))
            sock.sendall(json.dumps(payload).encode('utf-8'))
            return sock.recv(16384).decode('utf-8')
        except Exception as e:
            return f"Error: {e}"
        finally:
            sock.close()

    def select_node(self, required_mem):
        best_cid = -1
        min_alloc = float('inf')
        
        with self.lock:
            for cid, stats in self.nodes.items():
                free_mem = stats['total_mem'] - stats['alloc_mem']
                if free_mem >= required_mem:
                    if stats['alloc_mem'] < min_alloc:
                        min_alloc = stats['alloc_mem']
                        best_cid = cid
        return best_cid

    def update_node_mem(self, cid, mem_change):
        with self.lock:
            if cid in self.nodes:
                self.nodes[cid]['alloc_mem'] += mem_change

proxy = ZockerProxy()

def main():
    threading.Thread(target=proxy.start_discovery, daemon=True).start()
    
    print("\n--- Zocker Proxy CLI (Final Version) ---")
    print("Commands: nodes, run, ps, stop, rm, exec, exit")

    while True:
        try:
            line = input("zocker-proxy > ").strip()
            if not line: continue
            parts = shlex.split(line)
            cmd = parts[0]

            if cmd == "nodes":
                print(f"{'CID':<10} {'Total RAM (MB)':<15} {'Allocated RAM (MB)':<18} {'Free RAM (MB)'}")
                print("-" * 65)
                for cid, stats in proxy.nodes.items():
                    free = stats['total_mem'] - stats['alloc_mem']
                    print(f"{cid:<10} {stats['total_mem']:<15} {stats['alloc_mem']:<18} {free}")

            elif cmd == "run":
                p = argparse.ArgumentParser()
                p.add_argument("--memory", type=int, default=512)
                p.add_argument("config")
                try:
                    args = p.parse_args(parts[1:])
                except: continue
                
                if not os.path.exists(args.config):
                    print(f"Error: File {args.config} not found.")
                    continue

                with open(args.config, 'r') as f: 
                    config_data = json.load(f)

                best_cid = proxy.select_node(args.memory)

                if best_cid == -1:
                    print("Error: No node has enough free RAM for this request.")
                    continue

                u_id = str(uuid.uuid4())[:8]
                print(f"[*] Dispatching container {u_id} to VM {best_cid}...")
                
                res = proxy.send_command(best_cid, {
                    "cmd": "run", "uuid": u_id, "config": config_data,
                    "limits": {"memory": args.memory}
                })
                
                print(f"Result: {res}")
                
                if "OK" in res:
                    proxy.update_node_mem(best_cid, args.memory)

            elif cmd == "ps":
                header = f"{'VM':<5} {'ID':<12} {'STATUS':<10} {'PID':<8} {'AGE':<12} {'EXIT'}"
                print(header)
                print("-" * len(header))
                for cid in list(proxy.nodes.keys()):
                    res = proxy.send_command(cid, {"cmd": "ps"})
                    try:
                        containers = json.loads(res)
                        for c in containers:
                            exit_status = c.get('exit_code', '-') if c['status'] == 'stopped' else '-'
                            print(f"{cid:<5} {c['id'][:8]:<12} {c['status']:<10} {c['pid']:<8} {c.get('age','-'):<12} {exit_status}")
                    except:
                        print(f"[{cid}] Could not fetch PS data.")

            elif cmd == "stop":
                if len(parts) < 3: 
                    print("Usage: stop <VM_CID> <UUID>")
                    continue
                cid, u_id = int(parts[1]), parts[2]
                print(proxy.send_command(cid, {"cmd": "stop", "uuid": u_id}))

            elif cmd == "rm":
                # rm <VM_CID> <UUID> [-f]
                if len(parts) < 3: 
                    print("Usage: rm <VM_CID> <UUID> [-f]")
                    continue
                cid = int(parts[1])
                u_id = parts[2]
                force = "-f" in parts
                
                
                res = proxy.send_command(cid, {"cmd": "rm", "uuid": u_id, "force": force})
                print(f"Result from VM {cid}: {res}")

            elif cmd == "exec":
                if len(parts) < 4:
                    print("Usage: exec <VM_CID> <UUID> <CMD>")
                    continue
                cid, u_id = int(parts[1]), parts[2]
                command = " ".join(parts[3:])
                res = proxy.send_command(cid, {"cmd": "exec", "uuid": u_id, "shell_cmd": command})
                print(f"--- Output from {u_id} ---\n{res}")

            elif cmd == "connect":
                if len(parts) < 4:
                    print("Usage: connect <VM_CID> <UUID1> <UUID2>")
                    continue
                cid = int(parts[1])
                u_id1, u_id2 = parts[2], parts[3]
                res = proxy.send_command(cid, {
                    "cmd": "connect", "uuid1": u_id1, "uuid2": u_id2
                })
                print(f"Result: {res}")

            elif cmd == "exit": 
                break
        except Exception as e:
            print(f"CLI Error: {e}")

if __name__ == "__main__":
    import os
    main()