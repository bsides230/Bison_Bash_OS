from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import os
import master_admin.data_manager as dm

app = FastAPI(title="Port Hop Plinko - Dedicated Game Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path("master_admin/static")
TEMPLATE_PATH = Path("game_hub/games/bison_dash/templates/plinko.html")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

class PlinkoPayoutPayload(BaseModel):
    player_id: str | None = None
    id: str | None = None
    pin: str | None = None
    payout: int
    slot_index: int | None = None
    port: int | str | None = None

class PlinkoPlayPayload(BaseModel):
    player_id: str | None = None
    id: str | None = None
    pin: str | None = None

@app.get("/", response_class=HTMLResponse)
@app.get("/plinko", response_class=HTMLResponse)
def serve_plinko():
    if not TEMPLATE_PATH.exists():
        raise HTTPException(status_code=404, detail="plinko.html template not found")
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
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
def plinko_play(payload: PlinkoPlayPayload):
    ident = payload.player_id or payload.id or payload.pin
    if not ident:
        return JSONResponse({"status": "error", "message": "Player identifier required."}, status_code=400)
    res = dm.deduct_game_cost(ident, "plinko")
    if not res["allowed"]:
        return JSONResponse({"status": "error", "message": res.get("message", "Insufficient tokens."), "cost": res["cost"], "balance": res["balance"]}, status_code=400)
    return {"status": "success", "cost": res["cost"], "balance": res["balance"]}

@app.get("/api/player/{identifier}")
@app.get("/plinko/api/player/{identifier}")
def get_player_api(identifier: str):
    player = dm.get_player(identifier)
    if not player:
        player = dm.get_player_by_email(identifier)
    if not player:
        player = dm.get_player_by_pin(identifier)
    if not player:
        return JSONResponse({"status": "error", "message": "Player not found."}, status_code=404)
    return {"status": "success", "player": player}

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

    print(f"[Plinko] Payout {payload.payout} tokens to {player.get('name')} ({pid}) on port {payload.port}.")

    return {
        "status": "success",
        "new_balance": updated.get("balance", 0) if updated else 0,
        "payout": payload.payout,
        "player_name": player.get("name")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
