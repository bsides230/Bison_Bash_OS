from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import time
from pathlib import Path
import os
import uvicorn

from master_admin.data_manager import read_data, write_data, PLAYERS_FILE

# Ensure static directories exist
STATIC_DIR = Path("master_admin/static")
(STATIC_DIR / "css").mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "js").mkdir(parents=True, exist_ok=True)

app = FastAPI()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="master_admin/static"), name="static")
templates = Jinja2Templates(directory=".")

# Payload Models
class InjectTokensPayload(BaseModel):
    player_id: str
    amount: int

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="master_admin/templates/dashboard.html")

@app.post("/api/admin/inject-tokens")
def inject_tokens(payload: InjectTokensPayload):
    # This demonstrates Data Redundancy loop
    players_data = read_data(PLAYERS_FILE)

    if payload.player_id not in players_data["players"]:
        players_data["players"][payload.player_id] = {"balance": 0}

    players_data["players"][payload.player_id]["balance"] += payload.amount

    # write_data handles the atomic write + incremental backup loop
    write_data(PLAYERS_FILE, players_data)

    return {"status": "success", "new_balance": players_data["players"][payload.player_id]["balance"]}

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
