
#NoEnv
#SingleInstance Force
SetTitleMatchMode, 2
CoordMode, Mouse, Client

LOG := "E:/Projects/PokemonBlackPearlEmerald/BPE Emerald V1.0.1/pokeemerald-expansion/BPETools/_ahk_log.txt"
FileDelete, %LOG%
WinWait, mGBA,, 5
WinActivate, mGBA
Sleep, 300

; Open Tools menu
MouseClick, left, 209, 10
Sleep, 500

; Navigate DOWN 10 time(s) then Enter
Send, {Down}{Down}{Down}{Down}{Down}{Down}{Down}{Down}{Down}{Down}
Sleep, 200
Send, {Enter}
Sleep, 1000

; Collect all windows
WinGet, ids, list
result := ""
Loop %ids%
{
    id := ids%A_Index%
    WinGetTitle, t, ahk_id %id%
    WinGetClass, c, ahk_id %id%
    if (t != "" and !InStr(c, "#32770") and !InStr(t, "Claude") and !InStr(t, "Discord") and !InStr(t, "Spotify") and !InStr(t, "Program Manager"))
        result .= t . "|" . c . "`n"
}
FileAppend, %result%, %LOG%

; Close any dialog that might have opened
WinClose, ahk_class #32770
Sleep, 200
Send, {Escape}
ExitApp
