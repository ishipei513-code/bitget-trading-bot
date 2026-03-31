import paramiko

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)

bots = ['bitget-bot', 'bitget-bot-btc', 'bitget-bot-sol', 'bitget-bot-tsla', 'bitget-bot-siren']

with open('results.txt', 'w', encoding='utf-8') as f:
    f.write("=== 最新のトレード結果をチェック中 ===\n")
    for bot in bots:
        f.write(f"\n--- {bot.upper()} ---\n")
        cmd = f"journalctl -u {bot} | grep -E 'action=(LONG|SHORT)|注文|新規|決済|Position' | tail -n 5"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        
        if output:
            f.write(output + "\n")
        else:
            f.write("まだトレードは発生していません (様子見中)\n")
            
        cmd = f"journalctl -u {bot} | grep 'Gemini判断' | tail -n 1"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        last_action = stdout.read().decode('utf-8').strip()
        f.write(f"最近のAI判断: {last_action}\n")

ssh.close()
