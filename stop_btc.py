import paramiko

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)

print("Stopping BTC bot...")
ssh.exec_command("systemctl stop bitget-bot-btc")
ssh.exec_command("systemctl disable bitget-bot-btc")

stdin, stdout, stderr = ssh.exec_command("sleep 1 && systemctl is-active bitget-bot-btc || echo 'Stopped'")
print("BTC Bot:", stdout.read().decode('utf-8').strip())

ssh.close()
