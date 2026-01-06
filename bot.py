import asyncio
import logging
import math
import os
import re
import sys
import time
import html
from pathlib import Path
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile, LinkPreviewOptions

from config import set_bot_token, get_bot_token_cached, DATA_FILE, AUTHORIZED_USERS_FILE, CONFIG_DIR, Colors
from StarvellAPI.auth import fetch_homepage_data
from main import plugin_manager, GH as GITHUB
from version import VERSION
from Utils.updater import download_and_extract_latest_release
from colorama import Fore, Style

LOGO = """
                              ████████                                                              
                             ███████████                                                            
                            ███████████████                     ██████████                          
                            █████████████████               ████████████████                        
                            ████████████████████        ████████████████████                        
                            ██████████████████████   ███████████████████████                        
                            ████████████████████████████████████████████████                        
                             ███████████████████████████████████████████████                        
                             ██████████████████████████████████████████████                         
                             ██████████████████████████████████████████████                         
                             █████████████████████████████████████████████                          
                             ███████████████████████████████████████████                            
                              █████████████████████████████████████████                             
                             █████████████████████████████████████████                              
                         ███████████████████████████████████████████                                
                      █████████████████████████████████████████████                                
                   ██████████████████████████████████████████████                                   
                 █████████████████████████████████████████████                                      
               ██████████████████████████████████████████████                                       
              ████████████████████████████████████████████           ██████████                     
             ██████████████████████████████████████████         ██████████████████                  
             ███████████████████████████████████████         ███████████████████████                
             ███████████████████████████████████          ███████████████████████████               
              ██████████████████████████████           ███████████████████████████████              
               █████████████████████████            ███████████████████████████████████             
                   ███████████████              ████████████████████████████████████████            
                                             ███████████████████████████████████████████            
                                           █████████████████████████████████████████████            
                                         ███████████████████████████████████████████████            
                                        ███████████████████████████████████████████████             
                                      ███████████████████████████████████████████████               
                                      ████████████████████████                                      
                                     ████████████████████████                                       
                                     ███████████████████████                                        
                                     ██████████████████████                                         
                                      ████████████████████                                          
                                      ███████████████████                                           
                                       █████████████████                                            
                                        ███████████████                                             
                                         █████████████                                              
                                          ██████████                                                
                                            ██████                                                   
"""

logging.basicConfig(level=logging.ERROR)

bot = None
bot_info = None
dp = Dispatcher(storage=MemoryStorage())

import json
from typing import Optional, Dict, Any

_bot_sent_messages = {}
_bot_sent_messages_lock = asyncio.Lock()


async def get_latest_version_from_github() -> Optional[str]:
    if not GITHUB:
        return None
    
    try:
        import aiohttp
        
        base = GITHUB.rstrip("/")
        if "github.com" not in base:
            return None
        
        raw_base = base.replace("https://github.com/", "https://raw.githubusercontent.com/")
        candidate_urls = [
            f"{raw_base}/main/version.py",
            f"{raw_base}/master/version.py",
        ]
        
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for url in candidate_urls:
                try:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            continue
                        text = await resp.text()
                        # Пробуем извлечь версию через exec (как было)
                        try:
                            ns: Dict[str, Any] = {}
                            exec(text, ns)
                            latest = ns.get("VERSION")
                            if isinstance(latest, str):
                                return latest.strip()
                        except Exception:
                            pass
                        
                        # Дополнительно пробуем извлечь версию через регулярное выражение (fallback)
                        match = re.search(r"VERSION\s*=\s*['\"]([^'\"]+)['\"]", text)
                        if match:
                            return match.group(1).strip()
                except Exception:
                    continue
    except Exception:
        return None
    
    return None

async def register_bot_message(chat_id: str, message_id: str):
    async with _bot_sent_messages_lock:
        current_time = time.time()
        if chat_id not in _bot_sent_messages:
            _bot_sent_messages[chat_id] = []
        _bot_sent_messages[chat_id].append((message_id, current_time))
        _bot_sent_messages[chat_id] = [
            (mid, ts) for mid, ts in _bot_sent_messages[chat_id]
            if current_time - ts < 300
        ]

async def is_bot_message(chat_id: str, message_id: str) -> bool:
    async with _bot_sent_messages_lock:
        if chat_id not in _bot_sent_messages:
            return False
        return any(mid == message_id for mid, _ in _bot_sent_messages[chat_id])

def load_users() -> Dict[str, Any]:
    if not DATA_FILE.exists():
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def save_users(users: Dict[str, Any]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def get_user_data(user_id: int) -> Optional[Dict[str, Any]]:
    users = load_users()
    return users.get(str(user_id))

def set_user_data(user_id: int, data: Dict[str, Any]) -> None:
    users = load_users()
    users[str(user_id)] = data
    save_users(users)

def set_user_password(user_id: int, password: str) -> None:
    user_data = get_user_data(user_id) or {}
    user_data["password"] = password
    set_user_data(user_id, user_data)

def set_user_session(user_id: int, session: str) -> None:
    user_data = get_user_data(user_id) or {}
    user_data["session"] = session
    set_user_data(user_id, user_data)

def get_user_password(user_id: int) -> Optional[str]:
    user_data = get_user_data(user_id)
    return user_data.get("password") if user_data else None

def get_user_session(user_id: int) -> Optional[str]:
    user_data = get_user_data(user_id)
    return user_data.get("session") if user_data else None

def set_bot_token_user(user_id: int, token: str) -> None:
    user_data = get_user_data(user_id) or {}
    user_data["bot_token"] = token
    set_user_data(user_id, user_data)

def get_bot_token_user(user_id: int) -> Optional[str]:
    user_data = get_user_data(user_id)
    return user_data.get("bot_token") if user_data else None

def is_configured() -> bool:
    from config import is_configured as cfg_is_configured
    return cfg_is_configured()

def is_user_configured(user_id: int) -> bool:
    user_data = get_user_data(user_id)
    if not user_data:
        return False
    return bool(user_data.get("password") and user_data.get("session"))

def get_password() -> Optional[str]:
    from config import get_password as cfg_get_password
    return cfg_get_password() or None

def get_session() -> Optional[str]:
    from config import get_session as cfg_get_session
    return cfg_get_session() or None

def set_password(password: str) -> None:
    from config import set_password as cfg_set_password
    cfg_set_password(password)

def set_session(session: str) -> None:
    from config import set_session as cfg_set_session
    cfg_set_session(session)

def _load_data() -> dict:
    """Загружает все данные из data.json"""
    if not DATA_FILE.exists():
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def _save_data(data: dict) -> None:
    """Сохраняет все данные в data.json"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_authorized_users() -> set:
    data = _load_data()
    authorized_data = data.get("authorized_users", {})
    return set(authorized_data.get("users", []))

def save_authorized_users(user_ids: set) -> None:
    data = _load_data()
    data["authorized_users"] = {"users": list(user_ids)}
    _save_data(data)

def add_authorized_user(user_id: int) -> None:
    authorized = load_authorized_users()
    authorized.add(user_id)
    save_authorized_users(authorized)

def is_user_authorized(user_id: int) -> bool:
    authorized = load_authorized_users()
    return user_id in authorized

def load_templates() -> list:
    data = _load_data()
    return data.get("templates", [])

def save_templates(templates: list) -> None:
    data = _load_data()
    data["templates"] = templates
    _save_data(data)

def add_template(text: str) -> None:
    templates = load_templates()
    templates.append(text)
    save_templates(templates)

def get_templates() -> list:
    return load_templates()

def delete_template(index: int) -> bool:
    templates = load_templates()
    if 0 <= index < len(templates):
        templates.pop(index)
        save_templates(templates)
        return True
    return False

SETTINGS_FILE = CONFIG_DIR / "settings.json"

def load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {
            "notifications": {
                "new_order": True,
                "new_message": True,
                "bot_start": True
            },
            "auto_reply": {
                "enabled": False,
                "message": ""
            },
            "welcome_message": {
                "enabled": False,
                "message": ""
            },
            "global_switches": {
                "auto_bump": False,
                "logging": True
            }
        }
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {
            "notifications": {
                "new_order": True,
                "new_message": True,
                "bot_start": True
            },
            "auto_reply": {
                "enabled": False,
                "message": ""
            },
            "welcome_message": {
                "enabled": False,
                "message": ""
            },
            "global_switches": {
                "auto_bump": False,
                "logging": True
            }
        }

def save_settings(settings: dict) -> None:
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

def get_settings() -> dict:
    return load_settings()

def update_setting(category: str, key: str, value: Any) -> None:
    settings = load_settings()
    if category not in settings:
        settings[category] = {}
    settings[category][key] = value
    save_settings(settings)

def get_setting(category: str, key: str, default: Any = None) -> Any:
    settings = load_settings()
    return settings.get(category, {}).get(key, default)

MESSAGES_LOG_FILE = CONFIG_DIR / "messages_log.json"
DATA_FILE = CONFIG_DIR / "data.json"

def load_auto_reply_commands() -> dict:
    # Автоответы теперь в settings.json
    settings = load_settings()
    return settings.get("auto_reply_commands", {"commands": {}})

def save_auto_reply_commands(commands_data: dict) -> None:
    settings = load_settings()
    settings["auto_reply_commands"] = commands_data
    save_settings(settings)

def get_auto_reply_commands_dict() -> dict:
    commands_data = load_auto_reply_commands()
    result = {}
    for raw_command, command_data in commands_data.get("commands", {}).items():
        commands = [cmd.strip().lower() for cmd in raw_command.split("|") if cmd.strip()]
        for cmd in commands:
            result[cmd] = command_data
    return result

def load_last_messages() -> dict:
    data = _load_data()
    return data.get("last_messages", {})

def save_last_messages(last_messages: dict) -> None:
    data = _load_data()
    data["last_messages"] = last_messages
    _save_data(data)

def load_processed_orders() -> set:
    """Загружает список обработанных заказов"""
    data = _load_data()
    processed_data = data.get("processed_orders", {})
    return set(processed_data.get("order_ids", []))

def save_processed_orders(order_ids: set) -> None:
    """Сохраняет список обработанных заказов"""
    data = _load_data()
    data["processed_orders"] = {"order_ids": list(order_ids)}
    _save_data(data)

def load_notification_messages() -> dict:
    data = _load_data()
    return data.get("notification_messages", {})

def save_notification_messages(notification_messages: dict) -> None:
    data = _load_data()
    data["notification_messages"] = notification_messages
    _save_data(data)

def load_welcome_sent() -> set:
    data = _load_data()
    welcome_data = data.get("welcome_sent", {})
    return set(welcome_data.get("chats", []))

def save_welcome_sent(chats: set) -> None:
    data = _load_data()
    data["welcome_sent"] = {"chats": list(chats)}
    _save_data(data)

def clear_welcome_sent() -> None:
    data = _load_data()
    data["welcome_sent"] = {"chats": []}
    _save_data(data)

def log_message(chat_id: str, message_id: str, content: str, sender: str, timestamp: str) -> None:
    log_entry = {
        "chat_id": chat_id,
        "message_id": message_id,
        "content": content,
        "sender": sender,
        "timestamp": timestamp,
        "logged_at": datetime.now().isoformat()
    }
    
    if not MESSAGES_LOG_FILE.exists():
        logs = []
    else:
        try:
            with open(MESSAGES_LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except (json.JSONDecodeError, IOError):
            logs = []
    
    logs.append(log_entry)
    
    if len(logs) > 1000:
        logs = logs[-1000:]
    
    with open(MESSAGES_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE = LOGS_DIR / "log.log"

def write_log(message: str):
    timestamp = datetime.now().strftime("[%d-%m-%Y %H:%M:%S]")
    log_entry = f"{timestamp} {message}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception:
        pass

starvell_initialized = False


class SetupStates(StatesGroup):
    checking_password = State()
    adding_template = State()
    setting_welcome_message = State()
    setting_auto_reply_message = State()
    replying_to_chat = State()
    adding_auto_reply_command = State()
    editing_auto_reply_command_response = State()
    editing_auto_reply_command_notification = State()


def is_authorized(user_id: int) -> bool:
    return is_user_authorized(user_id)


def set_authorized(user_id: int) -> None:
    add_authorized_user(user_id)


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Глобальные переключатели", callback_data="global_switches")],
            [
                InlineKeyboardButton(text="🔔 Уведомления", callback_data="notifications"),
                InlineKeyboardButton(text="🤖 Авто-ответ", callback_data="auto_reply")
            ],
            [InlineKeyboardButton(text="👋 Приветственное сообщение", callback_data="welcome")],
            [
                InlineKeyboardButton(text="🧩 Плагины", callback_data="plugins"),
                InlineKeyboardButton(text="📝 Заготовки", callback_data="templates")
            ]
        ]
    )
    return keyboard


async def show_main_menu(message: Message = None, callback: CallbackQuery = None):
    text = "Выбери категорию настроек."
    keyboard = get_main_menu_keyboard()
    
    if callback:
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except Exception:
            await callback.message.answer(text, reply_markup=keyboard)
    elif message:
        await message.answer(text, reply_markup=keyboard)


@dp.message(Command("autostars"))
async def cmd_autostars(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("Сначала авторизуйтесь через /start")
        return
    
    try:
        autostars_plugin = plugin_manager.get_plugin("4836374b-a886-43a2-a28d-8cb87bc11f49")
        if not autostars_plugin:
            await message.answer("❌ Плагин AutoStars не найден")
            return
        
        plugin_module = autostars_plugin.plugin
        
        if hasattr(plugin_module, "_init_plugin_db"):
            try:
                await plugin_module._init_plugin_db()
            except Exception:
                pass
        
        if hasattr(plugin_module, "_settings_text") and hasattr(plugin_module, "_settings_kb") and hasattr(plugin_module, "_get_config"):
            user_id = message.from_user.id
            db_path = await plugin_module._db_path()
            import aiosqlite
            
            async with aiosqlite.connect(db_path) as db:
                await db.execute("PRAGMA foreign_keys = ON")
                async with db.execute(
                    "SELECT id FROM accounts WHERE user_id = ? AND is_active = 1 LIMIT 1",
                    (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        session = get_session()
                        if session:
                            try:
                                from StarvellAPI.auth import fetch_homepage_data
                                homepage_data = await fetch_homepage_data(session)
                                if homepage_data.get("authorized"):
                                    user_info = homepage_data.get("user", {})
                                    username = user_info.get("username", "Неизвестно")
                                    
                                    await db.execute(
                                        "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
                                        (user_id,)
                                    )
                                    
                                    await db.execute(
                                        """
                                        INSERT INTO accounts (user_id, starvell_username, is_active)
                                        VALUES (?, ?, 1)
                                        """,
                                        (user_id, username)
                                    )
                                    await db.commit()
                                    
                                    async with db.execute(
                                        "SELECT id FROM accounts WHERE user_id = ? AND is_active = 1 LIMIT 1",
                                        (user_id,)
                                    ) as cursor2:
                                        row = await cursor2.fetchone()
                                        if not row:
                                            await message.answer("❌ У вас нет активного аккаунта Starvell")
                                            return
                                        account_id = row[0]
                                else:
                                    await message.answer("❌ У вас нет активного аккаунта Starvell")
                                    return
                            except Exception as e:
                                await message.answer(f"❌ Ошибка при создании аккаунта: {str(e)}")
                                return
                        else:
                            await message.answer("❌ У вас нет активного аккаунта Starvell")
                            return
                    else:
                        account_id = row[0]
            
            cfg = await plugin_module._get_config(user_id, account_id)
            settings_text = await plugin_module._settings_text(cfg, user_id, account_id)
            settings_kb = await plugin_module._settings_kb(cfg)
            await message.answer(settings_text, reply_markup=settings_kb, parse_mode="HTML")
        else:
            await message.answer("❌ Плагин AutoStars не поддерживает команду")
    except Exception as e:
        await message.answer(f"❌ Ошибка при открытии меню AutoStars: {str(e)}")

@dp.message(Command("robux"))
async def cmd_robux(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("Сначала авторизуйтесь через /start")
        return
    
    try:
        robux_plugin = plugin_manager.get_plugin("f9d8c7b6-5e4a-4b2c-8a0d-9f8e7d6c5b4a")
        if not robux_plugin:
            await message.answer("❌ Плагин AutoRobux не найден")
            return
        
        plugin_module = robux_plugin.plugin
        if hasattr(plugin_module, "_about_text") and hasattr(plugin_module, "_settings_kb"):
            about_text = plugin_module._about_text()
            settings_kb = plugin_module._settings_kb()
            await message.answer(about_text, reply_markup=settings_kb, parse_mode="HTML")
        else:
            await message.answer("❌ Плагин AutoRobux не поддерживает команду")
    except Exception as e:
        await message.answer(f"❌ Ошибка при открытии меню AutoRobux: {str(e)}")

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if is_authorized(user_id):
        await show_main_menu(message)
        return
    
    await message.answer("Добро пожаловать в TipzyStarvell! Введите пароль для входа:")
    await state.set_state(SetupStates.checking_password)


@dp.message(SetupStates.checking_password)
async def check_password(message: Message, state: FSMContext):
    password = get_password()
    user_id = message.from_user.id
    
    if password and message.text.strip() == password:
        set_authorized(user_id)
        await state.clear()
        await show_main_menu(message)
    else:
        await message.answer("❌ Неверный пароль. Попробуйте снова или используйте /start")


@dp.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not is_authorized(user_id):
        await message.answer("Введите пароль для доступа к меню:")
        await state.set_state(SetupStates.checking_password)
        return
    
    await show_main_menu(message)


@dp.message(Command("logs"))
async def cmd_logs(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("Сначала авторизуйтесь через /start")
        return
    
    if not LOG_FILE.exists():
        await message.answer("❌ Файл логов не найден.")
        return
    
    try:
        await message.answer("📄 Отправляю файл логов...")
        document = FSInputFile(LOG_FILE)
        await message.answer_document(document, caption="📄 Файл логов")
    except Exception as e:
        write_log(f"Ошибка отправки логов: {str(e)}")
        await message.answer(f"❌ Ошибка при отправке логов: {str(e)}")


@dp.message(Command("restart"))
async def cmd_restart(message: Message):
    """Полный рестарт бота."""
    if not is_authorized(message.from_user.id):
        await message.answer("Сначала авторизуйтесь через /start")
        return
    
    await message.answer("Перезапуск...")
    await asyncio.sleep(1)
    os.execl(sys.executable, sys.executable, *sys.argv)


@dp.message(Command("update"))
async def cmd_update(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("Сначала авторизуйтесь через /start")
        return
    
    if not GITHUB:
        await message.answer(
            "ℹ️ Ссылка на GitHub-репозиторий бота не настроена.\n"
            "Укажи GH в файле version.py, например:\n"
            'GH = "https://github.com/totodiemono/Starvell-Tipzy"'
        )
        return
    
    checking_msg = await message.answer("🔄 Проверяю обновления...")
    
    latest = await get_latest_version_from_github()
    if not latest:
        await checking_msg.edit_text("⚠️ Не удалось получить информацию об обновлениях. Попробуйте позже.")
        return
    
    # Сравниваем версии с учётом пробелов и переводов строк
    log_info(f"Локальная версия: {VERSION!r}")
    log_info(f"GitHub версия: {latest!r}")
    if isinstance(latest, str) and isinstance(VERSION, str):
        _v_local = VERSION.strip()
        _v_remote = latest.strip()
    else:
        _v_local = VERSION
        _v_remote = latest
    if _v_local == _v_remote:
        await checking_msg.edit_text(
            f"✅ У вас установлена последняя версия бота: <b>{VERSION}</b>.",
            parse_mode="HTML",
        )
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    text = (
        "Доступна новая версия!\n\n"
        f"{latest}\n\n"
        "Чтобы обновиться, нажмите кнопку ниже"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Обновить", callback_data=f"update_install:{latest}")]
        ]
    )

    await checking_msg.edit_text(text, reply_markup=keyboard)



@dp.callback_query(F.data.startswith("update_install:"))
async def handle_update_install(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    await callback.answer("Начинаю установку обновления...", show_alert=False)
    
    latest = callback.data.split(":", 1)[1]
    
    try:
        from pathlib import Path
        base_dir = Path(__file__).resolve().parent
        help_dir = base_dir / "помощь"
        new_path_str = download_and_extract_latest_release(help_dir)
        if not new_path_str:
            await callback.message.edit_text(
                "⚠️ Не удалось скачать обновление автоматически. "
                "Открой репозиторий на GitHub и скачай обновление вручную."
            )
            return
        
        from Utils.updater import install_update_from_path
        new_path = Path(new_path_str)
        install_update_from_path(new_path, base_dir=base_dir)
        
        await callback.message.edit_text(
            f"✅ Обновление до версии {latest} установлено.\n\n"
            "Для применения изменений отправьте команду /restart."
        )
    except Exception as e:
        await callback.message.edit_text(
            f"⚠️ При установке обновления произошла ошибка: {e}\n"
            "Попробуйте обновиться позже или вручную."
        )


@dp.callback_query(F.data == "global_switches")
async def handle_global_switches(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    await callback.answer()
    
    settings = get_settings()
    global_switches = settings.get("global_switches", {})
    
    auto_bump_enabled = global_switches.get("auto_bump", False)
    logging_enabled = global_switches.get("logging", True)
    
    text = "⚙️ Глобальные переключатели\n\nНастройки глобальных функций бота."
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{'🟢' if auto_bump_enabled else '🔴'} Авто поднятие",
                    callback_data="toggle_auto_bump"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{'🟢' if logging_enabled else '🔴'} Логи",
                    callback_data="toggle_logging"
                )
            ],
            [InlineKeyboardButton(text="◀ Назад", callback_data="back_to_menu")]
        ]
    )
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)


@dp.callback_query(F.data == "toggle_auto_bump")
async def handle_toggle_auto_bump(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    settings = get_settings()
    global_switches = settings.get("global_switches", {})
    current = global_switches.get("auto_bump", False)
    global_switches["auto_bump"] = not current
    settings["global_switches"] = global_switches
    save_settings(settings)
    
    await callback.answer(f"{'Включено' if not current else 'Выключено'}")
    await handle_global_switches(callback)

@dp.callback_query(F.data == "toggle_logging")
async def handle_toggle_logging(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    settings = get_settings()
    global_switches = settings.get("global_switches", {})
    current = global_switches.get("logging", True)
    global_switches["logging"] = not current
    settings["global_switches"] = global_switches
    save_settings(settings)
    
    await callback.answer(f"{'Включено' if not current else 'Выключено'}")
    await handle_global_switches(callback)

@dp.callback_query(F.data == "notifications")
async def handle_notifications(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    await callback.answer()
    
    settings = load_settings()
    notifications = settings.get("notifications", {})
    new_order = notifications.get("new_order", True)
    new_message = notifications.get("new_message", True)
    bot_start = notifications.get("bot_start", True)
    
    text = "🔔 Уведомления\n\nВыберите, о каких событиях вы хотите получать уведомления:"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{'🟢' if new_order else '🔴'} Новый заказ",
                    callback_data="toggle_notification_new_order"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{'🟢' if new_message else '🔴'} Новое сообщение",
                    callback_data="toggle_notification_new_message"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{'🟢' if bot_start else '🔴'} Запуск бота",
                    callback_data="toggle_notification_bot_start"
                )
            ],
            [InlineKeyboardButton(text="◀ Назад", callback_data="back_to_menu")]
        ]
    )
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)


@dp.callback_query(F.data == "toggle_notification_new_order")
async def toggle_notification_new_order(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    current = get_setting("notifications", "new_order", True)
    update_setting("notifications", "new_order", not current)
    await callback.answer(f"{'Включено' if not current else 'Выключено'}")
    await handle_notifications(callback)


@dp.callback_query(F.data == "toggle_notification_new_message")
async def toggle_notification_new_message(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    current = get_setting("notifications", "new_message", True)
    update_setting("notifications", "new_message", not current)
    await callback.answer(f"{'Включено' if not current else 'Выключено'}")
    await handle_notifications(callback)


@dp.callback_query(F.data == "toggle_notification_bot_start")
async def toggle_notification_bot_start(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    current = get_setting("notifications", "bot_start", True)
    update_setting("notifications", "bot_start", not current)
    await callback.answer(f"{'Включено' if not current else 'Выключено'}")
    await handle_notifications(callback)


@dp.callback_query(F.data == "auto_reply")
async def handle_auto_reply(callback: CallbackQuery, state: FSMContext):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    await callback.answer()
    
    text = "Здесь ты можешь добавить команды или редактировать существующие."
    
    keyboard_buttons = [
        [InlineKeyboardButton(text="✏️ Редактировать существующие команды", callback_data="auto_reply_edit_commands")],
        [InlineKeyboardButton(text="➕ Добавить команду / сет команд", callback_data="add_auto_reply_command")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="back_to_menu")]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)


@dp.callback_query(F.data == "auto_reply_edit_commands")
async def handle_auto_reply_edit_commands(callback: CallbackQuery):
    callback.data = "ar_commands_list:0"
    await handle_ar_commands_list(callback)

@dp.callback_query(F.data.startswith("ar_commands_list:"))
async def handle_ar_commands_list(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    await callback.answer()
    
    offset = int(callback.data.split(":")[1])
    commands_data = load_auto_reply_commands()
    raw_commands = list(commands_data.get("commands", {}).keys())
    AR_BTNS_AMOUNT = 15
    
    commands_page = raw_commands[offset:offset + AR_BTNS_AMOUNT]
    if not commands_page and offset != 0:
        offset = 0
        commands_page = raw_commands[offset:offset + AR_BTNS_AMOUNT]
    
    keyboard_buttons = []
    for index, raw_cmd in enumerate(commands_page):
        keyboard_buttons.append([InlineKeyboardButton(text=raw_cmd, callback_data=f"ar_edit_command:{offset + index}:{offset}")])
    
    if len(raw_commands) > AR_BTNS_AMOUNT:
        nav_buttons = []
        back, forward = True, True
        
        if offset > 0:
            back_offset = offset - AR_BTNS_AMOUNT if offset > AR_BTNS_AMOUNT else 0
            back_cb = f"ar_commands_list:{back_offset}"
            first_cb = f"ar_commands_list:0"
        else:
            back, back_cb, first_cb = False, "empty", "empty"
        
        if offset + len(commands_page) < len(raw_commands):
            forward_offset = offset + len(commands_page)
            last_page_offset = ((len(raw_commands) - 1) // AR_BTNS_AMOUNT) * AR_BTNS_AMOUNT
            forward_cb = f"ar_commands_list:{forward_offset}"
            last_cb = f"ar_commands_list:{last_page_offset}"
        else:
            forward, forward_cb, last_cb = False, "empty", "empty"
        
        if back or forward:
            center_text = f"{(offset // AR_BTNS_AMOUNT) + 1}/{math.ceil(len(raw_commands) / AR_BTNS_AMOUNT)}"
            nav_row = []
            if back:
                nav_row.append(InlineKeyboardButton(text="◀️◀️", callback_data=first_cb))
                nav_row.append(InlineKeyboardButton(text="◀️", callback_data=back_cb))
            nav_row.append(InlineKeyboardButton(text=center_text, callback_data="empty"))
            if forward:
                nav_row.append(InlineKeyboardButton(text="▶️", callback_data=forward_cb))
                nav_row.append(InlineKeyboardButton(text="▶️▶️", callback_data=last_cb))
            keyboard_buttons.append(nav_row)
    
    keyboard_buttons.append([InlineKeyboardButton(text="➕ Добавить команду / сет команд", callback_data="add_auto_reply_command")])
    keyboard_buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="auto_reply")])
    
    text = "🤖 Авто-ответ\n\nВыберите команду для редактирования:"
    if not raw_commands:
        text = "🤖 Авто-ответ\n\nКоманды не найдены."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)

@dp.callback_query(F.data == "empty")
async def handle_empty(callback: CallbackQuery):
    await callback.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)

@dp.callback_query(F.data.startswith("ar_edit_command:"))
async def handle_ar_edit_command(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    parts = callback.data.split(":")
    command_index = int(parts[1])
    offset = int(parts[2])
    
    commands_data = load_auto_reply_commands()
    raw_commands = list(commands_data.get("commands", {}).keys())
    
    if command_index >= len(raw_commands):
        await callback.answer("Команда не найдена", show_alert=True)
        return
    
    raw_command = raw_commands[command_index]
    command_data = commands_data["commands"][raw_command]
    response = command_data.get("response", "")
    notification_enabled = command_data.get("telegramNotification", 0) == 1
    notification_text = command_data.get("notificationText", "")
    
    text = f"🤖 <b>[{raw_command}]</b>\n\n"
    text += f"<b>Текст ответа:</b>\n<code>{response[:100]}{'...' if len(response) > 100 else ''}</code>\n\n"
    text += f"<b>Уведомление:</b> {'🔔 Включено' if notification_enabled else '🔕 Выключено'}\n"
    if notification_text:
        text += f"<b>Текст уведомления:</b>\n<code>{notification_text[:100]}{'...' if len(notification_text) > 100 else ''}</code>\n"
    
    keyboard_buttons = [
        [InlineKeyboardButton(text="✏️ Изменить текст ответа", callback_data=f"ar_edit_response:{command_index}:{offset}")],
        [InlineKeyboardButton(text="📝 Изменить текст уведомления", callback_data=f"ar_edit_notification:{command_index}:{offset}")],
        [InlineKeyboardButton(text=f"{'🔔' if not notification_enabled else '🔕'} {'Включить' if not notification_enabled else 'Выключить'} уведомление", callback_data=f"ar_toggle_notification:{command_index}:{offset}")],
        [InlineKeyboardButton(text="🗑 Удалить команду", callback_data=f"ar_delete_command:{command_index}:{offset}")],
        [InlineKeyboardButton(text="◀ Назад", callback_data=f"ar_commands_list:{offset}")]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.answer()
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(F.data == "add_auto_reply_command")
async def handle_add_auto_reply_command(callback: CallbackQuery, state: FSMContext):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    await callback.answer()
    await callback.message.answer("Введите команду или набор команд через | (например: !продавец|!продав):")
    await state.set_state(SetupStates.adding_auto_reply_command)

@dp.message(SetupStates.adding_auto_reply_command)
async def process_add_auto_reply_command(message: Message, state: FSMContext):
    raw_command = message.text.strip().lower().replace("\n", "")
    if not raw_command:
        await message.answer("Команда не может быть пустой. Введите команду или набор команд через |:")
        return
    
    commands = [cmd.strip() for cmd in raw_command.split("|") if cmd.strip()]
    if not commands:
        await message.answer("Команда не может быть пустой. Введите команду или набор команд через |:")
        return
    
    commands_data = load_auto_reply_commands()
    commands_dict = commands_data.get("commands", {})
    
    for cmd in commands:
        for existing_raw in commands_dict:
            existing_commands = [c.strip().lower() for c in existing_raw.split("|") if c.strip()]
            if cmd in existing_commands:
                await message.answer(f"Команда '{cmd}' уже существует в наборе '{existing_raw}'. Введите другую команду:")
                return
    
    commands_dict[raw_command] = {
        "response": "Данной команде необходимо настроить текст ответа :(",
        "telegramNotification": 0,
        "notificationText": ""
    }
    commands_data["commands"] = commands_dict
    save_auto_reply_commands(commands_data)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀ Назад", callback_data="auto_reply"),
         InlineKeyboardButton(text="➕ Добавить еще", callback_data="add_auto_reply_command")]
    ])
    await message.answer(f"✅ Команда '{raw_command}' добавлена. Теперь настройте текст ответа.", reply_markup=keyboard)
    await state.clear()

@dp.callback_query(F.data.startswith("ar_edit_response:"))
async def handle_ar_edit_response(callback: CallbackQuery, state: FSMContext):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    parts = callback.data.split(":")
    command_index = int(parts[1])
    offset = int(parts[2])
    
    await callback.answer()
    await state.update_data(command_index=command_index, offset=offset)
    await callback.message.answer("Введите текст ответа на команду:")
    await state.set_state(SetupStates.editing_auto_reply_command_response)

@dp.message(SetupStates.editing_auto_reply_command_response)
async def process_ar_edit_response(message: Message, state: FSMContext):
    data = await state.get_data()
    command_index = data.get("command_index")
    offset = data.get("offset")
    
    response_text = message.text.strip()
    if not response_text:
        await message.answer("Текст не может быть пустым. Введите текст ответа:")
        return
    
    commands_data = load_auto_reply_commands()
    raw_commands = list(commands_data.get("commands", {}).keys())
    
    if command_index >= len(raw_commands):
        await message.answer("Команда не найдена")
        await state.clear()
        return
    
    raw_command = raw_commands[command_index]
    commands_data["commands"][raw_command]["response"] = response_text
    save_auto_reply_commands(commands_data)
    
    await message.answer("✅ Текст ответа сохранен")
    
    commands_data = load_auto_reply_commands()
    raw_commands = list(commands_data.get("commands", {}).keys())
    raw_command = raw_commands[command_index]
    command_data = commands_data["commands"][raw_command]
    response = command_data.get("response", "")
    notification_enabled = command_data.get("telegramNotification", 0) == 1
    notification_text = command_data.get("notificationText", "")
    
    text = f"🤖 <b>[{raw_command}]</b>\n\n"
    text += f"<b>Текст ответа:</b>\n<code>{response[:100]}{'...' if len(response) > 100 else ''}</code>\n\n"
    text += f"<b>Уведомление:</b> {'🔔 Включено' if notification_enabled else '🔕 Выключено'}\n"
    if notification_text:
        text += f"<b>Текст уведомления:</b>\n<code>{notification_text[:100]}{'...' if len(notification_text) > 100 else ''}</code>\n"
    
    keyboard_buttons = [
        [InlineKeyboardButton(text="✏️ Изменить текст ответа", callback_data=f"ar_edit_response:{command_index}:{offset}")],
        [InlineKeyboardButton(text="📝 Изменить текст уведомления", callback_data=f"ar_edit_notification:{command_index}:{offset}")],
        [InlineKeyboardButton(text=f"{'🔔' if not notification_enabled else '🔕'} {'Включить' if not notification_enabled else 'Выключить'} уведомление", callback_data=f"ar_toggle_notification:{command_index}:{offset}")],
        [InlineKeyboardButton(text="🗑 Удалить команду", callback_data=f"ar_delete_command:{command_index}:{offset}")],
        [InlineKeyboardButton(text="◀ Назад", callback_data=f"ar_commands_list:{offset}")]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data.startswith("ar_edit_notification:"))
async def handle_ar_edit_notification(callback: CallbackQuery, state: FSMContext):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    parts = callback.data.split(":")
    command_index = int(parts[1])
    offset = int(parts[2])
    
    await callback.answer()
    await state.update_data(command_index=command_index, offset=offset)
    await callback.message.answer("Введите текст уведомления об использовании команды:")
    await state.set_state(SetupStates.editing_auto_reply_command_notification)

@dp.message(SetupStates.editing_auto_reply_command_notification)
async def process_ar_edit_notification(message: Message, state: FSMContext):
    data = await state.get_data()
    command_index = data.get("command_index")
    offset = data.get("offset")
    
    notification_text = message.text.strip()
    
    commands_data = load_auto_reply_commands()
    raw_commands = list(commands_data.get("commands", {}).keys())
    
    if command_index >= len(raw_commands):
        await message.answer("Команда не найдена")
        await state.clear()
        return
    
    raw_command = raw_commands[command_index]
    commands_data["commands"][raw_command]["notificationText"] = notification_text
    save_auto_reply_commands(commands_data)
    
    await message.answer("✅ Текст уведомления сохранен")
    
    commands_data = load_auto_reply_commands()
    raw_commands = list(commands_data.get("commands", {}).keys())
    raw_command = raw_commands[command_index]
    command_data = commands_data["commands"][raw_command]
    response = command_data.get("response", "")
    notification_enabled = command_data.get("telegramNotification", 0) == 1
    notification_text = command_data.get("notificationText", "")
    
    text = f"🤖 <b>[{raw_command}]</b>\n\n"
    text += f"<b>Текст ответа:</b>\n<code>{response[:100]}{'...' if len(response) > 100 else ''}</code>\n\n"
    text += f"<b>Уведомление:</b> {'🔔 Включено' if notification_enabled else '🔕 Выключено'}\n"
    if notification_text:
        text += f"<b>Текст уведомления:</b>\n<code>{notification_text[:100]}{'...' if len(notification_text) > 100 else ''}</code>\n"
    
    keyboard_buttons = [
        [InlineKeyboardButton(text="✏️ Изменить текст ответа", callback_data=f"ar_edit_response:{command_index}:{offset}")],
        [InlineKeyboardButton(text="📝 Изменить текст уведомления", callback_data=f"ar_edit_notification:{command_index}:{offset}")],
        [InlineKeyboardButton(text=f"{'🔔' if not notification_enabled else '🔕'} {'Включить' if not notification_enabled else 'Выключить'} уведомление", callback_data=f"ar_toggle_notification:{command_index}:{offset}")],
        [InlineKeyboardButton(text="🗑 Удалить команду", callback_data=f"ar_delete_command:{command_index}:{offset}")],
        [InlineKeyboardButton(text="◀ Назад", callback_data=f"ar_commands_list:{offset}")]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data.startswith("ar_toggle_notification:"))
async def handle_ar_toggle_notification(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    parts = callback.data.split(":")
    command_index = int(parts[1])
    offset = int(parts[2])
    
    commands_data = load_auto_reply_commands()
    raw_commands = list(commands_data.get("commands", {}).keys())
    
    if command_index >= len(raw_commands):
        await callback.answer("Команда не найдена", show_alert=True)
        return
    
    raw_command = raw_commands[command_index]
    current = commands_data["commands"][raw_command].get("telegramNotification", 0)
    commands_data["commands"][raw_command]["telegramNotification"] = 1 if current == 0 else 0
    save_auto_reply_commands(commands_data)
    
    await callback.answer()
    await handle_ar_edit_command(callback)

@dp.callback_query(F.data.startswith("ar_delete_command:"))
async def handle_ar_delete_command(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    parts = callback.data.split(":")
    command_index = int(parts[1])
    offset = int(parts[2])
    
    commands_data = load_auto_reply_commands()
    raw_commands = list(commands_data.get("commands", {}).keys())
    
    if command_index >= len(raw_commands):
        await callback.answer("Команда не найдена", show_alert=True)
        return
    
    raw_command = raw_commands[command_index]
    del commands_data["commands"][raw_command]
    save_auto_reply_commands(commands_data)
    
    await callback.answer("✅ Команда удалена")
    callback.data = f"ar_commands_list:{offset}"
    await handle_ar_commands_list(callback)


@dp.callback_query(F.data == "welcome")
async def handle_welcome(callback: CallbackQuery, state: FSMContext):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    await callback.answer()
    
    settings = load_settings()
    welcome = settings.get("welcome_message", {})
    enabled = welcome.get("enabled", False)
    message = welcome.get("message", "")
    
    status_text = "🟢 Приветствовать пользователей" if enabled else "🔴 Приветствовать пользователей"
    text = f"👋 <b>Приветственное сообщение</b>\n\n{status_text}\n\nПриветственное сообщение отправляется покупателю при первом сообщении в чат на Starvell."
    if message:
        import html as html_escape
        safe_message = html_escape.escape(message)
        text += f"\n\n<b>Текущее сообщение:</b>\n<code>{safe_message}</code>"
    
    keyboard_buttons = [
        [InlineKeyboardButton(
            text=status_text,
            callback_data="toggle_welcome_message"
        )]
    ]
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="✏️ Изменить текст приветственного сообщения", callback_data="edit_welcome_message")
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="back_to_menu")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@dp.callback_query(F.data == "toggle_welcome_message")
async def toggle_welcome_message(callback: CallbackQuery, state: FSMContext):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    current = get_setting("welcome_message", "enabled", False)
    update_setting("welcome_message", "enabled", not current)
    await callback.answer()
    await handle_welcome(callback, state)

@dp.callback_query(F.data == "edit_welcome_message")
async def edit_welcome_message(callback: CallbackQuery, state: FSMContext):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    await callback.answer()
    await callback.message.answer("Введите текст приветственного сообщения:")
    await state.set_state(SetupStates.setting_welcome_message)


@dp.message(SetupStates.replying_to_chat)
async def process_reply_to_chat(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data.get("chat_id")
    text = message.text.strip()
    if not text:
        await message.answer("Текст не может быть пустым. Введите текст ответа:")
        return
    
    from StarvellAPI.send_message import send_chat_message
    session = get_session()
    if not session:
        await message.answer("Session не найден")
        await state.clear()
        return
    
    try:
        from StarvellAPI.chats import fetch_chats
        chats_data = await fetch_chats(session)
        page_props = chats_data.get("pageProps", {})
        chats = page_props.get("chats", [])
        chat_name = chat_id
        for c in chats:
            if str(c.get("id", "")) == chat_id:
                chat_name = c.get("name", c.get("username", chat_id))
                break
        await send_chat_message(session, chat_id, text, chat_name)
        await message.answer("✅ Сообщение отправлено")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    await state.clear()

@dp.message(SetupStates.setting_welcome_message)
async def process_welcome_message(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("Текст не может быть пустым. Введите текст приветственного сообщения:")
        return
    
    update_setting("welcome_message", "message", text)
    if not get_setting("welcome_message", "enabled", False):
        update_setting("welcome_message", "enabled", True)
    
    await message.answer("✅ Приветственное сообщение сохранено и включено")
    await state.clear()


@dp.callback_query(F.data == "plugins")
async def handle_plugins(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    await callback.answer()
    
    plugins = plugin_manager.get_all_plugins()
    
    if not plugins:
        text = "🧩 Плагины\n\nПлагины не найдены."
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀ Назад", callback_data="back_to_menu")]
            ]
        )
    else:
        text = "🧩 Плагины\n\nВыберите плагин для управления:"
        keyboard_buttons = []
        for uuid, plugin_data in plugins.items():
            status = "🟢" if plugin_data.enabled else "🔴"
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{status} {plugin_data.name} v{plugin_data.version}",
                    callback_data=f"plugin_{uuid}"
                )
            ])
        keyboard_buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="back_to_menu")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)




@dp.callback_query(F.data.startswith("plugin_") & ~F.data.startswith("plugin_commands_") & ~F.data.startswith("plugin_settings_"))
async def handle_plugin_detail(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    uuid = callback.data.replace("plugin_", "")
    plugin_data = plugin_manager.get_plugin(uuid)
    if not plugin_data:
        await callback.answer("Плагин не найден", show_alert=True)
        return
    
    status = "🟢 Активирован" if plugin_data.enabled else "🔴 Деактивирован"
    text = f"""🧩 <b>{plugin_data.name}</b> v{plugin_data.version}

{plugin_data.description}

<b>Автор:</b> {plugin_data.credits}
<b>UUID:</b> <code>{plugin_data.uuid}</code>
<b>Статус:</b> {status}"""
    
    keyboard_buttons = [
        [InlineKeyboardButton(
            text="🔄 Включить" if not plugin_data.enabled else "🛑 Выключить",
            callback_data=f"toggle_plugin_{uuid}"
        )]
    ]
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="⌨️ Команды", callback_data=f"plugin_commands_{uuid}")
    ])
    
    if plugin_data.settings_page:
        keyboard_buttons.append([
            InlineKeyboardButton(text="⚙️ Настройки", callback_data=f"plugin_settings_{uuid}")
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="plugins")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("toggle_plugin_"))
async def handle_toggle_plugin(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    uuid = callback.data.replace("toggle_plugin_", "")
    
    if plugin_manager.toggle_plugin(uuid):
        await callback.answer("✅ Плагин переключен")
        callback.data = f"plugin_{uuid}"
        await handle_plugin_detail(callback)
    else:
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.callback_query(F.data.startswith("plugin_commands_"))
async def handle_plugin_commands(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    uuid = callback.data.replace("plugin_commands_", "")
    plugin_data = plugin_manager.get_plugin(uuid)
    if not plugin_data:
        await callback.answer("Плагин не найден", show_alert=True)
        return
    
    await callback.answer()
    
    if not plugin_data.commands:
        text = f"<b>Команды плагина <i>{plugin_data.name}</i>.</b>\n\n❌ У плагина нет команд."
    else:
        commands_text_list = []
        for cmd, desc in plugin_data.commands.items():
            commands_text_list.append(f"/{cmd} - {desc}")
        
        commands_text = "\n\n".join(commands_text_list)
        text = f"<b>Команды плагина <i>{plugin_data.name}</i>.</b>\n\n{commands_text}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀ Назад", callback_data=f"plugin_{uuid}")]
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@dp.callback_query(F.data == "templates")
async def handle_templates(callback: CallbackQuery):
    callback.data = "templates_list:0"
    await handle_templates_list(callback)

@dp.callback_query(F.data.startswith("templates_list:"))
async def handle_templates_list(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    await callback.answer()
    
    offset = int(callback.data.split(":")[1])
    templates = get_templates()
    TMPLT_BTNS_AMOUNT = 15
    
    templates_page = templates[offset:offset + TMPLT_BTNS_AMOUNT]
    if not templates_page and offset != 0:
        offset = 0
        templates_page = templates[offset:offset + TMPLT_BTNS_AMOUNT]
    
    keyboard_buttons = []
    for index, tmplt in enumerate(templates_page):
        keyboard_buttons.append([InlineKeyboardButton(text=tmplt, callback_data=f"edit_template:{offset + index}:{offset}")])
    
    if len(templates) > TMPLT_BTNS_AMOUNT:
        nav_buttons = []
        back, forward = True, True
        
        if offset > 0:
            back_offset = offset - TMPLT_BTNS_AMOUNT if offset > TMPLT_BTNS_AMOUNT else 0
            back_cb = f"templates_list:{back_offset}"
            first_cb = f"templates_list:0"
        else:
            back, back_cb, first_cb = False, "empty", "empty"
        
        if offset + len(templates_page) < len(templates):
            forward_offset = offset + len(templates_page)
            last_page_offset = ((len(templates) - 1) // TMPLT_BTNS_AMOUNT) * TMPLT_BTNS_AMOUNT
            forward_cb = f"templates_list:{forward_offset}"
            last_cb = f"templates_list:{last_page_offset}"
        else:
            forward, forward_cb, last_cb = False, "empty", "empty"
        
        if back or forward:
            center_text = f"{(offset // TMPLT_BTNS_AMOUNT) + 1}/{math.ceil(len(templates) / TMPLT_BTNS_AMOUNT)}"
            nav_row = []
            if back:
                nav_row.append(InlineKeyboardButton(text="◀️◀️", callback_data=first_cb))
                nav_row.append(InlineKeyboardButton(text="◀️", callback_data=back_cb))
            else:
                nav_row.append(InlineKeyboardButton(text="◀️◀️", callback_data="empty"))
                nav_row.append(InlineKeyboardButton(text="◀️", callback_data="empty"))
            nav_row.append(InlineKeyboardButton(text=center_text, callback_data="empty"))
            if forward:
                nav_row.append(InlineKeyboardButton(text="▶️", callback_data=forward_cb))
                nav_row.append(InlineKeyboardButton(text="▶️▶️", callback_data=last_cb))
            else:
                nav_row.append(InlineKeyboardButton(text="▶️", callback_data="empty"))
                nav_row.append(InlineKeyboardButton(text="▶️▶️", callback_data="empty"))
            keyboard_buttons.append(nav_row)
    
    keyboard_buttons.append([InlineKeyboardButton(text="➕ Добавить заготовку", callback_data=f"add_template:{offset}")])
    keyboard_buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="back_to_menu")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    try:
        await callback.message.edit_text("Здесь вы можете добавлять и удалять заготовки ответов.", reply_markup=keyboard)
    except Exception:
        await callback.message.answer("Здесь вы можете добавлять и удалять заготовки ответов.", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("add_template:"))
async def handle_add_template(callback: CallbackQuery, state: FSMContext):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    await callback.answer()
    offset = int(callback.data.split(":")[1])
    await state.set_data({"offset": offset})
    await callback.message.answer("Введите текст заготовки:")
    await state.set_state(SetupStates.adding_template)


@dp.callback_query(F.data == "back_to_menu")
async def handle_back_to_menu(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    await callback.answer()
    await show_main_menu(callback=callback)


@dp.callback_query(F.data.startswith("edit_template:"))
async def handle_edit_template(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    parts = callback.data.split(":")
    template_index = int(parts[1])
    offset = int(parts[2])
    templates = get_templates()
    
    if template_index >= len(templates):
        await callback.answer("Заготовка не найдена", show_alert=True)
        return
    
    template_text = templates[template_index]
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_template:{template_index}:{offset}")],
            [InlineKeyboardButton(text="◀ Назад", callback_data=f"templates_list:{offset}")]
        ]
    )
    
    await callback.answer()
    try:
        await callback.message.edit_text(f"<code>{template_text}</code>", reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(f"<code>{template_text}</code>", reply_markup=keyboard, parse_mode="HTML")


@dp.message(SetupStates.adding_template)
async def process_template(message: Message, state: FSMContext):
    template_text = message.text.strip()
    if not template_text:
        await message.answer("Текст не может быть пустым. Введите текст заготовки:")
        return
    
    templates = get_templates()
    if template_text in templates:
        data = await state.get_data()
        offset = data.get("offset", 0)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ Назад", callback_data=f"templates_list:{offset}"),
             InlineKeyboardButton(text="➕ Добавить другую", callback_data=f"add_template:{offset}")]
        ])
        await message.answer("❌ Такая заготовка уже существует.", reply_markup=keyboard)
        await state.clear()
        return
    
    add_template(template_text)
    data = await state.get_data()
    offset = data.get("offset", 0)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀ Назад", callback_data=f"templates_list:{offset}"),
         InlineKeyboardButton(text="➕ Добавить еще", callback_data=f"add_template:{offset}")]
    ])
    await message.answer("✅ Заготовка добавлена.", reply_markup=keyboard)
    await state.clear()


@dp.callback_query(F.data.startswith("delete_template:"))
async def handle_delete_template(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    parts = callback.data.split(":")
    template_index = int(parts[1])
    offset = int(parts[2])
    
    templates = get_templates()
    if template_index >= len(templates):
        await callback.answer("Заготовка не найдена", show_alert=True)
        return
    
    if delete_template(template_index):
        await callback.answer("✅ Заготовка удалена")
        callback.data = f"templates_list:{offset}"
        await handle_templates_list(callback)
    else:
        await callback.answer("❌ Ошибка при удалении", show_alert=True)


def get_new_message_keyboard(chat_id: str) -> InlineKeyboardMarkup:
    templates = get_templates()
    keyboard_buttons = []
    
    keyboard_buttons.append([InlineKeyboardButton(text="💬 Ответ", callback_data=f"reply_chat_{chat_id}")])
    
    if templates:
        keyboard_buttons.append([InlineKeyboardButton(text="📄 Заготовки", callback_data=f"templates_for_chat_{chat_id}")])
    
    keyboard_buttons.append([InlineKeyboardButton(text="🔗 Перейти в чат", url=f"https://starvell.com/chat/{chat_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


async def send_new_message_notification(user_id: int, chat_id: str, message_text: str, chat_name: str):
    global bot
    if not is_authorized(user_id) or not bot:
        return
    
    safe_username = html.escape(chat_name)
    safe_text = html.escape(message_text[:500])
    if len(message_text) > 500:
        safe_text = safe_text[:497] + "..."
    
    text = f"💬 <b>Новое сообщение</b>\n\n👤 От: <code>{safe_username}</code>\n📄 Текст:\n<code>{safe_text}</code>"
    keyboard = get_new_message_keyboard(chat_id)
    
    notification_messages = load_notification_messages()
    key = f"{user_id}_{chat_id}"
    
    try:
        if key in notification_messages:
            message_id = notification_messages[key]
            try:
                await bot.edit_message_text(text, chat_id=user_id, message_id=message_id, reply_markup=keyboard, parse_mode="HTML")
                return
            except Exception:
                del notification_messages[key]
                save_notification_messages(notification_messages)
        
        msg = await bot.send_message(user_id, text, reply_markup=keyboard, parse_mode="HTML")
        notification_messages[key] = msg.message_id
        save_notification_messages(notification_messages)
    except Exception:
        pass


@dp.callback_query(F.data.startswith("reply_chat_"))
async def handle_reply_chat(callback: CallbackQuery, state: FSMContext):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    await callback.answer()
    chat_id = callback.data.replace("reply_chat_", "")
    await callback.message.answer("Введите текст ответа:")
    await state.set_state(SetupStates.replying_to_chat)
    await state.update_data(chat_id=chat_id)

@dp.callback_query(F.data.startswith("templates_for_chat_"))
async def handle_templates_for_chat(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    await callback.answer()
    chat_id = callback.data.replace("templates_for_chat_", "")
    templates = get_templates()
    if not templates:
        await callback.answer("Заготовки не найдены", show_alert=True)
        return
    keyboard_buttons = []
    for i, template in enumerate(templates):
        text_preview = template[:30] + "..." if len(template) > 30 else template
        keyboard_buttons.append([InlineKeyboardButton(text=f"📄 {text_preview}", callback_data=f"send_template_{chat_id}_{i}")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    try:
        await callback.message.edit_text("Выберите заготовку:", reply_markup=keyboard)
    except Exception:
        await callback.message.answer("Выберите заготовку:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("reply_order_"))
async def handle_reply_order(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Ответить' для заказа"""
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    parts = callback.data.split("_")
    order_id = parts[2]
    buyer_id = parts[3] if len(parts) > 3 else None
    
    # Находим chat_id по buyer_id
    chat_id = None
    if buyer_id:
        try:
            from StarvellAPI.chats import fetch_chats
            session = get_session()
            if session:
                chats_data = await fetch_chats(session)
                page_props = chats_data.get("pageProps", {})
                chats = page_props.get("chats", [])
                
                for chat in chats:
                    participants = chat.get("participants", [])
                    for participant in participants:
                        if str(participant.get("id")) == str(buyer_id):
                            chat_id = str(chat.get("id"))
                            break
                    if chat_id:
                        break
        except Exception:
            pass
    
    if not chat_id:
        await callback.answer("❌ Не удалось найти чат для этого заказа", show_alert=True)
        return
    
    await callback.answer()
    await callback.message.answer("Введите текст ответа:")
    await state.set_state(SetupStates.replying_to_chat)
    await state.update_data(chat_id=chat_id)


@dp.callback_query(F.data.startswith("templates_order_"))
async def handle_templates_order(callback: CallbackQuery):
    """Обработчик кнопки 'Заготовки' для заказа"""
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    await callback.answer()
    
    parts = callback.data.split("_")
    order_id = parts[2]
    buyer_id = parts[3] if len(parts) > 3 else None
    
    # Находим chat_id по buyer_id
    chat_id = None
    if buyer_id:
        try:
            from StarvellAPI.chats import fetch_chats
            session = get_session()
            if session:
                chats_data = await fetch_chats(session)
                page_props = chats_data.get("pageProps", {})
                chats = page_props.get("chats", [])
                
                for chat in chats:
                    participants = chat.get("participants", [])
                    for participant in participants:
                        if str(participant.get("id")) == str(buyer_id):
                            chat_id = str(chat.get("id"))
                            break
                    if chat_id:
                        break
        except Exception:
            pass
    
    if not chat_id:
        await callback.answer("❌ Не удалось найти чат для этого заказа", show_alert=True)
        return
    
    templates = get_templates()
    if not templates:
        await callback.answer("Заготовки не найдены", show_alert=True)
        return
    
    keyboard_buttons = []
    for i, template in enumerate(templates):
        text_preview = template[:30] + "..." if len(template) > 30 else template
        keyboard_buttons.append([InlineKeyboardButton(text=f"📄 {text_preview}", callback_data=f"send_template_{chat_id}_{i}")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    try:
        await callback.message.edit_text("Выберите заготовку:", reply_markup=keyboard)
    except Exception:
        await callback.message.answer("Выберите заготовку:", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("send_template_"))
async def handle_send_template(callback: CallbackQuery):
    if not is_authorized(callback.from_user.id):
        await callback.answer("Сначала авторизуйтесь через /start", show_alert=True)
        return
    
    parts = callback.data.split("_")
    chat_id = parts[2]
    template_index = int(parts[3])
    
    templates = get_templates()
    if template_index >= len(templates):
        await callback.answer("Заготовка не найдена", show_alert=True)
        return
    
    template_text = templates[template_index]
    
    from StarvellAPI.send_message import send_chat_message
    
    session = get_session()
    if not session:
        await callback.answer("Session не найден", show_alert=True)
        return
    
    chat_name = None
    try:
        from StarvellAPI.chats import fetch_chats
        chats_data = await fetch_chats(session)
        page_props = chats_data.get("pageProps", {})
        chats = page_props.get("chats", [])
        for c in chats:
            if str(c.get("id", "")) == chat_id:
                chat_name = c.get("name", c.get("username", chat_id))
                break
    except Exception:
        pass
    
    try:
        await send_chat_message(session, chat_id, template_text, chat_name)
        await callback.answer("✅ Сообщение отправлено")
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)




async def check_new_messages():
    from StarvellAPI.chats import fetch_chats
    from StarvellAPI.messages import fetch_chat_messages
    
    session = get_session()
    if not session:
        return
    
    try:
        chats_data = await fetch_chats(session)
        page_props = chats_data.get("pageProps", {})
        chats = page_props.get("chats", [])
        
        last_messages = load_last_messages()
        new_messages_found = False
        
        from StarvellAPI.auth import fetch_homepage_data
        homepage_data = await fetch_homepage_data(session)
        user_info = homepage_data.get("user", {}) if homepage_data.get("authorized") else {}
        starvell_user_id = user_info.get("id") if user_info else None
        
        for chat in chats:
            chat_id = str(chat.get("id", ""))
            if not chat_id:
                continue
            
            try:
                messages = await fetch_chat_messages(session, chat_id, limit=10)
                if not messages:
                    continue
                
                last_message = messages[0] if messages else None
                if not last_message:
                    continue
                
                message_id = str(last_message.get("id", ""))
                last_seen_id = last_messages.get(chat_id, "")
                
                if message_id and message_id != last_seen_id:
                    # ПЕРВАЯ проверка: является ли это сообщение, отправленное ботом
                    if await is_bot_message(chat_id, message_id):
                        last_messages[chat_id] = message_id
                        continue
                    
                    content = last_message.get("content", "")
                    created_at = last_message.get("createdAt", "")
                    
                    # Получаем sender_id из разных возможных полей
                    sender_id = (
                        last_message.get("senderId") or 
                        last_message.get("authorId") or
                        (last_message.get("author") or {}).get("id") or
                        (last_message.get("sender") or {}).get("id") or
                        ""
                    )
                    
                    # Определяем, является ли отправитель владельцем аккаунта (проверяем ДО обработки)
                    is_outgoing = False
                    
                    # Проверка 1: По sender_id
                    if starvell_user_id:
                        # Проверяем несколько вариантов сравнения ID
                        sender_id_str = str(sender_id) if sender_id else ""
                        starvell_id_str = str(starvell_user_id)
                        if sender_id_str == starvell_id_str or sender_id_str == starvell_id_str.strip():
                            is_outgoing = True
                    
                    # Проверка 2: По участникам чата (если sender_id не определен или не совпал)
                    if not is_outgoing and starvell_user_id:
                        participants = chat.get("participants", [])
                        starvell_username = user_info.get("username", "") if user_info else ""
                        for participant in participants:
                            participant_id = participant.get("id")
                            participant_username = participant.get("username", "")
                            # Если участник - это мы
                            if participant_id and str(participant_id) == str(starvell_user_id):
                                # Если у сообщения нет sender_id или он совпадает с нашим ID
                                if not sender_id or str(sender_id) == str(participant_id):
                                    is_outgoing = True
                                    break
                            # Также проверяем по username
                            elif participant_username and starvell_username and participant_username.lower() == starvell_username.lower():
                                if not sender_id:
                                    is_outgoing = True
                                    break
                    
                    # Проверка 3: По содержимому сообщения (всегда проверяем, так как sender_id может быть неправильным)
                    if not is_outgoing:
                        content_lower = content.lower() if content else ""
                        bot_phrases = [
                            "спасибо за покупку",
                            "напишите ваш telegram-тег",
                            "пример: @username",
                            "некорректный или несуществующий тег",
                            "отправьте верный telegram-тег",
                            "тег принят",
                            "отправляю",
                            "готово: отправлено",
                            "не удалось отправить",
                            "количество:",
                            "подтверди отправку",
                            "привет, это автоответчик",
                            "напиши \"+\" или \"да\"",
                            "напиши \"-\" или \"отмена\"",
                            "подтверди отправку:",
                            "пользователь найден",
                            "установите цену на геймпассе",
                            "после выставления геймпасса"
                        ]
                        if any(phrase in content_lower for phrase in bot_phrases):
                            # Вероятно, это сообщение от бота
                            is_outgoing = True
                    
                    # Если это исходящее сообщение от нас - пропускаем его
                    if is_outgoing:
                        last_messages[chat_id] = message_id
                        continue
                    
                    # Проверяем, есть ли в сообщении медиа или другие данные
                    has_image = bool(last_message.get("imageUrl") or last_message.get("image") or last_message.get("attachments"))
                    has_media = has_image or bool(last_message.get("media") or last_message.get("file"))
                    
                    # Пропускаем пустые сообщения без медиа
                    content_stripped = content.strip() if content else ""
                    if not content_stripped and not has_media:
                        last_messages[chat_id] = message_id
                        continue
                    
                    # Формируем текст для отображения
                    display_content = content_stripped if content_stripped else ("[медиа]" if has_media else "[пустое сообщение]")
                    
                    participants = chat.get("participants", [])
                    sender_name = "Unknown"
                    starvell_username = user_info.get("username", "Неизвестно") if user_info else "Неизвестно"
                    
                    if is_outgoing:
                        # Это исходящее сообщение от нас
                        sender_name = starvell_username
                    else:
                        # Это входящее сообщение от покупателя
                        if participants:
                            for participant in participants:
                                participant_id = participant.get("id")
                                if starvell_user_id and str(participant_id) == str(starvell_user_id):
                                    continue
                                username_candidate = participant.get("username") or ""
                                if username_candidate:
                                    sender_name = username_candidate
                                    break
                            if sender_name == "Unknown" and participants:
                                sender_name = participants[0].get("username") or participants[0].get("name", "Unknown")
                    
                    chat_name = chat.get("name", chat.get("username", ""))
                    if sender_name == "Unknown":
                        if chat_name:
                            sender_name = chat_name
                        else:
                            sender_name = "Unknown"
                    
                    log_message(chat_id, message_id, content, str(sender_id), created_at)
                    
                    from config import log_info
                    if is_outgoing:
                        # Исходящее сообщение от нас
                        log_info(f"┌── 📤 Исходящее сообщение в чате {chat_name if chat_name else sender_name}")
                        log_info(f"└───> {sender_name}: {display_content}")
                    else:
                        # Входящее сообщение от покупателя
                        log_info(f"┌── 💬 Входящее сообщение в чате {sender_name}")
                        log_info(f"└───> {sender_name}: {display_content}")
                    
                    last_messages[chat_id] = message_id
                    new_messages_found = True
                    
                    # Обрабатываем только входящие сообщения (не наши) и только если есть содержимое
                    if not is_outgoing and content_stripped:
                        try:
                            plugin_manager.run_handlers("BIND_TO_NEW_MESSAGE", chat_id, content, sender_id, created_at)
                        except Exception:
                            pass
                        
                        # Вызываем обработчики плагинов для сообщений (только для входящих, не от бота)
                        if not is_outgoing:
                            try:
                                # Обработчик для robux плагина
                                try:
                                    from plugins.robux import handle_new_message as robux_handle_new_message
                                    robux_handle_new_message(chat_id, content, sender_id, created_at)
                                except Exception:
                                    pass
                                
                                # Обработчик для autostars плагина
                                try:
                                    from plugins.autostars import handle_new_message as autostars_handle_new_message
                                    autostars_handle_new_message(chat_id, content, sender_id, created_at)
                                except Exception as e:
                                    from config import log_error
                                    log_error(f"Ошибка вызова обработчика autostars для сообщения: {e}")
                            except Exception:
                                pass
                        
                        if get_setting("notifications", "new_message", True):
                            authorized_users = load_authorized_users()
                            for user_id in authorized_users:
                                await send_new_message_notification(int(user_id), chat_id, content, sender_name)
                        
                        command = content.strip().lower().replace("\n", "")
                        commands_dict = get_auto_reply_commands_dict()
                        if command in commands_dict:
                            command_data = commands_dict[command]
                            response_text = command_data.get("response", "")
                            if response_text:
                                from datetime import datetime
                                date_obj = datetime.now()
                                date = date_obj.strftime("%d.%m.%Y")
                                time_ = date_obj.strftime("%H:%M")
                                time_full = date_obj.strftime("%H:%M:%S")
                                month_names = ["", "января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
                                month_name = month_names[date_obj.month]
                                str_date = f"{date_obj.day} {month_name}"
                                str_full_date = str_date + f" {date_obj.year} года"
                                
                                response_text = response_text.replace("$full_date_text", str_full_date)
                                response_text = response_text.replace("$date_text", str_date)
                                response_text = response_text.replace("$date", date)
                                response_text = response_text.replace("$time", time_)
                                response_text = response_text.replace("$full_time", time_full)
                                response_text = response_text.replace("$username", chat_name)
                                response_text = response_text.replace("$message_text", content)
                                response_text = response_text.replace("$chat_id", chat_id)
                                response_text = response_text.replace("$chat_name", chat_name)
                                
                                try:
                                    from StarvellAPI.send_message import send_chat_message
                                    result = await send_chat_message(session, chat_id, response_text, chat_name)
                                    
                                    if command_data.get("telegramNotification", 0) == 1:
                                        notification_text = command_data.get("notificationText", "")
                                        if not notification_text:
                                            notification_text = f"Пользователь {chat_name} ввел команду {command}."
                                        else:
                                            notification_text = notification_text.replace("$full_date_text", str_full_date)
                                            notification_text = notification_text.replace("$date_text", str_date)
                                            notification_text = notification_text.replace("$date", date)
                                            notification_text = notification_text.replace("$time", time_)
                                            notification_text = notification_text.replace("$full_time", time_full)
                                            notification_text = notification_text.replace("$username", chat_name)
                                            notification_text = notification_text.replace("$message_text", content)
                                            notification_text = notification_text.replace("$chat_id", chat_id)
                                            notification_text = notification_text.replace("$chat_name", chat_name)
                                        
                                        authorized_users = load_authorized_users()
                                        for user_id in authorized_users:
                                            try:
                                                await bot.send_message(int(user_id), f"🧑‍💻 {notification_text}")
                                            except Exception:
                                                pass
                                except Exception:
                                    pass
                    
                    # Отправляем welcome сообщение только для входящих сообщений
                    if not is_outgoing:
                        welcome_enabled = get_setting("welcome_message", "enabled", False)
                        if welcome_enabled:
                            try:
                                welcome_msg = get_setting("welcome_message", "message", "")
                                welcome_sent = load_welcome_sent()
                                if welcome_msg and chat_id not in welcome_sent:
                                    try:
                                        from StarvellAPI.send_message import send_chat_message
                                        await send_chat_message(session, chat_id, welcome_msg, chat_name)
                                        welcome_sent.add(chat_id)
                                        save_welcome_sent(welcome_sent)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
            
            except Exception as e:
                continue
        
        if new_messages_found:
            save_last_messages(last_messages)
    
    except Exception as e:
        pass


async def messages_checker():
    while True:
        try:
            await check_new_messages()
        except Exception:
            pass
        await asyncio.sleep(10)


async def send_new_order_notification(user_id: int, order_data: dict):
    """Отправляет уведомление о новом заказе пользователю"""
    try:
        offer = order_data.get("offerDetails", {})
        lot_title = offer.get("title") or offer.get("name") or "Неизвестный лот"
        
        user = order_data.get("user", {})
        buyer_username = user.get("username", "Неизвестно")
        
        # Сумма приходит в копейках, конвертируем в рубли
        total_price_raw = order_data.get("totalPrice") or order_data.get("basePrice", 0)
        total_price = float(total_price_raw) / 100.0 if total_price_raw else 0.0
        order_id = order_data.get("id", "")
        
        # Парсим ID заказа в короткий формат #893AD268
        short_order_id = order_id.replace("-", "").upper()
        if len(short_order_id) >= 8:
            short_order_id = f"#{short_order_id[-8:]}"
        else:
            short_order_id = f"#{short_order_id}"
        
        # Формируем текст уведомления
        text = (
            f"💠 <b>Новый заказ: {lot_title}</b>\n\n"
            f"💜 Покупатель: {buyer_username}\n"
            f"💵 Сумма: {total_price:.2f} ₽\n"
            f"📃 ID: {short_order_id}"
        )
        
        # Сохраняем buyer_id для использования в обработчиках
        buyer_id = user.get("id") or ""
        
        # Создаем инлайн кнопки
        order_url = f"https://starvell.com/order/{order_id}"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Перейти", url=order_url)],
            [
                InlineKeyboardButton(text="Ответить", callback_data=f"reply_order_{order_id}_{buyer_id}"),
                InlineKeyboardButton(text="Заготовки", callback_data=f"templates_order_{order_id}_{buyer_id}")
            ]
        ])
        
        await bot.send_message(user_id, text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        from config import log_error
        log_error(f"Ошибка отправки уведомления о заказе: {e}")


async def check_new_orders():
    """Проверяет новые заказы и отправляет уведомления"""
    from StarvellAPI.orders import fetch_sells
    
    session = get_session()
    if not session:
        return
    
    try:
        data = await fetch_sells(session)
        page_props = data.get("pageProps", {})
        orders = page_props.get("orders", [])
        
        if not orders:
            return
        
        processed_orders = load_processed_orders()
        new_orders_found = False

        # Если это первый запуск (нет сохранённых заказов), инициализируем список
        # текущими заказами без отправки уведомлений, чтобы не спамить старыми
        if not processed_orders:
            initial_ids = set()
            for order in orders:
                if (
                    isinstance(order, dict)
                    and order.get("id")
                    and order.get("status") in ("CREATED",)
                ):
                    initial_ids.add(order["id"])
            if initial_ids:
                save_processed_orders(initial_ids)
            return
        
        for order in orders:
            try:
                if not isinstance(order, dict):
                    continue
                
                order_id = order.get("id")
                status = order.get("status")
                
                if not order_id or status not in ("CREATED",):
                    continue
                
                # Проверяем, не обрабатывали ли мы уже этот заказ
                if order_id in processed_orders:
                    continue
                
                # Логируем новый заказ
                offer = order.get("offerDetails", {})
                category = offer.get("category", {})
                category_id = category.get("id") if isinstance(category, dict) else None
                lot_title = None
                # Пробуем извлечь название лота для Stars
                if category_id == 182:
                    try:
                        from plugins.autostars import _extract_star_lot_info
                        lot_title, _ = _extract_star_lot_info(order)
                    except Exception:
                        pass
                
                # Если не нашли через autostars, пробуем другие способы
                if not lot_title or lot_title == "Лот без названия":
                    lot_title = offer.get("title") or offer.get("name") or ""
                    if not lot_title:
                        subcat = offer.get("subCategory", {})
                        if isinstance(subcat, dict):
                            lot_title = subcat.get("name", "")
                    if not lot_title:
                        lot_title = offer.get("description", "")
                    if not lot_title:
                        # Пробуем из orderArgs
                        order_args = order.get("orderArgs", [])
                        if isinstance(order_args, list):
                            for arg in order_args:
                                if isinstance(arg, dict):
                                    for k, v in arg.items():
                                        if isinstance(v, str) and v:
                                            lot_title = v
                                            break
                                    if lot_title:
                                        break
                    if not lot_title:
                        lot_title = "Лот без названия"
                user = order.get("user", {})
                buyer_username = user.get("username", "Неизвестно")
                # Сумма приходит в копейках, конвертируем в рубли
                total_price_raw = order.get("totalPrice") or order.get("basePrice", 0)
                total_price = float(total_price_raw) / 100.0 if total_price_raw else 0.0
                
                from config import log_info
                # Парсим ID заказа в короткий формат #893AD268
                short_order_id = order_id.replace("-", "").upper()
                if len(short_order_id) >= 8:
                    short_order_id = f"#{short_order_id[-8:]}"
                else:
                    short_order_id = f"#{short_order_id}"
                log_info(f"💠 Новый заказ {short_order_id} | Покупатель: {buyer_username} | Лот: {lot_title} | Сумма: {total_price:.2f} ₽")
                
                # Отправляем уведомления авторизованным пользователям
                if get_setting("notifications", "new_order", True):
                    authorized_users = load_authorized_users()
                    for user_id in authorized_users:
                        try:
                            await send_new_order_notification(int(user_id), order)
                        except Exception:
                            pass
                
                # Вызываем обработчики плагинов
                try:
                    # Обработчик для robux плагина
                    try:
                        from plugins.robux import handle_new_order as robux_handle_new_order
                        user = order.get("user", {})
                        buyer_id = str(user.get("id", ""))
                        chat_id = str(order.get("chatId", buyer_id))
                        robux_handle_new_order(order_id, order, chat_id, buyer_id)
                    except Exception:
                        pass
                    
                    # Обработчик для autostars плагина
                    try:
                        from plugins.autostars import handle_new_order as autostars_handle_new_order
                        user = order.get("user", {})
                        buyer_id = str(user.get("id", ""))
                        chat_id = str(order.get("chatId", buyer_id))
                        autostars_handle_new_order(order_id, order, chat_id, buyer_id)
                    except Exception as e:
                        from config import log_error
                        log_error(f"Ошибка вызова обработчика autostars: {e}")
                except Exception:
                    pass
                
                # Добавляем заказ в список обработанных
                processed_orders.add(order_id)
                new_orders_found = True
                
            except Exception as e:
                continue
        
        if new_orders_found:
            save_processed_orders(processed_orders)
    
    except Exception as e:
        pass


async def orders_checker():
    """Периодическая проверка новых заказов"""
    while True:
        try:
            await check_new_orders()
        except Exception:
            pass
        await asyncio.sleep(15)


async def auto_bump_loop():
    from StarvellAPI.bump import bump_categories
    from StarvellAPI.auth import fetch_homepage_data
    import aiohttp
    import json
    
    while True:
        try:
            settings = get_settings()
            global_switches = settings.get("global_switches", {})
            auto_bump_enabled = global_switches.get("auto_bump", False)
            
            if not auto_bump_enabled:
                await asyncio.sleep(60)
                continue
            
            session = get_session()
            if not session:
                await asyncio.sleep(60)
                continue
            
            try:
                homepage_data = await fetch_homepage_data(session)
                if not homepage_data.get("authorized"):
                    await asyncio.sleep(300)
                    continue
                
                user_info = homepage_data.get("user", {})
                user_id = user_info.get("id")
                if not user_id:
                    await asyncio.sleep(300)
                    continue
                
                sid_cookie = homepage_data.get("sid")
                
                headers = {
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "accept-language": "ru,en;q=0.9",
                    "cache-control": "max-age=0",
                    "upgrade-insecure-requests": "1",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 YaBrowser/25.8.0.0 Safari/537.36",
                }
                cookies = {
                    "session": session,
                    "starvell.theme": "dark",
                    "starvell.time_zone": "Europe/Moscow",
                    "starvell.my_games": "10,1,11",
                }
                if sid_cookie:
                    cookies["sid"] = sid_cookie
                
                url = f"https://starvell.com/users/{user_id}"
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(headers=headers, cookies=cookies, timeout=timeout) as http_session:
                    async with http_session.get(url) as resp:
                        resp.raise_for_status()
                        html = await resp.text()
                
                marker = '<script id="__NEXT_DATA__" type="application/json">'
                idx = html.find(marker)
                if idx == -1:
                    await asyncio.sleep(300)
                    continue
                
                json_start = html.find('{', idx)
                if json_start == -1:
                    await asyncio.sleep(300)
                    continue
                
                json_end = html.find('</script>', json_start)
                if json_end == -1:
                    await asyncio.sleep(300)
                    continue
                
                data = json.loads(html[json_start:json_end])
                page_props = data.get("props", {}).get("pageProps", {})
                categories = page_props.get("categoriesWithOffers", [])
                
                game_to_categories = {}
                for category in categories:
                    game_id = category.get("gameId")
                    category_id = category.get("id")
                    if game_id and category_id:
                        if game_id not in game_to_categories:
                            game_to_categories[game_id] = set()
                        game_to_categories[game_id].add(category_id)
                
                if not game_to_categories:
                    await asyncio.sleep(300)
                    continue
                
                for game_id, category_ids in game_to_categories.items():
                    try:
                        result = await bump_categories(session, sid_cookie, game_id, list(category_ids))
                        if result.get("response", {}).get("success"):
                            from config import log_info
                            log_info(f"✅ Автоподнятие: поднято {len(category_ids)} категорий для игры {game_id}")
                        else:
                            from config import log_warning
                            log_warning(f"⚠️ Автоподнятие: ошибка для игры {game_id}")
                    except Exception as e:
                        from config import log_error
                        log_error(f"❌ Ошибка автоподнятия для игры {game_id}: {str(e)}")
                
                await asyncio.sleep(300)
            except Exception as e:
                from config import log_error
                log_error(f"❌ Ошибка в цикле автоподнятия: {str(e)}")
                await asyncio.sleep(300)
        except Exception:
            await asyncio.sleep(300)


async def init_starvell_account(init_message_ids: dict):
    global bot, starvell_initialized
    
    await asyncio.sleep(2)
    
    session = get_session()
    if not session:
        write_log("Ошибка инициализации Starvell: session не найден")
        return
    
    try:
        result = await fetch_homepage_data(session)
        if result.get("authorized"):
            user_info = result.get("user", {})
            username = user_info.get("username", "Неизвестно")
            starvell_user_id = user_info.get("id", "неизвестно")
            
            balance_rub = 0
            if isinstance(user_info.get("balance"), dict):
                balance_rub = user_info.get("balance", {}).get("rub", 0)
            elif user_info.get("balanceRub"):
                balance_rub = user_info.get("balanceRub", 0)
            elif user_info.get("balance"):
                balance_rub = user_info.get("balance", 0)
            
            try:
                import aiosqlite
                import os
                db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bot.sqlite3")
                async with aiosqlite.connect(db_path) as db:
                    await db.execute("PRAGMA foreign_keys = ON")
                    
                    await db.execute(
                        """
                        CREATE TABLE IF NOT EXISTS users (
                            user_id INTEGER PRIMARY KEY
                        )
                        """
                    )
                    
                    await db.execute(
                        """
                        CREATE TABLE IF NOT EXISTS accounts (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            starvell_username TEXT,
                            is_active INTEGER DEFAULT 0,
                            FOREIGN KEY (user_id) REFERENCES users(user_id)
                        )
                        """
                    )
                    
                    authorized_users = load_authorized_users()
                    for user_id_str in authorized_users:
                        try:
                            user_id_int = int(user_id_str)
                            
                            await db.execute(
                                "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
                                (user_id_int,)
                            )
                            
                            await db.execute(
                                """
                                INSERT OR IGNORE INTO accounts (user_id, starvell_username, is_active)
                                VALUES (?, ?, 1)
                                """,
                                (user_id_int, username)
                            )
                            
                            await db.execute(
                                """
                                UPDATE accounts 
                                SET starvell_username = ?, is_active = 1
                                WHERE user_id = ?
                                """,
                                (username, user_id_int)
                            )
                        except Exception:
                            pass
                    
                    await db.commit()
            except Exception as e:
                write_log(f"Ошибка создания записей в БД: {str(e)}")
            
            text = f"""✅ <b>Starvell Tipzy запущен!</b>

👑 <b>Профиль:</b> {username}
💰 <b>Баланс:</b> {balance_rub}₽

💬 <b>Чат Telegram:</b> <a href="https://t.me/+tUk3VYLlo20yZGZi">@TipzyChat</a>
🧩 <b>Плагины:</b> <a href="https://t.me/+qeS_88mIElE2YmFi">@TipzyPlugin</a>
👨‍💻 <b>Разработчик:</b> @totodiemono"""
            
            starvell_initialized = True
            
            if get_setting("notifications", "bot_start", True):
                authorized_users = load_authorized_users()
                for user_id in authorized_users:
                    try:
                        user_id_int = int(user_id)
                        link_preview_options = LinkPreviewOptions(is_disabled=True)
                        if user_id_int in init_message_ids:
                            try:
                                await bot.edit_message_text(
                                    text,
                                    chat_id=user_id_int,
                                    message_id=init_message_ids[user_id_int],
                                    parse_mode="HTML",
                                    link_preview_options=link_preview_options
                                )
                            except Exception:
                                await bot.send_message(user_id_int, text, parse_mode="HTML", link_preview_options=link_preview_options)
                        else:
                            await bot.send_message(user_id_int, text, parse_mode="HTML", link_preview_options=link_preview_options)
                    except Exception as e:
                        write_log(f"Ошибка отправки сообщения пользователю {user_id}: {str(e)}")
            
            from config import log_info, Colors, get_timestamp
            
            log_info("")
            log_info(f"✨ {Colors.GREEN}Добро пожаловать,{Colors.RESET} {Colors.CYAN}{username}{Colors.RESET}.")
            log_info(f"🆔 {Colors.GREEN}Ваш ID:{Colors.RESET} {Colors.CYAN}{starvell_user_id}{Colors.RESET}.")
            log_info(f"💰 {Colors.GREEN}Баланс:{Colors.RESET} {Colors.CYAN}{balance_rub} RUB{Colors.RESET}.")
            log_info(f"🚀 {Colors.GREEN}Удачной торговли!{Colors.RESET}")
            
            write_log(f"Starvell аккаунт инициализирован: {username}, баланс: {balance_rub}")
        else:
            write_log("Ошибка инициализации Starvell: не авторизован")
    except Exception as e:
        write_log(f"Ошибка инициализации Starvell: {str(e)}")


async def main():
    global bot
    
    print(Fore.LIGHTBLUE_EX + LOGO + Style.RESET_ALL)
    print("By totodiemono")
    print(" * Telegram: t.me/totodiemono")
    print(" * Плагины: t.me/tipzyfree")
    print()
    
    from config import load_main_config, log_info, log_error
    load_main_config(show_log=True)

    latest_version = await get_latest_version_from_github()
    
    # Если версия не получена, пропускаем проверку
    if not latest_version:
        log_info("Не удалось получить версию с GitHub. Проверка обновлений пропущена.")
    else:
        # Нормализуем версии для корректного сравнения
        if isinstance(latest_version, str) and isinstance(VERSION, str):
            _v_local = VERSION.strip()
            _v_remote = latest_version.strip()
            
            if _v_local == _v_remote:
                log_info("Обновлений не найдено.")
            else:
                log_info(f"{Colors.BLUE}Найдено обновление {latest_version}. для установки напишите /update.{Colors.RESET}")
        else:
            # Если версия не строка, считаем что обновлений нет
            log_info("Обновлений не найдено (неверный формат версии).")
    
    token = get_bot_token_cached()
    if not token:
        token = input("Введите токен бота: ").strip()
        if not token:
            log_error("BOT_TOKEN обязателен для работы бота")
            return
        set_bot_token(token)
        write_log("Токен бота установлен")
    
    if not is_configured():
        password = input("Введите пароль для бота: ").strip()
        if not password:
            log_error("Пароль обязателен для работы бота")
            return
        set_password(password)
        write_log("Пароль бота установлен")
        
        session = input("Введите session куки для Starvell: ").strip()
        if not session:
            log_error("Session обязателен для работы бота")
            return
        
        try:
            result = await fetch_homepage_data(session)
            if result.get("authorized"):
                set_session(session)
                user_info = result.get("user", {})
                username = user_info.get("username", "Неизвестно")
                log_info(f"Авторизация успешна: {username}")
                write_log(f"Session Starvell установлен для пользователя: {username}")
            else:
                log_error("Авторизация не удалась. Проверьте правильность session куки.")
                return
        except Exception as e:
            log_error(f"Ошибка при проверке авторизации: {str(e)}")
            write_log(f"Ошибка при проверке авторизации: {str(e)}")
            return
    
    bot = Bot(token=token)
    dp.bot = bot
    
    plugin_manager.load_plugins()
    plugin_manager.add_handlers()
    
    # Устанавливаем bot_info до инициализации плагинов, чтобы они могли получить TG ID
    global bot_info
    bot_info = await bot.get_me()
    
    for uuid, plugin_data in plugin_manager.get_all_plugins().items():
        plugin_module = plugin_data.plugin
        
        if hasattr(plugin_module, "init_plugin"):
            try:
                if asyncio.iscoroutinefunction(plugin_module.init_plugin):
                    asyncio.create_task(plugin_module.init_plugin())
                else:
                    plugin_module.init_plugin()
            except Exception as e:
                log_error(f"Ошибка вызова init_plugin для плагина {plugin_data.name}: {e}")
        
        if hasattr(plugin_module, "router"):
            router = plugin_module.router
            if router:
                dp.include_router(router)
    log_info(f"Telegram бот @{bot_info.username} запущен.")
    write_log(f"Бот @{bot_info.username} запущен и готов к работе")
    
    init_message_text = """✅ Бот работает.

⏳ Starvell Tipzy пока не запущен — его функции не активны.

🔄 Всё заработает, когда модуль инициализируется.

📄 Если процесс затянется, проверьте состояние через /logs."""
    
    init_message_ids = {}
    if get_setting("notifications", "bot_start", True):
        authorized_users = load_authorized_users()
        for user_id in authorized_users:
            try:
                msg = await bot.send_message(int(user_id), init_message_text)
                init_message_ids[int(user_id)] = msg.message_id
            except Exception:
                pass
    
    asyncio.create_task(init_starvell_account(init_message_ids))
    
    asyncio.create_task(messages_checker())
    
    asyncio.create_task(orders_checker())
    
    asyncio.create_task(auto_bump_loop())
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

