import paramiko

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)

stdin, stdout, stderr = ssh.exec_command('ls -la /root/bitget-trading-bot/data')
print(stdout.read().decode('utf-8'))
ssh.close()
