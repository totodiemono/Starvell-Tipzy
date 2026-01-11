import aiohttp
from aiohttp import ClientResponseError
from StarvellAPI.next_data import get_build_id, reset_build_id

def extract_review_from_order_data(order_data: dict) -> dict | None:
    if not order_data:
        return None
    
    try:
        page_props = order_data.get("pageProps", {})
        
        review = page_props.get("review")
        order_obj = page_props.get("order") or page_props.get("orderData") or {}
        
        if not review:
            if order_obj:
                review = order_obj.get("review")
        
        if not review:
            return None
        
        if not isinstance(review, dict):
            return None
        
        stars = review.get("rating")
        if not isinstance(stars, int) or stars < 1 or stars > 5:
            return None
        
        text = review.get("content") or ""
        
        author = None
        author_id = review.get("authorId")
        author_obj = review.get("author")
        if author_obj and isinstance(author_obj, dict):
            author = author_obj.get("username") or str(author_obj.get("id", ""))
            if not author_id:
                author_id = author_obj.get("id")
        
        created_at = review.get("createdAt")
        order_id = review.get("orderId")
        
        order_info = review.get("order", {})
        offer_details = order_info.get("offerDetails", {})
        game_info = offer_details.get("game", {})
        game_name = game_info.get("name", "")
        amount = order_info.get("amount", 0)
        
        chat_id = order_obj.get("chatId") or order_obj.get("chat_id")
        buyer_id = author_id
        
        return {
            "stars": stars,
            "text": text,
            "author": author,
            "author_id": author_id,
            "buyer_id": buyer_id,
            "chat_id": chat_id,
            "created_at": created_at,
            "review_id": review.get("id"),
            "is_hidden": review.get("isHidden", False),
            "recipient_id": review.get("recipientId"),
            "order_id": order_id,
            "game_name": game_name,
            "amount": amount,
            "delivery_speed_rating": review.get("deliverySpeedRating"),
            "response_speed_rating": review.get("responseSpeedRating")
        }
    except Exception:
        return None

async def get_order_review(session_cookie: str, order_id: str, sid_cookie: str | None = None) -> dict:
    headers = {
        'accept': '*/*',
        'accept-language': 'ru,en;q=0.9',
        'referer': f'https://starvell.com/order/{order_id}',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 YaBrowser/25.8.0.0 Safari/537.36',
        'x-nextjs-data': '1'
    }
    cookies = {
        'session': session_cookie,
        'starvell.theme': 'dark',
        'starvell.time_zone': 'Europe/Moscow',
        'starvell.my_games': '1,10,11'
    }
    if sid_cookie:
        cookies['sid'] = sid_cookie
    
    timeout = aiohttp.ClientTimeout(total=20)
    last_exc = None
    
    for attempt in range(2):
        build_id = await get_build_id(session_cookie)
        url = f'https://starvell.com/_next/data/{build_id}/order/{order_id}.json?order_id={order_id}'
        
        async with aiohttp.ClientSession(headers=headers, cookies=cookies, timeout=timeout) as session:
            try:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    return await resp.json()
            except ClientResponseError as exc:
                last_exc = exc
                if exc.status == 404 and attempt == 0:
                    reset_build_id()
                    continue
                raise
    
    if last_exc:
        raise last_exc
    raise RuntimeError('Unable to fetch order review')
