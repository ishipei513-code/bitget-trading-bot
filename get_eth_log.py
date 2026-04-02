import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("160.251.137.212", username="root", password="$$Ishipei513", timeout=15)
_, stdout, _ = ssh.exec_command("journalctl -u bitget-bot-eth -n 50 --no-pager 2>&1")
log = stdout.read().decode("utf-8","ignore")
with open("data/eth_log.txt", "w", encoding="utf-8") as f:
    f.write(log)
print("Saved to data/eth_log.txt")
ssh.close()
