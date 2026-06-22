import os
import json

class ResourceManager:
    def __init__(self, container_id):
        self.container_id = container_id
        self.path = os.path.join("/sys/fs/cgroup", f"zocker_{container_id}")

    def create_limits(self, mem_limit, cpu_shares):
        try:
            with open("/sys/fs/cgroup/cgroup.subtree_control", "w") as f:
                f.write("+memory +cpu +pids")
        except:
            pass

        os.makedirs(self.path, exist_ok=True)
        
        try:
            with open(os.path.join(self.path, "memory.max"), "w") as f:
                if int(mem_limit) < 1000000:
                    f.write("max")
                else:
                    f.write(str(mem_limit))
        except:
            pass

        try:
            with open(os.path.join(self.path, "cpu.max"), "w") as f:
                f.write(f"{cpu_shares} 100000")
        except:
            pass

    def attach(self, pid):
        try:
            with open(os.path.join(self.path, "cgroup.procs"), "w") as f:
                f.write(str(pid))
        except:
            pass

    def remove(self):
        if os.path.exists(self.path):
            os.system(f"sudo rmdir {self.path}")

def get_limits_from_config(container_id):
    home_dir = os.path.expanduser("~")
    config_path = os.path.join(home_dir, ".zocker", "containers", container_id, "config.json")
    if not os.path.exists(config_path):
        config_path = f"/root/.zocker/containers/{container_id}/config.json"
    
    with open(config_path, 'r') as f:
        data = json.load(f)
    mem = data['linux']['resources']['memory']['limit']
    cpu = data['linux']['resources']['cpu']['shares']
    return mem, cpu
