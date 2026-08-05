"""Cifratura a riposo del DB blocchi.

sqlcipher3 non e' disponibile su Windows senza toolchain di compilazione,
quindi si usa il fallback previsto da CLAUDE.md: l'intero file SQLite viene
cifrato con Fernet (AES-128-CBC + HMAC-SHA256, chiave derivata da
passphrase con PBKDF2-HMAC-SHA256).

Il database vive esclusivamente in memoria (`sqlite3` :memory: con
serialize/deserialize). Nessuna copia in chiaro tocca mai il disco: e' la
differenza sostanziale rispetto all'approccio con file temporaneo, dove un
arresto anomalo lasciava il database leggibile in %TEMP% a chiunque.

Limiti noti, documentati in SECURITY.md:
- la passphrase e la chiave derivata restano in memoria di processo per
  tutta la sessione (inevitabile: servono a ogni salvataggio);
- il numero di iterazioni PBKDF2 e' una costante del formato: cambiarlo
  rende illeggibili i vault esistenti.
"""
from __future__ import annotations

import base64
import os
import secrets
import sqlite3

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Non modificare senza una procedura di migrazione: i vault esistenti sono
# stati cifrati con questo valore e diventerebbero indecifrabili.
KDF_ITERATIONS = 480_000
SALT_BYTES = 16
SALT_SUFFIX = ".salt"

MIN_PASSPHRASE_LENGTH = 8


class WrongPassphraseError(Exception):
    pass


class VaultCorruptedError(Exception):
    pass


class WeakPassphraseError(Exception):
    pass


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def _salt_path(db_path: str) -> str:
    return db_path + SALT_SUFFIX


def is_first_run(db_path: str) -> bool:
    return not os.path.exists(db_path)


def _init_salt(db_path: str) -> bytes:
    salt = secrets.token_bytes(SALT_BYTES)
    directory = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(directory, exist_ok=True)
    with open(_salt_path(db_path), "wb") as f:
        f.write(salt)
        f.flush()
        os.fsync(f.fileno())
    return salt


def _load_salt(db_path: str) -> bytes:
    path = _salt_path(db_path)
    if not os.path.exists(path):
        raise VaultCorruptedError(
            "Manca il file .salt accanto al database. Senza di quello il vault "
            "non e' decifrabile: recuperalo dal backup insieme al .db."
        )
    with open(path, "rb") as f:
        salt = f.read()
    if len(salt) != SALT_BYTES:
        raise VaultCorruptedError("Il file .salt e' danneggiato o incompleto.")
    return salt


class EncryptedDatabase:
    """DB SQLite in memoria, cifrato su disco a ogni salvataggio.

        edb = EncryptedDatabase("ledger.db")
        conn = edb.open(passphrase)
        ...
        edb.close()
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._key: bytes | None = None
        self.conn: sqlite3.Connection | None = None

    def open(self, passphrase: str) -> sqlite3.Connection:
        first_run = is_first_run(self.db_path)

        if first_run and len(passphrase) < MIN_PASSPHRASE_LENGTH:
            raise WeakPassphraseError(
                f"Servono almeno {MIN_PASSPHRASE_LENGTH} caratteri. "
                "Chi ottiene il file puo' provare passphrase a volonta' senza limiti."
            )

        salt = _init_salt(self.db_path) if first_run else _load_salt(self.db_path)
        self._key = _derive_key(passphrase, salt)

        # check_same_thread=False: la quick capture e la finestra principale
        # invocano js_api da thread diversi.
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row

        if not first_run:
            with open(self.db_path, "rb") as f:
                encrypted = f.read()
            try:
                plain = Fernet(self._key).decrypt(encrypted)
            except InvalidToken as exc:
                conn.close()
                self._key = None
                raise WrongPassphraseError("Passphrase errata, oppure il file e' danneggiato") from exc
            try:
                conn.deserialize(plain)
            except sqlite3.Error as exc:
                conn.close()
                self._key = None
                raise VaultCorruptedError("Il contenuto decifrato non e' un database valido.") from exc

        self.conn = conn
        return self.conn

    def save(self) -> None:
        """Cifra lo stato corrente su disco. La connessione resta aperta."""
        if self.conn is None or self._key is None:
            return
        self.conn.commit()

        encrypted = Fernet(self._key).encrypt(self.conn.serialize())

        # Scrittura atomica: un'interruzione lascia intatto il file precedente
        # invece di troncarlo a meta'.
        tmp_path = self.db_path + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(encrypted)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.db_path)

    def close(self) -> None:
        if self.conn is None:
            return
        try:
            self.save()
        finally:
            self.conn.close()
            self.conn = None
            self._key = None
