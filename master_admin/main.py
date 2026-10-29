from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List
import time
from pathlib import Path
import os
import uvicorn
import httpx

import master_admin.data_manager as dm
import master_admin.email_manager as em
import master_admin.bison_ledger as bison_ledger
from master_admin.process_manager import manager
from master_admin.profanity_filter import validate_player_name

# Ensure static directories exist
STATIC_DIR = Path("master_admin/static")
(STATIC_DIR / "css").mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "js").mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Venue Command - Master Admin")

@app.middleware("http")
async def rewrite_slideshow_prefix(request: Request, call_next):
    if request.url.path.startswith("/slideshow/api/"):
        request.scope["path"] = request.url.path.replace("/slideshow/api/", "/api/", 1)
    elif request.url.path.startswith("/presremote/api/"):
        request.scope["path"] = request.url.path.replace("/presremote/api/", "/api/", 1)
    return await call_next(request)

# Mount static files, slides, and templates
app.mount("/static", StaticFiles(directory="master_admin/static"), name="static")
if Path("slides").exists():
    app.mount("/slides", StaticFiles(directory="slides"), name="slides")
templates = Jinja2Templates(directory=".")

# Register managed game processes
manager.register_game("bison_dash", 8001, "game_hub.games.bison_dash.main:app")
manager.register_game("dummy_game", 8002, "games.dummy_game:app")
manager.register_game("bughunt", 8003, "games.bughunt_server:app")
manager.register_game("n64", 8004, "games.n64_server:app")
manager.register_game("token_bank", 8005, "games.token_bank_server:app")
manager.register_game("gauntlet", 8007, "games.gauntlet_server:app")
manager.register_game("kiosk", 8008, "games.kiosk_server:app")
manager.register_game("player_portal", 8009, "games.portal_server:app")
manager.register_game("slideshow", 8010, "games.slideshow_server:app")
manager.register_game("presremote", 8011, "games.presremote_server:app")

# Payload Models
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
    pin: Optional[str] = None
    player_id: Optional[str] = None
    amount: int
    action: Optional[str] = "adjust"
    description: Optional[str] = None

class ProcessActionPayload(BaseModel):
    game_id: str

class PlayerRegisterPayload(BaseModel):
    email: str
    name: str
    newsletter_opt_in: bool = False

class EmailConfigPayload(BaseModel):
    enabled: Optional[bool] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    use_tls: Optional[bool] = None
    use_ssl: Optional[bool] = None
    username: Optional[str] = None
    password: Optional[str] = None
    from_name: Optional[str] = None
    from_email: Optional[str] = None
    subject_template: Optional[str] = None
    body_template: Optional[str] = None

class EmailTestPayload(BaseModel):
    to_email: str
    subject: Optional[str] = None
    body: Optional[str] = None

class GauntletPlayPayload(BaseModel):
    player_id: str | None = None
    id: str | None = None
    pin: str | None = None

class GauntletPayoutPayload(BaseModel):
    player_id: str | None = None
    id: str | None = None
    pin: str | None = None
    payout: int
    level_reached: int = 1
    outcome: str = "WIN"

class N64PayoutPayload(BaseModel):
    winner_id: str | None = None
    player_id: str | None = None
    id: str | None = None
    pin: str | None = None
    loser_id: str | None = None
    tokens: int | None = None

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

class AdjustBalancePayload(BaseModel):
    player_id: str
    delta: int

class ResetBalancesPayload(BaseModel):
    default_balance: int = 100

class SlideTogglePayload(BaseModel):
    slide_id: str
    enabled: bool

class SlideReorderPayload(BaseModel):
    slide_ids: List[str]

class BrandingPayload(BaseModel):
    show_header_title: Optional[bool] = True
    show_clock: Optional[bool] = True

class CountdownStartPayload(BaseModel):
    minutes: float = 0
    seconds: int = 0
    title: Optional[str] = "Next Bison Dash Race"

class SlideshowModePayload(BaseModel):
    mode: str

class PresentationStartPayload(BaseModel):
    slide_index: int = 0

class PresentationStepPayload(BaseModel):
    delta: int = 1

class PresentationSetIndexPayload(BaseModel):
    index: int = 0

class FinalizedLinkPayload(BaseModel):
    id: Optional[str] = None
    title: str
    subtitle: Optional[str] = ""
    port: Optional[int] = None
    path: Optional[str] = ""
    url: Optional[str] = None
    icon: Optional[str] = "🔗"
    is_custom: Optional[bool] = True

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="master_admin/templates/dashboard.html")

@app.get("/mint", response_class=HTMLResponse)
@app.get("/cashier", response_class=HTMLResponse)
def serve_mint():
    for p in [Path("templates/mint.html"), Path("master_admin/templates/mint.html")]:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
    raise HTTPException(status_code=404, detail="mint.html template not found")

@app.get("/signup", response_class=HTMLResponse)
@app.get("/register", response_class=HTMLResponse)
def serve_signup():
    with open("game_hub/games/bison_dash/templates/signup.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/kiosk", response_class=HTMLResponse)
@app.get("/tablet", response_class=HTMLResponse)
@app.get("/tablet1", response_class=HTMLResponse)
@app.get("/tablet2", response_class=HTMLResponse)
@app.get("/bet", response_class=HTMLResponse)
@app.get("/bet1", response_class=HTMLResponse)
@app.get("/bet2", response_class=HTMLResponse)
def serve_kiosk():
    with open("game_hub/games/bison_dash/templates/kiosk.html", "r", encoding="utf-8") as f:
        return f.read()

BISON_DASH_URL = os.environ.get("BISON_DASH_URL", "http://127.0.0.1:8001")

@app.get("/api/current_race")
async def proxy_current_race():
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{BISON_DASH_URL}/api/current_race")
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
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
            "message": f"Fallback: engine connecting ({e})"
        }, status_code=200)

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

@app.get("/api/bisondash/wagers")
def get_bisondash_wagers_admin():
    wagers = bison_ledger.get_all_active_wagers()
    return {
        "status": "success",
        "wagers": wagers,
        "count": len(wagers),
        "total_pot": sum(w.get("amount", 0) for w in wagers)
    }

@app.get("/api/bisondash/wager/{identifier}")
def get_player_wager_admin(identifier: str):
    w = bison_ledger.get_wager_for_player(identifier)
    if w:
        return {"status": "success", "has_wager": True, "wager": w}
    return {"status": "success", "has_wager": False, "wager": None}

@app.post("/api/bisondash/wager")
async def place_bison_wager_admin(request: Request):
    try:
        body = await request.json()
        pid = body.get("player_id") or body.get("pin")
        slot = body.get("slot")
        amount = body.get("amount")
        bison_name = body.get("bison_name", "")

        if not pid or not slot or not amount:
            return JSONResponse({"status": "error", "message": "Missing player_id, slot, or amount"}, status_code=400)

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
def settle_bisondash_admin(payload: SettlePayload):
    res = bison_ledger.settle_race(payload.winner_slot, multiplier=payload.multiplier or 2.0)
    return {"status": "success", "result": res}

@app.get("/manifest", response_class=HTMLResponse)
def serve_manifest():
    with open("game_hub/games/bison_dash/templates/manifest.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/slideshow", response_class=HTMLResponse)
def serve_slideshow():
    with open("master_admin/templates/slideshow.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/projector", response_class=HTMLResponse)
def serve_projector_arena():
    with open("game_hub/games/bison_dash/templates/projector.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/bisondash/test_race")
async def proxy_test_race_admin():
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(f"{BISON_DASH_URL}/api/bisondash/test_race", json={})
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/presremote", response_class=HTMLResponse)
@app.get("/presenter", response_class=HTMLResponse)
@app.get("/remote", response_class=HTMLResponse)
@app.get("/clicker", response_class=HTMLResponse)
def serve_presenter():
    with open("master_admin/templates/presenter.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/presremote.webmanifest")
@app.get("/manifest.webmanifest")
def serve_presremote_manifest():
    manifest_path = Path("master_admin/static/presremote.webmanifest")
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="application/manifest+json")
    raise HTTPException(status_code=404, detail="PresRemote manifest not found")

@app.get("/presremote-sw.js")
@app.get("/sw.js")
def serve_presremote_sw():
    sw_path = Path("master_admin/static/js/presremote-sw.js")
    if sw_path.exists():
        with open(sw_path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="PresRemote service worker not found")

# --- Slideshow & Screen Management APIs ---

@app.get("/api/slides")
@app.get("/api/slides/list")
def get_slides_api():
    manifest = dm.get_slides_manifest()
    return {
        "status": "success",
        "slides": manifest.get("slides", []),
        "presentation_slides": manifest.get("presentation_slides", []),
        "branding": manifest.get("branding", {}),
        "default_duration": manifest.get("default_duration", 10)
    }

@app.get("/api/slides/branding")
def get_branding_api():
    return {"status": "success", "branding": dm.get_slideshow_branding()}

@app.post("/api/slides/branding")
def set_branding_api(payload: BrandingPayload):
    branding = dm.set_slideshow_branding(
        show_header_title=payload.show_header_title if payload.show_header_title is not None else True,
        show_clock=payload.show_clock if payload.show_clock is not None else True
    )
    return {"status": "success", "branding": branding}

@app.post("/api/slides/upload_logo")
async def upload_logo_api(file: UploadFile = File(...)):
    if not file.filename:
        return JSONResponse({"status": "error", "message": "No file uploaded."}, status_code=400)
    valid_exts = {".png", ".jpg", ".jpeg", ".webp"}
    ext = Path(file.filename).suffix.lower()
    if ext not in valid_exts:
        return JSONResponse({"status": "error", "message": f"Please upload a PNG, JPG, or WEBP image (got {ext})."}, status_code=400)
    try:
        content = await file.read()
        branding = dm.save_custom_logo(content, file.filename)
        return {"status": "success", "message": "Logo uploaded & formatted to 100x100 PNG successfully.", "branding": branding}
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"Error saving logo: {e}"}, status_code=500)

@app.post("/api/slides/reset_logo")
def reset_logo_api():
    branding = dm.reset_custom_logo()
    return {"status": "success", "message": "Logo reset to default placeholder.", "branding": branding}

@app.post("/api/slides/upload")
async def upload_slide_api(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    deck: Optional[str] = Form("regular")
):
    if not file.filename:
        return JSONResponse({"status": "error", "message": "No file uploaded."}, status_code=400)

    valid_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    ext = Path(file.filename).suffix.lower()
    if ext not in valid_exts:
        return JSONResponse({
            "status": "error",
            "message": f"Unsupported format '{ext}'. Please upload PNG, JPG, JPEG, or WEBP."
        }, status_code=400)

    try:
        content = await file.read()
        if len(content) == 0:
            return JSONResponse({"status": "error", "message": "Uploaded file is empty."}, status_code=400)

        target_deck = (deck or "regular").strip().lower()
        new_slide = dm.process_and_save_slide(content, file.filename, title=title, deck=target_deck)
        deck_label = "presentation" if target_deck == "presentation" else "regular"
        return {
            "status": "success",
            "message": f"Slide uploaded to {deck_label} deck and resized to 1920x1080 successfully.",
            "slide": new_slide,
            "deck": deck_label
        }
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"Failed to process image: {str(e)}"}, status_code=500)

@app.delete("/api/slides/{slide_id}")
def delete_slide_api(slide_id: str):
    success = dm.delete_slide(slide_id)
    if not success:
        return JSONResponse({"status": "error", "message": "Slide not found."}, status_code=404)
    return {"status": "success", "message": "Slide deleted successfully."}

@app.post("/api/slides/toggle")
def toggle_slide_api(payload: SlideTogglePayload):
    found = dm.toggle_slide(payload.slide_id, payload.enabled)
    if not found:
        return JSONResponse({"status": "error", "message": "Slide not found."}, status_code=404)
    return {"status": "success", "message": "Slide updated."}

@app.post("/api/slides/reorder")
def reorder_slides_api(payload: SlideReorderPayload):
    dm.reorder_slides(payload.slide_ids)
    return {"status": "success", "message": "Slides reordered successfully."}

# --- Presentation Cut-In Deck APIs ---

@app.get("/api/slides/presentation")
def get_presentation_slides_api():
    slides = dm.get_presentation_slides()
    return {"status": "success", "slides": slides}

@app.delete("/api/slides/presentation/{slide_id}")
def delete_presentation_slide_api(slide_id: str):
    success = dm.delete_presentation_slide(slide_id)
    if not success:
        return JSONResponse({"status": "error", "message": "Presentation slide not found."}, status_code=404)
    return {"status": "success", "message": "Presentation slide deleted successfully."}

@app.post("/api/slides/presentation/reorder")
def reorder_presentation_slides_api(payload: SlideReorderPayload):
    dm.reorder_presentation_slides(payload.slide_ids)
    return {"status": "success", "message": "Presentation slides reordered successfully."}

# --- Slideshow Runtime & Cut-In State APIs ---

@app.get("/api/slideshow/state")
def get_slideshow_state_api():
    state = dm.get_slideshow_state()
    return {
        "status": "success",
        "state": state,
        "server_time": time.time()
    }

@app.post("/api/slideshow/bison/start_countdown")
def start_countdown_api(payload: CountdownStartPayload):
    state = dm.set_slideshow_countdown(payload.minutes, payload.seconds, payload.title)
    return {"status": "success", "state": state}

@app.post("/api/slideshow/bison/stop")
def stop_countdown_api():
    state = dm.stop_slideshow_countdown()
    return {"status": "success", "state": state}

@app.post("/api/slideshow/bison/set_mode")
def set_mode_api(payload: SlideshowModePayload):
    state = dm.set_slideshow_mode(payload.mode)
    return {"status": "success", "state": state}

@app.post("/api/slideshow/presentation/start")
def start_presentation_api(payload: Optional[PresentationStartPayload] = None):
    idx = payload.slide_index if payload else 0
    state = dm.start_presentation_mode(idx)
    return {"status": "success", "state": state}

@app.post("/api/slideshow/presentation/stop")
def stop_presentation_api():
    state = dm.stop_presentation_mode()
    return {"status": "success", "state": state}

@app.post("/api/slideshow/presentation/step")
def step_presentation_api(payload: PresentationStepPayload):
    state = dm.step_presentation_slide(payload.delta)
    return {"status": "success", "state": state}

@app.post("/api/slideshow/presentation/set_index")
def set_presentation_index_api(payload: PresentationSetIndexPayload):
    state = dm.set_presentation_slide_index(payload.index)
    return {"status": "success", "state": state}

@app.post("/api/slideshow/restart_regular")
def restart_regular_slideshow_api():
    state = dm.restart_regular_slideshow()
    return {"status": "success", "message": "Regular slideshow restarted cleanly.", "state": state}

# --- Finalized Links & QR APIs ---

@app.get("/api/links")
def get_links_api():
    return {"status": "success", "links": dm.get_finalized_links()}

@app.post("/api/links")
def save_link_api(payload: FinalizedLinkPayload):
    links = dm.save_or_update_link(payload.model_dump())
    return {"status": "success", "links": links}

@app.delete("/api/links/{link_id}")
def delete_link_api(link_id: str):
    success = dm.delete_finalized_link(link_id)
    return {"status": "success" if success else "error"}


# --- Process Manager APIs ---

@app.get("/api/process/status")
def get_process_status():
    return {"status": "success", "processes": manager.get_status()}

@app.post("/api/process/start")
async def start_process(payload: ProcessActionPayload):
    started = await manager.start_game(payload.game_id)
    return {"status": "success" if started else "error", "running": started}

@app.post("/api/process/stop")
async def stop_process(payload: ProcessActionPayload):
    stopped = await manager.stop_game(payload.game_id)
    return {"status": "success" if stopped else "error", "stopped": stopped}

@app.get("/api/global/logs")
def get_global_logs(limit: int = 100):
    return {"status": "success", "logs": manager.get_logs(limit=limit)}

# --- Attendee PIN Verification & Concurrency Control ---

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

@app.post("/api/mint/tokens")
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

    # 10-Second Concurrency & Anti-Spam Lock
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

# --- Player Manifest & Token APIs ---

@app.post("/api/admin/inject-tokens")
def inject_tokens(payload: InjectTokensPayload):
    pin = dm.get_pin_for_player(payload.player_id)
    if pin:
        allowed, err_msg = dm.check_and_update_pin_cooldown(pin, 10.0)
        if not allowed:
            return JSONResponse({"success": False, "error": err_msg}, status_code=429)

    updated = dm.adjust_player_balance(payload.player_id, payload.amount)
    if not updated:
        # Create player entry if it didn't exist
        email_val = f"{payload.player_id}@venue.com" if "@" not in payload.player_id else payload.player_id
        new_player, _ = dm.register_or_get_player(email=email_val, name=payload.player_id, starting_balance=payload.amount)
        new_balance = new_player["balance"]
    else:
        new_balance = updated["balance"]

    return {"status": "success", "new_balance": new_balance}

@app.get("/api/players")
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

@app.get("/api/economy/config")
def get_economy_config_endpoint():
    return {"status": "success", "config": dm.get_economy_config()}

@app.post("/api/economy/config")
async def update_economy_config_endpoint(request: Request):
    try:
        body = await request.json()
        dm.save_economy_config(body)
        return {"status": "success", "config": dm.get_economy_config()}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)

@app.post("/api/economy/reset")
def reset_economy_config_endpoint():
    dm.save_economy_config(dm.DEFAULT_ECONOMY_CONFIG)
    return {"status": "success", "config": dm.get_economy_config()}

@app.post("/api/admin/clear-players")
def admin_clear_all_players():
    dm.clear_all_players()
    return {"status": "success", "message": "All players cleared."}

@app.post("/api/player/register")
def register_player(payload: PlayerRegisterPayload):
    email = payload.email.strip().lower()
    name = payload.name.strip()

    if not email or "@" not in email:
        return JSONResponse({"status": "error", "message": "Please enter a valid email address."}, status_code=400)

    valid, reason = validate_player_name(name)
    if not valid:
        return JSONResponse({"status": "error", "message": reason}, status_code=400)

    player, is_new = dm.register_or_get_player(email, name, starting_balance=0, newsletter_opt_in=payload.newsletter_opt_in)
    email_dispatched = False
    try:
        ok, msg = em.send_player_pass_email(player)
        email_dispatched = ok
        if not ok:
            print(f"[MasterAdmin Register] Pass email not sent to {email}: {msg}")
        else:
            print(f"[MasterAdmin Register] Pass email successfully sent to {email}")
    except Exception as e:
        print(f"[MasterAdmin Register] Exception sending pass email to {email}: {e}")
    return {"status": "success", "player": player, "is_new": is_new, "email_sent": email_dispatched}

@app.get("/api/email/config")
def get_email_config_api():
    cfg = em.load_email_config()
    return {"status": "success", "config": cfg}

@app.post("/api/email/config")
def save_email_config_api(payload: EmailConfigPayload):
    current = em.load_email_config()
    data = payload.dict(exclude_unset=True)
    current.update(data)
    em.save_email_config(current)
    return {"status": "success", "message": "Email settings saved.", "config": current}

@app.post("/api/email/test")
def send_email_test_api(payload: EmailTestPayload):
    cfg = em.load_email_config()
    if payload.subject and payload.body:
        ok, msg = em.send_email(payload.to_email, payload.subject, payload.body, cfg)
    else:
        ok, msg = em.send_test_email(payload.to_email, cfg)
    if not ok:
        return JSONResponse({"status": "error", "message": msg}, status_code=400)
    return {"status": "success", "message": msg}

@app.post("/api/email/send-pass/{identifier}")
def send_player_pass_api(identifier: str):
    player = dm.get_player(identifier)
    if not player:
        return JSONResponse({"status": "error", "message": "Player not found."}, status_code=404)
    ok, msg = em.send_player_pass_email(player)
    if not ok:
        return JSONResponse({"status": "error", "message": msg}, status_code=400)
    return {"status": "success", "message": msg}

@app.get("/api/player/{identifier}")
def get_player_profile(identifier: str):
    player = None
    if "@" in identifier:
        player = dm.get_player_by_email(identifier)
    else:
        player = dm.get_player(identifier)
    if not player and identifier.isdigit() and len(identifier) == 4:
        player = dm.get_player_by_pin(identifier)

    if not player:
        return JSONResponse({"status": "error", "message": "Player not found."}, status_code=404)

    wager = bison_ledger.get_wager_for_player(player.get("id")) or (bison_ledger.get_wager_for_player(player.get("pin")) if player.get("pin") else None)
    player["current_wager"] = wager
    return {"status": "success", "player": player}

@app.get("/api/gauntlet/config")
def main_get_gauntlet_config():
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
def main_gauntlet_play(payload: GauntletPlayPayload):
    identifier = payload.player_id or payload.id or payload.pin
    if not identifier:
        return JSONResponse({"status": "error", "message": "Player ID or PIN is required."}, status_code=400)
    res = dm.deduct_game_cost(identifier, "gauntlet")
    if not res["allowed"]:
        return JSONResponse({"status": "error", "message": res.get("message", "Insufficient tokens."), "cost": res.get("cost", 4), "balance": res.get("balance", 0)}, status_code=400)
    return {"status": "success", "cost": res.get("cost", 4), "balance": res.get("balance", 0)}

@app.post("/api/gauntlet/payout")
def main_gauntlet_payout(payload: GauntletPayoutPayload):
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

@app.get("/api/n64/config")
def get_main_n64_config():
    eco = dm.get_economy_config()
    return {
        "status": "success",
        "cost": eco.get("costs", {}).get("n64", 0),
        "winner_payout": eco.get("payouts", {}).get("n64_winner", 8)
    }

@app.post("/api/n64/payout")
def main_n64_payout(payload: N64PayoutPayload):
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

@app.get("/api/bughunt/config")
def get_main_bughunt_config():
    eco = dm.get_economy_config()
    return {
        "status": "success",
        "cost": eco.get("costs", {}).get("bughunt", 1),
        "bugs_per_token": eco.get("payouts", {}).get("bughunt_bugs_per_token", 5),
        "pity_tokens": eco.get("payouts", {}).get("bughunt_pity_tokens", 1),
        "timer_seconds": eco.get("timers", {}).get("bughunt_duration", 60)
    }

@app.post("/api/bughunt/payout")
@app.post("/api/games/bughunt/payout")
def main_bughunt_payout(payload: BugHuntPayoutPayload):
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

@app.get("/api/plinko/config")
def get_main_plinko_config():
    eco = dm.get_economy_config()
    return {
        "status": "success",
        "cost": eco.get("costs", {}).get("plinko", 0),
        "slots": eco.get("payouts", {}).get("plinko_slots", [1, 1, 2, 2, 5, 2, 2, 1, 1])
    }

@app.post("/api/plinko/payout")
def main_plinko_payout(payload: PlinkoPayoutPayload):
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
    path = Path("game_hub/games/bison_dash/templates/gauntlet.html")
    if not path.exists():
        raise HTTPException(status_code=404, detail="gauntlet.html not found")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/poster", response_class=HTMLResponse)
def serve_poster():
    poster_path = Path("master_admin/templates/gauntlet_poster.html")
    if not poster_path.exists():
        poster_path = Path("game_hub/games/bison_dash/templates/gauntlet_poster.html")
    if not poster_path.exists():
        raise HTTPException(status_code=404, detail="gauntlet_poster.html not found")
    with open(poster_path, "r", encoding="utf-8") as f:
        return f.read()

# =========================================================================
# UNIFIED MOBILE PLAYER PORTAL ENDPOINTS (TAILSCALE FUNNEL RESILIENCE)
# =========================================================================
class PortalRegisterDirectPayload(BaseModel):
    name: str
    email: str
    newsletter_opt_in: bool = False

@app.get("/portal", response_class=HTMLResponse)
@app.get("/portal/", response_class=HTMLResponse)
def serve_portal_main():
    portal_path = Path("game_hub/games/bison_dash/templates/portal.html")
    if not portal_path.exists():
        raise HTTPException(status_code=404, detail="portal.html template not found")
    with open(portal_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/portal/config")
@app.get("/portal/api/portal/config")
def get_portal_config_main():
    eco = dm.get_economy_config()
    return {
        "status": "success",
        "initial_allotment": 0
    }

@app.post("/api/portal/register")
@app.post("/portal/api/portal/register")
def register_portal_player_main(payload: PortalRegisterDirectPayload):
    email = payload.email.strip().lower()
    name = payload.name.strip()
    if not email or "@" not in email:
        return JSONResponse({"status": "error", "message": "Please enter a valid email address."}, status_code=400)
    if not name:
        return JSONResponse({"status": "error", "message": "Please enter a display name."}, status_code=400)

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

    player, is_new = dm.register_or_get_player(email, name, starting_balance=0, newsletter_opt_in=payload.newsletter_opt_in)
    email_dispatched = False
    try:
        ok, msg = em.send_player_pass_email(player)
        email_dispatched = ok
        if not ok:
            print(f"[MasterAdmin Register] Pass email not sent to {email}: {msg}")
        else:
            print(f"[MasterAdmin Register] Pass email successfully sent to {email}")
    except Exception as e:
        print(f"[MasterAdmin Register] Exception sending pass email to {email}: {e}")

    return {
        "status": "success",
        "is_new": is_new,
        "email_sent": email_dispatched,
        "player": player
    }

@app.get("/api/portal/balance/{identifier}")
@app.get("/portal/api/portal/balance/{identifier}")
@app.get("/api/portal/lookup/{identifier}")
@app.get("/portal/api/portal/lookup/{identifier}")
def lookup_portal_player_balance_main(identifier: str):
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

if __name__ == "__main__":
    port_file = Path("port.txt")
    port = 8000
    try:
        if not port_file.exists():
            with open(port_file, "w") as f:
                f.write("8000")
        else:
            with open(port_file, "r") as f:
                port = int(f.read().strip())
    except Exception as e:
        print(f"Error reading port.txt: {e}. Defaulting to 8000.")
        with open(port_file, "w") as f:
            f.write("8000")
        port = 8000

    uvicorn.run(app, host="0.0.0.0", port=port)
