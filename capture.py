"""Quick capture globale: hotkey OS-level + mini-finestra pywebview
separata, utilizzabile anche ad app principale minimizzata o in secondo
piano. Salva come blocco type='text' con properties.inbox=True, nessuna
tabella nuova.

L'hotkey vive nel processo di Ledger: funziona con la finestra
minimizzata o dietro altre applicazioni, non ad app chiusa.
"""
from __future__ import annotations

import os
import threading

import webview

HOTKEY = "ctrl+shift+space"

_capture_window = None
_lock = threading.Lock()

# Slot prenotato mentre la finestra viene creata: impedisce che una seconda
# pressione dell'hotkey ne apra un'altra nel frattempo.
_PENDING = object()


class CaptureApi:
    """js_api minimale per la mini-finestra: salva e si chiude."""

    def __init__(self, main_api):
        self._main_api = main_api

    def save_capture(self, text: str) -> dict:
        if not text or not text.strip():
            return {"ok": True, "saved": False}
        try:
            self._main_api.create_block("text", None, {"text": text.strip()}, {"inbox": True})
        except Exception:
            # Vault ancora bloccato (o errore di scrittura): il testo resta
            # nella finestra, che non deve chiudersi buttandolo via.
            return {
                "ok": False,
                "error": "Ledger e' bloccato: sbloccalo e riprova, il testo resta qui.",
            }
        return {"ok": True, "saved": True}

    def close(self) -> dict:
        _destroy_capture_window()
        return {"ok": True}


def _destroy_capture_window() -> None:
    global _capture_window
    with _lock:
        window, _capture_window = _capture_window, None
    if window is None or window is _PENDING:
        return
    try:
        window.destroy()
    except Exception:
        pass


def _open_capture_window(main_api, base_dir: str) -> None:
    """Apre la mini-finestra, o la porta in primo piano se gia' aperta.

    La prenotazione dello slot avviene dentro il lock prima di creare la
    finestra: due pressioni ravvicinate dell'hotkey non devono aprire due
    finestre sovrapposte.
    """
    global _capture_window
    with _lock:
        if _capture_window is not None:
            return
        _capture_window = _PENDING

    capture_path = os.path.join(base_dir, "frontend", "capture.html")
    try:
        window = webview.create_window(
            "Quick Capture",
            capture_path,
            js_api=CaptureApi(main_api),
            width=420,
            height=180,
            on_top=True,
        )
    except Exception:
        with _lock:
            _capture_window = None
        return

    def _on_closed():
        global _capture_window
        with _lock:
            _capture_window = None

    window.events.closed += _on_closed

    with _lock:
        # Se nel frattempo la finestra e' gia' stata chiusa, non riscrivere
        # uno slot occupato da un riferimento morto.
        if _capture_window is _PENDING:
            _capture_window = window


def register_hotkey(main_api, base_dir: str) -> bool:
    """Registra l'hotkey globale. Ritorna False se il sistema non lo
    consente (hook di tastiera bloccato da criteri o antivirus): la quick
    capture si perde, l'app parte lo stesso.
    """
    try:
        import keyboard

        keyboard.add_hotkey(HOTKEY, lambda: _open_capture_window(main_api, base_dir))
    except Exception:
        return False
    return True
