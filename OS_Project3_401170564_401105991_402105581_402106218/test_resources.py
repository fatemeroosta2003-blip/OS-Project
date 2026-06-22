import os
import subprocess
import time
from resources import ResourceManager

def run_test():
    container_id = "test_cont"
    mem_limit = 100 * 1024 * 1024
    cpu_limit = 50000
    
    rm = ResourceManager(container_id)
    
    try:
        rm.create_limits(mem_limit, cpu_limit)
        
        process = subprocess.Popen(["sleep", "100"])
        
        rm.attach(process.pid)
        
        print(f"Container {container_id} setup with PID {process.pid}")
        print(f"Path: {rm.path}")
        
        time.sleep(2)
        
        if os.path.exists(os.path.join(rm.path, "cgroup.procs")):
            print("Status: Cgroup files verified.")
            
        process.terminate()
        rm.remove()
        print("Status: Cleanup successful.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_test()
