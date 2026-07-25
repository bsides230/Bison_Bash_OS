from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio
import time
from pathlib import Path
from master_admin.data_manager import read_data, write_data, SETTINGS_FILE, ACTIVE_LINEUP_FILE
from game_hub.games.bison_dash.engine.simulator import simulate_race

app = FastAPI()

# Make sure static and template directories exist for the game
STATIC_DIR = Path("game_hub/games/bison_dash/static")
TEMPLATE_DIR = Path("game_hub/games/bison_dash/templates")
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# In-memory cached race state
current_telemetry_cache = {}

class ResetPayload(BaseModel):
    action: str
    timestamp: int
    target_state: str

@app.post("/api/local/reset")
async def local_reset(payload: ResetPayload):
    """Triggered by the master admin 'Panic Reset' button."""
    settings = read_data(SETTINGS_FILE)
    if "bison_dash" in settings:
        settings["bison_dash"]["state"] = "Betting_Open"
        settings["bison_dash"]["state_start_time"] = time.time()
        write_data(SETTINGS_FILE, settings, backup=False)

    global current_telemetry_cache
    current_telemetry_cache = {}
    return {"status": "success", "message": "Bison Dash reset to Betting_Open"}

@app.get("/api/current_race")
def get_current_race():
    """Polled by projector.html to read state and get telemetry."""
    settings = read_data(SETTINGS_FILE)
    bison_state = settings.get("bison_dash", {})
    state = bison_state.get("state", "Betting_Open")

    lineup_data = read_data(ACTIVE_LINEUP_FILE)

    # Calculate exact elapsed time in this state
    state_start_time = bison_state.get("state_start_time", time.time())
    elapsed = time.time() - state_start_time

    return {
        "status": "success",
        "state": state,
        "elapsed_time": elapsed,
        "lineup": lineup_data.get("lineup", []),
        "telemetry": current_telemetry_cache
    }

async def elastic_clock_loop():
    """
    Background loop that continuously checks admin_settings.json for state and slider changes
    to drive the 'Elastic Clock' state machine.
    """
    global current_telemetry_cache

    while True:
        await asyncio.sleep(0.5)  # Poll 2 times a second

        try:
            settings = read_data(SETTINGS_FILE)
            if "bison_dash" not in settings:
                continue

            bison_state = settings["bison_dash"]
            current_state = bison_state["state"]
            timers = bison_state["timers"]
            start_time = bison_state["state_start_time"]

            elapsed = time.time() - start_time

            # State transitions based on elastic clock
            new_state = None

            if current_state == "Soft_Closure" and elapsed >= timers["Soft_Closure"]:
                new_state = "Closed_Intros"
            elif current_state == "Closed_Intros" and elapsed >= timers["Closed_Intros"]:
                new_state = "Race_Sprint"
            elif current_state == "Race_Sprint" and elapsed >= timers["Race_Sprint"]:
                new_state = "Results_Payout"
            elif current_state == "Results_Payout" and elapsed >= timers["Results_Payout"]:
                new_state = "Betting_Open"

            if new_state:
                bison_state["state"] = new_state
                bison_state["state_start_time"] = time.time()
                write_data(SETTINGS_FILE, settings, backup=False)
                print(f"[Bison Dash] State transitioned to {new_state}")

                # Triggers on specific state changes
                if new_state == "Closed_Intros":
                    # Generate deterministic simulation telemetry right before the race begins
                    lineup_data = read_data(ACTIVE_LINEUP_FILE)
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

@app.get("/projector", response_class=HTMLResponse)
def serve_projector():
    with open(TEMPLATE_DIR / "projector.html", "r") as f:
        return f.read()
