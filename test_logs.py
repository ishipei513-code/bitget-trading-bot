import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("160.251.137.212", username="root", password="$$Ishipei513", timeout=10)

for coin in ["eth", "sol", "bnb"]:
    svc = f"bitget-bot-{coin}"
    print(f"=== {svc} Status ===")
    _, stdout, _ = ssh.exec_command(f"systemctl is-active {svc}")
    print("Active:", stdout.read().decode().strip())
    
    _, stdout, _ = ssh.exec_command(f"journalctl -u {svc} -n 10 --no-pager")
    print(stdout.read().decode().strip())
    print("\n")

ssh.close()
