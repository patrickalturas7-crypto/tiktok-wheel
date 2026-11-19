import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent

app = FastAPI()
app.mount("/static", StaticFiles(directory="."), name="static")

connected_clients = set()
tiktok_client = None

@app.get("/")
async def get_index():
    return FileResponse("index.html") 

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
        
        if comment.lower().startswith("!notify "):
            name = comment[8:].strip()
            if name:
                for client in connected_clients.copy():
                    try:
                        # 1. Show the big purple notification
                        await client.send_text(json.dumps({"action": "show_notification", "name": name}))
                        # 2. Also add the name to the wheel (if not already there)
                        await client.send_text(json.dumps({"action": "add_name", "name": name}))
                    except: pass
                    
        elif comment.lower().startswith("!present "):
            name = comment[9:].strip()
            if name:
                # This one STILL adds the winner
                for client in connected_clients.copy():
                    try:
                        await client.send_text(json.dumps({"action": "add_winner", "name": name}))
                    except: pass

    await websocket.send_text(json.dumps({"status": "connecting"}))
    
    try:
        async def run_client():
            try:
                await tiktok_client.start()
                await websocket.send_text(json.dumps({"status": "connected"}))
                print("✅ Successfully connected!")
            except Exception as e:
                await websocket.send_text(json.dumps({"status": "error", "message": str(e)}))
                print(f"❌ Error: {e}")

        asyncio.create_task(run_client())
        
    except Exception as e:
        await websocket.send_text(json.dumps({"status": "error", "message": str(e)}))
        print(f"❌ Setup Error: {e}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("action") == "connect_tiktok":
                username = msg.get("username")
                asyncio.create_task(connect_tiktok(username, websocket))
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        print("🔌 Client disconnected")
