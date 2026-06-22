import argparse
import sys
import uuid
import json
import os
import time
import manager 

def format_age(timestamp):
    if not timestamp:
        return "-"
    diff = int(time.time() - timestamp)
    if diff < 60: return f"{diff}s"
    elif diff < 3600: return f"{diff // 60}m"
    elif diff < 86400: return f"{diff // 3600}h"
    else: return f"{diff // 86400}d"

def main():
    parser = argparse.ArgumentParser(description="Zocker Local Management CLI (Part 1)")
    subparsers = parser.add_subparsers(dest="command")

    # 1.run
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--memory", type=int, default=512)
    run_parser.add_argument("--cpu", type=int, default=1024)
    run_parser.add_argument("--name", help="Custom name for the container", default=None)
    run_parser.add_argument("config", help="Path to config.json")

    # 2.ps
    ps_parser = subparsers.add_parser("ps")
    ps_parser.add_argument("-a", action="store_true", help="Show all containers")

    # 3.exec
    exec_parser = subparsers.add_parser("exec")
    exec_parser.add_argument("id", help="Container UUID")
    exec_parser.add_argument("cmd", help="Command to run")

    # 4.stop
    stop_parser = subparsers.add_parser("stop")
    stop_parser.add_argument("id")

    # 5.restart
    restart_parser = subparsers.add_parser("restart")
    restart_parser.add_argument("id")

    # 6.rm
    rm_parser = subparsers.add_parser("rm")
    rm_parser.add_argument("id")
    rm_parser.add_argument("-f", action="store_true", help="Force remove")

    args = parser.parse_args()

    if args.command == "run":
        u_id = args.name if args.name else str(uuid.uuid4())[:8]
        c_dir = os.path.join(manager.BASE_PATH, u_id)
        
        try:
            with open(args.config, 'r') as f:
                new_config_data = json.load(f)
        except Exception as e:
            print(f"Error reading config: {e}")
            return

        if os.path.exists(c_dir):
            old_config_path = os.path.join(c_dir, "config.json")
            if os.path.exists(old_config_path):
                with open(old_config_path, 'r') as f:
                    old_config_data = json.load(f)
                
                if old_config_data == new_config_data:
                    print(f"[-] Container '{u_id}' is already running with this exact config.")
                    return 
                
                print(f"[*] Config change detected for '{u_id}'. Restarting...")
            
            manager.remove_container(u_id, force=True)
            time.sleep(1)

        os.makedirs(c_dir, exist_ok=True)
        with open(os.path.join(c_dir, "config.json"), 'w') as f:
            json.dump(new_config_data, f, indent=4)
            
        manager.create_and_start_service(u_id)
        print(f"[+] Container {u_id} started.")

    elif args.command == "ps":
        containers = manager.get_all_container_states()
        print(f"{'CONTAINER ID':<15} {'STATUS':<12} {'PID':<10} {'EXIT':<8} {'AGE / FINISHED'}")
        print("-" * 65)

        for c in containers:
            status = c.get('status', 'unknown')
            if not args.a and status != 'running': continue

            c_id = c.get('id', 'unknown')[:12]
            pid = c.get('pid', 0) if status == 'running' else 0
            exit_code = c.get('exit_code', '-') if status == 'stopped' else '-'
            
            if status == 'running':
                age_val = format_age(c.get('created_at'))
            else:
                finished_at = c.get('finished_at')
                age_val = f"Exited ({format_age(finished_at)} ago)" if finished_at else "unknown"

            print(f"{c_id:<15} {status:<12} {pid:<10} {exit_code:<8} {age_val}")

    elif args.command == "exec":
        print(f"[*] Entering container {args.id}...")
        manager.exec_in_container(args.id, args.cmd)

    elif args.command == "stop":
        os.system(f"sudo systemctl stop zocker-{args.id}")
        print(f"[+] Container {args.id} stopped.")

    elif args.command == "restart":
        print(f"[*] Restarting container {args.id}...")
        os.system(f"sudo systemctl stop zocker-{args.id}")
        
        time.sleep(1)
        
        os.system(f"sudo systemctl start zocker-{args.id}")
        
        print(f"[+] Container {args.id} restarted successfully.")

    elif args.command == "rm":
        success, msg = manager.remove_container(args.id, args.f)
        print(msg)

if __name__ == "__main__":
    main()