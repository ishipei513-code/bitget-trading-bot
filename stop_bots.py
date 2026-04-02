import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("160.251.137.212", username="root", password="$$Ishipei513", timeout=10)

stop_bots = ["bitget-bot-btc", "bitget-bot-tsla", "bitget-bot-siren"]

for svc in stop_bots:
    print(f"Stopping {svc}...")
    ssh.exec_command(f"systemctl stop {svc}")
    ssh.exec_command(f"systemctl disable {svc}")

# Verify
import time
time.sleep(2)
for svc in ["bitget-bot-eth", "bitget-bot-btc", "bitget-bot-sol", "bitget-bot-bnb", "bitget-bot-tsla", "bitget-bot-siren"]:
    _, stdout, _ = ssh.exec_command(f"systemctl is-active {svc}")
    status = stdout.read().decode().strip()
    print(f"  {svc}: {status}")

ssh.close()
print("Done.")
