import json

with open("game_hub/games/bison_dash/main.py", "r") as f:
    content = f.read()

# Replace update_bisondash_state
old_update = """def update_bisondash_state(payload: BisonDashStatePayload):
    settings = read_data(SETTINGS_FILE)
    settings["state"] = payload.state
    settings["state_start_time"] = time.time()
    write_data(SETTINGS_FILE, settings)
    return {"status": "success", "message": f"State set to {payload.state}"}"""

new_update = """def update_bisondash_state(payload: BisonDashStatePayload):
    global current_telemetry_cache
    settings = read_data(SETTINGS_FILE)
    settings["state"] = payload.state
    settings["state_start_time"] = time.time()
    write_data(SETTINGS_FILE, settings)

    # Also trigger telemetry cache updates when state is forced
    if payload.state == "Closed_Intros":
        lineup_data = read_data(LINEUP_FILE)
        current_telemetry_cache = simulate_race(lineup_data.get("lineup", []))
    elif payload.state == "Betting_Open":
        current_telemetry_cache = {}

    return {"status": "success", "message": f"State set to {payload.state}"}"""

content = content.replace(old_update, new_update)

with open("game_hub/games/bison_dash/main.py", "w") as f:
    f.write(content)
