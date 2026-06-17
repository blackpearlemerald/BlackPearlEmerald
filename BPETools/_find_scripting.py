"""
Find Scripting position in Tools menu by pressing DOWN N times then Enter,
checking each time whether the Scripting console opened.
"""
import subprocess, time
from pathlib import Path

ahk_exe = r'C:\Program Files\AutoHotkey\AutoHotkey.exe'
ahk_path = Path(__file__).parent / '_find_scripting.ahk'
log_path = Path(__file__).parent / '_ahk_log.txt'

def try_n_downs(n):
    """Open Tools menu, press DOWN n times, press Enter, wait, return window list."""
    log_path.unlink(missing_ok=True)
    log = str(log_path).replace('\\', '/')
    downs = '{Down}' * n

    script = f'''
#NoEnv
#SingleInstance Force
SetTitleMatchMode, 2
CoordMode, Mouse, Client

LOG := "{log}"
FileDelete, %LOG%
WinWait, mGBA,, 5
WinActivate, mGBA
Sleep, 300

; Open Tools menu
MouseClick, left, 209, 10
Sleep, 500

; Navigate DOWN {n} time(s) then Enter
Send, {downs}
Sleep, 200
Send, {{Enter}}
Sleep, 1000

; Collect all windows
WinGet, ids, list
result := ""
Loop %ids%
{{
    id := ids%A_Index%
    WinGetTitle, t, ahk_id %id%
    WinGetClass, c, ahk_id %id%
    if (t != "" and !InStr(c, "#32770") and !InStr(t, "Claude") and !InStr(t, "Discord") and !InStr(t, "Spotify") and !InStr(t, "Program Manager"))
        result .= t . "|" . c . "`n"
}}
FileAppend, %result%, %LOG%

; Close any dialog that might have opened
WinClose, ahk_class #32770
Sleep, 200
Send, {{Escape}}
ExitApp
'''
    ahk_path.write_text(script, encoding='utf-8')
    proc = subprocess.Popen([ahk_exe, str(ahk_path)])
    proc.wait(timeout=8)
    time.sleep(0.3)
    return log_path.read_text() if log_path.exists() else ''

# Baseline: no Tools menu, just list windows
log_path.unlink(missing_ok=True)
script = '''
#NoEnv
SetTitleMatchMode, 2
LOG := "''' + str(log_path).replace('\\', '/') + '''"
WinGet, ids, list
Loop %ids%
{
    id := ids%A_Index%
    WinGetTitle, t, ahk_id %id%
    WinGetClass, c, ahk_id %id%
    if (t != "" and !InStr(c, "#32770") and !InStr(t, "Claude") and !InStr(t, "Discord") and !InStr(t, "Spotify") and !InStr(t, "Program Manager"))
        FileAppend, [BASELINE] %t% | %c%`n, %LOG%
}
ExitApp
'''
ahk_path.write_text(script, encoding='utf-8')
subprocess.run([ahk_exe, str(ahk_path)], timeout=5)
baseline = log_path.read_text() if log_path.exists() else ''
baseline_titles = set(line.split('|')[0].strip() for line in baseline.splitlines() if line)
print('Baseline windows:', baseline_titles)
print()

# Try DOWN 1 through 10
for n in range(1, 11):
    result = try_n_downs(n)
    # Find new windows vs baseline
    current_titles = {}
    for line in result.splitlines():
        if '|' in line:
            t, c = line.split('|', 1)
            current_titles[t.strip()] = c.strip()

    new_wins = {t: c for t, c in current_titles.items()
                if not any(t.startswith(b.rstrip()) for b in baseline_titles if len(b) > 5)}
    # Remove mGBA main window (title changes with FPS)
    new_wins = {t: c for t, c in new_wins.items() if 'POKEMON EMER' not in t and 'mGBA' not in t}

    print(f'DOWN x{n}: new_windows={new_wins}')
    if new_wins:
        print(f'  *** Possible match at DOWN x{n} ***')

print('\nDone. Check above for which DOWN count opened a new window.')
