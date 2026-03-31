import paramiko
import os

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

local_file = r"c:\Users\iship\bitget-trading-bot\src\trading\executor.py"
remote_file = "/root/bitget-trading-bot/src/trading/executor.py"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)

sftp = ssh.open_sftp()
print(f"Uploading {local_file} to {remote_file}...")
sftp.put(local_file, remote_file)
sftp.close()

bot_services = ['bitget-bot', 'bitget-bot-btc', 'bitget-bot-sol', 'bitget-bot-tsla']
print("Restarting all bots to apply code update...")
for service in bot_services:
    ssh.exec_command(f"systemctl restart {service}")

ssh.close()
print("Upload and restart completed successfully!")
