import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent

# 1. Initialize FastAPI (This creates the 'app' variable Render is looking for)
app = FastAPI()

# Store connected browser sessions
connected_clients = set()
tiktok_client = None

@app.get("/")
async def get_index():
    # Make sure this path matches your Render Root Directory settings.
    # If Root Directory is 'roleta', use "index.html". 
    # If Root Directory is blank, use "roleta/index.html".
    return FileResponse("index.html") 

async def connect_tiktok(username: str, websocket: WebSocket):
    global tiktok_client
    if tiktok_client:
        try: 
            await tiktok_client.disconnect()
        except: 
            pass

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
                    except: 
                        pass
                    
        elif comment.lower().startswith("!present "):
            name = comment[9:].strip()
            if name:
                for client in connected_clients.copy():
                    try:
                        await client.send_text(json.dumps({"action": "add_winner", "name": name}))
                    except: 
                        pass

    await websocket.send_text(json.dumps({"status": "connecting"}))
    
    try:
        # --- THE FIX ---
        # Use .start() instead of .connect(). 
        # .start() is non-blocking and integrates with the existing FastAPI event loop.
        # We wrap it in a background task so the WebSocket doesn't hang waiting for the stream to end.
        
        async def run_client():
            try:
                # We must await start() first to schedule the connection
                await tiktok_client.start()
                await websocket.send_text(json.dumps({"status": "connected"}))
                print("✅ Successfully connected!")
            except Exception as e:
                # Check if the error is just a timeout or an actual failure
                await websocket.send_text(json.dumps({"status": "error", "message": str(e)}))
                print(f"❌ Error: {e}")

        # Run the start() method in the background
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
