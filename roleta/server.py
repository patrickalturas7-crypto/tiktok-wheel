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

current_names = []
user_notified = {} 

@app.get("/")
async def get_index():
    return FileResponse("index.html") 

async def broadcast(message: dict):
    for client in connected_clients.copy():
        try:
            await client.send_text(json.dumps(message))
        except:
            pass

async def connect_tiktok(username: str, websocket: WebSocket):
    global tiktok_client, current_names, user_notified
    if tiktok_client:
        try: await tiktok_client.disconnect()
        except: pass

    print(f"🔄 Connecting to TikTok: @{username}")
    tiktok_client = TikTokLiveClient(unique_id=f"@{username}")

    @tiktok_client.on(CommentEvent)
    async def on_comment(event: CommentEvent):
        comment = event.comment.strip()
        tiktok_user = event.user.unique_id.lower() if event.user else "unknown"
        
        if comment.lower().startswith("!notify "):
            name = comment[8:].strip()
            
            if tiktok_user in user_notified:
                return

            if name and name.lower() not in [n.lower() for n in current_names]:
                current_names.append(name)
                user_notified[tiktok_user] = name 
                
                await broadcast({"action": "show_notification", "name": name})
                await broadcast({"action": "add_name", "name": name})
                    
        elif comment.lower().startswith("!present "):
            name = comment[9:].strip()
            if name:
                await broadcast({"action": "add_winner", "name": name})

    await websocket.send_text(json.dumps({"status": "connecting"}))
    
    try:
        async def run_client():
            try:
                await tiktok_client.start()
                await broadcast({"status": "connected"})
            except Exception as e:
                await websocket.send_text(json.dumps({"status": "error", "message": str(e)}))

        asyncio.create_task(run_client())
        
    except Exception as e:
        await websocket.send_text(json.dumps({"status": "error", "message": str(e)}))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global current_names, user_notified
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            if msg.get("action") == "connect_tiktok":
                username = msg.get("username")
                asyncio.create_task(connect_tiktok(username, websocket))
            elif msg.get("action") == "clear_all":
                current_names = []
                user_notified = {}
                
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
