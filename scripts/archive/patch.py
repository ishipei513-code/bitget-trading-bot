import sys
path = '/root/bitget-trading-bot/src/main.py'
with open(path, 'r', encoding='utf-8') as f:
    data = f.read()
if 'self.trigger_evaluator.record_action' not in data:
    data = data.replace('                    # 4. ガードレール検証', '                    # HOLDカウンター更新\n                    self.trigger_evaluator.record_action(decision.action)\n\n                    # 4. ガードレール検証')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(data)
    print('PATCHED')
else:
    print('ALREADY_PATCHED')
