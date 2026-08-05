"""Backup cifrato locale: copia del DB gia' cifrato a riposo (+ salt)
su un percorso locale scelto dall'utente. Mai upload in rete.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime

CONFIG_SUFFIX = ".backup_config.json"


def _config_path(db_path: str) -> str:
    return db_path + CONFIG_SUFFIX


def read_config(db_path: str) -> dict:
    """Config di backup, o dict vuoto. Un file corrotto (arresto anomalo a
    meta' scrittura) non deve impedire l'avvio ne' la chiusura dell'app:
    vale come "nessun backup configurato" e viene riscritto al prossimo.
    """
    path = _config_path(db_path)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, ValueError):
        return {}
    return config if isinstance(config, dict) else {}


def write_config(db_path: str, config: dict) -> None:
    with open(_config_path(db_path), "w", encoding="utf-8") as f:
        json.dump(config, f)


def backup_now(db_path: str, dest_dir: str) -> str:
    """Copia il DB cifrato (+ salt) in dest_dir con timestamp. Ritorna il
    percorso del file copiato. Non tocca mai la rete: solo filesystem
    locale (anche un drive esterno montato va bene, resta locale).
    """
    os.makedirs(dest_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.basename(db_path)

    dest_db = os.path.join(dest_dir, f"{base_name}.{timestamp}.bak")
    shutil.copy2(db_path, dest_db)

    salt_path = db_path + ".salt"
    if os.path.exists(salt_path):
        dest_salt = os.path.join(dest_dir, f"{base_name}.salt.{timestamp}.bak")
        shutil.copy2(salt_path, dest_salt)

    config = read_config(db_path)
    config["backup_dir"] = dest_dir
    config["last_backup"] = datetime.now().isoformat()
    write_config(db_path, config)

    return dest_db


def auto_backup_if_configured(db_path: str) -> None:
    """Backup silenzioso su chiusura, solo se l'utente ha gia' scelto una
    cartella in precedenza. Errori (drive scollegato, ecc.) non devono
    mai bloccare la chiusura dell'app.
    """
    config = read_config(db_path)
    dest_dir = config.get("backup_dir")
    if not dest_dir:
        return
    try:
        backup_now(db_path, dest_dir)
    except OSError:
        pass
