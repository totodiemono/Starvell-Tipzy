import importlib.util
import sys
import os
from uuid import UUID
from typing import Optional, Dict, Any, Callable, List
from types import ModuleType
from pathlib import Path
PLUGINS_DIR = Path('plugins')
PLUGINS_DIR.mkdir(exist_ok=True)
from config import log_info, log_warning, log_error, Colors
GH = 'https://github.com/totodiemono/Starvell-Tipzy'

class PluginData:

    def __init__(self, name: str, version: str, desc: str, credits: str, uuid: str, path: str, plugin: ModuleType, settings_page: bool, delete_handler: Callable | None, enabled: bool):
        self.name = name
        self.version = version
        self.description = desc
        self.credits = credits
        self.uuid = uuid
        self.path = path
        self.plugin = plugin
        self.settings_page = settings_page
        self.commands = {}
        self.delete_handler = delete_handler
        self.enabled = enabled

class PluginManager:

    def __init__(self):
        self.plugins: Dict[str, PluginData] = {}
        self.disabled_plugins = self._load_disabled_plugins()
        self.handlers = {'BIND_TO_NEW_MESSAGE': [], 'BIND_TO_NEW_ORDER': []}

    def _load_disabled_plugins(self) -> List[str]:
        try:
            import json
            from config import CONFIG_DIR
            disabled_file = CONFIG_DIR / 'disabled_plugins.json'
            if disabled_file.exists():
                with open(disabled_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_disabled_plugins(self):
        try:
            import json
            from config import CONFIG_DIR
            disabled_file = CONFIG_DIR / 'disabled_plugins.json'
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(disabled_file, 'w', encoding='utf-8') as f:
                json.dump(self.disabled_plugins, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def is_uuid_valid(uuid: str) -> bool:
        try:
            uuid_obj = UUID(uuid, version=4)
            return str(uuid_obj) == uuid
        except ValueError:
            return False

    @staticmethod
    def is_plugin(file: str) -> bool:
        file_path = PLUGINS_DIR / file
        if not file_path.exists():
            return False
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                line = f.readline()
            if line.startswith('#'):
                line = line.replace('\n', '')
                args = line.split()
                if 'noplug' in args:
                    return False
        except Exception:
            return False
        return True

    @staticmethod
    def load_plugin(from_file: str) -> tuple:
        file_path = PLUGINS_DIR / from_file
        spec = importlib.util.spec_from_file_location(f'plugins.{from_file[:-3]}', str(file_path))
        plugin = importlib.util.module_from_spec(spec)
        sys.modules[f'plugins.{from_file[:-3]}'] = plugin
        spec.loader.exec_module(plugin)
        required_fields = ['NAME', 'VERSION', 'DESCRIPTION', 'CREDITS', 'UUID']
        optional_fields = {'SETTINGS_PAGE': False, 'BIND_TO_DELETE': None, 'COMMANDS': {}}
        result = {}
        for i in required_fields:
            try:
                value = getattr(plugin, i)
            except AttributeError:
                raise Exception(f'Поле {i} не найдено в плагине {from_file}')
            result[i] = value
        for i, default_value in optional_fields.items():
            try:
                value = getattr(plugin, i)
                result[i] = value
            except AttributeError:
                result[i] = default_value
        return (plugin, result)

    def load_plugins(self):
        if not PLUGINS_DIR.exists():
            return
        self.plugins.clear()
        plugins = [file for file in os.listdir(PLUGINS_DIR) if file.endswith('.py') and file != '__init__.py']
        if not plugins:
            return
        sys.path.insert(0, str(PLUGINS_DIR))
        for file in plugins:
            plugin_name = file
            try:
                if not self.is_plugin(file):
                    continue
                plugin, data = self.load_plugin(file)
                plugin_name = data.get('NAME', file)
            except Exception as e:
                log_error(f'Ошибка инициализации плагина {file}: {e}')
                continue
            if not self.is_uuid_valid(data['UUID']):
                log_error(f'Ошибка инициализации плагина {plugin_name}: невалидный UUID')
                continue
            if data['UUID'] in self.plugins:
                log_error(f'Ошибка инициализации плагина {plugin_name}: UUID {data['UUID']} уже зарегистрирован')
                continue
            plugin_data = PluginData(data['NAME'], data['VERSION'], data['DESCRIPTION'], data['CREDITS'], data['UUID'], str(PLUGINS_DIR / file), plugin, data.get('SETTINGS_PAGE', False), data.get('BIND_TO_DELETE', None), False if data['UUID'] in self.disabled_plugins else True)
            commands = data.get('COMMANDS', {})
            if isinstance(commands, dict):
                plugin_data.commands = commands
            self.plugins[data['UUID']] = plugin_data
            log_info(f'{Colors.YELLOW}Плагин {plugin_data.name} загружен.{Colors.RESET}')

    def add_handlers_from_plugin(self, plugin: ModuleType, uuid: Optional[str]=None):
        for handler_name in self.handlers.keys():
            try:
                functions = getattr(plugin, handler_name, [])
                if isinstance(functions, list):
                    for func in functions:
                        func.plugin_uuid = uuid
                    self.handlers[handler_name].extend(functions)
            except AttributeError:
                continue

    def add_handlers(self):
        for handler_name in self.handlers.keys():
            self.handlers[handler_name].clear()
        for uuid in self.plugins:
            plugin = self.plugins[uuid].plugin
            self.add_handlers_from_plugin(plugin, uuid)

    def run_handlers(self, handler_name: str, *args):
        handlers_list = self.handlers.get(handler_name, [])
        for func in handlers_list:
            try:
                plugin_uuid = getattr(func, 'plugin_uuid', None)
                if plugin_uuid is None or (plugin_uuid in self.plugins and self.plugins[plugin_uuid].enabled):
                    func(*args)
            except Exception as e:
                log_error(f'Ошибка выполнения хэндлера {func.__name__}: {e}')
                continue

    def toggle_plugin(self, uuid: str):
        if uuid not in self.plugins:
            return False
        self.plugins[uuid].enabled = not self.plugins[uuid].enabled
        if self.plugins[uuid].enabled and uuid in self.disabled_plugins:
            self.disabled_plugins.remove(uuid)
        elif not self.plugins[uuid].enabled and uuid not in self.disabled_plugins:
            self.disabled_plugins.append(uuid)
        self._save_disabled_plugins()
        return True

    def get_plugin(self, uuid: str) -> Optional[PluginData]:
        return self.plugins.get(uuid)

    def get_all_plugins(self) -> Dict[str, PluginData]:
        return self.plugins.copy()
plugin_manager = PluginManager()