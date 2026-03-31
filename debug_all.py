import paramiko

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)

bots = ['bitget-bot', 'bitget-bot-sol', 'bitget-bot-tsla', 'bitget-bot-siren']

with open('debug_report.txt', 'w', encoding='utf-8') as f:
    for bot in bots:
        f.write(f"\n{'='*60}\n")
        f.write(f"  {bot.upper()}\n")
        f.write(f"{'='*60}\n")
        
        # Check service status
        stdin, stdout, stderr = ssh.exec_command(f"systemctl is-active {bot}")
        status = stdout.read().decode('utf-8').strip()
        f.write(f"Status: {status}\n\n")
        
        # Get last 30 lines of log including errors
        stdin, stdout, stderr = ssh.exec_command(f"journalctl -u {bot} -n 30 --no-pager 2>&1")
        log = stdout.read().decode('utf-8')
        f.write(f"--- Latest logs ---\n{log}\n")
        
        # Check for ERROR lines specifically
        stdin, stdout, stderr = ssh.exec_command(f"journalctl -u {bot} --no-pager | grep -i 'ERROR\\|WARN\\|Traceback\\|Exception' | tail -10")
        errors = stdout.read().decode('utf-8')
        f.write(f"--- Errors/Warnings ---\n{errors}\n")

ssh.close()
print("Debug report saved to debug_report.txt")
