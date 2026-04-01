import paramiko
import time

HOSTNAME = "160.251.137.212"
USERNAME = "root"
PASSWORD = "$$Ishipei513"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD, timeout=10)
    print('Connected via paramiko!')

    patch_code = '''
import sys
path = '/root/bitget-trading-bot/src/main.py'
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = f.read()
    if 'record_action' not in data:
        data = data.replace('                    # 4. ガードレール検証', '                    # HOLDカウンター更新\\n                    self.trigger_evaluator.record_action(decision.action)\\n\\n                    # 4. ガードレール検証')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(data)
        print('PATCH_SUCCESS')
    else:
        print('ALREADY_PATCHED')
except Exception as e:
    print('PATCH_ERROR:', e)
'''
    stdin, stdout, stderr = ssh.exec_command('python3 -c "{}"'.format(patch_code.replace('"', '\\"')))
    print(stdout.read().decode().strip())
    print(stderr.read().decode().strip())

    print('Restarting services...')
    stdin, stdout, stderr = ssh.exec_command('systemctl restart bitget-bot.service bitget-bot-siren.service bitget-bot-sol.service bitget-bot-tsla.service')
    print('stdout:', stdout.read().decode().strip())
    print('stderr:', stderr.read().decode().strip())
    
    ssh.close()
    print('Finished!')
except Exception as e:
    print('Error:', e)
