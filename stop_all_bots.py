import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("160.251.137.212", username="root", password="$$Ishipei513", timeout=15)

all_bots = [
    "bitget-bot",
    "bitget-bot-btc",
    "bitget-bot-sol",
    "bitget-bot-bnb",
    "bitget-bot-tsla",
    "bitget-bot-siren",
]

print("=== 全ボット停止中 ===")
for svc in all_bots:
    _, stdout, _ = ssh.exec_command(f"systemctl stop {svc}")
    stdout.channel.recv_exit_status()
    print(f"  停止: {svc}")

time.sleep(3)

print("")
print("=== 停止確認 ===")
for svc in all_bots:
    _, stdout, _ = ssh.exec_command(f"systemctl is-active {svc}")
    status = stdout.read().decode().strip()
    icon = "OK" if status == "inactive" else "NG"
    print(f"  [{icon}] {svc}: {status}")

ssh.close()
print("")
print("完了")
