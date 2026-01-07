from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from logging import getLogger
import requests
import json
import os
import time
import asyncio
from config import log_info, log_error

logger = getLogger("announcements")

REQUESTS_DELAY = 600
LAST_TAG = None
GIST_ID = "6575075024b2ec41159baf7f145c4be7"

def get_last_tag() -> str | None:
    cache_file = "config/cache/announcement_tag.txt"
    if not os.path.exists(cache_file):
        return None
    try:
        with open(cache_file, "r", encoding="UTF-8") as f:
            data = f.read()
        return data
    except:
        return None

LAST_TAG = get_last_tag()

def save_last_tag():
    global LAST_TAG
    cache_dir = "config/cache"
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    cache_file = os.path.join(cache_dir, "announcement_tag.txt")
    try:
        with open(cache_file, "w", encoding="UTF-8") as f:
            f.write(LAST_TAG)
    except:
        pass

def get_announcement(ignore_last_tag: bool = False) -> dict | None:
    global LAST_TAG
    headers = {
        'X-GitHub-Api-Version': '2022-11-28',
        'accept': 'application/vnd.github+json'
    }
    try:
        response = requests.get(f"https://api.github.com/gists/{GIST_ID}", headers=headers, timeout=10)
        if not response.status_code == 200:
            return None

        files = response.json().get("files", {})
        if not files:
            return None
        
        file_content = None
        for file_name, file_data in files.items():
            if file_name.endswith('.json') or file_name.endswith('.txt'):
                file_content = file_data.get("content")
                break
        
        if not file_content:
            return None
            
        content = json.loads(file_content)
        if content.get("tag") == LAST_TAG and not ignore_last_tag:
            return None
        return content
    except:
        return None

def download_photo(url: str) -> bytes | None:
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None
    except:
        return None
    return response.content

def get_notification_type(data: dict) -> str:
    types = {
        0: "ad",
        1: "announcement",
        2: "important_announcement"
    }
    return types.get(data.get("type"), "critical")

def get_photo(data: dict) -> bytes | None:
    if not (photo := data.get("ph")):
        return None
    return download_photo(str(photo))

def get_text(data: dict) -> str | None:
    if not (text := data.get("text")):
        return None
    return str(text)

def get_pin(data: dict) -> bool:
    return bool(data.get("pin"))

def get_keyboard(data: dict):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    if not (kb_data := data.get("kb")):
        return None

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    try:
        keyboard_rows = []
        for row in kb_data:
            buttons = []
            for btn in row:
                btn_text = btn.get("text", "")
                btn_url = btn.get("url", "")
                if btn_text and btn_url:
                    buttons.append(InlineKeyboardButton(text=btn_text, url=btn_url))
            if buttons:
                keyboard_rows.append(buttons)
        if keyboard_rows:
            kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    except:
        return None
    return kb

async def send_notification(bot_instance, text: str | None, photo: bytes | None = None, keyboard = None, pin: bool = False):
    from bot import load_authorized_users
    
    if not bot_instance:
        return
    
    authorized_users = load_authorized_users()
    if not authorized_users:
        return
    
    to_delete = []
    for user_id in authorized_users:
        try:
            user_id_int = int(user_id)
            if photo:
                msg = await bot_instance.send_photo(user_id_int, photo, text, reply_markup=keyboard)
            else:
                msg = await bot_instance.send_message(user_id_int, text, reply_markup=keyboard)
            
            if pin:
                try:
                    await bot_instance.pin_chat_message(user_id_int, msg.message_id)
                except:
                    pass
        except Exception as e:
            error_str = str(e).lower()
            if "chat not found" in error_str or "user is deactivated" in error_str or "blocked" in error_str:
                to_delete.append(user_id)
            continue
    
    if to_delete:
        from bot import save_authorized_users
        authorized = load_authorized_users()
        for uid in to_delete:
            authorized.discard(uid)
        save_authorized_users(authorized)

def announcements_loop_iteration(bot_instance, ignore_last_tag: bool = False):
    global LAST_TAG
    if not (data := get_announcement(ignore_last_tag=ignore_last_tag)):
        return

    elif not LAST_TAG:
        LAST_TAG = data.get("tag")
        save_last_tag()
        return

    if not ignore_last_tag:
        LAST_TAG = data.get("tag")
        save_last_tag()
    text = get_text(data)
    photo = get_photo(data)
    keyboard = get_keyboard(data)
    pin = get_pin(data)

    if text or photo:
        asyncio.create_task(send_notification(bot_instance, text, photo, keyboard, pin))

async def announcements_loop(bot_instance):
    if not bot_instance:
        return

    while True:
        try:
            announcements_loop_iteration(bot_instance, ignore_last_tag=False)
        except:
            pass
        await asyncio.sleep(REQUESTS_DELAY)
