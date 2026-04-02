import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("160.251.137.212", username="root", password="$$Ishipei513", timeout=10)

cmds = [
    "sed -i 's/GEMINI_API_KEY=.*/GEMINI_API_KEY=AIzaSyDhW3J_QeHtz4IweXjO7jZ3_bUrtF6yJKs/g' /root/bitget-trading-bot/.env.*",
    "sed -i 's/GEMINI_API_KEY=.*/GEMINI_API_KEY=AIzaSyDhW3J_QeHtz4IweXjO7jZ3_bUrtF6yJKs/g' /root/bitget-trading-bot/.env",
    "systemctl restart bitget-bot-eth bitget-bot-sol bitget-bot-bnb"
]

for cmd in cmds:
    print(f"Running: {cmd}")
    _, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())
    print(stderr.read().decode())

ssh.close()
print("Done.")
