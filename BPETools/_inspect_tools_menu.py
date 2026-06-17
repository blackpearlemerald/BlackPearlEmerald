"""
Open the Tools dropdown and immediately enumerate its UI children.
Runs AHK to click Tools (keeps dropdown open), then PowerShell to inspect.
"""
import subprocess, time, ctypes, ctypes.wintypes
from pathlib import Path

ahk_log = Path(__file__).parent / '_ahk_log.txt'
log = str(ahk_log).replace('\\', '/')

# AHK: click Tools, wait 3s (dropdown stays open), then close
ahk_script = f'''
#NoEnv
#SingleInstance Force
SetTitleMatchMode, 2
CoordMode, Mouse, Client

LOG := "{log}"
FileDelete, %LOG%
FileAppend, [AHK] Opening Tools dropdown`n, %LOG%

WinWait, mGBA,, 10
WinActivate, mGBA
Sleep, 400

MouseClick, left, 209, 10
Sleep, 2800   ; keep dropdown open for 2.8s so PowerShell can inspect it
Send, {{Escape}}  ; close the dropdown cleanly
FileAppend, [AHK] Dropdown closed`n, %LOG%
ExitApp
'''

ahk_path = Path(__file__).parent / '_inspect_tools.ahk'
ahk_path.write_text(ahk_script, encoding='utf-8')

ahk_exe = r'C:\Program Files\AutoHotkey\AutoHotkey.exe'
# Start AHK (it will click Tools and hold dropdown open)
proc = subprocess.Popen([ahk_exe, str(ahk_path)])
print('AHK started, waiting 1.5s for dropdown to open...')
time.sleep(1.5)

# Now inspect the popup window via PowerShell UI Automation
ps_code = r"""
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes

$desktop = [System.Windows.Automation.AutomationElement]::RootElement

# Find the Qt popup (Tools dropdown)
$allWindows = $desktop.FindAll([System.Windows.Automation.TreeScope]::Children,
    [System.Windows.Automation.Condition]::TrueCondition)

foreach ($w in $allWindows) {
    $name = $w.Current.Name
    $cls  = $w.Current.ClassName
    if ($cls -like "*Popup*" -or $cls -like "*DropDown*" -or $name -eq "mGBA") {
        Write-Host "POPUP: name='$name' class='$cls' bounds=$($w.Current.BoundingRectangle)"
        $children = $w.FindAll([System.Windows.Automation.TreeScope]::Descendants,
            [System.Windows.Automation.Condition]::TrueCondition)
        Write-Host "  Children: $($children.Count)"
        foreach ($c in $children) {
            Write-Host "  ITEM: type=$($c.Current.ControlType.ProgrammaticName) name='$($c.Current.Name)' bounds=$($c.Current.BoundingRectangle)"
        }
    }
}
"""

result = subprocess.run(
    ['powershell.exe', '-Command', ps_code],
    capture_output=True, text=True, timeout=10
)
print('=== UI Automation results ===')
print(result.stdout or '(no output)')
if result.stderr:
    print('STDERR:', result.stderr[:500])

proc.wait()
print('\n=== AHK log ===')
print(ahk_log.read_text() if ahk_log.exists() else '(no log)')
