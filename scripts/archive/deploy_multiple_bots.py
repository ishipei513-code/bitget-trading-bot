import paramiko
import re

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)

sftp = ssh.open_sftp()
print("Fetching current .env file...")
with sftp.open('/root/bitget-trading-bot/.env', 'r') as f:
    env_content = f.read().decode('utf-8')

def create_and_upload_env(coin, symbol, initial_capital, max_pos_size, webhook):
    content = env_content
    content = re.sub(r'TRADING_SYMBOL=.*', f'TRADING_SYMBOL={symbol}', content)
    content = re.sub(r'INITIAL_CAPITAL=.*', f'INITIAL_CAPITAL={initial_capital}', content)
    content = re.sub(r'MAX_POSITION_SIZE=.*', f'MAX_POSITION_SIZE={max_pos_size}', content)
    content = re.sub(r'DISCORD_WEBHOOK_URL=.*', f'DISCORD_WEBHOOK_URL={webhook}', content)
    
    remote_path = f'/root/bitget-trading-bot/.env.{coin.lower()}'
    print(f"Uploading {remote_path}...")
    with sftp.open(remote_path, 'w') as f:
        f.write(content.encode('utf-8'))

# それぞれの専用Webhook URL
BNB_WEBHOOK = "https://discord.com/api/webhooks/1488168296388759564/-ZA5lpco_StaZCWCRIQJrmJqwGifvMMfHKIKqzWxhy0JJccCa7ThDJiTpfwtfFtO_HuM"
BTC_WEBHOOK = "https://discord.com/api/webhooks/1488520063811190844/uujN0v14qGDKTKGSUu9lYsH5whC9k_NyrdESF9aP1abLE4dOUTvlVmPLRylCC6i6DpZ_"
SOL_WEBHOOK = "https://discord.com/api/webhooks/1488520008911945788/WZmOOQ7hSMUtjQVRIBsV5ce97KkcVVGS5wR3BwrNUWr-0rrzl35P3URR4iTpf3r2nKek"

# Deploy .env copies
create_and_upload_env('bnb', 'BNB/USDT:USDT', '30', '0.05', BNB_WEBHOOK)
create_and_upload_env('btc', 'BTC/USDT:USDT', '30', '0.001', BTC_WEBHOOK)
create_and_upload_env('sol', 'SOL/USDT:USDT', '30', '0.5', SOL_WEBHOOK)
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

print("Creating systemd services...")
create_service('bnb')
create_service('btc')
create_service('sol')

print("Starting services...")
ssh.exec_command("systemctl daemon-reload")
ssh.exec_command("systemctl enable bitget-bot-bnb bitget-bot-btc bitget-bot-sol")
ssh.exec_command("systemctl restart bitget-bot-bnb bitget-bot-btc bitget-bot-sol")

ssh.close()
print("Deployment completed!")
