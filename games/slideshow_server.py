import os
import sys
import time
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

import master_admin.data_manager as dm

SLIDESHOW_PORT = int(os.environ.get("SLIDESHOW_PORT", "8010"))
BISON_DASH_URL = os.environ.get("BISON_DASH_URL", "http://127.0.0.1:8001")
PROJECTOR_TEMPLATE = Path("game_hub/games/bison_dash/templates/projector.html")
BISON_STATIC_DIR = Path("game_hub/games/bison_dash/static")

app = FastAPI(
    title="Bison Bash - Stadium Slideshow & Presenter Server (Port 8010)",
    description="Dedicated FastAPI backend service for the 1080p Arena Projector Slideshow (DJ Mac) and Mobile Presenter Remote",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def rewrite_slideshow_prefix(request: Request, call_next):
    if request.url.path.startswith("/slideshow/api/"):
        request.scope["path"] = request.url.path.replace("/slideshow/api/", "/api/", 1)
    return await call_next(request)

# Paths
STATIC_DIR = Path("master_admin/static")
SLIDES_DIR = dm.SLIDES_DIR
SLIDESHOW_TEMPLATE = Path("master_admin/templates/slideshow.html")
PRESENTER_TEMPLATE = Path("master_admin/templates/presenter.html")

if (BISON_STATIC_DIR / "display").exists():
    app.mount("/static/display", StaticFiles(directory=str(BISON_STATIC_DIR / "display")), name="bison_display")
if (BISON_STATIC_DIR / "bisons").exists():
    app.mount("/static/bisons", StaticFiles(directory=str(BISON_STATIC_DIR / "bisons")), name="bison_sprites")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.mount("/slideshow/static", StaticFiles(directory=str(STATIC_DIR)), name="slideshow_static")

if SLIDES_DIR.exists():
    app.mount("/slides", StaticFiles(directory=str(SLIDES_DIR)), name="slides")
    app.mount("/slideshow/slides", StaticFiles(directory=str(SLIDES_DIR)), name="slideshow_slides")

@app.get("/projector", response_class=HTMLResponse)
@app.get("/slideshow/projector", response_class=HTMLResponse)
def serve_projector():
    if not PROJECTOR_TEMPLATE.exists():
        raise HTTPException(status_code=404, detail="projector.html template not found")
    with open(PROJECTOR_TEMPLATE, "r", encoding="utf-8") as f:
        return f.read()

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
        return JSONResponse({"status": "success", "state": "Betting_Open", "lineup": lineup}, status_code=200)

@app.get("/api/bisondash/wagers")
def proxy_bisondash_wagers():
    try:
        import master_admin.bison_ledger as bison_ledger
        wagers = bison_ledger.get_all_active_wagers()
        return {"status": "success", "wagers": wagers, "count": len(wagers), "total_pot": sum(w.get("amount", 0) for w in wagers)}
    except Exception:
        return {"status": "success", "wagers": []}

@app.post("/api/bisondash/test_race")
async def proxy_test_race():
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(f"{BISON_DASH_URL}/api/bisondash/test_race", json={})
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/slideshow/bison/start_race_cutin")
def start_race_cutin_api(minutes: int = 5):
    state = dm.set_slideshow_countdown(minutes=minutes, seconds=0, title="Bison Dash: Championship Track")
    return {"status": "success", "state": state}

# Payload Models
class SlideTogglePayload(BaseModel):
    slide_id: str
    enabled: bool

class SlideReorderPayload(BaseModel):
    slide_ids: List[str]

class BrandingPayload(BaseModel):
    show_header_title: Optional[bool] = True
    show_clock: Optional[bool] = True

class CountdownStartPayload(BaseModel):
    minutes: float = 0.0
    seconds: int = 0
    title: Optional[str] = "Next Bison Dash Race"

class SlideshowModePayload(BaseModel):
    mode: str

class PresentationStartPayload(BaseModel):
    slide_index: int = 0

class PresentationStepPayload(BaseModel):
    delta: int = 1

class PresentationSetIndexPayload(BaseModel):
    index: int

class AttendeeLookupPayload(BaseModel):
    pin: str

class TokenTransactPayload(BaseModel):
    pin: str | None = None
    player_id: str | None = None
    amount: int
    action: str | None = "adjust"
    description: str | None = None

# --- Health & Web Interface Routes ---

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
    return {
        "status": "ok",
        "service": "slideshow_service",
        "port": SLIDESHOW_PORT,
        "mode": dm.get_slideshow_state().get("mode", "slideshow")
    }

@app.get("/", response_class=HTMLResponse)
@app.get("/slideshow", response_class=HTMLResponse)
def serve_slideshow():
    """Serves the clean 1080p stadium display for the DJ's Mac with native F11 fullscreen."""
    if not SLIDESHOW_TEMPLATE.exists():
        raise HTTPException(status_code=404, detail="slideshow.html template not found")
    with open(SLIDESHOW_TEMPLATE, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/presremote", response_class=HTMLResponse)
@app.get("/presenter", response_class=HTMLResponse)
@app.get("/remote", response_class=HTMLResponse)
@app.get("/clicker", response_class=HTMLResponse)
def serve_presenter():
    """Serves the mobile touch clicker / remote control for smartphones (PresRemote)."""
    if not PRESENTER_TEMPLATE.exists():
        raise HTTPException(status_code=404, detail="presenter.html template not found")
    with open(PRESENTER_TEMPLATE, "r", encoding="utf-8") as f:
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

# --- Slideshow & Slide Deck APIs ---

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

# --- Stage Presentation Cut-In Deck APIs ---

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
@app.post("/api/presentation/start")
def start_presentation_api(payload: Optional[PresentationStartPayload] = None):
    idx = payload.slide_index if payload else 0
    state = dm.start_presentation_mode(idx)
    return {"status": "success", "state": state}

@app.post("/api/slideshow/presentation/stop")
@app.post("/api/presentation/stop")
def stop_presentation_api():
    state = dm.stop_presentation_mode()
    return {"status": "success", "state": state}

@app.post("/api/slideshow/presentation/step")
@app.post("/api/presentation/step")
def step_presentation_api(payload: PresentationStepPayload):
    state = dm.step_presentation_slide(payload.delta)
    return {"status": "success", "state": state}

@app.post("/api/slideshow/presentation/set_index")
@app.post("/api/presentation/set_index")
@app.post("/api/presentation/index")
def set_presentation_index_api(payload: PresentationSetIndexPayload):
    state = dm.set_presentation_slide_index(payload.index)
    return {"status": "success", "state": state}

@app.post("/api/slideshow/restart_regular")
def restart_regular_slideshow_api():
    state = dm.restart_regular_slideshow()
    return {"status": "success", "message": "Regular slideshow restarted cleanly.", "state": state}

# --- Leaderboard Integration for Slideshow Mix ---

@app.get("/api/players")
@app.get("/api/players/manifest")
def get_manifest_api():
    players = dm.get_all_players()
    return {"status": "success", "players": players}

if __name__ == "__main__":
    import uvicorn
    print(f"[*] Starting Bison Bash Stadium Slideshow & Presenter Server on port {SLIDESHOW_PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=SLIDESHOW_PORT)
