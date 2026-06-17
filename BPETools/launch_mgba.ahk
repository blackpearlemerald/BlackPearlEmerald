
#NoEnv
#SingleInstance Force
SetTitleMatchMode, 2

; ── Paths ──────────────────────────────────────────────────────────────────
MGBA_EXE  := "E:\Programs\mGBA-0.10.5-win32\mGBA.exe"
ROM_PATH  := "E:\Projects\PokemonBlackPearlEmerald\BPE Emerald V1.0.1\pokeemerald-expansion\pokeemerald.gba"
LUA_SHIM  := "E:/Programs/mGBA-0.10.5-win32/bpe_autostart.lua"
LOG       := "E:\Projects\PokemonBlackPearlEmerald\BPE Emerald V1.0.1\pokeemerald-expansion\BPETools\_ahk_log.txt"

FileDelete, %LOG%
FileAppend, [AHK] launch_mgba.ahk started`n, %LOG%

; ── Step 1: Kill any existing mGBA ─────────────────────────────────────────
Process, Close, mGBA.exe
Sleep, 2000
FileAppend, [AHK] Old mGBA closed`n, %LOG%

; ── Step 2: Launch mGBA with ROM ───────────────────────────────────────────
Run, "%MGBA_EXE%" "%ROM_PATH%"
FileAppend, [AHK] mGBA launched`n, %LOG%

WinWait, mGBA,, 20
if ErrorLevel {
    FileAppend, [AHK] ERROR: mGBA window never appeared`n, %LOG%
    ExitApp
}
FileAppend, [AHK] mGBA window found`n, %LOG%

; Wait for ROM to load and menu bar to be ready
Sleep, 4000
FileAppend, [AHK] Startup wait done`n, %LOG%

; ── Step 3: Open Tools > Scripting via click + 5 Down + Enter ──────────────
; (Scripting is item 5 in the Tools dropdown, confirmed empirically)
WinActivate, mGBA
Sleep, 400

CoordMode, Mouse, Client
MouseClick, left, 209, 10   ; Tools menu bar item (client-area coords)
Sleep, 600
FileAppend, [AHK] Opened Tools dropdown`n, %LOG%

; Navigate down to Scripting (5th item) and select it
Send, {Down}{Down}{Down}{Down}{Down}
Sleep, 200
Send, {Enter}
FileAppend, [AHK] Selected Scripting (Down x5 + Enter)`n, %LOG%

; ── Step 4: Wait for Scripting console window ──────────────────────────────
WinWait, Scripting,, 8
if ErrorLevel {
    FileAppend, [AHK] ERROR: Scripting window did not appear`n, %LOG%
    ExitApp
}
FileAppend, [AHK] Scripting window opened`n, %LOG%
Sleep, 400

; ── Step 5: Type dofile() into the Scripting console input ─────────────────
WinActivate, Scripting
Sleep, 300

; Click on the input field at client-relative position (483, 596)
; (measured: Edit input is 483px right, 596px down from Scripting client top-left)
MouseClick, left, 483, 596
Sleep, 300

; Type dofile command (forward slashes to avoid escaping issues)
Send, dofile("%LUA_SHIM%")
Sleep, 200
Send, {Enter}
FileAppend, [AHK] dofile command sent`n, %LOG%
Sleep, 1500

FileAppend, [AHK] Done`n, %LOG%
ExitApp
