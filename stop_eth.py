import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("160.251.137.212", username="root", password="$$Ishipei513", timeout=15)

# 致命的なミスだったETHボットを止める
ssh.exec_command("systemctl stop bitget-bot-eth")
ssh.exec_command("systemctl disable bitget-bot-eth")

# さらに、全main.pyを再び念入りに消す
ssh.exec_command("pkill -9 -f 'main.py'")

ssh.close()
