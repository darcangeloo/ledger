<#
    Installa Ledger per l'utente corrente.

        powershell -ExecutionPolicy Bypass -File install.ps1

    Copia Ledger.exe in %LOCALAPPDATA%\Programs\Ledger e crea i
    collegamenti su Desktop e nel menu Start. Nessun diritto di
    amministratore, nessuna scrittura fuori dal profilo utente, nessuna
    connessione di rete.

    Il vault cifrato vive in %APPDATA%\Ledger e non viene mai toccato:
    reinstallare o disinstallare non cancella le tue note.
#>

[CmdletBinding()]
param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$AppName    = "Ledger"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\$AppName"
$ExePath    = Join-Path $InstallDir "$AppName.exe"
$DesktopLnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "$AppName.lnk"
$StartLnk   = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\$AppName.lnk"
$DataDir    = Join-Path $env:APPDATA $AppName

function Write-Step($Message) {
    Write-Host "  $Message"
}

if ($Uninstall) {
    Write-Host "Rimozione di $AppName"

    foreach ($lnk in @($DesktopLnk, $StartLnk)) {
        if (Test-Path $lnk) {
            Remove-Item $lnk -Force
            Write-Step "Collegamento rimosso: $lnk"
        }
    }

    if (Test-Path $InstallDir) {
        Remove-Item $InstallDir -Recurse -Force
        Write-Step "Programma rimosso: $InstallDir"
    }

    Write-Host ""
    Write-Host "Fatto. Le tue note restano in $DataDir."
    Write-Host "Per cancellare anche quelle, elimina a mano quella cartella."
    return
}

# --- verifica che ci sia qualcosa da installare ---

$Source = Join-Path $PSScriptRoot "dist\$AppName.exe"
if (-not (Test-Path $Source)) {
    Write-Host "Non trovo dist\$AppName.exe."
    Write-Host "Compila prima l'eseguibile:"
    Write-Host ""
    Write-Host "    npm run build"
    Write-Host "    pyinstaller build.spec --noconfirm"
    exit 1
}

# --- se e' in esecuzione la copia fallirebbe a meta' ---

$running = Get-Process -Name $AppName -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "$AppName e' aperto. Chiudilo e rilancia l'installazione."
    exit 1
}

Write-Host "Installazione di $AppName"

if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}
Copy-Item $Source $ExePath -Force
Write-Step "Programma copiato in $InstallDir"

$shell = New-Object -ComObject WScript.Shell
foreach ($target in @($DesktopLnk, $StartLnk)) {
    $parent = Split-Path $target -Parent
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $shortcut = $shell.CreateShortcut($target)
    $shortcut.TargetPath       = $ExePath
    $shortcut.WorkingDirectory = $InstallDir
    $shortcut.IconLocation     = "$ExePath,0"
    $shortcut.Description      = "Note cifrate, in locale"
    $shortcut.Save()
    Write-Step "Collegamento creato: $target"
}
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($shell) | Out-Null

Write-Host ""
Write-Host "Fatto. Avvia $AppName dal Desktop o dal menu Start."
Write-Host "Le note vengono salvate cifrate in $DataDir."
Write-Host "Per rimuovere: install.ps1 -Uninstall"
