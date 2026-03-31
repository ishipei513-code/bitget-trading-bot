import paramiko
import re

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

NEW_MODEL = "gemini-flash-lite-latest"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)

sftp = ssh.open_sftp()

files = ['.env', '.env.sol', '.env.tsla', '.env.siren']
bot_services = ['bitget-bot', 'bitget-bot-sol', 'bitget-bot-tsla', 'bitget-bot-siren']

for file in files:
    remote_path = f'/root/bitget-trading-bot/{file}'
    print(f"Updating {remote_path} to use model {NEW_MODEL}...")
    
    with sftp.open(remote_path, 'r') as f:
        content = f.read().decode('utf-8')
    
    # Update GEMINI_MODEL
    # If GEMINI_MODEL key doesn't exist, we might need to append it, but we know it exists.
    content = re.sub(r'GEMINI_MODEL=.*', f'GEMINI_MODEL={NEW_MODEL}', content)
    
    with sftp.open(remote_path, 'w') as f:
        f.write(content.encode('utf-8'))

sftp.close()

print("Restarting all bots to apply new AI model...")
for service in bot_services:
    ssh.exec_command(f"systemctl restart {service}")

stdin, stdout, stderr = ssh.exec_command("sleep 2 && systemctl is-active bitget-bot")
print("Main Bot Status:", stdout.read().decode('utf-8').strip())

ssh.close()
print("All bots updated and restarted successfully!")
