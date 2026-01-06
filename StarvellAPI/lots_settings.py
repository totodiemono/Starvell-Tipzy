import aiohttp
from aiohttp import ClientResponseError

async def lot_setting(session_cookie: str, is_active: int, quality: int, price: int, offer_id: int):
    headers = {'accept': '*/*', 'accept-language': 'ru,en;q=0.9', 'referer': 'https://starvell.com/account/sells', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'x-nextjs-data': '1'}
    cookies = {'session': session_cookie, 'starvell.theme': 'dark', 'starvell.time_zone': 'Europe/Moscow', 'starvell.my_games': '1,10,11'}
    json_lot = {'availability': quality, 'isActive': is_active, 'price': str(price)}
    url = f'https://starvell.com/api/offers/{offer_id}/partial-update'
    async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
        for attempt in range(2):
            try:
                async with session.post(url, json=json_lot) as resp:
                    resp.raise_for_status()
                    return await resp.json()
            except ClientResponseError as exc:
                if exc.status == 404 and attempt == 0:
                    continue
                raise