import paramiko

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)
    print("=== VPS Bot Status ===")
    services = [
        "bitget-bot", 
        "bitget-bot-btc", 
        "bitget-bot-sol", 
        "bitget-bot-bnb", 
        "bitget-bot-tsla", 
        "bitget-bot-siren"
    ]
    
    for s in services:
        _, stdout, _ = ssh.exec_command(f"systemctl is-active {s}")
        status = stdout.read().decode().strip()
        print(f"[{s.upper()}]: {status}")
        
        if status == "active":
            _, stdout, _ = ssh.exec_command(f"journalctl -u {s} -n 3 --no-pager")
            logs = stdout.read().decode().strip()
            # print only the actual log messages (last part of journalctl line)
            for line in logs.split('\n'):
                print(f"  > {line}")
        print("-" * 50)
        
except Exception as e:
    print(f"Connection failed: {e}")
finally:
    ssh.close()
