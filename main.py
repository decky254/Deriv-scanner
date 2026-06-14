import asyncio
import json
import uvicorn
from fastapi import FastAPI, WebSocket
from collections import deque
import websockets

app = FastAPI()

# Configuration
APP_ID = "YOUR_APP_ID"
API_TOKEN = "YOUR_API_TOKEN"
SYMBOL = "R_100"
STAKE = 1.00
ticks = deque(maxlen=20)
latest_stats = {"p_even_under_5": 0, "last_digit": 0}

def get_last_digit(quote):
    return int(str(round(float(quote), 2))[-1])

# --- Trading Logic ---
async def deriv_bot():
    url = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"authorize": API_TOKEN}))
        await ws.recv()
        await ws.send(json.dumps({"ticks": SYMBOL, "subscribe": 1}))
        
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("msg_type") == "tick":
                digit = get_last_digit(msg["tick"]["quote"])
                ticks.append(digit)
                
                # Calculate stats
                n = len(ticks)
                even_under_5 = sum(1 for d in ticks if d in [0, 2, 4])
                p_val = even_under_5 / n
                
                # Update global state for the frontend
                latest_stats.update({"p_even_under_5": p_val, "last_digit": digit})

                # Signal Execution
                if p_val > 0.60:
                    print("Signal Detected! Executing...")
                    # Add place_trade logic here
                    ticks.clear() 

# --- FastAPI Bridge ---
@app.websocket("/ws/monitor")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        await websocket.send_json(latest_stats)
        await asyncio.sleep(0.5)

# --- Startup ---
@app.on_event("startup")
def startup_event():
    asyncio.create_task(deriv_bot())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
