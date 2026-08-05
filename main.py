"""Entry point dell'app: finestra pywebview + js_api."""
import os
import sys

import webview

import capture
from api import Api

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))


def resource_dir() -> str:
    """Asset in sola lettura (frontend/). Nell'exe onefile PyInstaller li
    estrae in una cartella temporanea indicata da sys._MEIPASS.
    """
    return getattr(sys, "_MEIPASS", SOURCE_DIR)


def data_dir() -> str:
    """Dati dell'utente (DB cifrato, salt, config di backup).

    Non possono stare in _MEIPASS: quella cartella viene cancellata a ogni
    uscita e il vault sparirebbe. Nell'exe finiscono in %APPDATA%\\Ledger,
    in sviluppo restano accanto al sorgente. Sempre e solo su disco locale.
    """
    if getattr(sys, "frozen", False):
        base = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Ledger")
        os.makedirs(base, exist_ok=True)
        return base
    return SOURCE_DIR


def main():
    api = Api(db_path=os.path.join(data_dir(), "ledger.db"))
    index_path = os.path.join(resource_dir(), "frontend", "index.html")

    window = webview.create_window(
        "Ledger",
        index_path,
        js_api=api,
        width=1200,
        height=800,
        min_size=(800, 600),
    )

    # Senza questo il DB cifrato non verrebbe mai riscritto su disco: le
    # modifiche restano nel file temporaneo e si perdono alla chiusura.
    # close_vault e' idempotente, quindi chiamarlo due volte non nuoce.
    window.events.closed += api.close_vault

    # Se il sistema nega l'hook di tastiera l'app deve partire lo stesso:
    # si perde la quick capture, non l'accesso alle note.
    capture.register_hotkey(api, resource_dir())

    try:
        webview.start(gui="edgechromium")
    finally:
        # Ultima rete di sicurezza: un'uscita anomala non deve lasciare su
        # disco un vault piu' vecchio della sessione appena conclusa.
        api.close_vault()


if __name__ == "__main__":
    main()
