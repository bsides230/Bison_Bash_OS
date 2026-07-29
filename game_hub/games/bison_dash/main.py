import json
import os
import time
import asyncio
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
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

# Custom bisons directories
BISONS_DATA_DIR = DATA_DIR / "bisons"
BISONS_IMG_DIR = STATIC_DIR / "bisons"
BISONS_DATA_DIR.mkdir(parents=True, exist_ok=True)
BISONS_IMG_DIR.mkdir(parents=True, exist_ok=True)

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
    # Store just the mapping of slot (1-6) to bison_id, or None
    initial_lineup = [{"slot": i, "bison_id": None} for i in range(1, 7)]
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


class AssignBisonPayload(BaseModel):
    slot: int
    bison_id: str | None = None

@app.post("/api/bisondash/lineup/assign")
def assign_bison_to_slot(payload: AssignBisonPayload):
    lineup_data = read_data(LINEUP_FILE)
    lineup = lineup_data.get("lineup", [{"slot": i, "bison_id": None} for i in range(1, 7)])

    for item in lineup:
        if item["slot"] == payload.slot:
            item["bison_id"] = payload.bison_id
            break

    lineup_data["lineup"] = lineup
    write_data(LINEUP_FILE, lineup_data)
    return {"status": "success"}

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

def _get_mapped_lineup():
    """Maps lineup slots to actual bison data, falling back to procedural generation if empty."""
    lineup_data = read_data(LINEUP_FILE).get("lineup", [])

    # Ensure exactly 6 slots exist, padding if necessary (legacy fallback)
    slots_map = {item.get("slot"): item for item in lineup_data}
    padded_lineup = [slots_map.get(i, {"slot": i, "bison_id": None}) for i in range(1, 7)]

    mapped = []
    for item in padded_lineup:

        b_id = item.get("bison_id")
        b_slot = item.get("slot")
        bison = None

        if b_id:
            json_path = BISONS_DATA_DIR / f"{b_id}.json"
            if json_path.exists():
                bison = read_data(json_path)
                bison["slot"] = b_slot
                # Engine needs stats in a specific format
                bison["stats"] = {
                    "jockey_reaction": 10,
                    "bison_speed": bison.get("speed_base", 50),
                    "bison_cornering": 5,
                    "bison_stamina": 50
                }

        if not bison:
            # Fallback for empty slots
            bison = procedural.generate_bison(b_slot)

        mapped.append(bison)

    return mapped

@app.get("/api/current_race")
def get_current_race():
    """Polled by projector.html to read state and get telemetry."""
    settings = read_data(SETTINGS_FILE)
    state = settings.get("state", "Betting_Open")

    # Calculate exact elapsed time in this state
    state_start_time = settings.get("state_start_time", time.time())
    elapsed = time.time() - state_start_time

    return {
        "status": "success",
        "state": state,
        "elapsed_time": elapsed,
        "lineup": _get_mapped_lineup(),
        "telemetry": current_telemetry_cache
    }

@app.get("/api/bisondash/state")
def get_bisondash_state():
    settings = read_data(SETTINGS_FILE)
    return {"status": "success", "state_data": settings}

@app.post("/api/bisondash/state/update")
def update_bisondash_state(payload: BisonDashStatePayload):
    global current_telemetry_cache
    settings = read_data(SETTINGS_FILE)
    settings["state"] = payload.state
    settings["state_start_time"] = time.time()
    write_data(SETTINGS_FILE, settings)

    if payload.state == "Closed_Intros":
        current_telemetry_cache = simulate_race(_get_mapped_lineup())
    elif payload.state == "Betting_Open":
        current_telemetry_cache = {}

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
    return {"status": "success", "lineup": _get_mapped_lineup()}

@app.post("/api/bisondash/lineup/retire")
def retire_bison(payload: BisonDashRetirePayload):
    lineup_data = read_data(LINEUP_FILE)
    lineup = lineup_data.get("lineup", [])

    for i, item in enumerate(lineup):
        if item.get("bison_id") == payload.bison_id:
            item["bison_id"] = None
            break

    lineup_data["lineup"] = lineup
    write_data(LINEUP_FILE, lineup_data)

    return {"status": "success", "message": f"Retired bison slot {payload.bison_id}."}

# --- New Bison Roster API ---

@app.get("/bison", response_class=HTMLResponse)
def get_bison_builder():
    with open(TEMPLATE_DIR / "bison.html", 'r') as f:
        return f.read()

@app.get("/api/bisondash/bisons")
def list_bisons():
    bisons = []
    for f in BISONS_DATA_DIR.glob("*.json"):
        try:
            bisons.append(read_data(f))
        except:
            pass
    bisons.sort(key=lambda x: x.get('name', ''))
    return {"status": "success", "bisons": bisons}

class BisonData(BaseModel):
    id: str
    name: str
    color: str
    speed_base: int

@app.post("/api/bisondash/bisons/save")
def save_bison(payload: BisonData):
    safe_id = payload.id.replace("/", "").replace("\\", "")
    filepath = BISONS_DATA_DIR / f"{safe_id}.json"

    data = {
        "id": safe_id,
        "name": payload.name,
        "color": payload.color,
        "speed_base": payload.speed_base
    }
    write_data(filepath, data)
    return {"status": "success", "message": "Bison saved"}

@app.post("/api/bisondash/bisons/upload")
async def upload_bison_sprite(id: str = Form(...), file: UploadFile = File(...)):
    safe_id = id.replace("/", "").replace("\\", "")
    if not file.filename.endswith('.png'):
        return JSONResponse({"status": "error", "message": "Must be a PNG"}, status_code=400)

    filepath = BISONS_IMG_DIR / f"{safe_id}.png"
    contents = await file.read()
    with open(filepath, "wb") as f:
        f.write(contents)
    return {"status": "success", "message": "Uploaded successfully"}

@app.delete("/api/bisondash/bisons/{bison_id}")
def delete_bison(bison_id: str):
    safe_id = bison_id.replace("/", "").replace("\\", "")
    json_path = BISONS_DATA_DIR / f"{safe_id}.json"
    img_path = BISONS_IMG_DIR / f"{safe_id}.png"

    if json_path.exists():
        json_path.unlink()
    if img_path.exists():
        img_path.unlink()

    return {"status": "success", "message": "Deleted"}

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
                    current_telemetry_cache = simulate_race(_get_mapped_lineup())
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
