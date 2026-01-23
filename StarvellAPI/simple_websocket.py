import asyncio
import websockets
import json
import logging
from config import log_info, log_error, get_session

logger = logging.getLogger(__name__)

class SimpleWebSocket:
    def __init__(self):
        self.connection = None
        self.connected = False
        self.session = get_session()
    
    async def connect(self):
        try:
            urls = [
                'wss://starvell.com/socket.io/?EIO=4&transport=websocket',
                'wss://starvell.com/socket.io/',
                'wss://starvell.com/ws',
                'ws://starvell.com/socket.io/'
            ]
            
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Origin': 'https://starvell.com'
            }
            
            if self.session:
                headers['Cookie'] = f'session={self.session}'
            
            for url in urls:
                try:
                    log_info(f"🔗 Пробую {url}")
                    self.connection = await websockets.connect(
                        url,
                        extra_headers=headers,
                        ping_interval=20,
                        ping_timeout=20
                    )
                    
                    self.connected = True
                    log_info(f"✅ Подключился к {url}")
                    
                    asyncio.create_task(self.listen())
                    return True
                    
                except Exception as e:
                    log_error(f"❌ Не удалось {url}: {e}")
                    continue
            
            return False
            
        except Exception as e:
            log_error(f"💥 Общая ошибка: {e}")
            return False
    
    async def listen(self):
        try:
            async for message in self.connection:
                log_info(f"📥 Получил: {message[:200]}...")
                
                if message.startswith('0'):
                    await self.send('0')
                elif message.startswith('2'): 
                    await self.send('3')
                elif message.startswith('4'):
                    if len(message) > 1:
                        try:
                            data = json.loads(message[1:])
                            log_info(f"📨 Сообщение: {data}")
                        except:
                            log_info(f"📨 Raw: {message[1:]}")
        except Exception as e:
            log_error(f"❌ Ошибка слушателя: {e}")
            self.connected = False
    
    async def send(self, message):
        if self.connected and self.connection:
            await self.connection.send(message)
            log_info(f"📤 Отправил: {message[:50]}...")
    
    async def disconnect(self):
        if self.connection:
            await self.connection.close()
            self.connected = False

simple_ws = None

async def start_simple_websocket():
    global simple_ws
    
    await asyncio.sleep(3)
    
    simple_ws = SimpleWebSocket()
    connected = await simple_ws.connect()
    
    if connected:
        return True
    else:
        return False