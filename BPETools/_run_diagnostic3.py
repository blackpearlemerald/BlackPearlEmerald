"""Close version dialog, click Tools, press s to open Scripting, find window title."""
from pathlib import Path
import subprocess

ahk_log = Path(__file__).parent / '_ahk_log.txt'
ahk_log.unlink(missing_ok=True)
log = str(ahk_log).replace('\\', '/')

TOOLS_X = 695
TOOLS_Y = 289

script = f'''
#NoEnv
#SingleInstance Force
SetTitleMatchMode, 2

LOG := "{log}"
FileAppend, [AHK] Diagnostic3 started`n, %LOG%

; Close any lingering dialogs first
IfWinExist, version
{{
    WinClose, version
    FileAppend, [AHK] Closed version dialog`n, %LOG%
    Sleep, 500
}}

; Also close any AHK dialogs
IfWinExist, ahk_class #32770
{{
    WinClose, ahk_class #32770
    Sleep, 300
}}

; Activate mGBA
WinActivate, mGBA
Sleep, 500
FileAppend, [AHK] mGBA activated`n, %LOG%

; Click Tools menu at known screen coordinates
MouseClick, left, {TOOLS_X}, {TOOLS_Y}
FileAppend, [AHK] Clicked Tools at {TOOLS_X},{TOOLS_Y}`n, %LOG%
Sleep, 600

; Press S to select Scripting
Send, s
FileAppend, [AHK] Sent s`n, %LOG%
Sleep, 1000

; List all windows
WinGet, ids, list
Loop %ids%
{{
    id := ids%A_Index%
    WinGetTitle, t, ahk_id %id%
    WinGetClass, c, ahk_id %id%
    if (t != "")
        FileAppend, WINDOW: "%t%" class=%c%`n, %LOG%
}}

FileAppend, [AHK] Done`n, %LOG%
ExitApp
'''

ahk_path = Path(__file__).parent / '_mgba_autoload.ahk'
ahk_path.write_text(script, encoding='utf-8')

ahk_exe = r'C:\Program Files\AutoHotkey\AutoHotkey.exe'
proc = subprocess.Popen([ahk_exe, str(ahk_path)])
print(f'Diagnostic3 AHK PID: {proc.pid}')
