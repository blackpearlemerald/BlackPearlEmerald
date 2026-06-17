
#NoEnv
#SingleInstance Force
SetTitleMatchMode, 2

LOG := "E:/Projects/PokemonBlackPearlEmerald/BPE Emerald V1.0.1/pokeemerald-expansion/BPETools/_ahk_log.txt"

FileAppend, [AHK] Script started`n, %LOG%

; Wait for mGBA window
WinWait, mGBA,, 20
if ErrorLevel {
    FileAppend, [AHK] ERROR: mGBA window not found`n, %LOG%
    ExitApp
}
FileAppend, [AHK] mGBA window found`n, %LOG%

Sleep, 5000
FileAppend, [AHK] Startup sleep done, activating`n, %LOG%

; Activate mGBA and open Tools > Scripting via WinMenuSelectItem (reliable, no keystroke guessing)
WinActivate, mGBA
Sleep, 300
WinMenuSelectItem, mGBA, , Tools, Scripting
FileAppend, [AHK] WinMenuSelectItem Tools>Scripting sent`n, %LOG%

; Wait for Scripting console window
WinWait, Scripting,, 8
if ErrorLevel {
    FileAppend, [AHK] ERROR: Scripting window did not open`n, %LOG%
    ExitApp
}
FileAppend, [AHK] Scripting window opened`n, %LOG%
Sleep, 300

; Open File > Load Script via WinMenuSelectItem
WinActivate, Scripting
Sleep, 300
WinMenuSelectItem, Scripting, , File, Load script
FileAppend, [AHK] WinMenuSelectItem File>Load script sent`n, %LOG%

; Wait for file-open dialog
WinWait, ahk_class #32770,, 8
if ErrorLevel {
    FileAppend, [AHK] ERROR: File dialog did not appear`n, %LOG%
    ExitApp
}
FileAppend, [AHK] File dialog opened`n, %LOG%
Sleep, 300

; Type path into filename field and press Enter
WinActivate, ahk_class #32770
Sleep, 200
ControlSetText, Edit1, E:/Projects/PokemonBlackPearlEmerald/BPE Emerald V1.0.1/pokeemerald-expansion/BPETools/mgba_server.lua
Sleep, 300
Send, {Enter}
FileAppend, [AHK] Typed path and pressed Enter`n, %LOG%
Sleep, 500

FileAppend, [AHK] Done`n, %LOG%
ExitApp
