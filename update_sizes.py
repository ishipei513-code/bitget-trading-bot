import json

updates = {
    "btc": {"initial_capital": 15, "max_position_size": 0.001},
    "eth": {"initial_capital": 15, "max_position_size": 0.018},
    "sol": {"initial_capital": 15, "max_position_size": 0.9},
    "bnb": {"initial_capital": 15, "max_position_size": 0.125},
    "tsla": {"initial_capital": 15, "max_position_size": 0.2},
    "siren": {"initial_capital": 15, "max_position_size": 90.0}
}

with open("bots_config.json", "r", encoding="utf-8") as f:
    d = json.load(f)

for bot_name, values in updates.items():
    if bot_name in d["bots"]:
        d["bots"][bot_name].update(values)

with open("bots_config.json", "w", encoding="utf-8") as f:
    json.dump(d, f, indent=4)

print("Sizes updated successfully!")
