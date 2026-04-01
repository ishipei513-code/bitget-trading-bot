import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("160.251.137.212", username="root", password="$$Ishipei513")

_, out, _ = ssh.exec_command("systemctl is-active bitget-bot")
status = out.read().decode().strip()

_, out, _ = ssh.exec_command("journalctl -u bitget-bot -n 15 --no-pager")
logs = out.read().decode()

with open("bot_logs.txt", "w", encoding="utf-8") as f:
    f.write(f"Status: {status}\n\nLogs:\n{logs}")

ssh.close()
print("Logs saved to bot_logs.txt")
