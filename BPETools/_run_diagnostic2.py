"""Click Tools menu at known screen coords, list all new windows to find Scripting window title."""
from pathlib import Path
import subprocess

ahk_log = Path(__file__).parent / '_ahk_log.txt'
ahk_log.unlink(missing_ok=True)
log = str(ahk_log).replace('\\', '/')

# Tools menu center from UI Automation: x=673+22=695, y=279+10=289
TOOLS_X = 695
TOOLS_Y = 289

script = f'''
#NoEnv
#SingleInstance Force
SetTitleMatchMode, 2

LOG := "{log}"
FileAppend, [AHK] Diagnostic2 started`n, %LOG%

; Capture window list BEFORE clicking
WinGet, ids_before, list
beforeList := ""
Loop %ids_before%
{{
    id := ids_before%A_Index%
    WinGetTitle, t, ahk_id %id%
    if (t != "")
        beforeList .= t . "|"
}}

; Activate mGBA and click the Tools menu at known screen coordinates
WinActivate, mGBA
Sleep, 400

MouseClick, left, {TOOLS_X}, {TOOLS_Y}
FileAppend, [AHK] Clicked Tools at {TOOLS_X},{TOOLS_Y}`n, %LOG%
Sleep, 800

; List all new windows
WinGet, ids_after, list
Loop %ids_after%
{{
    id := ids_after%A_Index%
    WinGetTitle, t, ahk_id %id%
    WinGetClass, c, ahk_id %id%
    if (t != "" and !InStr(beforeList, t))
        FileAppend, NEW WINDOW: "%t%" class=%c%`n, %LOG%
}}

; Also log all windows for reference
Loop %ids_after%
{{
    id := ids_after%A_Index%
    WinGetTitle, t, ahk_id %id%
    WinGetClass, c, ahk_id %id%
    if (t != "")
        FileAppend, WINDOW: "%t%" class=%c%`n, %LOG%
}}

; Press Escape to close the menu
Send, {{Escape}}
FileAppend, [AHK] Done`n, %LOG%
ExitApp
'''

ahk_path = Path(__file__).parent / '_mgba_autoload.ahk'
ahk_path.write_text(script, encoding='utf-8')

ahk_exe = r'C:\Program Files\AutoHotkey\AutoHotkey.exe'
proc = subprocess.Popen([ahk_exe, str(ahk_path)])
print(f'Diagnostic2 AHK PID: {proc.pid}')
