from pathlib import Path
import subprocess

ahk_log = Path(__file__).parent / '_ahk_log.txt'
ahk_log.unlink(missing_ok=True)

log = str(ahk_log).replace('\\', '/')

script = f'''
#NoEnv
#SingleInstance Force
SetTitleMatchMode, 2

LOG := "{log}"

FileAppend, [AHK] Diagnostic started`n, %LOG%

WinWait, mGBA,, 10
if ErrorLevel {{
    FileAppend, [AHK] ERROR: mGBA not found`n, %LOG%
    ExitApp
}}
FileAppend, [AHK] mGBA found`n, %LOG%

WinActivate, mGBA
Sleep, 500

; Try F10 to activate menu bar
Send, {{F10}}
Sleep, 600
FileAppend, [AHK] Sent F10`n, %LOG%

; Press Right 3 times then Enter to open Tools menu
Send, {{Right}}{{Right}}{{Right}}
Sleep, 400
Send, {{Return}}
Sleep, 800
FileAppend, [AHK] Opened Tools menu (hopefully)`n, %LOG%

; Press S to select Scripting
Send, s
Sleep, 600
FileAppend, [AHK] Sent s`n, %LOG%

Sleep, 1000

; enumerate all windows
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
print(f'Diagnostic AHK PID: {proc.pid}')
