import paramiko
import re

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

# ETHと同等の設定に揃える
SETTINGS = {
    '.env': {'INITIAL_CAPITAL': '15', 'MAX_POSITION_SIZE': '0.33'},       # BNB
    '.env.sol': {'INITIAL_CAPITAL': '15', 'MAX_POSITION_SIZE': '1.5'},    # SOL
    '.env.tsla': {'INITIAL_CAPITAL': '15', 'MAX_POSITION_SIZE': '0.8'},   # TSLA
}

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)

sftp = ssh.open_sftp()

for file, updates in SETTINGS.items():
    remote_path = f'/root/bitget-trading-bot/{file}'
    print(f"Updating {remote_path}...")
    
    with sftp.open(remote_path, 'r') as f:
        content = f.read().decode('utf-8')
    
    for key, value in updates.items():
        content = re.sub(rf'{key}=.*', f'{key}={value}', content)
    
    with sftp.open(remote_path, 'w') as f:
        f.write(content.encode('utf-8'))
    print(f"  INITIAL_CAPITAL={updates['INITIAL_CAPITAL']}, MAX_POSITION_SIZE={updates['MAX_POSITION_SIZE']}")

sftp.close()

print("\nRestarting active bots...")
for service in ['bitget-bot', 'bitget-bot-sol', 'bitget-bot-tsla']:
    ssh.exec_command(f"systemctl restart {service}")

stdin, stdout, stderr = ssh.exec_command("sleep 2 && systemctl is-active bitget-bot && systemctl is-active bitget-bot-sol && systemctl is-active bitget-bot-tsla")
print("Status:", stdout.read().decode('utf-8').strip())

ssh.close()
print("All settings updated and bots restarted!")
