import paramiko
import re

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)

sftp = ssh.open_sftp()

files = ['.env', '.env.btc', '.env.sol', '.env.tsla']
bot_services = ['bitget-bot', 'bitget-bot-btc', 'bitget-bot-sol', 'bitget-bot-tsla']

for file in files:
    remote_path = f'/root/bitget-trading-bot/{file}'
    print(f"Updating {remote_path} to MAX_POSITION_SIZE=9999...")
    
    with sftp.open(remote_path, 'r') as f:
        content = f.read().decode('utf-8')
    
    # Update MAX_POSITION_SIZE to 9999 so that INITIAL_CAPITAL becomes the active constraint
    content = re.sub(r'MAX_POSITION_SIZE=.*', 'MAX_POSITION_SIZE=9999', content)
    
    with sftp.open(remote_path, 'w') as f:
        f.write(content.encode('utf-8'))

sftp.close()

print("Restarting all bots to apply changes...")
for service in bot_services:
    ssh.exec_command(f"systemctl restart {service}")

ssh.close()
print("All bots updated and restarted!")
