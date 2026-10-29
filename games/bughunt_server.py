from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import os
import master_admin.data_manager as dm

app = FastAPI(title="Bug Bounty: Alpha Critical - Dedicated Game Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static paths
STATIC_DIR = Path("master_admin/static")
TEMPLATE_PATH = Path("game_hub/games/bison_dash/templates/bughunt.html")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

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
@app.get("/bughunt", response_class=HTMLResponse)
@app.get("/bugbounty", response_class=HTMLResponse)
@app.get("/bugbounty/", response_class=HTMLResponse)
def serve_bughunt():
    if not TEMPLATE_PATH.exists():
        raise HTTPException(status_code=404, detail="bughunt.html template not found")
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/bughunt/config")
@app.get("/bugbounty/api/bughunt/config")
def get_bughunt_config():
    eco = dm.get_economy_config()
    return {
        "status": "success",
        "cost": eco.get("costs", {}).get("bughunt", 0),
        "bugs_per_token": eco.get("payouts", {}).get("bughunt_bugs_per_token", 3),
        "pity_tokens": eco.get("payouts", {}).get("bughunt_pity_tokens", 0),
        "timer_seconds": eco.get("timers", {}).get("bughunt_duration", eco.get("bughunt_timer_seconds", 60))
    }

@app.post("/api/bughunt/play")
@app.post("/bugbounty/api/bughunt/play")
def bughunt_play(payload: BugHuntPlayPayload):
    identifier = payload.player_id or payload.id or payload.pin
    if not identifier:
        return JSONResponse({"status": "error", "message": "Player ID or PIN required."}, status_code=400)

    pin = dm.get_pin_for_player(identifier) or (identifier if str(identifier).isdigit() and len(str(identifier)) == 4 else None)
    if pin:
        allowed, err_msg = dm.check_and_update_pin_cooldown(pin, 10.0)
        if not allowed:
            return JSONResponse({"status": "error", "message": err_msg or "Please wait before using your PIN again."}, status_code=429)

    res = dm.deduct_game_cost(identifier, "bughunt")
    if not res["allowed"]:
        return JSONResponse({"status": "error", "message": res.get("message", "Insufficient tokens."), "cost": res.get("cost", 0), "balance": res.get("balance", 0)}, status_code=400)
    print(f"[Bug Hunt] Deducted entry cost ({res.get('cost', 0)} tokens) for player {identifier}. Remaining balance: {res.get('balance', 0)}")
    return {"status": "success", "cost": res.get("cost", 0), "balance": res.get("balance", 0)}

@app.get("/api/player/{identifier}")
@app.get("/bugbounty/api/player/{identifier}")
def get_player_api(identifier: str):
    player = dm.get_player(identifier)
    if not player:
        player = dm.get_player_by_email(identifier)
    if not player:
        player = dm.get_player_by_pin(identifier)
    if not player:
        return JSONResponse({"status": "error", "message": "Player not found."}, status_code=404)
    return {"status": "success", "player": player}

@app.post("/api/bughunt/payout")
@app.post("/api/games/bughunt/payout")
@app.post("/bugbounty/api/bughunt/payout")
def bughunt_payout(payload: BugHuntPayoutPayload):
    if payload.bugs < 0 or payload.bugs > 500:
        return JSONResponse({"status": "error", "message": "Invalid bug count."}, status_code=400)

    identifier = payload.player_id or payload.id or payload.pin
    if not identifier:
        return JSONResponse({"status": "error", "message": "Parent account / PIN not specified."}, status_code=400)

    parent = dm.get_player(identifier)
    if not parent:
        parent = dm.get_player_by_email(identifier)
    if not parent:
        parent = dm.get_player_by_pin(identifier)
    if not parent:
        return JSONResponse({"status": "error", "message": "Parent account not found."}, status_code=404)

    eco = dm.get_economy_config()
    bugs_per_token = max(1, int(eco.get("payouts", {}).get("bughunt_bugs_per_token", 3)))
    pity_tokens = int(eco.get("payouts", {}).get("bughunt_pity_tokens", 0))

    # Dynamic conversion
    tokens = payload.bugs // bugs_per_token

    # Toddler pity credit override
    if payload.pity_credit and tokens == 0 and payload.bugs > 0:
        tokens = pity_tokens

    parent_id = parent["id"]
    updated = dm.adjust_player_balance(parent_id, tokens, winnings=tokens)

    print(f"[Bug Hunt] Awarded {tokens} tokens to {parent.get('name')} ({parent_id}) for {payload.bugs} bugs.")

    return {
        "status": "success",
        "new_balance": updated.get("balance", 0) if updated else 0,
        "tokens": tokens,
        "tokens_awarded": tokens,
        "parent_name": parent.get("name")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
