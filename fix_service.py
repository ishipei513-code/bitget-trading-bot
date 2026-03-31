import paramiko

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)

print("Fixing systemd service PYTHONPATH...")
service_content = """[Unit]
Description=Bitget AI Trading Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/bitget-trading-bot
Environment="PYTHONPATH=/root/bitget-trading-bot"
ExecStart=/root/bitget-trading-bot/venv/bin/python src/main.py
Restart=always
RestartSec=10
EnvironmentFile=/root/bitget-trading-bot/.env

[Install]
WantedBy=multi-user.target
"""
ssh.exec_command(f"cat << 'EOF' > /etc/systemd/system/bitget-bot.service\n{service_content}\nEOF")
ssh.exec_command("systemctl daemon-reload")
ssh.exec_command("systemctl restart bitget-bot")

stdin, stdout, stderr = ssh.exec_command('sleep 2 && systemctl status bitget-bot --no-pager')
print(stdout.read().decode('utf-8'))
ssh.close()
