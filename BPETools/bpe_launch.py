#!/usr/bin/env python3
"""
bpe_launch.py — Kill any running mGBA, launch it with the BPE ROM, and
automatically load mgba_server.lua via AutoHotkey menu automation.

Usage:
  py BPETools/bpe_launch.py          # launch and load script
  py BPETools/bpe_launch.py --wait   # also wait until server heartbeat is live

Requires AutoHotkey (v1 or v2) installed on the system.
AutoHotkey.exe must be findable via PATH or at a standard install location.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
MGBA_EXE    = Path(r"E:\Programs\mGBA-0.10.5-win32\mGBA.exe")
ROM_PATH    = Path(r"E:\Projects\PokemonBlackPearlEmerald\BPE Emerald V1.0.1\pokeemerald-expansion\pokeemerald.gba")
SERVER_SCRIPT = Path(r"E:\Projects\PokemonBlackPearlEmerald\BPE Emerald V1.0.1\pokeemerald-expansion\BPETools\mgba_server.lua")
HEARTBEAT   = Path(r"E:\Projects\PokemonBlackPearlEmerald\BPE Emerald V1.0.1\pokeemerald-expansion\BPETools\bpe_heartbeat.json")

# AHK timing (ms) — increase if your machine is slow
MGBA_START_WAIT_MS  = 5000   # wait after launching mGBA before interacting
MENU_STEP_MS        = 300    # wait between each menu action
DIALOG_WAIT_S       = 8      # seconds to wait for file dialog to appear

# ── AutoHotkey locator ──────────────────────────────────────────────────────
_AHK_CANDIDATES = [
    r"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe",
    r"C:\Program Files\AutoHotkey\v2\AutoHotkey32.exe",
    r"C:\Program Files\AutoHotkey\v2\AutoHotkey.exe",
    r"C:\Program Files\AutoHotkey\AutoHotkey.exe",
    r"C:\Program Files\AutoHotkey\AutoHotkey64.exe",
    r"C:\Program Files (x86)\AutoHotkey\AutoHotkey.exe",
]

def find_ahk() -> Path:
    # Try PATH first
    for name in ("AutoHotkey64.exe", "AutoHotkey.exe", "AutoHotkey32.exe"):
        try:
            result = subprocess.run(["where", name], capture_output=True, text=True)
            if result.returncode == 0:
                return Path(result.stdout.strip().splitlines()[0])
        except Exception:
            pass
    # Try known install locations
    for p in _AHK_CANDIDATES:
        if Path(p).exists():
            return Path(p)
    raise FileNotFoundError(
        "AutoHotkey not found. Install it from https://www.autohotkey.com/ "
        "or ensure AutoHotkey.exe is on your PATH."
    )


# ── AHK script (v1 syntax — works with v1 and v2 compatibility layer) ───────
# We use MenuSelect which reliably clicks menu items by name regardless of
# window focus or language, avoiding fragile keystroke sequences.

def build_ahk_script(script_path: str, startup_ms: int, step_ms: int,
                     dialog_wait_s: int, log_path: str) -> str:
    fwd = script_path.replace("\\", "/")
    return f"""
#NoEnv
#SingleInstance Force
SetTitleMatchMode, 2

LOG := "{log_path.replace(chr(92), "/")}"

FileAppend, [AHK] Script started`n, %LOG%

; Wait for mGBA window
WinWait, mGBA,, 20
if ErrorLevel {{
    FileAppend, [AHK] ERROR: mGBA window not found`n, %LOG%
    ExitApp
}}
FileAppend, [AHK] mGBA window found`n, %LOG%

Sleep, {startup_ms}
FileAppend, [AHK] Startup sleep done, activating`n, %LOG%

; Activate mGBA and open Tools > Scripting via WinMenuSelectItem (reliable, no keystroke guessing)
WinActivate, mGBA
Sleep, 300
WinMenuSelectItem, mGBA, , Tools, Scripting
FileAppend, [AHK] WinMenuSelectItem Tools>Scripting sent`n, %LOG%

; Wait for Scripting console window
WinWait, Scripting,, {dialog_wait_s}
if ErrorLevel {{
    FileAppend, [AHK] ERROR: Scripting window did not open`n, %LOG%
    ExitApp
}}
FileAppend, [AHK] Scripting window opened`n, %LOG%
Sleep, {step_ms}

; Open File > Load Script via WinMenuSelectItem
WinActivate, Scripting
Sleep, 300
WinMenuSelectItem, Scripting, , File, Load script
FileAppend, [AHK] WinMenuSelectItem File>Load script sent`n, %LOG%

; Wait for file-open dialog
WinWait, ahk_class #32770,, {dialog_wait_s}
if ErrorLevel {{
    FileAppend, [AHK] ERROR: File dialog did not appear`n, %LOG%
    ExitApp
}}
FileAppend, [AHK] File dialog opened`n, %LOG%
Sleep, {step_ms}

; Type path into filename field and press Enter
WinActivate, ahk_class #32770
Sleep, 200
ControlSetText, Edit1, {fwd}
Sleep, 300
Send, {{Enter}}
FileAppend, [AHK] Typed path and pressed Enter`n, %LOG%
Sleep, 500

FileAppend, [AHK] Done`n, %LOG%
ExitApp
"""


def kill_mgba():
    subprocess.run(
        ["powershell.exe", "-Command",
         "Stop-Process -Name 'mGBA' -Force -ErrorAction SilentlyContinue"],
        capture_output=True,
    )
    time.sleep(0.5)


def launch_mgba():
    subprocess.Popen(
        ["powershell.exe", "-Command",
         f"Start-Process '{MGBA_EXE}' -ArgumentList '\"{ROM_PATH}\"'"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run_ahk(ahk_exe: Path, script_content: str):
    # Write to a fixed path (not a temp file) so it persists for inspection
    ahk_path = Path(__file__).parent / "_mgba_autoload.ahk"
    ahk_path.write_text(script_content, encoding="utf-8")
    subprocess.Popen([str(ahk_exe), str(ahk_path)])


def wait_for_heartbeat(timeout: float = 30.0) -> bool:
    """Poll bpe_heartbeat.json until it reports a fresh timestamp."""
    deadline = time.monotonic() + timeout
    print("Waiting for mGBA server heartbeat", end="", flush=True)
    while time.monotonic() < deadline:
        print(".", end="", flush=True)
        try:
            data = json.loads(HEARTBEAT.read_text(encoding="utf-8"))
            age = time.time() - data.get("time", 0)
            if age < 3.0:
                print(" OK")
                return True
        except Exception:
            pass
        time.sleep(0.5)
    print(" TIMEOUT")
    return False


def main():
    wait = "--wait" in sys.argv

    print("Killing any existing mGBA instances...")
    kill_mgba()

    print(f"Launching mGBA with ROM...")
    launch_mgba()

    print("Locating AutoHotkey...")
    try:
        ahk_exe = find_ahk()
        print(f"  Found: {ahk_exe}")
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    ahk_log = Path(__file__).parent / "_ahk_log.txt"
    ahk_log.unlink(missing_ok=True)
    script = build_ahk_script(
        script_path=str(SERVER_SCRIPT),
        startup_ms=MGBA_START_WAIT_MS,
        step_ms=MENU_STEP_MS,
        dialog_wait_s=DIALOG_WAIT_S,
        log_path=str(ahk_log),
    )
    print("Running AutoHotkey script to load mgba_server.lua...")
    run_ahk(ahk_exe, script)

    if wait:
        ok = wait_for_heartbeat(timeout=45.0)
        if ok:
            print("Server is live. Run: py BPETools/bpe_test.py read_game_state")
        else:
            print(f"ERROR: Server did not become live within 45 seconds.")
            print("Check the mGBA Scripting console for errors.")
            sys.exit(1)
    else:
        est = (MGBA_START_WAIT_MS + MENU_STEP_MS * 3) // 1000 + 2
        print(f"AHK automation running in background (~{est}s to complete).")
        print("Run: py BPETools/bpe_test.py read_game_state  (once mGBA is ready)")


if __name__ == "__main__":
    main()
