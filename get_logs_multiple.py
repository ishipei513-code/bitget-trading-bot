import paramiko

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)

def check_log(coin):
    print(f"\n--- Output for {coin.upper()} ---")
    stdin, stdout, stderr = ssh.exec_command(f'journalctl -u bitget-bot-{coin.lower()} -n 15 --no-pager')
    print(stdout.read().decode('utf-8'))

check_log('btc')
check_log('sol')

ssh.close()
