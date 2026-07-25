from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import httpx
import time
import asyncio
from pathlib import Path
import os
import uvicorn

from master_admin.process_manager import manager
from master_admin.data_manager import read_data, write_data, PLAYERS_FILE, SETTINGS_FILE

# Ensure static directories exist
STATIC_DIR = Path("master_admin/static")
(STATIC_DIR / "css").mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "js").mkdir(parents=True, exist_ok=True)

app = FastAPI()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="master_admin/static"), name="static")
templates = Jinja2Templates(directory=".")

# Register real game hub games
manager.register_game("bison_dash", 8001, "game_hub.games.bison_dash.main:app")

# Tailscale Middleware
@app.middleware("http")
async def tailscale_enforcement(request: Request, call_next):
    settings = read_data(SETTINGS_FILE)
    if settings.get("tailscale_enforcement", False):
        client_ip = request.client.host
        # Read the current tailscale_ip_pool on each incoming request
        pool = settings.get("tailscale_ip_pool", "100.")
        if not client_ip.startswith(pool):
            return HTMLResponse("Forbidden: Must connect via Tailscale", status_code=403)
    response = await call_next(request)
    return response

# Payload Models
class StartStopPayload(BaseModel):
    game_id: str

class InjectTokensPayload(BaseModel):
    player_id: str
    amount: int

class UpdateSettingsPayload(BaseModel):
    tailscale_enforcement: bool
    tailscale_ip_pool: str

class BisonDashStatePayload(BaseModel):
    state: str

class BisonDashTimersPayload(BaseModel):
    soft_closure: int
    closed_intros: int
    race_sprint: int
    results_payout: int

class BisonDashRetirePayload(BaseModel):
    bison_id: str

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="master_admin/templates/dashboard.html")

@app.get("/api/process/status")
def get_process_status():
    return manager.get_status()

@app.post("/api/process/start")
async def start_process(payload: StartStopPayload):
    success = await manager.start_game(payload.game_id)
    if success:
        return {"status": "success", "message": f"Started {payload.game_id}"}
    return {"status": "error", "message": f"Failed to start {payload.game_id} or already running"}

@app.post("/api/process/stop")
async def stop_process(payload: StartStopPayload):
    success = await manager.stop_game(payload.game_id)
    if success:
        return {"status": "success", "message": f"Stopped {payload.game_id}"}
    return {"status": "error", "message": f"Failed to stop {payload.game_id} or not running"}

@app.post("/api/global/reset")
async def global_reset():
    status = manager.get_status()
    active_ports = [info["port"] for game_id, info in status.items() if info["running"]]

    payload = {
        "action": "GLOBAL_RESET",
        "timestamp": int(time.time()),
        "target_state": "IDLE"
    }

    async def reset_port(port):
        async with httpx.AsyncClient() as client:
            try:
                # Fire and forget with short timeout
                await client.post(f"http://127.0.0.1:{port}/api/local/reset", json=payload, timeout=2.0)
            except Exception as e:
                print(f"Error resetting port {port}: {e}")

    # Broadcast concurrently to all active game servers
    await asyncio.gather(*(reset_port(port) for port in active_ports))

    return {"status": "success", "message": f"Global reset broadcasted to {len(active_ports)} instances"}

@app.get("/api/global/logs")
def get_global_logs():
    return {"logs": manager.get_logs(limit=200)}

@app.post("/api/admin/inject-tokens")
def inject_tokens(payload: InjectTokensPayload):
    # This demonstrates Data Redundancy loop
    players_data = read_data(PLAYERS_FILE)

    if payload.player_id not in players_data["players"]:
        players_data["players"][payload.player_id] = {"balance": 0}

    players_data["players"][payload.player_id]["balance"] += payload.amount

    # write_data handles the atomic write + incremental backup loop
    write_data(PLAYERS_FILE, players_data)

    return {"status": "success", "new_balance": players_data["players"][payload.player_id]["balance"]}

@app.get("/api/admin/settings")
def get_admin_settings():
    settings = read_data(SETTINGS_FILE)
    return {"status": "success", "settings": settings}

@app.post("/api/admin/settings/update")
def update_admin_settings(payload: UpdateSettingsPayload):
    settings = read_data(SETTINGS_FILE)
    settings["tailscale_enforcement"] = payload.tailscale_enforcement
    settings["tailscale_ip_pool"] = payload.tailscale_ip_pool
    # write_data handles the atomic write + incremental backup loop
    write_data(SETTINGS_FILE, settings, backup=False)
    return {"status": "success", "message": "Settings updated"}


# Bison Dash Specific Endpoints
from master_admin.data_manager import ACTIVE_LINEUP_FILE
import game_hub.games.bison_dash.engine.procedural as procedural

@app.get("/api/bisondash/state")
def get_bisondash_state():
    settings = read_data(SETTINGS_FILE)
    if "bison_dash" not in settings:
        return {"status": "error", "message": "Bison Dash not initialized"}
    return {"status": "success", "state_data": settings["bison_dash"]}

@app.post("/api/bisondash/state/update")
def update_bisondash_state(payload: BisonDashStatePayload):
    settings = read_data(SETTINGS_FILE)
    if "bison_dash" not in settings:
        settings["bison_dash"] = {}

    settings["bison_dash"]["state"] = payload.state
    settings["bison_dash"]["state_start_time"] = time.time()
    write_data(SETTINGS_FILE, settings, backup=False)
    return {"status": "success", "message": f"State set to {payload.state}"}

@app.post("/api/bisondash/timers/update")
def update_bisondash_timers(payload: BisonDashTimersPayload):
    settings = read_data(SETTINGS_FILE)
    if "bison_dash" not in settings:
        settings["bison_dash"] = {}
    if "timers" not in settings["bison_dash"]:
        settings["bison_dash"]["timers"] = {}

    settings["bison_dash"]["timers"]["Soft_Closure"] = payload.soft_closure
    settings["bison_dash"]["timers"]["Closed_Intros"] = payload.closed_intros
    settings["bison_dash"]["timers"]["Race_Sprint"] = payload.race_sprint
    settings["bison_dash"]["timers"]["Results_Payout"] = payload.results_payout

    write_data(SETTINGS_FILE, settings, backup=False)
    return {"status": "success", "message": "Timers updated"}

@app.get("/api/bisondash/lineup")
def get_bisondash_lineup():
    lineup_data = read_data(ACTIVE_LINEUP_FILE)
    return {"status": "success", "lineup": lineup_data.get("lineup", [])}

@app.post("/api/bisondash/lineup/retire")
def retire_bison(payload: BisonDashRetirePayload):
    lineup_data = read_data(ACTIVE_LINEUP_FILE)
    lineup = lineup_data.get("lineup", [])

    # Find and replace the bison
    for i, bison in enumerate(lineup):
        if bison.get("id") == payload.bison_id:
            new_bison = procedural.generate_bison(i+1)
            lineup[i] = new_bison
            break

    lineup_data["lineup"] = lineup
    write_data(ACTIVE_LINEUP_FILE, lineup_data, backup=False) # Only players.json needs backup

    return {"status": "success", "message": f"Retired bison {payload.bison_id} and replaced it."}

if __name__ == "__main__":
    port_file = Path("port.txt")
    port = 8000
    try:
        if not port_file.exists():
            with open(port_file, "w") as f:
                f.write("8000")
        else:
            with open(port_file, "r") as f:
                port = int(f.read().strip())
    except Exception as e:
        print(f"Error reading port.txt: {e}. Defaulting to 8000.")
        with open(port_file, "w") as f:
            f.write("8000")
        port = 8000

    uvicorn.run(app, host="0.0.0.0", port=port)
