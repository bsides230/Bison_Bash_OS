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
from game_hub.profanity_filter import validate_player_name
import master_admin.data_manager as dm

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
if Path("slides").exists():
    app.mount("/slides", StaticFiles(directory="slides"), name="slides")

# Local settings and lineup files
SETTINGS_FILE = DATA_DIR / "bison_settings.json"
LINEUP_FILE = DATA_DIR / "lineup.json"
RACERS_FILE = DATA_DIR / "bison_racers.json"

# Duration preset for the race (e.g. 40s)
RACE_DURATION = int(os.environ.get("RACE_DURATION", 40))

def read_data(filepath: Path) -> dict:
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def write_data(filepath: Path, data: dict):
    lock_path = str(filepath) + ".lock"
    with FileLock(lock_path, is_singleton=True):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

# Initialize files
if not SETTINGS_FILE.exists():
    write_data(SETTINGS_FILE, {
        "state": "Betting_Open",
        "timers": {
            "Soft_Closure": 10,
            "Closed_Intros": 60,
            "Race_Sprint": RACE_DURATION,
            "Results_Payout": 30
        },
        "state_start_time": time.time()
    })

if not LINEUP_FILE.exists():
    # Store just the mapping of slot (1-6) to bison_id, or None
    initial_lineup = [{"slot": i, "bison_id": None} for i in range(1, 7)]
    write_data(LINEUP_FILE, {"lineup": initial_lineup})

# In-memory cached race state & active wagering ledger
current_telemetry_cache = {}
active_wagers = {} # player_id -> { slot, amount, timestamp, player_name, bison_name }
last_race_payouts = []

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

class PlayerRegisterPayload(BaseModel):
    email: str
    name: str
    newsletter_opt_in: bool = False

class WagerPayload(BaseModel):
    player_id: str
    slot: int
    amount: int

class AdjustBalancePayload(BaseModel):
    player_id: str
    delta: int

class ResetBalancesPayload(BaseModel):
    default_balance: int = 100

class PlinkoPayoutPayload(BaseModel):
    player_id: str | None = None
    id: str | None = None
    pin: str | None = None
    payout: int
    slot_index: int | None = None
    port: int | str | None = None

class GauntletPayoutPayload(BaseModel):
    player_id: str | None = None
    id: str | None = None
    pin: str | None = None
    payout: int
    level_reached: int = 1
    outcome: str = "WIN"

class GauntletPlayPayload(BaseModel):
    player_id: str | None = None
    id: str | None = None
    pin: str | None = None

class N64PayoutPayload(BaseModel):
    winner_id: str | None = None
    player_id: str | None = None
    id: str | None = None
    pin: str | None = None
    loser_id: str | None = None
    tokens: int | None = None

class BugHuntPayoutPayload(BaseModel):
    player_id: str | None = None
    id: str | None = None
    pin: str | None = None
    bugs: int = 0
    pity_credit: bool = False

class BugHuntPlayPayload(BaseModel):
    player_id: str | None = None
    id: str | None = None
    pin: str | None = None

class AttendeeLookupPayload(BaseModel):
    pin: str

class TokenTransactPayload(BaseModel):
    pin: str | None = None
    player_id: str | None = None
    amount: int
    action: str | None = "adjust"
    description: str | None = None

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
    """Triggered by the master admin 'Panic Reset' button. Refunds all active bets."""
    global current_telemetry_cache, active_wagers, last_race_payouts
    settings = read_data(SETTINGS_FILE)
    settings["state"] = "Betting_Open"
    settings["state_start_time"] = time.time()
    write_data(SETTINGS_FILE, settings)

    # Refund active wagers if race was interrupted
    refund_count = 0
    for pid, wager in list(active_wagers.items()):
        amt = wager.get("amount", 0)
        if amt > 0:
            dm.adjust_player_balance(pid, amt)
            refund_count += 1
    active_wagers.clear()
    current_telemetry_cache = {}

    return {"status": "success", "message": f"Bison Dash reset to Betting_Open. {refund_count} wagers refunded."}

DEFAULT_STATIC_RACERS = [
    {
        "id": "bison_1",
        "slot": 1,
        "name": "Thunder Stampede",
        "color": "#ff4757",
        "jockey_name": "Jockey Jax",
        "jockey_color": "#ff4757",
        "stats": {
            "jockey_reaction": 12,
            "bison_speed": 65,
            "bison_cornering": 6,
            "bison_stamina": 55,
            "jockey_aggression": 5,
            "jockey_luck": 5
        }
    },
    {
        "id": "bison_2",
        "slot": 2,
        "name": "Cyber Steer",
        "color": "#2ed573",
        "jockey_name": "Dash Volt",
        "jockey_color": "#2ed573",
        "stats": {
            "jockey_reaction": 10,
            "bison_speed": 70,
            "bison_cornering": 5,
            "bison_stamina": 50,
            "jockey_aggression": 5,
            "jockey_luck": 5
        }
    },
    {
        "id": "bison_3",
        "slot": 3,
        "name": "Prairie Rocket",
        "color": "#3742fa",
        "jockey_name": "Nova Drift",
        "jockey_color": "#3742fa",
        "stats": {
            "jockey_reaction": 14,
            "bison_speed": 60,
            "bison_cornering": 7,
            "bison_stamina": 45,
            "jockey_aggression": 5,
            "jockey_luck": 5
        }
    },
    {
        "id": "bison_4",
        "slot": 4,
        "name": "Iron Horn",
        "color": "#ffa502",
        "jockey_name": "Steel Spur",
        "jockey_color": "#ffa502",
        "stats": {
            "jockey_reaction": 8,
            "bison_speed": 75,
            "bison_cornering": 4,
            "bison_stamina": 60,
            "jockey_aggression": 5,
            "jockey_luck": 5
        }
    },
    {
        "id": "bison_5",
        "slot": 5,
        "name": "Neon Goliath",
        "color": "#9b5de5",
        "jockey_name": "Pulse Rider",
        "jockey_color": "#9b5de5",
        "stats": {
            "jockey_reaction": 11,
            "bison_speed": 62,
            "bison_cornering": 5,
            "bison_stamina": 65,
            "jockey_aggression": 5,
            "jockey_luck": 5
        }
    },
    {
        "id": "bison_6",
        "slot": 6,
        "name": "Solar Flare",
        "color": "#00d2d3",
        "jockey_name": "Blaze Vector",
        "jockey_color": "#00d2d3",
        "stats": {
            "jockey_reaction": 13,
            "bison_speed": 68,
            "bison_cornering": 6,
            "bison_stamina": 50,
            "jockey_aggression": 5,
            "jockey_luck": 5
        }
    }
]

def _get_mapped_lineup():
    """Returns the 6 static racers for the night. Never randomly mutates on poll ticks."""
    if RACERS_FILE.exists():
        try:
            racers = read_data(RACERS_FILE)
            if isinstance(racers, list) and len(racers) == 6:
                return racers
        except Exception:
            pass

    # Ensure default static racers exist
    write_data(RACERS_FILE, DEFAULT_STATIC_RACERS)
    for r in DEFAULT_STATIC_RACERS:
        write_data(BISONS_DATA_DIR / f"{r['id']}.json", r)
    write_data(LINEUP_FILE, {"lineup": [{"slot": r["slot"], "bison_id": r["id"]} for r in DEFAULT_STATIC_RACERS]})
    return DEFAULT_STATIC_RACERS

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
        "telemetry": current_telemetry_cache,
        "race_duration": settings.get("timers", {}).get("Race_Sprint", RACE_DURATION),
        "active_wagers_count": len(active_wagers),
        "total_pot": sum(w.get("amount", 0) for w in active_wagers.values()),
        "winner": current_telemetry_cache.get("_winner"),
        "last_payouts": last_race_payouts
    }

@app.get("/api/bisondash/state")
def get_bisondash_state():
    settings = read_data(SETTINGS_FILE)
    return {"status": "success", "state_data": settings}

@app.post("/api/bisondash/state/update")
def update_bisondash_state(payload: BisonDashStatePayload):
    global current_telemetry_cache, active_wagers
    settings = read_data(SETTINGS_FILE)
    settings["state"] = payload.state
    settings["state_start_time"] = time.time()
    write_data(SETTINGS_FILE, settings)

    race_duration = settings.get("timers", {}).get("Race_Sprint", RACE_DURATION)

    if payload.state == "Closed_Intros":
        current_telemetry_cache = simulate_race(_get_mapped_lineup(), race_duration)
    elif payload.state == "Race_Sprint":
        if not current_telemetry_cache:
            current_telemetry_cache = simulate_race(_get_mapped_lineup(), race_duration)
    elif payload.state == "Betting_Open":
        current_telemetry_cache = {}
        active_wagers.clear()

    return {"status": "success", "message": f"State set to {payload.state}"}

@app.post("/api/bisondash/test_race")
def trigger_test_race():
    global current_telemetry_cache
    settings = read_data(SETTINGS_FILE)
    settings["state"] = "Race_Sprint"
    settings["state_start_time"] = time.time()
    write_data(SETTINGS_FILE, settings)

    race_duration = settings.get("timers", {}).get("Race_Sprint", RACE_DURATION)
    current_telemetry_cache = simulate_race(_get_mapped_lineup(), race_duration)

    return {
        "status": "success",
        "message": "Test race launched!",
        "state": "Race_Sprint",
        "race_duration": race_duration,
        "winner": current_telemetry_cache.get("_winner")
    }

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

@app.get("/api/bisondash/racers")
def get_bisondash_racers():
    return {"status": "success", "racers": _get_mapped_lineup()}

@app.post("/api/bisondash/racers/save")
async def save_bisondash_racers(payload: list[dict] | dict):
    racers = payload if isinstance(payload, list) else payload.get("racers", [])
    if len(racers) == 6:
        write_data(RACERS_FILE, racers)
        lineup = []
        for r in racers:
            b_id = r.get("id") or f"bison_{r['slot']}"
            r["id"] = b_id
            write_data(BISONS_DATA_DIR / f"{b_id}.json", r)
            lineup.append({"slot": r["slot"], "bison_id": b_id})
        write_data(LINEUP_FILE, {"lineup": lineup})
        return {"status": "success", "message": "Racers saved successfully"}
    return JSONResponse(status_code=400, content={"status": "error", "message": "Expected exactly 6 racers"})

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
    with open(TEMPLATE_DIR / "bison.html", "r", encoding="utf-8") as f:
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
    speed_base: int = 50
    stats: dict | None = None
    jockey_name: str | None = None
    jockey_color: str | None = None
    slot: int | None = None

@app.post("/api/bisondash/bisons/save")
def save_bison(payload: BisonData):
    safe_id = payload.id.replace("/", "").replace("\\", "")
    filepath = BISONS_DATA_DIR / f"{safe_id}.json"

    stats = payload.stats or {}
    speed_val = int(stats.get("bison_speed", payload.speed_base))

    data = {
        "id": safe_id,
        "name": payload.name,
        "color": payload.color,
        "speed_base": speed_val,
        "stats": {
            "jockey_reaction": int(stats.get("jockey_reaction", 10)),
            "bison_speed": speed_val,
            "bison_cornering": int(stats.get("bison_cornering", 5)),
            "bison_stamina": int(stats.get("bison_stamina", 50)),
            "jockey_aggression": int(stats.get("jockey_aggression", 5)),
            "jockey_luck": int(stats.get("jockey_luck", 5))
        },
        "jockey_name": payload.jockey_name or "Rider",
        "jockey_color": payload.jockey_color or "#00ffcc"
    }
    write_data(filepath, data)

    # If slot is specified (1-6), assign it directly to lineup
    if payload.slot and 1 <= payload.slot <= 6:
        lineup_data = read_data(LINEUP_FILE)
        lineup = lineup_data.get("lineup", [{"slot": i, "bison_id": None} for i in range(1, 7)])
        for item in lineup:
            if item["slot"] == payload.slot:
                item["bison_id"] = safe_id
                break
        lineup_data["lineup"] = lineup
        write_data(LINEUP_FILE, lineup_data)

    return {"status": "success", "message": "Bison saved", "bison": data}

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
            elif current_state == "Race_Sprint" and elapsed >= timers.get("Race_Sprint", RACE_DURATION):
                new_state = "Results_Payout"
            elif current_state == "Results_Payout" and elapsed >= timers.get("Results_Payout", 30):
                new_state = "Betting_Open"

            if new_state:
                settings["state"] = new_state
                settings["state_start_time"] = time.time()
                write_data(SETTINGS_FILE, settings)
                print(f"[Bison Dash] State transitioned to {new_state}")

                race_duration = timers.get("Race_Sprint", RACE_DURATION)

                # Triggers on specific state changes
                if new_state == "Closed_Intros":
                    current_telemetry_cache = simulate_race(_get_mapped_lineup(), race_duration)
                    print(f"[Bison Dash] Telemetry calculated for upcoming race.")

                if new_state == "Results_Payout":
                    # Process automated payouts to winning bets
                    winner_info = current_telemetry_cache.get("_winner", {})
                    winner_slot = winner_info.get("slot")
                    last_race_payouts.clear()

                    if winner_slot:
                        eco = dm.get_economy_config()
                        payout_mult = float(eco.get("payouts", {}).get("bison_dash_multiplier", 2.0))
                        for pid, wager in list(active_wagers.items()):
                            if wager.get("slot") == winner_slot:
                                win_amt = int(wager.get("amount", 0) * payout_mult)
                                net_win = max(0, win_amt - wager.get("amount", 0))
                                dm.adjust_player_balance(pid, win_amt, winnings=net_win)

                                last_race_payouts.append({
                                    "player_id": pid,
                                    "name": wager.get("player_name"),
                                    "amount": wager.get("amount"),
                                    "payout": win_amt,
                                    "slot": winner_slot
                                })
                        print(f"[Bison Dash] Payouts processed: {len(last_race_payouts)} winners paid for Slot {winner_slot}.")
                        try:
                            import master_admin.bison_ledger as bison_ledger
                            bison_ledger.settle_race(int(winner_slot), multiplier=payout_mult)
                            print(f"[Bison Dash] bison_active_wagers.json settled automatically for Slot {winner_slot}.")
                        except Exception as e:
                            print(f"[Bison Dash] Notice auto-settling ledger: {e}")

                if new_state == "Betting_Open":
                    # Clear telemetry and wagers when back to idle
                    current_telemetry_cache = {}
                    active_wagers.clear()
                    try:
                        dm.stop_slideshow_countdown()
                        print("[Bison Dash] 30s results elapsed -> Automatically resumed regular stadium slideshow.")
                    except Exception as e:
                        pass

        except Exception as e:
            print(f"[Bison Dash] Error in elastic clock loop: {e}")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(elastic_clock_loop())

# --- Frontend Page Routes ---

@app.get("/", response_class=HTMLResponse)
def read_root():
    with open(TEMPLATE_DIR / "projector.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/projector", response_class=HTMLResponse)
def serve_projector():
    with open(TEMPLATE_DIR / "projector.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/admin", response_class=HTMLResponse)
def serve_admin():
    with open(TEMPLATE_DIR / "admin.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/signup", response_class=HTMLResponse)
@app.get("/register", response_class=HTMLResponse)
def serve_signup():
    with open(TEMPLATE_DIR / "signup.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/kiosk", response_class=HTMLResponse)
@app.get("/tablet", response_class=HTMLResponse)
@app.get("/tablet1", response_class=HTMLResponse)
@app.get("/tablet2", response_class=HTMLResponse)
@app.get("/bet", response_class=HTMLResponse)
@app.get("/bet1", response_class=HTMLResponse)
@app.get("/bet2", response_class=HTMLResponse)
def serve_kiosk():
    with open(TEMPLATE_DIR / "kiosk.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/manifest", response_class=HTMLResponse)
def serve_manifest():
    with open(TEMPLATE_DIR / "manifest.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/slideshow", response_class=HTMLResponse)
def serve_slideshow():
    slideshow_file = Path("master_admin/templates/slideshow.html")
    if slideshow_file.exists():
        with open(slideshow_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Slideshow template not found</h1>"

@app.get("/api/slides/list")
def list_slides():
    slides_dir = Path("slides")
    if not slides_dir.exists():
        return {"status": "success", "slides": []}
    valid_exts = {".png", ".jpg", ".jpeg", ".webp"}
    images = [f"/slides/{f.name}" for f in slides_dir.iterdir() if f.is_file() and f.suffix.lower() in valid_exts]
    return {"status": "success", "slides": sorted(images)}

@app.get("/plinko", response_class=HTMLResponse)
def serve_plinko():
    with open(TEMPLATE_DIR / "plinko.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/plinko/config")
@app.get("/plinko/api/plinko/config")
def get_plinko_config():
    eco = dm.get_economy_config()
    return {
        "status": "success",
        "cost": eco.get("costs", {}).get("plinko", 0),
        "slots": eco.get("payouts", {}).get("plinko_slots", [1, 1, 2, 2, 5, 2, 2, 1, 1])
    }

@app.post("/api/plinko/play")
@app.post("/plinko/api/plinko/play")
def plinko_play(payload: PlinkoPayoutPayload):
    ident = payload.player_id or payload.id or payload.pin
    if not ident:
        return JSONResponse({"status": "error", "message": "Player identifier required."}, status_code=400)
    res = dm.deduct_game_cost(ident, "plinko")
    if not res["allowed"]:
        return JSONResponse({"status": "error", "message": res.get("message", "Insufficient tokens."), "cost": res["cost"], "balance": res["balance"]}, status_code=400)
    return {"status": "success", "cost": res["cost"], "balance": res["balance"]}

@app.post("/api/plinko/payout")
@app.post("/plinko/api/plinko/payout")
@app.post("/api/games/plinko/payout")
def plinko_payout(payload: PlinkoPayoutPayload):
    if payload.payout < 0 or payload.payout > 500:
        return JSONResponse({"status": "error", "message": "Invalid payout amount."}, status_code=400)

    ident = payload.player_id or payload.id or payload.pin
    if not ident:
        return JSONResponse({"status": "error", "message": "Player identifier required."}, status_code=400)

    player = dm.get_player(ident)
    if not player:
        player = dm.get_player_by_email(ident)
    if not player:
        player = dm.get_player_by_pin(ident)
    if not player:
        return JSONResponse({"status": "error", "message": "Player not found."}, status_code=404)

    pid = player["id"]
    updated = dm.adjust_player_balance(pid, payload.payout, winnings=payload.payout)

    return {
        "status": "success",
        "new_balance": updated.get("balance", 0) if updated else 0,
        "payout": payload.payout,
        "player_name": player.get("name")
    }

@app.get("/gauntlet", response_class=HTMLResponse)
def serve_gauntlet():
    with open(TEMPLATE_DIR / "gauntlet.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/poster", response_class=HTMLResponse)
def serve_poster():
    poster_path = TEMPLATE_DIR / "gauntlet_poster.html"
    if not poster_path.exists():
        raise HTTPException(status_code=404, detail="gauntlet_poster.html not found")
    with open(poster_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/gauntlet/config")
def get_gauntlet_config():
    eco = dm.get_economy_config()
    return {
        "status": "success",
        "cost": eco.get("costs", {}).get("gauntlet", 4),
        "payouts": eco.get("payouts", {}).get("gauntlet", {
            "stage1": 2,
            "stage2": 3,
            "stage3": 5,
            "stage4": 8,
            "vault_jackpot": 25,
            "vault_runner_up": 10
        })
    }

@app.post("/api/gauntlet/play")
def gauntlet_play(payload: GauntletPlayPayload):
    identifier = payload.player_id or payload.id or payload.pin
    if not identifier:
        return JSONResponse({"status": "error", "message": "Player ID or PIN is required."}, status_code=400)
    res = dm.deduct_game_cost(identifier, "gauntlet")
    if not res["allowed"]:
        return JSONResponse({"status": "error", "message": res.get("message", "Insufficient tokens."), "cost": res.get("cost", 4), "balance": res.get("balance", 0)}, status_code=400)
    return {"status": "success", "cost": res.get("cost", 4), "balance": res.get("balance", 0)}

@app.post("/api/gauntlet/payout")
def gauntlet_payout(payload: GauntletPayoutPayload):
    if payload.payout < 0 or payload.payout > 500:
        return JSONResponse({"status": "error", "message": "Invalid payout amount."}, status_code=400)

    identifier = payload.player_id or payload.id or payload.pin
    if not identifier:
        return JSONResponse({"status": "error", "message": "Player ID or PIN is required."}, status_code=400)

    player = dm.get_player(identifier)
    if not player:
        player = dm.get_player_by_email(identifier)
    if not player:
        player = dm.get_player_by_pin(identifier)
    if not player:
        return JSONResponse({"status": "error", "message": "Player not found."}, status_code=404)

    pid = player["id"]
    updated = dm.adjust_player_balance(pid, payload.payout, winnings=payload.payout)

    return {
        "status": "success",
        "new_balance": updated.get("balance", 0) if updated else 0,
        "payout": payload.payout,
        "player_name": player.get("name")
    }

@app.get("/n64", response_class=HTMLResponse)
def serve_n64():
    with open(TEMPLATE_DIR / "n64.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/n64/config")
@app.get("/n64/api/n64/config")
def get_n64_config():
    eco = dm.get_economy_config()
    return {
        "status": "success",
        "cost": eco.get("costs", {}).get("n64", 0),
        "winner_payout": eco.get("payouts", {}).get("n64_winner", 8)
    }

@app.post("/api/n64/play")
@app.post("/n64/api/n64/play")
def n64_play(payload: N64PayoutPayload):
    ident = payload.winner_id or payload.player_id or payload.id or payload.pin
    if not ident:
        return JSONResponse({"status": "error", "message": "Player identifier required."}, status_code=400)
    res = dm.deduct_game_cost(ident, "n64")
    if not res["allowed"]:
        return JSONResponse({"status": "error", "message": res.get("message", "Insufficient tokens."), "cost": res["cost"], "balance": res["balance"]}, status_code=400)
    return {"status": "success", "cost": res["cost"], "balance": res["balance"]}

@app.post("/api/n64/payout")
@app.post("/n64/api/n64/payout")
@app.post("/api/games/n64/payout")
def n64_payout(payload: N64PayoutPayload):
    eco = dm.get_economy_config()
    tokens_to_award = payload.tokens if (payload.tokens is not None and payload.tokens > 0) else eco.get("payouts", {}).get("n64_winner", 8)

    ident = payload.winner_id or payload.player_id or payload.id or payload.pin
    if not ident:
        return JSONResponse({"status": "error", "message": "Winner identifier not specified."}, status_code=400)

    winner = dm.get_player(ident)
    if not winner:
        winner = dm.get_player_by_email(ident)
    if not winner:
        winner = dm.get_player_by_pin(ident)
    if not winner:
        return JSONResponse({"status": "error", "message": "Winner player not found."}, status_code=404)

    winner_id = winner["id"]
    updated = dm.adjust_player_balance(winner_id, tokens_to_award, winnings=tokens_to_award)

    return {
        "status": "success",
        "new_balance": updated.get("balance", 0) if updated else 0,
        "winner_name": winner.get("name"),
        "tokens": tokens_to_award
    }

@app.get("/bughunt", response_class=HTMLResponse)
def serve_bughunt():
    with open(TEMPLATE_DIR / "bughunt.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/bughunt/config")
def get_bughunt_config():
    eco = dm.get_economy_config()
    return {
        "status": "success",
        "cost": eco.get("costs", {}).get("bughunt", 1),
        "bugs_per_token": eco.get("payouts", {}).get("bughunt_bugs_per_token", 5),
        "pity_tokens": eco.get("payouts", {}).get("bughunt_pity_tokens", 1),
        "timer_seconds": eco.get("timers", {}).get("bughunt_duration", 60)
    }

@app.post("/api/bughunt/play")
def bughunt_play(payload: BugHuntPlayPayload):
    identifier = payload.player_id or payload.id or payload.pin
    if not identifier:
        return JSONResponse({"status": "error", "message": "Player ID or PIN required."}, status_code=400)
    res = dm.deduct_game_cost(identifier, "bughunt")
    if not res["allowed"]:
        return JSONResponse({"status": "error", "message": res.get("message", "Insufficient tokens."), "cost": res.get("cost", 0), "balance": res.get("balance", 0)}, status_code=400)
    return {"status": "success", "cost": res.get("cost", 0), "balance": res.get("balance", 0)}

@app.post("/api/bughunt/payout")
@app.post("/api/games/bughunt/payout")
def bughunt_payout(payload: BugHuntPayoutPayload):
    if payload.bugs < 0 or payload.bugs > 500:
        return JSONResponse({"status": "error", "message": "Invalid bug count."}, status_code=400)

    identifier = payload.player_id or payload.id or payload.pin
    if not identifier:
        return JSONResponse({"status": "error", "message": "Parent account not found."}, status_code=404)

    parent = dm.get_player(identifier)
    if not parent:
        parent = dm.get_player_by_email(identifier)
    if not parent:
        parent = dm.get_player_by_pin(identifier)
    if not parent:
        return JSONResponse({"status": "error", "message": "Parent account not found."}, status_code=404)

    eco = dm.get_economy_config()
    bugs_per_token = max(1, int(eco.get("payouts", {}).get("bughunt_bugs_per_token", 5)))
    pity_tokens = int(eco.get("payouts", {}).get("bughunt_pity_tokens", 1))

    tokens = payload.bugs // bugs_per_token
    if payload.pity_credit and tokens == 0 and payload.bugs > 0:
        tokens = pity_tokens

    parent_id = parent["id"]
    updated = dm.adjust_player_balance(parent_id, tokens, winnings=tokens)

    return {
        "status": "success",
        "tokens_awarded": tokens,
        "tokens": tokens,
        "new_balance": updated.get("balance", 0) if updated else parent.get("balance", 0),
        "parent_name": parent.get("name"),
        "bugs": payload.bugs
    }

# --- Player & Wagering API Endpoints ---

@app.post("/api/player/register")
def register_player(payload: PlayerRegisterPayload):
    import re
    email = payload.email.strip().lower()
    name = payload.name.strip()

    if not email or "@" not in email:
        return JSONResponse({"status": "error", "message": "Please enter a valid email address."}, status_code=400)

    # Validate profanity and name format
    valid, reason = validate_player_name(name)
    if not valid:
        return JSONResponse({"status": "error", "message": reason}, status_code=400)

    player, is_new = dm.register_or_get_player(email, name, starting_balance=None, newsletter_opt_in=payload.newsletter_opt_in)
    email_dispatched = False
    try:
        import master_admin.email_manager as em
        ok, msg = em.send_player_pass_email(player)
        email_dispatched = ok
        if not ok:
            print(f"[BisonDash Register] Email not sent to {email}: {msg}")
        else:
            print(f"[BisonDash Register] Email pass successfully sent to {email}")
    except Exception as e:
        print(f"[BisonDash Register] Exception sending email pass: {e}")

    return {"status": "success", "player": player, "is_new": is_new, "email_sent": email_dispatched}

@app.get("/api/bisondash/config")
def get_bisondash_config():
    eco = dm.get_economy_config()
    return {
        "status": "success",
        "min_bet": max(1, int(eco.get("costs", {}).get("bison_dash_min_bet", 1))),
        "multiplier": float(eco.get("payouts", {}).get("bison_dash_multiplier", 2.0))
    }

@app.get("/api/player/{identifier}")
def get_player_profile(identifier: str):
    # Support lookup by either player_id or email
    player = None
    if "@" in identifier:
        player = dm.get_player_by_email(identifier)
    else:
        player = dm.get_player(identifier)

    if not player:
        return JSONResponse({"status": "error", "message": "Player not found."}, status_code=404)

    # Check for active wager in current race
    active_w = active_wagers.get(player["id"])
    player["current_wager"] = active_w

    return {"status": "success", "player": player}

@app.post("/api/attendee/lookup")
def attendee_lookup_api(payload: AttendeeLookupPayload):
    attendee = dm.lookup_attendee_by_pin(payload.pin)
    if not attendee:
        return JSONResponse({"success": False, "error": "Invalid PIN"}, status_code=404)
    return {
        "success": True,
        "display_name": attendee["display_name"],
        "email": attendee["email"],
        "balance": attendee["balance"],
        "id": attendee["id"],
        "pin": attendee["pin"]
    }

@app.post("/api/tokens/transact")
def tokens_transact_api(payload: TokenTransactPayload):
    pin = payload.pin
    player = None
    if pin:
        player = dm.get_player_by_pin(pin)
    elif payload.player_id:
        player = dm.get_player(payload.player_id)
        if not player:
            player = dm.get_player_by_email(payload.player_id)
        if player and "pin" in player:
            pin = player["pin"]

    if not player:
        return JSONResponse({"success": False, "error": "Invalid PIN or player not found."}, status_code=404)

    if pin:
        allowed, err_msg = dm.check_and_update_pin_cooldown(pin, 10.0)
        if not allowed:
            return JSONResponse({"success": False, "error": err_msg}, status_code=429)

    amount = payload.amount
    if payload.action == "deduct" and amount > 0:
        amount = -amount

    updated = dm.adjust_player_balance(player["id"], amount)
    return {
        "success": True,
        "display_name": player.get("name") or player.get("display_name"),
        "balance": updated["balance"] if updated else player.get("balance", 0),
        "delta": amount
    }

@app.post("/api/bisondash/wager")
def place_wager(payload: WagerPayload):
    pin = dm.get_pin_for_player(payload.player_id)
    if pin:
        allowed, err_msg = dm.check_and_update_pin_cooldown(pin, 10.0)
        if not allowed:
            return JSONResponse({"success": False, "error": err_msg}, status_code=429)

    settings = read_data(SETTINGS_FILE)
    if settings.get("state") != "Betting_Open":
        return JSONResponse({"status": "error", "message": "Betting is currently closed for this race."}, status_code=400)

    # Reject duplicate bets in same race (Doc 01A)
    if payload.player_id in active_wagers:
        return JSONResponse({
            "status": "error",
            "error_code": "DUPLICATE_WAGER",
            "message": "System Error: Player has already placed a bet."
        }, status_code=400)

    if payload.slot < 1 or payload.slot > 6:
        return JSONResponse({"status": "error", "message": "Invalid slot. Must be 1 to 6."}, status_code=400)

    eco = dm.get_economy_config()
    min_bet = max(1, int(eco.get("costs", {}).get("bison_dash_min_bet", 1)))

    if payload.amount < min_bet:
        return JSONResponse({"status": "error", "message": f"Wager amount must be at least {min_bet} credits."}, status_code=400)

    player = dm.get_player(payload.player_id)
    if not player:
        return JSONResponse({"status": "error", "message": "Player account not found."}, status_code=404)

    if player.get("balance", 0) < payload.amount:
        return JSONResponse({"status": "error", "message": "Insufficient credits for this wager."}, status_code=400)

    # Deduct wager amount atomically
    updated_player = dm.adjust_player_balance(payload.player_id, -payload.amount)

    # Find bison name for slot
    lineup = _get_mapped_lineup()
    bison_obj = next((b for b in lineup if b.get("slot") == payload.slot), None)
    bison_name = bison_obj.get("name") if bison_obj else f"Slot {payload.slot}"

    # Record wager
    active_wagers[payload.player_id] = {
        "player_id": payload.player_id,
        "player_name": player.get("name", payload.player_id),
        "slot": payload.slot,
        "bison_name": bison_name,
        "amount": payload.amount,
        "timestamp": time.time()
    }

    # Increment player total_wagers count
    pdata = dm.read_data(dm.PLAYERS_FILE)
    if payload.player_id in pdata.get("players", {}):
        pdata["players"][payload.player_id]["total_wagers"] = pdata["players"][payload.player_id].get("total_wagers", 0) + 1
        dm.write_data(dm.PLAYERS_FILE, pdata)

    return {
        "status": "success",
        "new_balance": updated_player.get("balance", 0),
        "wager": active_wagers[payload.player_id]
    }

@app.get("/api/bisondash/wagers")
def get_current_wagers():
    w_list = list(active_wagers.values())
    total_pool = sum(w.get("amount", 0) for w in w_list)
    return {
        "status": "success",
        "count": len(w_list),
        "total_pool": total_pool,
        "wagers": w_list
    }

@app.get("/api/players/manifest")
def get_manifest():
    return {"status": "success", "players": dm.get_all_players()}

@app.post("/api/players/adjust-balance")
def admin_adjust_balance(payload: AdjustBalancePayload):
    updated = dm.adjust_player_balance(payload.player_id, payload.delta)
    if not updated:
        return JSONResponse({"status": "error", "message": "Player not found."}, status_code=404)
    return {"status": "success", "player": updated}

@app.post("/api/players/reset-all")
def admin_reset_all_balances(payload: ResetBalancesPayload):
    count = dm.reset_all_balances(payload.default_balance)
    return {"status": "success", "count": count, "new_balance": payload.default_balance}
