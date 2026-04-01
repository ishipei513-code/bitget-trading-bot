import os
import json
import re
import paramiko

def run_cmd(ssh, cmd):
    print(f"Running: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='ignore')
    err = stderr.read().decode('utf-8', errors='ignore')
    if out: print(out.strip())
    if err: print(f"stderr: {err.strip()}")
    print(f"Exit status: {exit_status}\n")
    return exit_status

def create_and_upload_env(sftp, base_env_content, remote_dir, coin, conf):
    content = base_env_content
    content = re.sub(r'TRADING_SYMBOL=.*', f'TRADING_SYMBOL={conf["symbol"]}', content)
    content = re.sub(r'INITIAL_CAPITAL=.*', f'INITIAL_CAPITAL={conf["initial_capital"]}', content)
    content = re.sub(r'MAX_POSITION_SIZE=.*', f'MAX_POSITION_SIZE={conf["max_position_size"]}', content)
    content = re.sub(r'DISCORD_WEBHOOK_URL=.*', f'DISCORD_WEBHOOK_URL={conf["webhook"]}', content)
    
    remote_path = f"{remote_dir}/.env.{coin}"
    print(f"Uploading config to {remote_path}...")
    with sftp.open(remote_path, 'w') as f:
        f.write(content.encode('utf-8'))

def create_service(ssh, remote_dir, coin):
    # Ensure systemd uses a unique name per coin
    service_name = f"bitget-bot-{coin}"
    service_content = f"""[Unit]
Description=Bitget AI Trading Bot ({coin.upper()})
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={remote_dir}
Environment="PYTHONPATH={remote_dir}"
ExecStart={remote_dir}/venv/bin/python src/main.py
Restart=always
RestartSec=10
EnvironmentFile={remote_dir}/.env.{coin}

[Install]
WantedBy=multi-user.target
"""
    cmd = f"cat << 'EOF' > /etc/systemd/system/{service_name}.service\n{service_content}\nEOF"
    ssh.exec_command(cmd)
    return service_name

def main():
    config_path = os.path.join(os.path.dirname(__file__), 'bots_config.json')
    if not os.path.exists(config_path):
        print("Error: bots_config.json not found!")
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    vps = config["vps"]
    bots = config["bots"]
    remote_dir = vps["remote_dir"]

    print(f"Connecting to VPS at {vps['hostname']}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(vps['hostname'], username=vps['username'], password=vps['password'], timeout=10)
        print("Connected successfully!\n")
        
        # 1. Update and install packages
        run_cmd(ssh, "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv git")
        
        # 2. Clone or Update repo
        run_cmd(ssh, f"if [ ! -d '{remote_dir}' ]; then git clone {vps['repo_url']} {remote_dir}; else cd {remote_dir} && git reset --hard && git pull; fi")
        
        # 3. Upload base .env file
        local_env_path = os.path.join(os.path.dirname(__file__), ".env")
        if not os.path.exists(local_env_path):
            print("Error: .env file missing locally! Aborting to prevent overriding keys with blanks.")
            return

        print(f"Uploading base .env to {remote_dir}/.env...")
        sftp = ssh.open_sftp()
        sftp.put(local_env_path, f"{remote_dir}/.env")
        
        # Fetch it back into memory to act as a template
        with sftp.open(f"{remote_dir}/.env", 'r') as f:
            base_env_content = f.read().decode('utf-8')

        # 4. Setup venv and install requirements
        run_cmd(ssh, f"cd {remote_dir} && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt")

        # 5. Disable old legacy 'bitget-bot' service if we are standardizing names
        run_cmd(ssh, "systemctl stop bitget-bot; systemctl disable bitget-bot; rm -f /etc/systemd/system/bitget-bot.service")

        # 6. Generate individual env configs & service files
        active_services = []
        for coin, conf in bots.items():
            create_and_upload_env(sftp, base_env_content, remote_dir, coin, conf)
            service_name = create_service(ssh, remote_dir, coin)
            active_services.append(service_name)
        
        sftp.close()

        # 7. Start and enable all services
        run_cmd(ssh, "systemctl daemon-reload")
        services_str = " ".join(active_services)
        print(f"\nRestarting services: {services_str}")
        run_cmd(ssh, f"systemctl enable {services_str}")
        run_cmd(ssh, f"systemctl restart {services_str}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        ssh.close()
        print("Deployment finished!")

if __name__ == "__main__":
    main()
