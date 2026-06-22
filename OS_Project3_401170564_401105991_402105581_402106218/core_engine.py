import os
import sys
import json
import ctypes
import time
from pathlib import Path
from resources import ResourceManager, get_limits_from_config
from isolation import apply_isolation, set_container_hostname

def get_base_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts = current_dir.split(os.sep)
    if 'home' in parts:
        home_index = parts.index('home')
        user_home = os.sep + os.path.join(parts[home_index], parts[home_index + 1])
        return os.path.join(user_home, ".zocker", "containers")
    return os.path.expanduser("~/.zocker/containers")

BASE_PATH = get_base_path()

# --- Flags ---
CLONE_NEWPID = 0x20000000
CLONE_NEWNS  = 0x00020000
CLONE_NEWUTS = 0x04000000
MS_REC = 16384
MS_PRIVATE = 262144

def update_state_file(container_id, pid, status, exit_code=0):
    state_path = os.path.join(BASE_PATH, container_id, "state.json")
    created_at = time.time()
    if os.path.exists(state_path):
        with open(state_path, 'r') as f:
            try:
                old_data = json.load(f)
                created_at = old_data.get("created_at", time.time())
            except: pass

    state_data = {
        "id": container_id,
        "status": status,
        "pid": pid,
        "bundle": os.path.dirname(state_path),
        "created_at": created_at,
        "exit_code": exit_code,
        "finished_at": time.time() if status == "stopped" else None
    }
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, 'w') as f:
        json.dump(state_data, f)

def manage_rootfs(rootfs_path, action="setup"):
    dirs = ['bin', 'lib', 'lib64', 'usr', 'etc', 'proc', 'sys', 'dev']
    
    if action == "setup":
        for d in dirs:
            target = os.path.join(rootfs_path, d)
            os.makedirs(target, exist_ok=True)
            source = f"/{d}"
            if os.path.exists(source):
                os.system(f"mount --bind -n {source} {target}")
                os.system(f"mount -o remount,ro,bind {target}")

    elif action == "cleanup":
        os.system(f"umount -fl {rootfs_path}/* > /dev/null 2>&1")
        
        for d in reversed(dirs):
            target = os.path.join(rootfs_path, d)
            if os.path.ismount(target):
                os.system(f"umount -fl {target}")

def run_container_process(container_id, rootfs_path, config_data, rm):
    try:
        libc = ctypes.CDLL("libc.so.6")
        libc.mount(None, b"/", None, MS_REC | MS_PRIVATE, None)
        if "mounts" in config_data:
            for mnt in config_data["mounts"]:
                src = mnt["source"]
                dst = os.path.join(rootfs_path, mnt["destination"].lstrip("/"))
                os.makedirs(dst, exist_ok=True)
                os.system(f"mount --bind {src} {dst}")
                print(f"[*] Mounted {src} to {mnt['destination']}")

        os.system(f"mount --bind /dev {os.path.join(rootfs_path, 'dev')}")
        os.chroot(rootfs_path)
        os.chdir("/")
        
        os.makedirs("/proc", exist_ok=True)
        os.system("mount -t proc proc /proc")
        os.makedirs("/sys", exist_ok=True)
        os.system("mount -t sysfs sys /sys")
        
        if "env" in config_data:
            for env_item in config_data["env"]:
                if "=" in env_item:
                    k, v = env_item.split("=", 1)
                    os.environ[k] = v

        set_container_hostname(f"zocker-{container_id[:6]}")
        rm.attach(os.getpid())
        
        os.environ["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        os.environ["TERM"] = "xterm"
        
        print(f"[*] Container {container_id} is starting as PID 1...")


        os.execlp("sh", "sh", "-c", "tail -f /dev/null")
        
    except Exception as e:
        with open("/tmp/zocker_error.log", "a") as f:
            f.write(f"Error in child: {str(e)}\n")
        sys.exit(1)

def start_container(container_id):
    try:
        base_dir = os.path.join(BASE_PATH, container_id)
        config_path = os.path.join(base_dir, "config.json")
        
        with open(config_path, 'r') as f:
            config_data = json.load(f)
            
        rootfs_path = os.path.join(base_dir, "rootfs")
        mem, cpu = get_limits_from_config(container_id)
        rm = ResourceManager(container_id)
        rm.create_limits(mem, cpu)
        
        manage_rootfs(rootfs_path, "setup")
        apply_isolation()
        
        libc = ctypes.CDLL("libc.so.6")
        if libc.unshare(CLONE_NEWPID | CLONE_NEWNS | CLONE_NEWUTS) != 0:
            raise OSError("Unshare failed")

        pid = os.fork()
        if pid == 0:
            run_container_process(container_id, rootfs_path, config_data, rm)
        else:
            update_state_file(container_id, pid, "running")
            try:
                _, status = os.waitpid(pid, 0)
                exit_code = os.waitstatus_to_exitcode(status)
            except:
                exit_code = 0
            
            update_state_file(container_id, 0, "stopped", exit_code)
            manage_rootfs(rootfs_path, "cleanup")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        start_container(sys.argv[1])