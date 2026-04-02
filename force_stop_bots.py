import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("160.251.137.212", username="root", password="$$Ishipei513", timeout=15)

print("=== 強制停止処理を開始 ===")

# systemctl で止める (再起動を防ぐため disable)
bots = ["bitget-bot", "bitget-bot-btc", "bitget-bot-sol", "bitget-bot-bnb", "bitget-bot-tsla", "bitget-bot-siren"]
for bot in bots:
    ssh.exec_command(f"systemctl stop {bot}")
    ssh.exec_command(f"systemctl disable {bot}")

time.sleep(2)

print("\n=== 現在のPythonプロセス (kill前) ===")
_, stdout, _ = ssh.exec_command("ps aux | grep python | grep -v grep")
print(stdout.read().decode().strip())

# ボットプロセス（main.py等）を確実に kill -9 する
print("\n=== ボットプロセスを強制終了 ===")
ssh.exec_command("pkill -9 -f 'python.*main.py'")
ssh.exec_command("pkill -9 -f 'python.*src.main'")  # 実行パスに依るため念の為
time.sleep(2)

print("\n=== 現在のPythonプロセス (kill後) ===")
_, stdout, _ = ssh.exec_command("ps aux | grep python | grep -v grep")
after_ps = stdout.read().decode().strip()
if after_ps:
    print(after_ps)
else:
    print("👉 全てのPythonプロセスが完全に消滅しました。")

ssh.close()
