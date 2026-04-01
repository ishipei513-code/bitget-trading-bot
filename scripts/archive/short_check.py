import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("160.251.137.212", username="root", password="$$Ishipei513")

services = ["bitget-bot", "bitget-bot-btc", "bitget-bot-sol", "bitget-bot-bnb", "bitget-bot-tsla", "bitget-bot-siren"]
out = []
print("Checking services...")
for s in services:
    _, stdout, _ = ssh.exec_command(f'systemctl is-active {s}')
    status = stdout.read().decode().strip()
    out.append(f"{s}: {status}")

with open("clean_status.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))

ssh.close()
print("Done. Status saved to clean_status.txt")
