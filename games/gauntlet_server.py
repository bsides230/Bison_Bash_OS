from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import os
import master_admin.data_manager as dm

app = FastAPI(title="The Gauntlet - Dedicated Game Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path("master_admin/static")
TEMPLATE_PATH = Path("game_hub/games/bison_dash/templates/gauntlet.html")

POSTER_PATH = Path("game_hub/games/bison_dash/templates/gauntlet_poster.html")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

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

class AttendeeLookupPayload(BaseModel):
    pin: str

class TokenTransactPayload(BaseModel):
    pin: str | None = None
    player_id: str | None = None
    amount: int
    action: str | None = "adjust"
    description: str | None = None

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

@app.get("/", response_class=HTMLResponse)
@app.get("/gauntlet", response_class=HTMLResponse)
@app.get("/gauntlet/", response_class=HTMLResponse)
def serve_gauntlet():
    if not TEMPLATE_PATH.exists():
        raise HTTPException(status_code=404, detail="gauntlet.html template not found")
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/poster", response_class=HTMLResponse)
@app.get("/gauntlet/poster", response_class=HTMLResponse)
def serve_poster():
    if not POSTER_PATH.exists():
        raise HTTPException(status_code=404, detail="gauntlet_poster.html template not found")
    with open(POSTER_PATH, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/gauntlet/config")
@app.get("/gauntlet/api/gauntlet/config")
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
@app.post("/gauntlet/api/gauntlet/play")
def gauntlet_play(payload: GauntletPlayPayload):
    identifier = payload.player_id or payload.id or payload.pin
    if not identifier:
        return JSONResponse({"status": "error", "message": "Player ID or PIN is required."}, status_code=400)
    res = dm.deduct_game_cost(identifier, "gauntlet")
    if not res["allowed"]:
        return JSONResponse({"status": "error", "message": res.get("message", "Insufficient tokens."), "cost": res.get("cost", 4), "balance": res.get("balance", 0)}, status_code=400)
    return {"status": "success", "cost": res.get("cost", 4), "balance": res.get("balance", 0)}

@app.get("/api/player/{identifier}")
@app.get("/gauntlet/api/player/{identifier}")
def get_player_api(identifier: str):
    player = dm.get_player(identifier)
    if not player:
        player = dm.get_player_by_email(identifier)
    if not player:
        return JSONResponse({"status": "error", "message": "Player not found."}, status_code=404)
    return {"status": "success", "player": player}

@app.post("/api/gauntlet/payout")
@app.post("/gauntlet/api/gauntlet/payout")
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

    print(f"[Gauntlet] Payout {payload.payout} tokens to {player.get('name')} ({pid}) - Level {payload.level_reached} ({payload.outcome}).")

    return {
        "status": "success",
        "new_balance": updated.get("balance", 0) if updated else 0,
        "payout": payload.payout,
        "player_name": player.get("name")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
