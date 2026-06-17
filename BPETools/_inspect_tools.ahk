
#NoEnv
#SingleInstance Force
SetTitleMatchMode, 2
CoordMode, Mouse, Client

LOG := "E:/Projects/PokemonBlackPearlEmerald/BPE Emerald V1.0.1/pokeemerald-expansion/BPETools/_ahk_log.txt"
FileDelete, %LOG%
FileAppend, [AHK] Opening Tools dropdown`n, %LOG%

WinWait, mGBA,, 10
WinActivate, mGBA
Sleep, 400

MouseClick, left, 209, 10
Sleep, 2800   ; keep dropdown open for 2.8s so PowerShell can inspect it
Send, {Escape}  ; close the dropdown cleanly
FileAppend, [AHK] Dropdown closed`n, %LOG%
ExitApp
