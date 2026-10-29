from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import os
import master_admin.data_manager as dm

app = FastAPI(title="Token Bank & Cashier Desk - Dedicated Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path("master_admin/static")
TEMPLATE_PATH = Path("templates/mint.html") if Path("templates/mint.html").exists() else Path("master_admin/templates/mint.html")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

class InjectTokensPayload(BaseModel):
    player_id: str
    amount: int

class AttendeeLookupPayload(BaseModel):
    pin: str

class MintTokensPayload(BaseModel):
    pin: str
    donation_amount: float
    tokens_to_add: int

class TokenTransactPayload(BaseModel):
    pin: str | None = None
    player_id: str | None = None
    amount: int
    action: str | None = "adjust"
    description: str | None = None

class PlayerRegisterPayload(BaseModel):
    email: str
    name: str
    newsletter_opt_in: bool = False

@app.get("/", response_class=HTMLResponse)
@app.get("/mint", response_class=HTMLResponse)
@app.get("/cashier", response_class=HTMLResponse)
def serve_mint():
    for p in [Path("templates/mint.html"), Path("master_admin/templates/mint.html")]:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
    raise HTTPException(status_code=404, detail="mint.html template not found")

@app.get("/api/mint/config")
@app.get("/mint/api/mint/config")
def get_mint_config():
    eco = dm.get_economy_config()
    return {
        "status": "success",
        "tokens_per_dollar": eco.get("tokens_per_dollar", 5)
    }

@app.post("/api/attendee/lookup")
@app.post("/mint/api/attendee/lookup")
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

@app.post("/api/mint/tokens")
@app.post("/mint/api/mint/tokens")
def mint_tokens_api(payload: MintTokensPayload):
    result = dm.mint_tokens(payload.pin, payload.donation_amount, payload.tokens_to_add)
    if not result:
        return JSONResponse({"success": False, "error": "Invalid PIN"}, status_code=404)
    return result

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

@app.get("/api/player/{identifier}")
def get_player_api(identifier: str):
    player = dm.get_player(identifier)
    if not player:
        player = dm.get_player_by_email(identifier)
    if not player:
        return JSONResponse({"status": "error", "message": "Player not found."}, status_code=404)
    return {"status": "success", "player": player}

@app.post("/api/admin/inject-tokens")
def inject_tokens(payload: InjectTokensPayload):
    player = dm.get_player(payload.player_id)
    if not player:
        player = dm.get_player_by_email(payload.player_id)
    if not player:
        return JSONResponse({"status": "error", "message": "Player not found."}, status_code=404)

    pin = dm.get_pin_for_player(payload.player_id)
    if pin:
        allowed, err_msg = dm.check_and_update_pin_cooldown(pin, 10.0)
        if not allowed:
            return JSONResponse({"success": False, "error": err_msg}, status_code=429)

    updated = dm.adjust_player_balance(player["id"], payload.amount)
    print(f"[Token Bank] Injected {payload.amount} tokens for {player.get('name')} ({player['id']}). New balance: {updated.get('balance')}")
    return {"status": "success", "player": updated}

@app.post("/api/player/register")
def register_player_api(payload: PlayerRegisterPayload):
    player, is_new = dm.register_or_get_player(payload.email, payload.name, None, payload.newsletter_opt_in)
    return {"status": "success", "player": player, "is_new": is_new}

@app.get("/api/players/manifest")
def get_manifest():
    return {"status": "success", "players": dm.get_all_players()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
