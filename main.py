import asyncio
import json
import os
import uvicorn
from fastapi import FastAPI, WebSocket
from collections import deque
import websockets

app = FastAPI()

# Configuration (Use environment variables on Render)
APP_ID = os.getenv("APP_ID", "YOUR_APP_ID")
API_TOKEN = os.getenv("API_TOKEN", "YOUR_API_TOKEN")
SYMBOL = "R_100"
STAKE = 1.00

# State Management
ticks = deque(maxlen=20)
status_log = deque(maxlen=10)
latest_stats = {"p_even_under_5": 0, "last_digit": 0, "logs": []}

def get_last_digit(quote):
    return int(str(round(float(quote), 2))[-1])

async def place_trade(ws, contract_type):
    """Executes the trade with diagnostic error handling."""
    proposal_req = {
        "proposal": 1,
        "amount": STAKE,
        "basis": "stake",
        "contract_type": contract_type,
        "currency": "USD",
        "duration": 1,
        "duration_unit": "t",
        "symbol": SYMBOL
    }
    await ws.send(json.dumps(proposal_req))
    proposal_resp = json.loads(await ws.recv())

    if "error" in proposal_resp:
        log = f"TRADE FAILED: {proposal_resp['error']['message']}"
        status_log.append(log)
        print(log)
        return

    # Execute Buy
    buy_req = {"buy": proposal_resp["proposal"]["id"], "price": proposal_resp["proposal"]["ask_price"]}
    await ws.send(json.dumps(buy_req))
    buy_resp = json.loads(await ws.recv())
    
    if "buy" in buy_resp:
        log = f"TRADE SUCCESS: ID {buy_resp['buy']['contract_id']}"
    else:
        log = f"TRADE FAILED: {buy_resp}"
    
    status_log.append(log)
    print(log)

async def deriv_bot():
    url = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
    while True:
        try:
            async with websockets.connect(url) as ws:
                await ws.send(json.dumps({"authorize": API_TOKEN}))
                await ws.recv()
                await ws.send(json.dumps({"ticks": SYMBOL, "subscribe": 1}))
                
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("msg_type") == "tick":
                        digit = get_last_digit(msg["tick"]["quote"])
                        ticks.append(digit)
                        
                        if len(ticks) == 20:
                            p_val = sum(1 for d in ticks if d in [0, 2, 4]) / 20
                            latest_stats.update({"p_even_under_5": p_val, "last_digit": digit})

                            if p_val > 0.60:
                                status_log.append(f"SIGNAL DETECTED: P={p_val:.2f}")
                                await place_trade(ws, "DIGITUNDER")
                                ticks.clear() # Prevent immediate re-trigger
        except Exception as e:
            print(f"Connection error: {e}. Retrying...")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(deriv_bot())

@app.websocket("/ws/monitor")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        await websocket.send_json({**latest_stats, "logs": list(status_log)})
        await asyncio.sleep(0.5)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
