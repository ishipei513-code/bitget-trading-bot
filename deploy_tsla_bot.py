import paramiko
import re

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

TSLA_WEBHOOK = "https://discord.com/api/webhooks/1488522191971680260/8BYL2LGiIHgLTmG0d3rJ4snoZ7BWp1nH_TXe4hEzTFMmp_i605w97V5a0UE7KQQpBfS4"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)

sftp = ssh.open_sftp()
print("Fetching current base .env file...")
with sftp.open('/root/bitget-trading-bot/.env', 'r') as f:
    env_content = f.read().decode('utf-8')

def create_and_upload_env(coin, symbol, webhook):
    content = env_content
    content = re.sub(r'TRADING_SYMBOL=.*', f'TRADING_SYMBOL={symbol}', content)
    content = re.sub(r'DISCORD_WEBHOOK_URL=.*', f'DISCORD_WEBHOOK_URL={webhook}', content)
    
    remote_path = f'/root/bitget-trading-bot/.env.{coin.lower()}'
    print(f"Uploading {remote_path}...")
    with sftp.open(remote_path, 'w') as f:
        f.write(content.encode('utf-8'))

# Deploy TSLA .env config (Max size/Capital defaults to base config)
create_and_upload_env('tsla', 'TSLA/USDT:USDT', TSLA_WEBHOOK)
sftp.close()

def create_service(coin):
    service_content = f"""[Unit]
Description=Bitget AI Trading Bot ({coin.upper()})
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/bitget-trading-bot
Environment="PYTHONPATH=/root/bitget-trading-bot"
ExecStart=/root/bitget-trading-bot/venv/bin/python src/main.py
Restart=always
RestartSec=10
EnvironmentFile=/root/bitget-trading-bot/.env.{coin.lower()}

[Install]
WantedBy=multi-user.target
"""
    cmd = f"cat << 'EOF' > /etc/systemd/system/bitget-bot-{coin.lower()}.service\n{service_content}\nEOF"
    ssh.exec_command(cmd)

print("Creating TSLA systemd service...")
create_service('tsla')

print("Starting TSLA bot...")
ssh.exec_command("systemctl daemon-reload")
ssh.exec_command("systemctl enable bitget-bot-tsla")
ssh.exec_command("systemctl start bitget-bot-tsla")

stdin, stdout, stderr = ssh.exec_command("sleep 2 && systemctl is-active bitget-bot-tsla")
print("TSLA Bot Status:", stdout.read().decode('utf-8').strip())

ssh.close()
print("Deployment completed!")
