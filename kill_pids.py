import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("160.251.137.212", username="root", password="$$Ishipei513", timeout=15)

# 確実にmain.pyを含むプロセスを検索してkill
_, stdout, _ = ssh.exec_command("ps aux | grep 'main.py' | grep -v grep | awk '{print $2}'")
pids = stdout.read().decode().strip().split()
for pid in pids:
    if pid:
        print(f"Killing PID {pid}")
        ssh.exec_command(f"kill -9 {pid}")

_, stdout, _ = ssh.exec_command("ps aux | grep 'main.py' | grep -v grep")
print("Remaining main.py processes:")
print(stdout.read().decode().strip())

ssh.close()
