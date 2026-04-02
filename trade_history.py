import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("160.251.137.212", username="root", password="$$Ishipei513", timeout=10)

bots = ["eth", "sol", "bnb"]
lines = []

for coin in bots:
    svc = f"bitget-bot-{coin}"
    # 直近3時間のログから重要イベントだけを抽出するよう変更
    _, stdout, _ = ssh.exec_command(f"journalctl -u {svc} --since '3 hours ago' --no-pager | grep -E 'エントリー|Gemini判断|決済|PnL|勝ち|負け|SL|TP|ポジションサイズ|キャップ|サイズ自動|注文成功|rule_engine|FormatGuard'")
    logs = stdout.read().decode().strip()
    lines.append(f"=== [{coin.upper()}] ===")
    if logs:
        for line in logs.split('\n'):
            parts = line.split(']: ', 1)
            msg = parts[1] if len(parts) > 1 else line
            lines.append(f"  {msg}")
            print(f"  {msg}")
    else:
        lines.append("  (no trade logs found)")
        print("  (no trade logs found)")
    lines.append("")
    print("")

ssh.close()

with open("trade_history.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("Done.")
