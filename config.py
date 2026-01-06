import os
import configparser
from pathlib import Path
from datetime import datetime
from colorama import Fore, Style, init
init(autoreset=True)
CONFIG_DIR = Path('config')
CONFIG_DIR.mkdir(exist_ok=True)
MAIN_CFG_FILE = CONFIG_DIR / 'main.cfg'
DATA_FILE = CONFIG_DIR / 'data.json'
AUTHORIZED_USERS_FILE = DATA_FILE

class Colors:
    GREEN = Fore.GREEN
    YELLOW = Fore.YELLOW
    RED = Fore.RED
    BLUE = Fore.BLUE
    CYAN = Fore.CYAN
    RESET = Style.RESET_ALL

def get_timestamp():
    return datetime.now().strftime('[%d-%m-%Y %H:%M:%S]')

def is_logging_enabled() -> bool:
    try:
        from pathlib import Path
        import json
        config_dir = Path('config')
        settings_file = config_dir / 'settings.json'
        if settings_file.exists():
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                global_switches = settings.get('global_switches', {})
                return global_switches.get('logging', True)
        return True
    except Exception:
        return True

def write_log_to_file(message: str, level: str='I'):
    if not is_logging_enabled():
        return
    try:
        from pathlib import Path
        logs_dir = Path('logs')
        logs_dir.mkdir(exist_ok=True)
        log_file = logs_dir / 'log.log'
        timestamp = get_timestamp()
        log_entry = f'{timestamp}> {level}: {message}\n'
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception:
        pass

def log_info(message: str):
    print(f'{get_timestamp()}> {Colors.GREEN}I: {message}{Colors.RESET}')
    write_log_to_file(message, 'I')

def log_warning(message: str):
    print(f'{get_timestamp()}> {Colors.YELLOW}W: {message}{Colors.RESET}')
    write_log_to_file(message, 'W')

def log_error(message: str):
    print(f'{get_timestamp()}> {Colors.RED}E: {message}{Colors.RESET}')
    write_log_to_file(message, 'E')

def create_default_config():
    config = configparser.ConfigParser()
    config.add_section('Bot')
    config.set('Bot', 'token', '')
    config.set('Bot', 'password', '')
    config.add_section('Starvell')
    config.set('Starvell', 'session', '')
    return config
_main_config_cache = None

def load_main_config(show_log: bool=False):
    global _main_config_cache
    if _main_config_cache is not None:
        return _main_config_cache
    config = configparser.ConfigParser()
    if not MAIN_CFG_FILE.exists():
        config = create_default_config()
        save_main_config(config)
    else:
        config.read(MAIN_CFG_FILE, encoding='utf-8')
    _main_config_cache = config
    if show_log:
        log_info('Конфиг main.cfg загружен.')
    return config

def save_main_config(config: configparser.ConfigParser):
    global _main_config_cache
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(MAIN_CFG_FILE, 'w', encoding='utf-8') as f:
        config.write(f)
    _main_config_cache = config

def get_bot_token() -> str:
    config = load_main_config(show_log=False)
    token = config.get('Bot', 'token', fallback='')
    if not token:
        token = os.getenv('BOT_TOKEN', '')
    return token

def set_bot_token(token: str) -> None:
    config = load_main_config(show_log=False)
    config.set('Bot', 'token', token)
    save_main_config(config)

def get_session() -> str:
    config = load_main_config(show_log=False)
    return config.get('Starvell', 'session', fallback='')

def set_session(session: str) -> None:
    config = load_main_config(show_log=False)
    config.set('Starvell', 'session', session)
    save_main_config(config)

def get_password() -> str:
    config = load_main_config(show_log=False)
    return config.get('Bot', 'password', fallback='')

def set_password(password: str) -> None:
    config = load_main_config(show_log=False)
    config.set('Bot', 'password', password)
    save_main_config(config)

def is_configured() -> bool:
    config = load_main_config(show_log=False)
    password = config.get('Bot', 'password', fallback='')
    session = config.get('Starvell', 'session', fallback='')
    return bool(password and session)

def get_bot_token_cached() -> str:
    return get_bot_token()
BOT_TOKEN = ''