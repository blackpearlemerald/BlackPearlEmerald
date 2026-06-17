"""Click the Scripting input field and type dofile to load the server."""
import subprocess, time
from pathlib import Path

ahk_log = Path(__file__).parent / '_ahk_log.txt'
log = str(ahk_log).replace('\\', '/')

script = f'''
#NoEnv
#SingleInstance Force
SetTitleMatchMode, 2

LOG := "{log}"
FileDelete, %LOG%
FileAppend, [AHK] test_dofile started`n, %LOG%

; Scripting window must already be open
IfWinNotExist, Scripting
{{
    FileAppend, [AHK] ERROR: Scripting window not found`n, %LOG%
    ExitApp
}}
FileAppend, [AHK] Scripting window found`n, %LOG%

WinActivate, Scripting
Sleep, 400

; Click the input field at client-relative (483, 596)
CoordMode, Mouse, Client
MouseClick, left, 483, 596
Sleep, 300
FileAppend, [AHK] Clicked input field`n, %LOG%

; Type dofile command
Send, dofile("E:/Programs/mGBA-0.10.5-win32/bpe_autostart.lua")
Sleep, 200
Send, {{Enter}}
FileAppend, [AHK] dofile sent`n, %LOG%
Sleep, 2000

FileAppend, [AHK] Done`n, %LOG%
ExitApp
'''

ahk_path = Path(__file__).parent / '_test_dofile.ahk'
ahk_path.write_text(script, encoding='utf-8')
ahk_exe = r'C:\Program Files\AutoHotkey\AutoHotkey.exe'
proc = subprocess.Popen([ahk_exe, str(ahk_path)])
proc.wait(timeout=15)
print(ahk_log.read_text() if ahk_log.exists() else '(no log)')
