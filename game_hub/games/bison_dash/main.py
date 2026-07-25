import json
import os
import time
import asyncio
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from filelock import FileLock

from game_hub.games.bison_dash.engine.simulator import simulate_race
import game_hub.games.bison_dash.engine.procedural as procedural

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Make sure static and template directories exist for the game
BASE_DIR = Path("game_hub/games/bison_dash")
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"
DATA_DIR = BASE_DIR / "data"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Local settings and lineup files
SETTINGS_FILE = DATA_DIR / "bison_settings.json"
LINEUP_FILE = DATA_DIR / "lineup.json"

def read_data(filepath: Path) -> dict:
    if not filepath.exists():
        return {}
    with open(filepath, "r") as f:
        return json.load(f)

def write_data(filepath: Path, data: dict):
    lock_path = str(filepath) + ".lock"
    with FileLock(lock_path):
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

# Initialize files
if not SETTINGS_FILE.exists():
    write_data(SETTINGS_FILE, {
        "state": "Betting_Open",
        "timers": {
            "Soft_Closure": 10,
            "Closed_Intros": 60,
            "Race_Sprint": 30,
            "Results_Payout": 120
        },
        "state_start_time": time.time()
    })

if not LINEUP_FILE.exists():
    # Generate initial lineup
    initial_lineup = [procedural.generate_bison(i+1) for i in range(4)]
    write_data(LINEUP_FILE, {"lineup": initial_lineup})

# In-memory cached race state
current_telemetry_cache = {}

class ResetPayload(BaseModel):
    action: str
    timestamp: int
    target_state: str

class BisonDashStatePayload(BaseModel):
    state: str

class BisonDashTimersPayload(BaseModel):
    soft_closure: int
    closed_intros: int
    race_sprint: int
    results_payout: int

class BisonDashRetirePayload(BaseModel):
    bison_id: str

@app.post("/api/local/reset")
async def local_reset(payload: ResetPayload):
    """Triggered by the master admin 'Panic Reset' button."""
    settings = read_data(SETTINGS_FILE)
    settings["state"] = "Betting_Open"
    settings["state_start_time"] = time.time()
    write_data(SETTINGS_FILE, settings)

    global current_telemetry_cache
    current_telemetry_cache = {}
    return {"status": "success", "message": "Bison Dash reset to Betting_Open"}

@app.get("/api/current_race")
def get_current_race():
    """Polled by projector.html to read state and get telemetry."""
    settings = read_data(SETTINGS_FILE)
    state = settings.get("state", "Betting_Open")

    lineup_data = read_data(LINEUP_FILE)

    # Calculate exact elapsed time in this state
    state_start_time = settings.get("state_start_time", time.time())
    elapsed = time.time() - state_start_time

    return {
        "status": "success",
        "state": state,
        "elapsed_time": elapsed,
        "lineup": lineup_data.get("lineup", []),
        "telemetry": current_telemetry_cache
    }

@app.get("/api/bisondash/state")
def get_bisondash_state():
    settings = read_data(SETTINGS_FILE)
    return {"status": "success", "state_data": settings}

@app.post("/api/bisondash/state/update")
def update_bisondash_state(payload: BisonDashStatePayload):
    settings = read_data(SETTINGS_FILE)
    settings["state"] = payload.state
    settings["state_start_time"] = time.time()
    write_data(SETTINGS_FILE, settings)
    return {"status": "success", "message": f"State set to {payload.state}"}

@app.post("/api/bisondash/timers/update")
def update_bisondash_timers(payload: BisonDashTimersPayload):
    settings = read_data(SETTINGS_FILE)
    if "timers" not in settings:
        settings["timers"] = {}

    settings["timers"]["Soft_Closure"] = payload.soft_closure
    settings["timers"]["Closed_Intros"] = payload.closed_intros
    settings["timers"]["Race_Sprint"] = payload.race_sprint
    settings["timers"]["Results_Payout"] = payload.results_payout

    write_data(SETTINGS_FILE, settings)
    return {"status": "success", "message": "Timers updated"}

@app.get("/api/bisondash/lineup")
def get_bisondash_lineup():
    lineup_data = read_data(LINEUP_FILE)
    return {"status": "success", "lineup": lineup_data.get("lineup", [])}

@app.post("/api/bisondash/lineup/retire")
def retire_bison(payload: BisonDashRetirePayload):
    lineup_data = read_data(LINEUP_FILE)
    lineup = lineup_data.get("lineup", [])

    # Find and replace the bison
    for i, bison in enumerate(lineup):
        if bison.get("id") == payload.bison_id:
            new_bison = procedural.generate_bison(i+1)
            lineup[i] = new_bison
            break

    lineup_data["lineup"] = lineup
    write_data(LINEUP_FILE, lineup_data)

    return {"status": "success", "message": f"Retired bison {payload.bison_id} and replaced it."}

async def elastic_clock_loop():
    """
    Background loop that continuously checks settings for state and slider changes
    to drive the 'Elastic Clock' state machine.
    """
    global current_telemetry_cache

    while True:
        await asyncio.sleep(0.5)  # Poll 2 times a second

        try:
            settings = read_data(SETTINGS_FILE)
            if not settings:
                continue

            current_state = settings.get("state", "Betting_Open")
            timers = settings.get("timers", {})
            start_time = settings.get("state_start_time", time.time())

            elapsed = time.time() - start_time

            # State transitions based on elastic clock
            new_state = None

            if current_state == "Soft_Closure" and elapsed >= timers.get("Soft_Closure", 10):
                new_state = "Closed_Intros"
            elif current_state == "Closed_Intros" and elapsed >= timers.get("Closed_Intros", 60):
                new_state = "Race_Sprint"
            elif current_state == "Race_Sprint" and elapsed >= timers.get("Race_Sprint", 30):
                new_state = "Results_Payout"
            elif current_state == "Results_Payout" and elapsed >= timers.get("Results_Payout", 120):
                new_state = "Betting_Open"

            if new_state:
                settings["state"] = new_state
                settings["state_start_time"] = time.time()
                write_data(SETTINGS_FILE, settings)
                print(f"[Bison Dash] State transitioned to {new_state}")

                # Triggers on specific state changes
                if new_state == "Closed_Intros":
                    # Generate deterministic simulation telemetry right before the race begins
                    lineup_data = read_data(LINEUP_FILE)
                    current_telemetry_cache = simulate_race(lineup_data.get("lineup", []))
                    print(f"[Bison Dash] Telemetry calculated for upcoming race.")

                if new_state == "Betting_Open":
                    # Clear telemetry when back to idle
                    current_telemetry_cache = {}

        except Exception as e:
            print(f"[Bison Dash] Error in elastic clock loop: {e}")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(elastic_clock_loop())

@app.get("/", response_class=HTMLResponse)
def read_root():
    with open(TEMPLATE_DIR / "projector.html", "r") as f:
        return f.read()

@app.get("/projector", response_class=HTMLResponse)
def serve_projector():
    with open(TEMPLATE_DIR / "projector.html", "r") as f:
        return f.read()

@app.get("/admin", response_class=HTMLResponse)
def serve_admin():
    with open(TEMPLATE_DIR / "admin.html", "r") as f:
        return f.read()
