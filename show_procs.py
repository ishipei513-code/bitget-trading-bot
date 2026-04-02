import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("160.251.137.212", username="root", password="$$Ishipei513", timeout=15)

# Pythonプロセスの取得 (grepプロセスとfail2banは除外)
_, stdout, _ = ssh.exec_command("ps aux | grep 'python' | grep -v 'grep' | grep -v 'fail2ban'")
python_procs = stdout.read().decode().strip()

# bot関連のsystemctlステータス取得（activeなものだけ）
_, stdout, _ = ssh.exec_command("systemctl list-units --type=service | grep 'bitget-bot'")
systemd_procs = stdout.read().decode().strip()

print("=== Python Processes on VPS ===")
if python_procs:
    print(python_procs)
else:
    print("(なし - すべてのPythonプロセスは停止しています)")

print("\n=== Active bot systemd services ===")
if systemd_procs:
    print(systemd_procs)
else:
    print("(なし - ボットのサービスはすべて停止しています)")

ssh.close()
