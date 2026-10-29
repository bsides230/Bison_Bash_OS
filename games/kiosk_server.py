from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import os
import httpx
import master_admin.data_manager as dm
import master_admin.bison_ledger as bison_ledger

app = FastAPI(title="Betting Kiosk & Tablet Station - Dedicated Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path("master_admin/static")
BISON_STATIC_DIR = Path("game_hub/games/bison_dash/static")
TEMPLATE_PATH = Path("game_hub/games/bison_dash/templates/kiosk.html")
BISON_DASH_URL = os.environ.get("BISON_DASH_URL", "http://127.0.0.1:8001")

if (BISON_STATIC_DIR / "display").exists():
    app.mount("/static/display", StaticFiles(directory=str(BISON_STATIC_DIR / "display")), name="bison_display")
if (BISON_STATIC_DIR / "bisons").exists():
    app.mount("/static/bisons", StaticFiles(directory=str(BISON_STATIC_DIR / "bisons")), name="bison_sprites")
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

class AttendeeLookupPayload(BaseModel):
    pin: str

class TokenTransactPayload(BaseModel):
    pin: str | None = None
    player_id: str | None = None
    amount: int
    action: str | None = "adjust"
    description: str | None = None

@app.get("/", response_class=HTMLResponse)
@app.get("/kiosk", response_class=HTMLResponse)
@app.get("/tablet", response_class=HTMLResponse)
@app.get("/tablet1", response_class=HTMLResponse)
@app.get("/tablet2", response_class=HTMLResponse)
@app.get("/bet", response_class=HTMLResponse)
@app.get("/bet1", response_class=HTMLResponse)
@app.get("/bet2", response_class=HTMLResponse)
def serve_kiosk():
    if not TEMPLATE_PATH.exists():
        raise HTTPException(status_code=404, detail="kiosk.html template not found")
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/attendee/lookup")
def attendee_lookup_api(payload: AttendeeLookupPayload):
    attendee = dm.lookup_attendee_by_pin(payload.pin)
    if not attendee:
        return JSONResponse({"success": False, "error": "Invalid PIN"}, status_code=404)
    wager = bison_ledger.get_wager_for_player(payload.pin) or bison_ledger.get_wager_for_player(attendee.get("id"))
    return {
        "success": True,
        "display_name": attendee["display_name"],
        "email": attendee["email"],
        "balance": attendee["balance"],
        "id": attendee["id"],
        "pin": attendee["pin"],
        "current_wager": wager
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

@app.get("/api/bisondash/config")
async def get_bisondash_config():
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{BISON_DASH_URL}/api/bisondash/config")
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception:
        eco = dm.get_economy_config()
        return {
            "status": "success",
            "min_bet": max(1, int(eco.get("costs", {}).get("bison_dash_min_bet", 1))),
            "multiplier": float(eco.get("payouts", {}).get("bison_dash_multiplier", 2.0))
        }

@app.get("/api/bisondash/lineup")
@app.get("/api/bisondash/racers")
async def get_bisondash_lineup():
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{BISON_DASH_URL}/api/bisondash/lineup")
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception:
        racers_file = Path("game_hub/games/bison_dash/data/bison_racers.json")
        if racers_file.exists():
            import json
            with open(racers_file, "r", encoding="utf-8") as f:
                return {"status": "success", "lineup": json.load(f)}
        return {"status": "error", "message": "Lineup unavailable"}

@app.get("/api/player/{identifier}")
def get_player_api(identifier: str):
    player = dm.get_player(identifier)
    if not player:
        player = dm.get_player_by_email(identifier)
    if not player and identifier.isdigit() and len(identifier) == 4:
        player = dm.get_player_by_pin(identifier)
    if not player:
        return JSONResponse({"status": "error", "message": "Player not found."}, status_code=404)
    wager = bison_ledger.get_wager_for_player(player.get("id")) or (bison_ledger.get_wager_for_player(player.get("pin")) if player.get("pin") else None)
    player["current_wager"] = wager
    return {"status": "success", "player": player}

@app.get("/api/current_race")
async def proxy_current_race():
    # Return always-open status backed by static lineup (KISS)
    racers_file = Path("game_hub/games/bison_dash/data/bison_racers.json")
    lineup = []
    if racers_file.exists():
        import json
        with open(racers_file, "r", encoding="utf-8") as f:
            lineup = json.load(f)
    return JSONResponse({
        "status": "success",
        "state": "Betting_Open",
        "lineup": lineup,
        "active_wagers": len(bison_ledger.get_all_active_wagers())
    }, status_code=200)

@app.get("/api/bisondash/wagers")
def get_wagers_api():
    wagers = bison_ledger.get_all_active_wagers()
    return {
        "status": "success",
        "wagers": wagers,
        "count": len(wagers),
        "total_pot": sum(w.get("amount", 0) for w in wagers)
    }

@app.get("/api/bisondash/wager/{identifier}")
def get_player_wager_api(identifier: str):
    w = bison_ledger.get_wager_for_player(identifier)
    if w:
        return {"status": "success", "has_wager": True, "wager": w}
    return {"status": "success", "has_wager": False, "wager": None}

@app.post("/api/bisondash/wager")
async def place_bison_wager_api(request: Request):
    try:
        body = await request.json()
        pid = body.get("player_id") or body.get("pin")
        slot = body.get("slot")
        amount = body.get("amount")
        bison_name = body.get("bison_name", "")

        if not pid or not slot or not amount:
            return JSONResponse({"status": "error", "message": "Missing player_id, slot, or amount"}, status_code=400)

        # 5-second anti-spam lock
        pin = dm.get_pin_for_player(pid) if pid else None
        if pin:
            allowed, err_msg = dm.check_and_update_pin_cooldown(pin, 5.0)
            if not allowed:
                return JSONResponse({"success": False, "error": err_msg}, status_code=429)

        success, msg, data = bison_ledger.place_wager(pid, int(slot), int(amount), bison_name=bison_name)
        if not success:
            err_code = "DUPLICATE_WAGER" if "already placed" in msg.lower() else "ERROR"
            return JSONResponse({
                "status": "error",
                "error_code": err_code,
                "message": msg,
                "existing_wager": data
            }, status_code=400)

        return {
            "status": "success",
            "message": msg,
            "wager": data.get("wager"),
            "new_balance": data.get("new_balance")
        }
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"Wager error: {e}"}, status_code=500)

class SettlePayload(BaseModel):
    winner_slot: int
    multiplier: float | None = 2.0

@app.post("/api/bisondash/settle")
def settle_race_api(payload: SettlePayload):
    res = bison_ledger.settle_race(payload.winner_slot, multiplier=payload.multiplier or 2.0)
    return {"status": "success", "result": res}

if __name__ == "__main__":
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8008)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args, _ = parser.parse_known_args()
    uvicorn.run(app, host=args.host, port=args.port)
