from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import os
import master_admin.data_manager as dm
import master_admin.email_manager as em

app = FastAPI(title="Bison Bash - Mobile Player Portal (Port 8009)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path("master_admin/static")
TEMPLATE_PATH = Path("game_hub/games/bison_dash/templates/portal.html")
POSTER_PATH = Path("game_hub/games/bison_dash/templates/gauntlet_poster.html")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

class RegisterPayload(BaseModel):
    name: str
    email: str
    newsletter_opt_in: bool = False

class EmailConfigPayload(BaseModel):
    enabled: bool | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    use_tls: bool | None = None
    use_ssl: bool | None = None
    username: str | None = None
    password: str | None = None
    from_name: str | None = None
    from_email: str | None = None
    subject_template: str | None = None
    body_template: str | None = None

class BalanceLookupPayload(BaseModel):
    query: str

class AttendeeLookupPayload(BaseModel):
    pin: str

class TokenTransactPayload(BaseModel):
    pin: str | None = None
    player_id: str | None = None
    amount: int
    action: str | None = "adjust"
    description: str | None = None

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

class PlinkoPayoutPayload(BaseModel):
    player_id: str | None = None
    id: str | None = None
    pin: str | None = None
    payout: int
    slot_index: int | None = None
    port: int | str | None = None

class BugHuntPayoutPayload(BaseModel):
    player_id: str | None = None
    id: str | None = None
    pin: str | None = None
    bugs: int = 0
    pity_credit: bool = False

class N64PayoutPayload(BaseModel):
    winner_id: str | None = None
    player_id: str | None = None
    id: str | None = None
    pin: str | None = None
    loser_id: str | None = None
    tokens: int | None = None

class BugHuntPlayPayload(BaseModel):
    player_id: str | None = None
    id: str | None = None
    pin: str | None = None

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

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "player_portal", "port": 8009}

# --- GAUNTLET INTEGRATION (Unified API Access for Tailscale Funnel) ---
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

    return {
        "status": "success",
        "new_balance": updated.get("balance", 0) if updated else 0,
        "payout": payload.payout,
        "player_name": player.get("name")
    }

@app.get("/api/player/{identifier}")
def get_player_api(identifier: str):
    player = dm.get_player(identifier)
    if not player:
        player = dm.get_player_by_email(identifier)
    if not player:
        player = dm.get_player_by_pin(identifier)
    if not player:
        return JSONResponse({"status": "error", "message": "Player not found."}, status_code=404)
    return {"status": "success", "player": player}

# --- BUG BOUNTY INTEGRATION (Unified API Access for Tailscale Funnel) ---
@app.get("/api/bughunt/config")
@app.get("/bugbounty/api/bughunt/config")
def portal_get_bughunt_config():
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
def portal_bughunt_play(payload: BugHuntPlayPayload):
    identifier = payload.player_id or payload.id or payload.pin
    if not identifier:
        return JSONResponse({"status": "error", "message": "Player ID or PIN required."}, status_code=400)
    pin = dm.get_pin_for_player(identifier) or (identifier if str(identifier).isdigit() and len(str(identifier)) == 4 else None)
    if pin:
        allowed, err_msg = dm.check_and_update_pin_cooldown(pin, 10.0)
        if not allowed:
            return JSONResponse({"success": False, "error": err_msg}, status_code=429)
    res = dm.deduct_game_cost(identifier, "bughunt")
    if not res["allowed"]:
        return JSONResponse({"status": "error", "message": res.get("message", "Insufficient tokens."), "cost": res.get("cost", 0), "balance": res.get("balance", 0)}, status_code=400)
    return {"status": "success", "cost": res.get("cost", 0), "balance": res.get("balance", 0)}

@app.post("/api/bughunt/payout")
@app.post("/api/games/bughunt/payout")
@app.post("/bugbounty/api/bughunt/payout")
def portal_bughunt_payout(payload: BugHuntPayoutPayload):
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
    tokens = payload.bugs // bugs_per_token
    if payload.pity_credit and tokens == 0 and payload.bugs > 0:
        tokens = pity_tokens
    parent_id = parent["id"]
    updated = dm.adjust_player_balance(parent_id, tokens, winnings=tokens)
    return {
        "status": "success",
        "new_balance": updated.get("balance", 0) if updated else 0,
        "tokens": tokens,
        "tokens_awarded": tokens,
        "parent_name": parent.get("name")
    }

@app.get("/api/n64/config")
@app.get("/n64/api/n64/config")
def get_portal_n64_config():
    eco = dm.get_economy_config()
    return {
        "status": "success",
        "cost": eco.get("costs", {}).get("n64", 0),
        "winner_payout": eco.get("payouts", {}).get("n64_winner", 8)
    }

@app.post("/api/n64/payout")
@app.post("/n64/api/n64/payout")
def portal_n64_payout(payload: N64PayoutPayload):
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

@app.get("/api/plinko/config")
@app.get("/plinko/api/plinko/config")
def get_portal_plinko_config():
    eco = dm.get_economy_config()
    return {
        "status": "success",
        "cost": eco.get("costs", {}).get("plinko", 0),
        "slots": eco.get("payouts", {}).get("plinko_slots", [1, 1, 2, 2, 5, 2, 2, 1, 1])
    }

@app.post("/api/plinko/payout")
@app.post("/plinko/api/plinko/payout")
def portal_plinko_payout(payload: PlinkoPayoutPayload):
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

@app.get("/", response_class=HTMLResponse)
@app.get("/portal", response_class=HTMLResponse)
@app.get("/portal/", response_class=HTMLResponse)
def serve_portal():
    if not TEMPLATE_PATH.exists():
        raise HTTPException(status_code=404, detail="portal.html template not found")
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/portal/register")
@app.post("/portal/api/portal/register")
def register_player(payload: RegisterPayload):
    email = payload.email.strip().lower()
    name = payload.name.strip()

    if not email or "@" not in email:
        return JSONResponse({"status": "error", "message": "Please enter a valid email address."}, status_code=400)
    if not name:
        return JSONResponse({"status": "error", "message": "Please enter a display name."}, status_code=400)

    # Check if email is already in the system
    existing = dm.get_player_by_email(email)
    if existing:
        return {
            "status": "exists",
            "message": "Email is already registered in the system!",
            "player": {
                "id": existing["id"],
                "name": existing.get("name", name),
                "email": existing.get("email", email),
                "pin": existing.get("pin", "----"),
                "balance": existing.get("balance", 0),
                "total_winnings": existing.get("total_winnings", 0)
            }
        }

    # Register new player (0 starting tokens - no complimentary credits or bonus allotments)
    player, is_new = dm.register_or_get_player(email, name, starting_balance=0, newsletter_opt_in=payload.newsletter_opt_in)

    # Attempt email dispatch if SMTP is configured
    email_dispatched = False
    try:
        ok, msg = em.send_player_pass_email(player)
        email_dispatched = ok
        if not ok:
            print(f"[Portal Register] Pass email not sent to {email}: {msg}")
        else:
            print(f"[Portal Register] Pass email successfully sent to {email}")
    except Exception as e:
        print(f"[Portal Register] Exception sending pass email to {email}: {e}")

    return {
        "status": "success",
        "is_new": is_new,
        "email_sent": email_dispatched,
        "player": player
    }

@app.get("/api/portal/config")
@app.get("/portal/api/portal/config")
def get_portal_config():
    eco = dm.get_economy_config()
    return {
        "status": "success",
        "initial_allotment": eco.get("initial_allotment", 50)
    }

@app.get("/api/portal/balance/{identifier}")
@app.get("/portal/api/portal/balance/{identifier}")
@app.get("/api/portal/lookup/{identifier}")
@app.get("/portal/api/portal/lookup/{identifier}")
def lookup_player_balance(identifier: str):
    query = identifier.strip()
    if not query:
        return JSONResponse({"status": "error", "message": "Query parameter cannot be empty."}, status_code=400)

    player = None
    if len(query) == 4 and query.isdigit():
        player = dm.get_player_by_pin(query)
    elif "@" in query:
        player = dm.get_player_by_email(query)
    elif query.startswith("p_"):
        player = dm.get_player(query)

    # Universal robust lookup: check PIN, Email, and master registry/file matches
    if not player:
        player = dm.get_player_by_pin(query)
    if not player and "@" in query:
        player = dm.get_player_by_email(query)
    if not player:
        player = dm.get_player(query)
    if not player:
        return JSONResponse({
            "status": "not_found",
            "message": f"No account found matching '{query}'. Check your PIN or registered email."
        }, status_code=404)

    return {
        "status": "success",
        "player": {
            "id": player["id"],
            "name": player.get("name", "Player"),
            "email": player.get("email", ""),
            "pin": player.get("pin", "----"),
            "balance": player.get("balance", 0),
            "total_wagers": player.get("total_wagers", 0),
            "total_winnings": player.get("total_winnings", 0),
            "created_at": player.get("created_at", 0)
        }
    }

@app.post("/api/portal/balance")
def lookup_balance_post(payload: BalanceLookupPayload):
    return lookup_player_balance(payload.query)

@app.get("/api/email/config")
def portal_get_email_config():
    cfg = em.load_email_config()
    return {"status": "success", "config": cfg}

@app.post("/api/email/config")
def portal_save_email_config(payload: EmailConfigPayload):
    current = em.load_email_config()
    data = payload.dict(exclude_unset=True)
    current.update(data)
    em.save_email_config(current)
    return {"status": "success", "message": "Email settings saved.", "config": current}

class MintTokensPayload(BaseModel):
    pin: str
    donation_amount: float
    tokens_to_add: int

@app.get("/api/mint/config")
@app.get("/mint/api/mint/config")
def get_mint_config_portal():
    eco = dm.get_economy_config()
    return {
        "status": "success",
        "tokens_per_dollar": eco.get("tokens_per_dollar", 5)
    }

@app.post("/api/mint/tokens")
@app.post("/mint/api/mint/tokens")
def mint_tokens_portal(payload: MintTokensPayload):
    result = dm.mint_tokens(payload.pin, payload.donation_amount, payload.tokens_to_add)
    if not result:
        return JSONResponse({"success": False, "error": "Invalid PIN"}, status_code=404)
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8009)
