import os
import shutil
import zipfile
from pathlib import Path
import requests
from main import GH as GITHUB

def download_and_extract_latest_release(target_dir: Path) -> str | None:
    if not GITHUB:
        return None
    api_url = GITHUB.rstrip('/').replace('https://github.com/', 'https://api.github.com/repos/') + '/zipball/main'
    target_dir.mkdir(parents=True, exist_ok=True)
    zip_path = target_dir / 'update_tmp.zip'
    try:
        resp = requests.get(api_url, timeout=60, stream=True)
        resp.raise_for_status()
        with open(zip_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            root_name = zf.namelist()[0].split('/')[0]
            extract_path = target_dir / 'update_tmp'
            if extract_path.exists():
                shutil.rmtree(extract_path, ignore_errors=True)
            zf.extractall(extract_path)
        os.remove(zip_path)
        return str(extract_path / root_name)
    except Exception:
        if zip_path.exists():
            try:
                os.remove(zip_path)
            except Exception:
                pass
        return None

def install_update_from_path(source_root: Path, base_dir: Path | None=None) -> None:
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent.parent
    skip_names = {'.git', 'logs', 'config', 'помощь', '__pycache__', '.venv', 'venv', 'README.MD', 'README.md', 'README'}
    for item in source_root.iterdir():
        name = item.name
        if name in skip_names:
            continue
        target = base_dir / name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(item, target)
        elif item.is_file():
            if target.exists():
                os.remove(target)
            shutil.copy2(item, target)