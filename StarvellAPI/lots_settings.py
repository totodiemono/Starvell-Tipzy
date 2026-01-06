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

async def get_lot_info(session_cookie: str, offer_id: int) -> dict:
    headers = {'accept': 'application/json', 'accept-language': 'ru,en;q=0.9', 'referer': 'https://starvell.com/account/sells', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'x-nextjs-data': '1'}
    cookies = {'session': session_cookie, 'starvell.theme': 'dark', 'starvell.time_zone': 'Europe/Moscow', 'starvell.my_games': '1,10,11'}
    url = f'https://starvell.com/api/offers/{offer_id}'
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(headers=headers, cookies=cookies, timeout=timeout) as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {'success': True, 'data': data}
                else:
                    error_text = await resp.text()
                    return {'success': False, 'error': f'HTTP {resp.status}: {error_text[:200]}', 'status': resp.status}
        except ClientResponseError as exc:
            return {'success': False, 'error': f'HTTP {exc.status}', 'status': exc.status}
        except Exception as e:
            return {'success': False, 'error': str(e)}

async def update_lot_settings(session_cookie: str, offer_id: int, availability: int = None, is_active: bool = None, price: int = None):
    if is_active is not None and (availability is None or price is None):
        lot_info = await get_lot_info(session_cookie, offer_id)
        if lot_info.get('success'):
            lot_data = lot_info.get('data', {})
            if availability is None:
                availability = lot_data.get('availability') or lot_data.get('quantity') or lot_data.get('stock') or 1
            if price is None:
                price_value = lot_data.get('price') or lot_data.get('priceAmount') or lot_data.get('priceRub') or 0
                if isinstance(price_value, (int, float)):
                    price = int(price_value)
                elif isinstance(price_value, str):
                    try:
                        price = int(float(price_value))
                    except:
                        price = 0
        else:
            return {'success': False, 'error': f'Не удалось получить данные лота: {lot_info.get("error", "Неизвестная ошибка")}'}
    
    headers = {'accept': '*/*', 'accept-language': 'ru,en;q=0.9', 'referer': 'https://starvell.com/account/sells', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'x-nextjs-data': '1', 'content-type': 'application/json'}
    cookies = {'session': session_cookie, 'starvell.theme': 'dark', 'starvell.time_zone': 'Europe/Moscow', 'starvell.my_games': '1,10,11'}
    
    json_data = {}
    if availability is not None:
        json_data['availability'] = int(availability)
    if is_active is not None:
        json_data['isActive'] = bool(is_active)
    if price is not None:
        json_data['price'] = str(int(price))
    
    if not json_data:
        return {'success': False, 'error': 'No parameters provided'}
    
    url = f'https://starvell.com/api/offers/{offer_id}/partial-update'
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(headers=headers, cookies=cookies, timeout=timeout) as session:
        for attempt in range(2):
            try:
                async with session.post(url, json=json_data) as resp:
                    if resp.status == 200:
                        try:
                            data = await resp.json()
                            return {'success': True, 'data': data}
                        except:
                            return {'success': True, 'data': {}}
                    else:
                        error_text = await resp.text()
                        return {'success': False, 'error': f'HTTP {resp.status}: {error_text[:500]}', 'status': resp.status}
            except ClientResponseError as exc:
                if exc.status == 404 and attempt == 0:
                    continue
                try:
                    error_text = await exc.response.text() if hasattr(exc, 'response') else str(exc)
                    return {'success': False, 'error': f'HTTP {exc.status}: {error_text[:500]}', 'status': exc.status}
                except:
                    return {'success': False, 'error': f'HTTP {exc.status}', 'status': exc.status}
            except Exception as e:
                return {'success': False, 'error': str(e)}