import asyncio
import aiohttp
import json
import logging
from config import log_info, log_error, get_session

logger = logging.getLogger(__name__)

class StarvellWebSocket:
    def __init__(self):
        self.ws = None
        self.connected = False
        self.session = None
    
    async def connect_direct(self):
        try:
            
            session_token = get_session()
            if not session_token:
                log_error("❌ Нет session токена")
                return False
            
            self.session = aiohttp.ClientSession(
                cookies={'session': session_token},
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Origin': 'https://starvell.com'
                }
            )
            
            self.ws = await self.session.ws_connect(
                'wss://starvell.com/socket.io/?EIO=4&transport=websocket',
                heartbeat=30,
                receive_timeout=30
            )
            
            self.connected = True
            log_info("✅ WebSocket подключен!")
            
            asyncio.create_task(self.listen())
            return True
            
        except Exception as e:
            log_error(f"❌ Ошибка: {type(e).__name__}: {str(e)}")
            return False
    
    async def connect_with_handshake(self):
        try:
            
            session_token = get_session()
            if not session_token:
                return False
            
            session = aiohttp.ClientSession(
                cookies={'session': session_token}
            )
            
            async with session.get(
                'https://starvell.com/socket.io/',
                params={'EIO': '4', 'transport': 'polling'}
            ) as resp:
                data = await resp.text()
                if data.startswith('0'):
                    sid_data = json.loads(data[1:])
                    sid = sid_data.get('sid')
                    log_info(f"📡 Получил SID: {sid}")
                    
                    ws_url = f'wss://starvell.com/socket.io/?EIO=4&transport=websocket&sid={sid}'
                    self.ws = await session.ws_connect(ws_url)
                    
                    self.connected = True
                    self.session = session
                    
                    asyncio.create_task(self.listen())
                    return True
            
            return False
            
        except Exception as e:
            log_error(f"❌ Ошибка handshake: {e}")
            return False
    
    async def listen(self):
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    log_info(f"📥 Получил: {msg.data[:200]}")
                    if msg.data.startswith('0'):
                        log_info("🔗 Socket.IO подключен")
                    elif msg.data.startswith('2'):
                        await self.ws.send_str('3' + msg.data[1:])
                    elif msg.data.startswith('4'):
                        try:
                            event_data = json.loads(msg.data[1:])
                            log_info(f"🎯 Событие: {event_data}")
                        except:
                            pass
                            
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log_error(f"WebSocket ошибка: {self.ws.exception()}")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    log_info("Соединение закрыто")
                    break
                    
        except Exception as e:
            log_error(f"Ошибка прослушки: {e}")
        finally:
            self.connected = False
    
    async def send(self, message):
        if self.connected and self.ws:
            await self.ws.send_str(message)
    
    async def disconnect(self):
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()
        self.connected = False

websocket_client = None

async def start_websocket():
    global websocket_client
    
    websocket_client = StarvellWebSocket()
    
    methods = [
        ('direct', websocket_client.connect_direct),
        ('handshake', websocket_client.connect_with_handshake)
    ]
    
    for method_name, method in methods:
        log_info(f"🔄 Пробую метод: {method_name}")
        success = await method()
        if success:
            log_info(f"✅ Метод {method_name} сработал!")
            return True
        await asyncio.sleep(2)
    
    log_error("❌ Все методы не сработали")
    return False

def get_websocket():
    return websocket_client

async def send_via_websocket(data):
    client = get_websocket()
    if client and client.connected:
        await client.send(data)
        return True
    return False