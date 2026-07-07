from fastapi import FastAPI, Request
from pydantic import BaseModel
import sys
import logging
import asyncio

# Setup logging to stream to stdout/stderr so the Master Admin can capture it
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# Dummy in-memory state
game_state = {
    "status": "IDLE",
    "wagers": {},
    "temporary_spreadsheet": []
}

class ResetPayload(BaseModel):
    action: str
    timestamp: int
    target_state: str

@app.on_event("startup")
async def startup_event():
    logger.info("Dummy Game Server started.")
    # Example background task
    asyncio.create_task(background_loop())

async def background_loop():
    while True:
        # Simulate some activity to generate logs
        if game_state["status"] != "IDLE":
            logger.info(f"Game loop tick. State: {game_state['status']}")
        await asyncio.sleep(5)

@app.get("/")
def read_root():
    return {"message": "Dummy Game Module Running"}

@app.get("/state")
def get_state():
    return game_state

@app.post("/api/local/reset")
def reset_state(payload: ResetPayload):
    global game_state
    if payload.action == "GLOBAL_RESET":
        logger.info(f"Received GLOBAL_RESET payload at {payload.timestamp}. Resetting to {payload.target_state}.")
        game_state = {
            "status": payload.target_state,
            "wagers": {},
            "temporary_spreadsheet": []
        }
        return {"status": "success", "message": "State reset successfully."}
    return {"status": "ignored"}

@app.post("/simulate_crash")
def simulate_crash():
    logger.error("Simulating a critical crash!")
    # Intentional unhandled exception
    raise Exception("Simulated unhandled exception for testing fault containment!")

@app.post("/simulate_wager")
def simulate_wager(player_id: str, amount: int):
    game_state["wagers"][player_id] = amount
    game_state["status"] = "BETTING_OPEN"
    logger.info(f"Wager added for {player_id}: {amount}")
    return {"status": "success", "wagers": game_state["wagers"]}
