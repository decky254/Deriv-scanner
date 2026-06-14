import asyncio
import json
import os
import uvicorn
from fastapi import FastAPI, WebSocket
from collections import deque
import websockets

app = FastAPI()

# Configuration using Environment Variables
APP_ID = os.getenv("APP_ID", "YOUR_APP_ID")
API_TOKEN = os.getenv("API_TOKEN", "YOUR_API_TOKEN")
SYMBOL = "R_100"
STAKE = 1.00

# State
ticks = deque(maxlen=20)
latest_stats = {"p_even_under_5": 0, "last_digit": 0}

def get_last_digit(quote):
    return int(str(round(float(quote), 2))[-1])

async def deriv_bot():
    url = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
    
    while True: # Infinite reconnection loop
        try:
            async with websockets.connect(url) as ws:
                # Authorize
                await ws.send(json.dumps({"authorize": API_TOKEN}))
                await ws.recv()
                
                # Subscribe
                await ws.send(json.dumps({"ticks": SYMBOL, "subscribe": 1}))
                print("Connected to Deriv WebSocket")
                
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("msg_type") == "tick":
                        digit = get_last_digit(msg["tick"]["quote"])
                        ticks.append(digit)
                        
                        if len(ticks) == 20:
                            n = len(ticks)
                            even_under_5 = sum(1 for d in ticks if d in [0, 2, 4])
                            p_val = even_under_5 / n
                            
                            latest_stats.update({"p_even_under_5": p_val, "last_digit": digit})

                            # Signal trigger
                            if p_val > 0.60:
                                print(f"Signal: {p_val:.2f}. Logic placeholder.")
                                # await place_trade(ws, "DIGITUNDER")
                                ticks.clear()
        
        except Exception as e:
            print(f"Connection error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(deriv_bot())

@app.websocket("/ws/monitor")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        await websocket.send_json(latest_stats)
        await asyncio.sleep(0.5)

if __name__ == "__main__":
    # Render uses the PORT environment variable
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
