import os
file_path = "f:/Food Donation Platform/backend/app/main.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

import re

# Remove ConnectionManager
content = re.sub(
    r"class ConnectionManager:.*?manager = ConnectionManager\(\)",
    "from app.services import websocket_service",
    content,
    flags=re.DOTALL
)

# Update websocket_endpoint
content = re.sub(
    r"@app\.websocket\(\"/ws\"\)\s*async def websocket_endpoint\(websocket: WebSocket\):\s*await manager\.connect\(websocket\)\s*try:\s*while True:\s*data = await websocket\.receive_text\(\)\s*# In a full implementation, we can do selective pushes here.\s*except WebSocketDisconnect:\s*manager\.disconnect\(websocket\)",
    """@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_service.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_service.disconnect(websocket)""",
    content,
    flags=re.DOTALL
)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("done")
