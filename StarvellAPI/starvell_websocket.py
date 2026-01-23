import asyncio

class WebSocketClient:
    def __init__(self):
        self.connected = False
    
    async def connect(self):
        self.connected = True
    
    async def disconnect(self):
        self.connected = False

websocket_client = WebSocketClient()

async def start_websocket():
    await websocket_client.connect()
    return websocket_client

def get_websocket():
    return websocket_client