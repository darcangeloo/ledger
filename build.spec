# -*- mode: python ; coding: utf-8 -*-
"""Build PyInstaller: eseguibile singolo, nessuna finestra di console.

    pyinstaller build.spec --noconfirm

Il risultato e' dist/Ledger.exe, autosufficiente. Il frontend (bundle JS
gia' compilati da `npm run build`) viene incluso nell'eseguibile; il DB
cifrato NON sta qui dentro: vive in %APPDATA%\\Ledger, altrimenti verrebbe
cancellato a ogni uscita insieme alla cartella temporanea di estrazione.
"""

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    # Tutto il frontend viaggia dentro l'exe: nessun file caricato dalla rete.
    datas=[
        ("frontend/index.html", "frontend"),
        ("frontend/capture.html", "frontend"),
        ("frontend/style.css", "frontend"),
        ("frontend/editor.bundle.js", "frontend"),
        ("frontend/mermaid_view.bundle.js", "frontend"),
        ("frontend/views", "frontend/views"),
        ("frontend/ledger.ico", "frontend"),
    ],
    hiddenimports=[
        # pywebview sceglie il backend a runtime: senza questi PyInstaller
        # non li vede come import statici e l'exe parte senza GUI.
        "webview.platforms.edgechromium",
        "clr_loader",
        "pythonnet",
        # hotkey globale della quick capture
        "keyboard",
        # cifratura a riposo
        "cryptography.hazmat.primitives.kdf.pbkdf2",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # backend pywebview non usati su Windows: pesano e non servono
        "webview.platforms.cocoa",
        "webview.platforms.gtk",
        "webview.platforms.qt",
        "tkinter",
        # presente per generare l'icona, non serve a runtime
        "PIL",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Ledger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="frontend/ledger.ico",
)
