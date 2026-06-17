"""Click Tools > Scripting, then use UI Automation to find the Scripting panel."""
from pathlib import Path
import subprocess
import time

ahk_log = Path(__file__).parent / '_ahk_log.txt'
ahk_log.unlink(missing_ok=True)
log = str(ahk_log).replace('\\', '/')

# Use window-relative coords for the Tools menu (209, 10)
script = f'''
#NoEnv
#SingleInstance Force
SetTitleMatchMode, 2
CoordMode, Mouse, Window

LOG := "{log}"
FileAppend, [AHK] Diag4 started`n, %LOG%

WinWait, mGBA,, 10
if ErrorLevel {{
    FileAppend, [AHK] mGBA not found`n, %LOG%
    ExitApp
}}

WinActivate, mGBA
Sleep, 500
FileAppend, [AHK] mGBA activated`n, %LOG%

; Click Tools menu using window-relative coords (209, 10)
MouseClick, left, 209, 10
Sleep, 100
FileAppend, [AHK] MouseClick sent`n, %LOG%
Sleep, 600

; Press S to select Scripting
Send, s
Sleep, 100
FileAppend, [AHK] Sent s`n, %LOG%
Sleep, 1500

FileAppend, [AHK] Waiting done`n, %LOG%
ExitApp
'''

ahk_path = Path(__file__).parent / '_mgba_autoload.ahk'
ahk_path.write_text(script, encoding='utf-8')

ahk_exe = r'C:\Program Files\AutoHotkey\AutoHotkey.exe'
proc = subprocess.Popen([ahk_exe, str(ahk_path)])
print(f'AHK PID: {proc.pid}')
time.sleep(5)

# Now use UI Automation to inspect mGBA window
print('Inspecting mGBA via UI Automation...')
