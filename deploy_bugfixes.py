import paramiko

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

files_to_upload = [
    (r"c:\Users\iship\bitget-trading-bot\src\ai\prompts.py", "/root/bitget-trading-bot/src/ai/prompts.py"),
    (r"c:\Users\iship\bitget-trading-bot\src\ai\gemini_client.py", "/root/bitget-trading-bot/src/ai/gemini_client.py"),
    (r"c:\Users\iship\bitget-trading-bot\src\main.py", "/root/bitget-trading-bot/src/main.py"),
    (r"c:\Users\iship\bitget-trading-bot\src\trading\executor.py", "/root/bitget-trading-bot/src/trading/executor.py"),
    (r"c:\Users\iship\bitget-trading-bot\src\trading\risk_manager.py", "/root/bitget-trading-bot/src/trading/risk_manager.py"),
    (r"c:\Users\iship\bitget-trading-bot\src\analysis\data_collector.py", "/root/bitget-trading-bot/src/analysis/data_collector.py"),
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)

sftp = ssh.open_sftp()
for local, remote in files_to_upload:
    name = local.split(chr(92))[-1]
    print(f"Uploading {name}...")
    sftp.put(local, remote)
sftp.close()

print("\nRestarting all active bots...")
for service in ['bitget-bot', 'bitget-bot-sol', 'bitget-bot-tsla', 'bitget-bot-siren']:
    ssh.exec_command(f"systemctl restart {service}")

ssh.close()
print("All fixes deployed!")
