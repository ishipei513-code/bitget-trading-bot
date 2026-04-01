import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("160.251.137.212", username="root", password="$$Ishipei513", timeout=10)

with open('check_logs_out.txt', 'w', encoding='utf-8') as f:
    f.write("=== ETH ===\n")
    _, stdout, _ = ssh.exec_command("journalctl -u bitget-bot-eth --since '30 minutes ago' | grep -E 'Gemini判断|FormatGuard'")
    f.write(stdout.read().decode())
    
    f.write("=== BNB ===\n")
    _, stdout, _ = ssh.exec_command("journalctl -u bitget-bot-bnb --since '30 minutes ago' | grep -E 'Gemini判断|FormatGuard'")
    f.write(stdout.read().decode())
