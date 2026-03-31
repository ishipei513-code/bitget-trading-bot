import paramiko
import re

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

SOL_WEBHOOK = "https://discord.com/api/webhooks/1488520008911945788/WZmOOQ7hSMUtjQVRIBsV5ce97KkcVVGS5wR3BwrNUWr-0rrzl35P3URR4iTpf3r2nKek"
BTC_WEBHOOK = "https://discord.com/api/webhooks/1488520063811190844/uujN0v14qGDKTKGSUu9lYsH5whC9k_NyrdESF9aP1abLE4dOUTvlVmPLRylCC6i6DpZ_"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)

sftp = ssh.open_sftp()

def update_webhook(coin, new_url):
    remote_path = f'/root/bitget-trading-bot/.env.{coin.lower()}'
    print(f"Updating {remote_path}...")
    with sftp.open(remote_path, 'r') as f:
        content = f.read().decode('utf-8')
    
    # Replace the discord webhook url
    content = re.sub(r'DISCORD_WEBHOOK_URL=.*', f'DISCORD_WEBHOOK_URL={new_url}', content)
    
    with sftp.open(remote_path, 'w') as f:
        f.write(content.encode('utf-8'))
    print(f"Updated {coin} webhook successfully.")

update_webhook('btc', BTC_WEBHOOK)
update_webhook('sol', SOL_WEBHOOK)

sftp.close()

print("Restarting bots...")
ssh.exec_command("systemctl start bitget-bot-btc")
ssh.exec_command("systemctl start bitget-bot-sol")

stdin, stdout, stderr = ssh.exec_command("sleep 2 && systemctl is-active bitget-bot-btc")
print("BTC Bot:", stdout.read().decode('utf-8').strip())

stdin, stdout, stderr = ssh.exec_command("systemctl is-active bitget-bot-sol")
print("SOL Bot:", stdout.read().decode('utf-8').strip())

ssh.close()
