import paramiko
import os
import sys

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

def run_cmd(ssh, cmd):
    print(f"Running: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    
    # Wait for completion and read output line by line
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='ignore')
    err = stderr.read().decode('utf-8', errors='ignore')
    
    print(out)
    if err:
        print(f"stderr: {err}")
    print(f"Exit status: {exit_status}\n")
    return exit_status

print(f"Connecting to {HOSTNAME}...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)
    print("Connected successfully!")
    
    # 1. Update and install packages
    run_cmd(ssh, "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv git")
    
    # 2. Clone or Update repo
    run_cmd(ssh, "if [ ! -d '/root/bitget-trading-bot' ]; then git clone https://github.com/ishipei513-code/bitget-trading-bot.git /root/bitget-trading-bot; else cd /root/bitget-trading-bot && git pull; fi")
    
    # 3. Upload .env file
    local_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    remote_env_path = "/root/bitget-trading-bot/.env"
    print(f"Uploading {local_env_path} to {remote_env_path}...")
    sftp = ssh.open_sftp()
    sftp.put(local_env_path, remote_env_path)
    sftp.close()
    print("Upload complete.\n")
    
    # 4. Setup venv and install requirements
    run_cmd(ssh, "cd /root/bitget-trading-bot && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt")
    
    # 5. Create systemd service
    service_content = """[Unit]
Description=Bitget AI Trading Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/bitget-trading-bot
Environment="PYTHONPATH=/root/bitget-trading-bot"
ExecStart=/root/bitget-trading-bot/venv/bin/python src/main.py
Restart=always
RestartSec=10
EnvironmentFile=/root/bitget-trading-bot/.env

[Install]
WantedBy=multi-user.target
"""
    # Write service file to remote
    run_cmd(ssh, f"cat << 'EOF' > /etc/systemd/system/bitget-bot.service\n{service_content}\nEOF")
    
    # 6. Start service
    run_cmd(ssh, "systemctl daemon-reload")
    run_cmd(ssh, "systemctl enable bitget-bot")
    run_cmd(ssh, "systemctl restart bitget-bot")
    
    # 7. Check status
    run_cmd(ssh, "systemctl status bitget-bot --no-pager")
    
except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
    print("Deployment finished.")
