from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import os
import master_admin.data_manager as dm

app = FastAPI(title="N64 Tournament Station - Dedicated Game Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path("master_admin/static")
TEMPLATE_PATH = Path("game_hub/games/bison_dash/templates/n64.html")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

class N64PayoutPayload(BaseModel):
    winner_id: str | None = None
    player_id: str | None = None
    id: str | None = None
    pin: str | None = None
    loser_id: str | None = None
    tokens: int | None = None

class N64EntryPayload(BaseModel):
    p1_id: str
    p2_id: str

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
def serve_n64():
    if not TEMPLATE_PATH.exists():
        raise HTTPException(status_code=404, detail="n64.html template not found")
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/n64/config")
def get_n64_config():
    eco = dm.get_economy_config()
    return {
        "status": "success",
        "cost": eco.get("costs", {}).get("n64", 0),
        "winner_payout": eco.get("payouts", {}).get("n64_winner", 8)
    }

@app.post("/api/n64/entry")
def n64_entry(payload: N64EntryPayload):
    eco = dm.get_economy_config()
    cost = int(eco.get("costs", {}).get("n64", 0))

    p1 = dm.get_player(payload.p1_id)
    p2 = dm.get_player(payload.p2_id)
    if not p1 or not p2:
        return JSONResponse({"status": "error", "message": "Competitors not found."}, status_code=404)

    pin1 = dm.get_pin_for_player(p1["id"])
    pin2 = dm.get_pin_for_player(p2["id"])
    if pin1:
        allowed, err_msg = dm.check_and_update_pin_cooldown(pin1, 10.0)
        if not allowed:
            return JSONResponse({"success": False, "error": err_msg}, status_code=429)
    if pin2:
        allowed, err_msg = dm.check_and_update_pin_cooldown(pin2, 10.0)
        if not allowed:
            return JSONResponse({"success": False, "error": err_msg}, status_code=429)

    if cost <= 0:
        return {"status": "success", "cost": 0, "message": "Free entry"}
    if not p1 or not p2:
        return JSONResponse({"status": "error", "message": "Competitors not found."}, status_code=404)

    if p1.get("balance", 0) < cost:
        return JSONResponse({"status": "error", "message": f"{p1.get('name', 'Player 1')} has insufficient tokens! Need {cost} tokens (Balance: {p1.get('balance', 0)})."}, status_code=400)
    if p2.get("balance", 0) < cost:
        return JSONResponse({"status": "error", "message": f"{p2.get('name', 'Player 2')} has insufficient tokens! Need {cost} tokens (Balance: {p2.get('balance', 0)})."}, status_code=400)

    u1 = dm.adjust_player_balance(p1["id"], -cost)
    u2 = dm.adjust_player_balance(p2["id"], -cost)
    return {
        "status": "success",
        "cost": cost,
        "p1_balance": u1.get("balance", 0) if u1 else 0,
        "p2_balance": u2.get("balance", 0) if u2 else 0
    }

@app.get("/api/player/{identifier}")
def get_player_api(identifier: str):
    player = dm.get_player(identifier)
    if not player:
        player = dm.get_player_by_email(identifier)
    if not player:
        return JSONResponse({"status": "error", "message": "Player not found."}, status_code=404)
    return {"status": "success", "player": player}

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

    print(f"[N64] Awarded {tokens_to_award} tokens to {winner.get('name')} ({winner_id}).")

    return {
        "status": "success",
        "new_balance": updated.get("balance", 0) if updated else 0,
        "winner_name": winner.get("name"),
        "tokens": tokens_to_award
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
