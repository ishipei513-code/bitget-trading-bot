import paramiko

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)

sftp = ssh.open_sftp()
remote_path = '/root/bitget-trading-bot/data/bot.log'
local_path = 'VPS_Trade_Log.txt'

try:
    sftp.get(remote_path, local_path)
    print(f"Log downloaded successfully to: {local_path}")
except Exception as e:
    print(f"Failed to download log: {e}")

sftp.close()
ssh.close()
