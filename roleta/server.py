import asyncio
import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent

app = FastAPI()

# Store connected browser sessions
connected_clients = set()
tiktok_client = None

@app.get("/")
async def get_index():
    return FileResponse("roleta/index.html")

async def connect_tiktok(username: str, websocket: WebSocket):
    global tiktok_client
    if tiktok_client:
        try: await tiktok_client.disconnect()
        except: pass

    print(f"🔄 Connecting to TikTok: @{username}")
    tiktok_client = TikTokLiveClient(unique_id=f"@{username}")

    @tiktok_client.on(CommentEvent)
    async def on_comment(event: CommentEvent):
        comment = event.comment.strip()
        
        # Check for commands
        if comment.lower().startswith("!notify "):
            name = comment[8:].strip()
            if name:
                for client in connected_clients.copy():
                    try:
                        await client.send_text(json.dumps({"action": "add_name", "name": name}))
                    except: pass
                    
        elif comment.lower().startswith("!present "):
            name = comment[9:].strip()
            if name:
                for client in connected_clients.copy():
                    try:
                        await client.send_text(json.dumps({"action": "add_winner", "name": name}))
                    except: pass

    await websocket.send_text(json.dumps({"status": "connecting"}))
    try:
        # 15 second timeout for connection
        await asyncio.wait_for(tiktok_client.connect(), timeout=15.0)
        await websocket.send_text(json.dumps({"status": "connected"}))
        print("✅ Successfully connected!")
    except Exception as e:
        await websocket.send_text(json.dumps({"status": "error", "message": str(e)}))
        print(f"❌ Error: {e}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg["action"] == "connect_tiktok":
                # Run in a background task to avoid blocking
                asyncio.create_task(connect_tiktok(msg["username"], websocket))
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
