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
        # --- THIS IS THE FIX ---
        # Use create_task to run the connection in the background.
        # We use a wrapper function to handle the success/error messages 
        # without blocking the main FastAPI loop.
        async def run_client():
            try:
                # 15 second timeout
                await asyncio.wait_for(tiktok_client.connect(), timeout=15.0)
                await websocket.send_text(json.dumps({"status": "connected"}))
                print("✅ Successfully connected!")
            except Exception as e:
                await websocket.send_text(json.dumps({"status": "error", "message": str(e)}))
                print(f"❌ Error: {e}")

        asyncio.create_task(run_client())
        
    except Exception as e:
        await websocket.send_text(json.dumps({"status": "error", "message": str(e)}))
        print(f"❌ Setup Error: {e}")
