import os
import sys
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import master_admin.data_manager as dm

PRESREMOTE_PORT = int(os.environ.get("PRESREMOTE_PORT", "8011"))

app = FastAPI(
    title="Bison Bash - PresRemote Dedicated Server (Port 8011)",
    description="Dedicated standalone FastAPI service for the PresRemote Mobile PWA & Stage Clicker",
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
async def rewrite_presremote_prefix(request: Request, call_next):
    if request.url.path.startswith("/presremote/api/"):
        request.scope["path"] = request.url.path.replace("/presremote/api/", "/api/", 1)
    elif request.url.path.startswith("/presenter/api/"):
        request.scope["path"] = request.url.path.replace("/presenter/api/", "/api/", 1)
    return await call_next(request)

# Paths
STATIC_DIR = Path("master_admin/static")
SLIDES_DIR = dm.SLIDES_DIR
PRESENTER_TEMPLATE = Path("master_admin/templates/presenter.html")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.mount("/presremote/static", StaticFiles(directory=str(STATIC_DIR)), name="presremote_static")

if SLIDES_DIR.exists():
    app.mount("/slides", StaticFiles(directory=str(SLIDES_DIR)), name="slides")
    app.mount("/presremote/slides", StaticFiles(directory=str(SLIDES_DIR)), name="presremote_slides")

# Payload Models
class PresentationStepPayload(BaseModel):
    delta: int

class PresentationSetIndexPayload(BaseModel):
    index: int

class PresentationStartPayload(BaseModel):
    slide_index: Optional[int] = 0

# --- Health & Web Shell ---

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "presremote_service",
        "port": PRESREMOTE_PORT,
        "mode": dm.get_slideshow_state().get("mode", "slideshow")
    }

# All primary routes on port 8011 directly serve PresRemote!
@app.get("/", response_class=HTMLResponse)
@app.get("/presremote", response_class=HTMLResponse)
@app.get("/presenter", response_class=HTMLResponse)
@app.get("/remote", response_class=HTMLResponse)
@app.get("/clicker", response_class=HTMLResponse)
def serve_presremote():
    """Serves the standalone PresRemote mobile clicker / PWA."""
    if not PRESENTER_TEMPLATE.exists():
        raise HTTPException(status_code=404, detail="presenter.html template not found")
    with open(PRESENTER_TEMPLATE, "r", encoding="utf-8") as f:
        return f.read()

# --- PWA Manifest & Service Worker ---

@app.get("/presremote.webmanifest")
@app.get("/manifest.webmanifest")
@app.get("/manifest.json")
def serve_manifest():
    manifest_path = Path("master_admin/static/presremote.webmanifest")
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="application/manifest+json")
    raise HTTPException(status_code=404, detail="PresRemote manifest not found")

@app.get("/presremote-sw.js")
@app.get("/sw.js")
def serve_service_worker():
    sw_path = Path("master_admin/static/js/presremote-sw.js")
    if sw_path.exists():
        with open(sw_path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="PresRemote service worker not found")

# --- Slide & Presentation Control APIs ---

@app.get("/api/slides/presentation")
def get_presentation_slides_api():
    slides = dm.get_presentation_slides()
    return {"status": "success", "slides": slides, "count": len(slides)}

@app.get("/api/slideshow/state")
def get_slideshow_state_api():
    return {"status": "success", "state": dm.get_slideshow_state()}

@app.post("/api/slideshow/presentation/start")
@app.post("/api/presentation/start")
@app.post("/presremote/api/presentation/start")
def start_presentation_api(payload: Optional[PresentationStartPayload] = None):
    idx = payload.slide_index if payload else 0
    state = dm.start_presentation_mode(idx)
    return {"status": "success", "state": state}

@app.post("/api/slideshow/presentation/stop")
@app.post("/api/presentation/stop")
@app.post("/presremote/api/presentation/stop")
def stop_presentation_api():
    state = dm.stop_presentation_mode()
    return {"status": "success", "state": state}

@app.post("/api/slideshow/presentation/step")
@app.post("/api/presentation/step")
@app.post("/presremote/api/presentation/step")
def step_presentation_api(payload: PresentationStepPayload):
    state = dm.step_presentation_slide(payload.delta)
    return {"status": "success", "state": state}

@app.post("/api/slideshow/presentation/set_index")
@app.post("/api/presentation/set_index")
@app.post("/api/presentation/index")
@app.post("/presremote/api/presentation/set_index")
@app.post("/presremote/api/presentation/index")
def set_presentation_index_api(payload: PresentationSetIndexPayload):
    state = dm.set_presentation_slide_index(payload.index)
    return {"status": "success", "state": state}

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PRESREMOTE_PORT)
