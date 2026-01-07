import json
import aiohttp

def load_settings() -> dict:
    try:
        with open("config/settings.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, FileNotFoundError):
        return {}

def get_settings() -> dict:
    return load_settings()

async def send_chat_message(session_cookie: str, chat_id: str, content: str, chat_name: str=None) -> dict:
    settings = get_settings()
    global_switches = settings.get("global_switches", {})

    watermark_text_text = global_switches.get("watermark", "[ Не указан ;/ ]")
    watermark_enabled = global_switches.get("watermark_enabled", True)

    content_watermark = (watermark_text_text + "\n\n" + content) if watermark_enabled else content

    headers = {'accept': '*/*', 'accept-language': 'ru,en;q=0.9', 'content-type': 'application/json', 'origin': 'https://starvell.com', 'referer': f'https://starvell.com/chat/{chat_id}', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 YaBrowser/25.8.0.0 Safari/537.36'}
    cookies = {'session': session_cookie, 'starvell.theme': 'dark', 'starvell.time_zone': 'Europe/Moscow', 'starvell.my_games': '10,1,11'}
    payload = {'chatId': chat_id, 'content': content_watermark}
    url = 'https://starvell.com/api/messages/send'
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(headers=headers, cookies=cookies, timeout=timeout) as session:
        async with session.post(url, json=payload) as resp:
            response_text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f'HTTP {resp.status}: {response_text}')
            try:
                result = json.loads(response_text)
                try:
                    from config import log_info
                    from StarvellAPI.auth import fetch_homepage_data
                    homepage_data = await fetch_homepage_data(session_cookie)
                    if homepage_data.get('authorized'):
                        user_info = homepage_data.get('user', {})
                        starvell_username = user_info.get('username', 'Неизвестно')
                    else:
                        starvell_username = 'Неизвестно'
                    display_chat_name = chat_name if chat_name else chat_id
                    log_info(f'┌── 📤 Исходящее сообщение в чате {display_chat_name}')
                    log_info(f'└───> {starvell_username}: {content}')
                except Exception:
                    pass
                try:
                    from bot import register_bot_message
                    if result and isinstance(result, dict) and result.get('id'):
                        await register_bot_message(chat_id, str(result['id']))
                except Exception:
                    pass
                return result
            except json.JSONDecodeError as exc:
                raise RuntimeError('Invalid response from server') from exc
