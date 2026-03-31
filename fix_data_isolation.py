import paramiko
import re

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)

sftp = ssh.open_sftp()

# 各通貨のenvファイルにDATA_DIRを追加（通貨ごとに分離）
env_files = {
    '.env': 'bnb',
    '.env.sol': 'sol',
    '.env.tsla': 'tsla',
    '.env.siren': 'siren',
}

for file, coin in env_files.items():
    remote_path = f'/root/bitget-trading-bot/{file}'
    print(f"Updating {remote_path} → DATA_DIR=data/{coin}")
    
    with sftp.open(remote_path, 'r') as f:
        content = f.read().decode('utf-8')
    
    # DATA_DIRが既にあれば置換、なければ追加
    if 'DATA_DIR=' in content:
        content = re.sub(r'DATA_DIR=.*', f'DATA_DIR=data/{coin}', content)
    else:
        content += f'\nDATA_DIR=data/{coin}\n'
    
    with sftp.open(remote_path, 'w') as f:
        f.write(content.encode('utf-8'))

sftp.close()

# 各通貨のデータディレクトリを作成
for coin in env_files.values():
    ssh.exec_command(f"mkdir -p /root/bitget-trading-bot/data/{coin}/trades /root/bitget-trading-bot/data/{coin}/events")

# 全Botを再起動
print("\nRestarting all active bots...")
for service in ['bitget-bot', 'bitget-bot-sol', 'bitget-bot-tsla', 'bitget-bot-siren']:
    ssh.exec_command(f"systemctl restart {service}")

stdin, stdout, stderr = ssh.exec_command("sleep 3 && systemctl is-active bitget-bot && echo '---' && systemctl is-active bitget-bot-sol && echo '---' && systemctl is-active bitget-bot-tsla && echo '---' && systemctl is-active bitget-bot-siren")
print("Status:", stdout.read().decode('utf-8').strip())

ssh.close()
print("\nAll bots now have isolated data directories!")
