
#NoEnv
#SingleInstance Force
SetTitleMatchMode, 2

LOG := "E:/Projects/PokemonBlackPearlEmerald/BPE Emerald V1.0.1/pokeemerald-expansion/BPETools/_ahk_log.txt"
FileDelete, %LOG%
FileAppend, [AHK] test_dofile started`n, %LOG%

; Scripting window must already be open
IfWinNotExist, Scripting
{
    FileAppend, [AHK] ERROR: Scripting window not found`n, %LOG%
    ExitApp
}
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
Send, {Enter}
FileAppend, [AHK] dofile sent`n, %LOG%
Sleep, 2000

FileAppend, [AHK] Done`n, %LOG%
ExitApp
