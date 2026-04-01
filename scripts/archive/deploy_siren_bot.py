import paramiko
import re

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

COIN = "siren"
SYMBOL = "SIREN/USDT:USDT"
WEBHOOK = "https://discord.com/api/webhooks/1488541425267114064/9pcEMGEvqE7Jj5vh04miMRE_hzvD8n2VJgMakpbeliPtnVfKzV2NBo2UsM1Qk-c00kDZ"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)

sftp = ssh.open_sftp()
print("Fetching base .env file...")
with sftp.open('/root/bitget-trading-bot/.env', 'r') as f:
    env_content = f.read().decode('utf-8')

# ETHと同等の設定に合わせる
content = env_content
content = re.sub(r'TRADING_SYMBOL=.*', f'TRADING_SYMBOL={SYMBOL}', content)
content = re.sub(r'DISCORD_WEBHOOK_URL=.*', f'DISCORD_WEBHOOK_URL={WEBHOOK}', content)
content = re.sub(r'INITIAL_CAPITAL=.*', 'INITIAL_CAPITAL=15', content)
# SIRENは低価格トークンのため、MAX_POSITION_SIZEは大きめに設定
# 内部の証拠金ベース計算が自動で適切なサイズに制限してくれる
content = re.sub(r'MAX_POSITION_SIZE=.*', 'MAX_POSITION_SIZE=9999', content)

remote_path = f'/root/bitget-trading-bot/.env.{COIN}'
print(f"Uploading {remote_path}...")
with sftp.open(remote_path, 'w') as f:
    f.write(content.encode('utf-8'))
sftp.close()

# Create systemd service
service_content = f"""[Unit]
Description=Bitget AI Trading Bot ({COIN.upper()})
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/bitget-trading-bot
Environment="PYTHONPATH=/root/bitget-trading-bot"
ExecStart=/root/bitget-trading-bot/venv/bin/python src/main.py
Restart=always
RestartSec=10
EnvironmentFile=/root/bitget-trading-bot/.env.{COIN}

[Install]
WantedBy=multi-user.target
"""
cmd = f"cat << 'EOF' > /etc/systemd/system/bitget-bot-{COIN}.service\n{service_content}\nEOF"
ssh.exec_command(cmd)

print("Starting SIREN bot...")
ssh.exec_command("systemctl daemon-reload")
ssh.exec_command(f"systemctl enable bitget-bot-{COIN}")
ssh.exec_command(f"systemctl start bitget-bot-{COIN}")

stdin, stdout, stderr = ssh.exec_command(f"sleep 3 && systemctl is-active bitget-bot-{COIN}")
print(f"SIREN Bot Status: {stdout.read().decode('utf-8').strip()}")

ssh.close()
print("Deployment completed!")
