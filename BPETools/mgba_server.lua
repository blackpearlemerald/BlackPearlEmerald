--[[
  mgba_server.lua — BPE Emerald mGBA Lua script (file-based IPC)
  Version: 1.3  (BPE Emerald v1.0.1 / pokeemerald-expansion v1.15.1)

  Runs inside mGBA via Tools → Scripting (load script button).
  Uses file-based IPC: Python writes BPETools/bpe_cmd.json, this script
  reads it on the next frame and writes BPETools/bpe_resp.json.

  Memory addresses are from the compiled BPE Emerald v1.0.1 pokeemerald.map.
--]]

-- ============================================================
-- CONFIG
-- ============================================================
-- Absolute path to the BPETools directory (trailing slash)
local TOOLS_DIR = "E:/Projects/PokemonBlackPearlEmerald/BPE Emerald V1.0.1/pokeemerald-expansion/BPETools/"
local TABLES_PATH = TOOLS_DIR .. "lua_tables.lua"
local CMD_FILE       = TOOLS_DIR .. "bpe_cmd.json"
local RESP_FILE      = TOOLS_DIR .. "bpe_resp.json"
local HEARTBEAT_FILE = TOOLS_DIR .. "bpe_heartbeat.json"
local HEARTBEAT_INTERVAL = 30  -- frames between heartbeat writes (~0.5s at 60fps)

-- ============================================================
-- MEMORY ADDRESSES (from pokeemerald.map for BPE Emerald v1.0.1)
-- ============================================================
local ADDR = {
  -- Battle
  gBattleMons         = 0x02000420,  -- struct BattlePokemon[4]
  gBattleTypeFlags    = 0x020000AC,  -- u32
  gBattleOutcome      = 0x0200012C,  -- u8
  gBattleStruct       = 0x020000B4,  -- ptr → BattleStruct
  gBattlerPartyIndexes= 0x02000144,  -- u8[4]
  gBattlerPositions   = 0x02000238,  -- u8[4]

  -- Party
  gPlayerPartyCount   = 0x02031DCD,  -- u8
  gPlayerParty        = 0x0203202C,  -- struct Pokemon[6]  (100 bytes each)
  gEnemyPartyCount    = 0x02031DCE,  -- u8
  gEnemyParty         = 0x02031DD4,  -- struct Pokemon[6]  (100 bytes each)

  -- Overworld
  gObjectEvents       = 0x020015C4,  -- struct ObjectEvent[]
  gPlayerAvatar       = 0x02001594,  -- struct PlayerAvatar

  -- Save blocks (IWRAM pointers)
  gSaveBlock1Ptr      = 0x030051BC,  -- ptr → SaveBlock1
  gSaveBlock2Ptr      = 0x030051B8,  -- ptr → SaveBlock2

  -- Main game state (IWRAM)
  gMain               = 0x030066B8,  -- struct Main
  gSaveFileStatus     = 0x03006C00,  -- u16 (SAVE_STATUS_*)
  gTasks              = 0x03006C1C,  -- struct Task[16]
}

-- ============================================================
-- GAME STATE DETECTION (from pokeemerald.map v1.0.1)
-- ============================================================
-- gMain field addresses
local GMAIN_CB2_ADDR   = 0x030066BC  -- gMain.callback2  (offset +0x004)
local GMAIN_STATE_ADDR = 0x03006AF0  -- gMain.state      (offset +0x438)

-- Callback address ranges for static (unexported) functions.
-- Thumb function pointers have LSB=1; mask off before comparing.
-- Ranges come from pokeemerald.map .text section start + size.
local CB_TITLE_LO  = 0x0820F228  -- title_screen.o  text start
local CB_TITLE_HI  = 0x0820FCF0  -- title_screen.o  text end  (start + 0xAC8)
local CB_MENU_LO   = 0x0817876C  -- main_menu.o     text start
local CB_MENU_HI   = 0x0817B470  -- main_menu.o     text end  (start + 0x2D04)

-- Exact exported callback addresses (mask off LSB when comparing read value)
local CB_OVERWORLD       = 0x08191EBC  -- CB2_Overworld
local CB_OVERWORLD_BASIC = 0x081920B4  -- CB2_OverworldBasic
local CB_NEW_GAME        = 0x081920D0  -- CB2_NewGame
local CB_LOADING_SAVE    = 0x08192458  -- CB2_ContinueSavedGame
local CB_BATTLE          = 0x080849D4  -- BattleMainCB2
local CB_BATTLE2         = 0x080871D0  -- CB2_InitBattle

-- Save file status constants (gSaveFileStatus values)
local SAVE_STATUS_EMPTY  = 0
local SAVE_STATUS_OK     = 1
local SAVE_STATUS_CORRUPT= 2
local SAVE_STATUS_ERROR  = 0xFF

-- struct Task layout (task.h): func(4) isActive(1) prev(1) next(1) priority(1) data[16](32) = 0x28 bytes
local TASK_SIZE     = 0x28
local TASK_ISACTIVE = 0x04  -- bool8 isActive
local TASK_DATA     = 0x08  -- s16 data[16] starts here

-- Main menu task data field indices (from main_menu.c #define tMenuType / tCurrItem)
local TASK_MENU_TYPE = 0   -- data[0]: HAS_NO_SAVED_GAME(0) / HAS_SAVED_GAME(1) / etc.
local TASK_CURR_ITEM = 1   -- data[1]: currently highlighted item index

-- Automation timeout constants
local AUTO_TOTAL_TIMEOUT  = 1800  -- 30s total   (frames at ~60fps)
local AUTO_STEP_MENU_WAIT =   30  -- 0.5s: let menu init tasks settle before pressing A
local AUTO_STEP_KEY_GAP   =    8  -- frames between sequential key presses
local AUTO_STEP_OW_WAIT   =  600  -- 10s: max wait for overworld/new-game to load

-- SaveBlock1 field offsets (relative to the pointer target)
local SB1 = {
  pos_x       = 0x00,  -- s16 (Coords16.x)
  pos_y       = 0x02,  -- s16 (Coords16.y)
  location    = 0x04,  -- WarpData (8 bytes: s8 mapGroup, s8 mapNum, s8 warpId, s8 pad, s16 x, s16 y)
  flags       = 0x1270, -- u8[] (each bit is one FLAG_*)
  vars        = 0x139C, -- u16[] (VAR_0x4000 = index 0)
}

-- BattlePokemon struct size and field offsets
local BATTLPKM_SIZE = 0x58  -- rough; actual size from struct is ~0x64 but only reading subset
local BATTLPKM = {
  species   = 0x00,  -- u16
  attack    = 0x02,  -- u16
  defense   = 0x04,  -- u16
  speed     = 0x06,  -- u16
  spAtk     = 0x08,  -- u16
  spDef     = 0x0A,  -- u16
  moves     = 0x0C,  -- u16[4]
  ability   = 0x20,  -- u16 (enum Ability)
  types0    = 0x22,  -- u8
  types1    = 0x23,  -- u8
  pp        = 0x25,  -- u8[4]
  hp        = 0x29,  -- u16
  level     = 0x2B,  -- u8
  maxHP     = 0x2D,  -- u16
  item      = 0x2F,  -- u16 (enum Item, with fshort-enums)
  nickname  = 0x31,  -- u8[11] GBA charmap
}
local BATTLPKM_FULL_SIZE = 0x64  -- sizeof(struct BattlePokemon)

-- Pokemon (party) struct: BoxPokemon (80 bytes) + unencrypted stat cache
local PARTY_PKM_SIZE = 0x64  -- sizeof(struct Pokemon) = 100 bytes
local PARTY_PKM = {
  -- encrypted region (0x00–0x4F): skip species/moves, unavailable without decryption
  status  = 0x50,  -- u32
  level   = 0x54,  -- u8
  hp      = 0x56,  -- u16  (current HP)
  maxHP   = 0x58,  -- u16
  attack  = 0x5A,  -- u16
  defense = 0x5C,  -- u16
  speed   = 0x5E,  -- u16
  spAtk   = 0x60,  -- u16
  spDef   = 0x62,  -- u16
}

-- PlayerAvatar offsets
local AVATAR = {
  objectEventId = 0x05,  -- u8
}

-- ObjectEvent size (from global.fieldmap.h)
local OBJEVEN_SIZE = 0x24  -- approximate; exact value from source
local OBJEVEN = {
  map_x = 0x10,  -- s16
  map_y = 0x12,  -- s16
}

-- GBA input keys bitmask
local KEYS = {
  A=0x0001, B=0x0002, SELECT=0x0004, START=0x0008,
  RIGHT=0x0010, LEFT=0x0020, UP=0x0040, DOWN=0x0080,
  R=0x0100, L=0x0200,
}

-- Battle type flags
local BATTLE_TYPE_TRAINER = (1 << 3)
local BATTLE_TYPE_DOUBLE  = (1 << 0)

-- ============================================================
-- MINIMAL JSON LIBRARY
-- ============================================================
local json = {}

local function escape_str(s)
  return s:gsub('\\', '\\\\'):gsub('"', '\\"'):gsub('\n', '\\n'):gsub('\r', '\\r'):gsub('\t', '\\t')
end

local function is_array(t)
  local n = 0
  for _ in pairs(t) do n = n + 1 end
  for i = 1, n do
    if t[i] == nil then return false end
  end
  return n > 0 or next(t) == nil
end

function json.encode(val)
  local t = type(val)
  if val == nil then return "null"
  elseif t == "boolean" then return val and "true" or "false"
  elseif t == "number" then
    if val ~= val then return "null" end  -- NaN
    return tostring(math.floor(val) == val and math.floor(val) or val)
  elseif t == "string" then return '"' .. escape_str(val) .. '"'
  elseif t == "table" then
    if is_array(val) then
      local parts = {}
      for _, v in ipairs(val) do parts[#parts+1] = json.encode(v) end
      return "[" .. table.concat(parts, ",") .. "]"
    else
      local parts = {}
      for k, v in pairs(val) do
        parts[#parts+1] = '"' .. escape_str(tostring(k)) .. '":' .. json.encode(v)
      end
      return "{" .. table.concat(parts, ",") .. "}"
    end
  end
  return "null"
end

-- Minimal JSON decode (handles objects, arrays, strings, numbers, booleans, null)
local function skip_ws(s, i)
  while i <= #s and s:sub(i,i):match("%s") do i = i + 1 end
  return i
end

local function decode_value(s, i)
  i = skip_ws(s, i)
  local c = s:sub(i,i)
  if c == '"' then
    -- string
    local j = i + 1
    local parts = {}
    while j <= #s do
      local ch = s:sub(j,j)
      if ch == '"' then
        return table.concat(parts), j + 1
      elseif ch == '\\' then
        j = j + 1
        local esc = s:sub(j,j)
        if esc == '"' then parts[#parts+1] = '"'
        elseif esc == '\\' then parts[#parts+1] = '\\'
        elseif esc == 'n' then parts[#parts+1] = '\n'
        elseif esc == 't' then parts[#parts+1] = '\t'
        elseif esc == 'r' then parts[#parts+1] = '\r'
        else parts[#parts+1] = esc end
        j = j + 1
      else
        parts[#parts+1] = ch
        j = j + 1
      end
    end
    error("unterminated string")
  elseif c == '{' then
    local obj = {}
    i = i + 1
    i = skip_ws(s, i)
    if s:sub(i,i) == '}' then return obj, i+1 end
    while true do
      i = skip_ws(s, i)
      local key, ni = decode_value(s, i)
      i = skip_ws(s, ni)
      assert(s:sub(i,i) == ':', "expected ':'")
      i = i + 1
      local val, ni2 = decode_value(s, i)
      obj[key] = val
      i = skip_ws(s, ni2)
      local sep = s:sub(i,i)
      if sep == '}' then return obj, i+1 end
      assert(sep == ',', "expected ',' or '}'")
      i = i + 1
    end
  elseif c == '[' then
    local arr = {}
    i = i + 1
    i = skip_ws(s, i)
    if s:sub(i,i) == ']' then return arr, i+1 end
    while true do
      local val, ni = decode_value(s, i)
      arr[#arr+1] = val
      i = skip_ws(s, ni)
      local sep = s:sub(i,i)
      if sep == ']' then return arr, i+1 end
      assert(sep == ',', "expected ',' or ']'")
      i = i + 1
    end
  elseif s:sub(i, i+3) == "true" then return true, i+4
  elseif s:sub(i, i+4) == "false" then return false, i+5
  elseif s:sub(i, i+3) == "null" then return nil, i+4
  else
    -- number
    local num_str = s:match("^-?%d+%.?%d*[eE]?[+-]?%d*", i)
    assert(num_str, "invalid JSON value at pos " .. i .. ": " .. s:sub(i, i+10))
    return tonumber(num_str), i + #num_str
  end
end

function json.decode(s)
  local ok, val = pcall(function()
    local v, _ = decode_value(s, 1)
    return v
  end)
  if ok then return val end
  return nil
end

-- ============================================================
-- LOOKUP TABLES (loaded from gen_lua_tables.py output)
-- ============================================================
local SPECIES = {}
local MOVES   = {}
local MAPS    = {}

local function load_tables()
  local path = TABLES_PATH
  if not path then
    -- Try to find lua_tables.lua relative to this script's directory
    local src = debug and debug.getinfo and debug.getinfo(1, "S").source or ""
    local dir = src:match("^@(.+)[/\\][^/\\]+$") or "."
    path = dir .. "/lua_tables.lua"
  end

  local f = io.open(path, "r")
  if not f then
    console:log("[BPE] WARNING: lua_tables.lua not found at: " .. tostring(path))
    console:log("[BPE] Run: py BPETools/gen_lua_tables.py > BPETools/lua_tables.lua")
    return
  end
  f:close()

  local ok, err = pcall(function()
    local t = dofile(path)
    if t and t.SPECIES then SPECIES = t.SPECIES end
    if t and t.MOVES   then MOVES   = t.MOVES   end
    if t and t.MAPS    then MAPS    = t.MAPS    end
  end)
  if not ok then
    console:log("[BPE] ERROR loading lua_tables.lua: " .. tostring(err))
  else
    local ns = 0; for _ in pairs(SPECIES) do ns = ns+1 end
    local nm = 0; for _ in pairs(MOVES)   do nm = nm+1 end
    local nma= 0; for _ in pairs(MAPS)    do nma= nma+1 end
    console:log(string.format("[BPE] Loaded tables: %d species, %d moves, %d maps", ns, nm, nma))
  end
end

-- ============================================================
-- GBA CHARMAP DECODE (for nicknames)
-- ============================================================
local CHARMAP = {}
do
  local A = 0xBB
  for i = 0, 25 do CHARMAP[A + i] = string.char(65 + i) end  -- A-Z
  local a = 0xD5
  for i = 0, 25 do CHARMAP[a + i] = string.char(97 + i) end  -- a-z
  -- Numbers
  local nums = {[0xA1]='0',[0xA2]='1',[0xA3]='2',[0xA4]='3',[0xA5]='4',
                [0xA6]='5',[0xA7]='6',[0xA8]='7',[0xA9]='8',[0xAA]='9'}
  for k, v in pairs(nums) do CHARMAP[k] = v end
  CHARMAP[0x00] = " "
  CHARMAP[0xAB] = "!"
  CHARMAP[0xAC] = "?"
  CHARMAP[0xAD] = "."
  CHARMAP[0xAE] = "-"
  CHARMAP[0xB0] = "'"
  CHARMAP[0xFF] = nil  -- end of string sentinel
end

local function read_gba_string(base_addr, max_len)
  local chars = {}
  for i = 0, max_len - 1 do
    local b = emu:read8(base_addr + i)
    if b == 0xFF then break end
    chars[#chars+1] = CHARMAP[b] or ("?")
  end
  return table.concat(chars)
end

-- ============================================================
-- MEMORY HELPERS
-- ============================================================
local function read_s8(addr)
  local b = emu:read8(addr)
  return b >= 128 and b - 256 or b
end

local function read_s16(addr)
  local b = emu:read16(addr)
  return b >= 32768 and b - 65536 or b
end

local function sb1()
  -- Read the SaveBlock1 pointer from IWRAM
  return emu:read32(ADDR.gSaveBlock1Ptr)
end

local function read_flag(flag_id)
  local base = sb1() + SB1.flags
  local byte_off = flag_id >> 3
  local bit_off  = flag_id & 7
  local bval     = emu:read8(base + byte_off)
  return (bval >> bit_off) & 1
end

local function write_flag(flag_id, value)
  local base = sb1() + SB1.flags
  local byte_off = flag_id >> 3
  local bit_off  = flag_id & 7
  local bval = emu:read8(base + byte_off)
  if value ~= 0 then
    bval = bval | (1 << bit_off)
  else
    bval = bval & ~(1 << bit_off)
  end
  emu:write8(base + byte_off, bval)
end

local function read_var(var_id)
  -- Ordinary script vars start at 0x4000; temp vars at 0x8000
  if var_id < 0x4000 or var_id >= 0x8000 then
    return nil, "var_id out of range (use 0x4000..0x7FFF)"
  end
  local base = sb1() + SB1.vars
  return emu:read16(base + (var_id - 0x4000) * 2), nil
end

local function write_var(var_id, value)
  if var_id < 0x4000 or var_id >= 0x8000 then
    return nil, "var_id out of range (use 0x4000..0x7FFF)"
  end
  local base = sb1() + SB1.vars
  emu:write16(base + (var_id - 0x4000) * 2, value & 0xFFFF)
  return true, nil
end

-- ============================================================
-- POKEMON READERS
-- ============================================================
local function read_battle_pokemon(battler_idx)
  -- Read a BattlePokemon from gBattleMons[battler_idx] (always decrypted)
  local base = ADDR.gBattleMons + battler_idx * BATTLPKM_FULL_SIZE
  local species_id = emu:read16(base + BATTLPKM.species)
  if species_id == 0 then return nil end

  local moves = {}
  for m = 0, 3 do
    local move_id = emu:read16(base + BATTLPKM.moves + m * 2)
    local pp      = emu:read8( base + BATTLPKM.pp    + m)
    if move_id > 0 then
      moves[m+1] = {
        id   = move_id,
        name = MOVES[move_id] or ("Move#" .. move_id),
        pp   = pp,
      }
    end
  end

  return {
    battler  = battler_idx,
    species  = species_id,
    name     = SPECIES[species_id] or ("Species#" .. species_id),
    nickname = read_gba_string(base + BATTLPKM.nickname, 11),
    level    = emu:read8( base + BATTLPKM.level),
    hp       = emu:read16(base + BATTLPKM.hp),
    maxHP    = emu:read16(base + BATTLPKM.maxHP),
    attack   = emu:read16(base + BATTLPKM.attack),
    defense  = emu:read16(base + BATTLPKM.defense),
    speed    = emu:read16(base + BATTLPKM.speed),
    spAtk    = emu:read16(base + BATTLPKM.spAtk),
    spDef    = emu:read16(base + BATTLPKM.spDef),
    item_id  = emu:read16(base + BATTLPKM.item),
    moves    = moves,
  }
end

local function read_party_pokemon(party_base, idx)
  -- Read from the unencrypted stat cache (+0x50) of struct Pokemon
  local base = party_base + idx * PARTY_PKM_SIZE
  local level = emu:read8(base + PARTY_PKM.level)
  if level == 0 then return nil end

  local status = emu:read32(base + PARTY_PKM.status)
  local status_str = "OK"
  if status ~= 0 then
    if (status & 0x7) ~= 0 then status_str = "SLP"
    elseif (status & 0x08) ~= 0 then status_str = "PSN"
    elseif (status & 0x10) ~= 0 then status_str = "BRN"
    elseif (status & 0x20) ~= 0 then status_str = "FRZ"
    elseif (status & 0x40) ~= 0 then status_str = "PAR"
    elseif (status & 0x80) ~= 0 then status_str = "TOX"
    end
  end

  return {
    slot     = idx + 1,
    -- species unavailable without BoxPokemon decryption (use read_battle during battle)
    species  = "?",
    level    = level,
    hp       = emu:read16(base + PARTY_PKM.hp),
    maxHP    = emu:read16(base + PARTY_PKM.maxHP),
    attack   = emu:read16(base + PARTY_PKM.attack),
    defense  = emu:read16(base + PARTY_PKM.defense),
    speed    = emu:read16(base + PARTY_PKM.speed),
    spAtk    = emu:read16(base + PARTY_PKM.spAtk),
    spDef    = emu:read16(base + PARTY_PKM.spDef),
    status   = status_str,
  }
end

-- ============================================================
-- GAME STATE HELPERS
-- ============================================================

-- Read gMain.callback2, classify into a named screen state.
-- Returns: state_string, raw_cb2_address (with LSB masked off)
local function get_game_state()
  local cb2 = emu:read32(GMAIN_CB2_ADDR) & 0xFFFFFFFE  -- mask Thumb LSB
  -- Range checks cover static (unexported) callback functions
  if cb2 >= CB_TITLE_LO and cb2 < CB_TITLE_HI then
    return "title_screen", cb2
  end
  if cb2 >= CB_MENU_LO and cb2 < CB_MENU_HI then
    return "main_menu", cb2
  end
  -- Exact matches for exported callbacks
  if cb2 == CB_OVERWORLD or cb2 == CB_OVERWORLD_BASIC then return "overworld",     cb2 end
  if cb2 == CB_NEW_GAME      then return "new_game",      cb2 end
  if cb2 == CB_LOADING_SAVE  then return "loading_save",  cb2 end
  if cb2 == CB_BATTLE or cb2 == CB_BATTLE2 then return "battle", cb2 end
  return string.format("unknown:0x%08X", cb2), cb2
end

-- ============================================================
-- COMMAND HANDLERS
-- ============================================================
local handlers = {}
local pending_keys = nil  -- shared between press_buttons handler and frame_callback
local automation   = nil  -- set by load_save / new_game; drives multi-frame sequences

-- read_state: general overworld state
handlers.read_state = function(cmd)
  local s1 = sb1()
  local px = read_s16(s1 + SB1.pos_x)
  local py = read_s16(s1 + SB1.pos_y)

  -- Map identity from location WarpData
  local map_group = read_s8(s1 + SB1.location + 0)
  local map_num   = read_s8(s1 + SB1.location + 1)
  local map_key   = (map_group << 8) | (map_num & 0xFF)
  local map_name  = MAPS[map_key] or string.format("Map(%d,%d)", map_group, map_num)

  local battle_flags = emu:read32(ADDR.gBattleTypeFlags)
  local in_battle    = battle_flags ~= 0

  local party_count = emu:read8(ADDR.gPlayerPartyCount)

  return {
    ok        = true,
    map_group = map_group,
    map_num   = map_num,
    map_name  = map_name,
    x         = px,
    y         = py,
    in_battle = in_battle,
    party_count = party_count,
    frame     = emu:currentFrame(),
  }
end

-- read_game_state: classify the current screen by reading gMain.callback2
handlers.read_game_state = function(cmd)
  local state, cb2 = get_game_state()
  local save_status = emu:read16(ADDR.gSaveFileStatus)
  local main_state  = emu:read8(GMAIN_STATE_ADDR)

  -- When in main_menu, also report which item is highlighted.
  -- Search gTasks for the first active task whose func ptr is in main_menu.o range.
  local menu_type, curr_item
  if state == "main_menu" then
    for i = 0, 15 do
      local tbase  = ADDR.gTasks + i * TASK_SIZE
      local active = emu:read8(tbase + TASK_ISACTIVE)
      if active ~= 0 then
        local fn = emu:read32(tbase) & 0xFFFFFFFE
        if fn >= CB_MENU_LO and fn < CB_MENU_HI then
          menu_type = emu:read16(tbase + TASK_DATA + TASK_MENU_TYPE * 2)
          curr_item = emu:read16(tbase + TASK_DATA + TASK_CURR_ITEM * 2)
          break
        end
      end
    end
  end

  return {
    ok          = true,
    state       = state,
    cb2         = cb2,
    main_state  = main_state,
    save_status = save_status,
    menu_type   = menu_type,
    curr_item   = curr_item,
    frame       = emu:currentFrame(),
  }
end

-- load_save: state-driven automation — title screen → main menu → CONTINUE → overworld
-- Response is deferred until the automation completes (up to 30s).
handlers.load_save = function(cmd)
  if automation then
    return { ok=false, error="automation already running: " .. automation.step }
  end
  local frame = emu:currentFrame()
  automation = {
    cmd_type    = "load_save",
    step        = "start",
    step_frame  = frame,
    start_frame = frame,
    seq         = cmd.seq,
  }
  return { _async = true }
end

-- new_game: state-driven automation — title screen → main menu → NEW GAME → game start
-- Response is deferred until the automation completes (up to 30s).
handlers.new_game = function(cmd)
  if automation then
    return { ok=false, error="automation already running: " .. automation.step }
  end
  local frame = emu:currentFrame()
  automation = {
    cmd_type    = "new_game",
    step        = "start",
    step_frame  = frame,
    start_frame = frame,
    seq         = cmd.seq,
  }
  return { _async = true }
end

-- read_battle: read active battlers from gBattleMons
handlers.read_battle = function(cmd)
  local battle_flags = emu:read32(ADDR.gBattleTypeFlags)
  if battle_flags == 0 then
    return { ok=false, error="not in battle" }
  end

  local is_trainer = (battle_flags & BATTLE_TYPE_TRAINER) ~= 0
  local is_double  = (battle_flags & BATTLE_TYPE_DOUBLE)  ~= 0

  local battlers = {}
  -- battler 0,2 = player side; battler 1,3 = opponent side
  local num_battlers = is_double and 4 or 2
  for i = 0, num_battlers - 1 do
    local pkm = read_battle_pokemon(i)
    if pkm then
      pkm.side = (i % 2 == 0) and "player" or "opponent"
      battlers[#battlers+1] = pkm
    end
  end

  return {
    ok         = true,
    is_trainer = is_trainer,
    is_double  = is_double,
    battlers   = battlers,
    outcome    = emu:read8(ADDR.gBattleOutcome),
  }
end

-- read_party: read player's party stat cache
handlers.read_party = function(cmd)
  local count = emu:read8(ADDR.gPlayerPartyCount)
  local party = {}
  for i = 0, count - 1 do
    local pkm = read_party_pokemon(ADDR.gPlayerParty, i)
    if pkm then party[#party+1] = pkm end
  end
  return { ok=true, count=count, party=party,
           note="species/moves only available via read_battle (encrypted in BoxPokemon)" }
end

-- read_enemy: read enemy's party stat cache
handlers.read_enemy = function(cmd)
  local count = emu:read8(ADDR.gEnemyPartyCount)
  local party = {}
  for i = 0, count - 1 do
    local pkm = read_party_pokemon(ADDR.gEnemyParty, i)
    if pkm then party[#party+1] = pkm end
  end
  return { ok=true, count=count, party=party,
           note="use read_battle for decrypted species/moves during battle" }
end

-- read_flag: read a game flag
handlers.read_flag = function(cmd)
  local flag_id = cmd.flag_id
  if type(flag_id) ~= "number" then
    return { ok=false, error="flag_id required (number)" }
  end
  local val = read_flag(flag_id)
  return { ok=true, flag_id=flag_id, value=val }
end

-- set_flag: set or clear a game flag
handlers.set_flag = function(cmd)
  local flag_id = cmd.flag_id
  local value   = cmd.value
  if type(flag_id) ~= "number" then
    return { ok=false, error="flag_id required (number)" }
  end
  value = (value and value ~= 0 and value ~= false) and 1 or 0
  write_flag(flag_id, value)
  return { ok=true, flag_id=flag_id, value=value }
end

-- read_var: read a script variable (0x4000–0x7FFF)
handlers.read_var = function(cmd)
  local var_id = cmd.var_id
  if type(var_id) ~= "number" then
    return { ok=false, error="var_id required (number, e.g. 0x4000)" }
  end
  local val, err = read_var(var_id)
  if err then return { ok=false, error=err } end
  return { ok=true, var_id=var_id, value=val }
end

-- set_var: write a script variable
handlers.set_var = function(cmd)
  local var_id = cmd.var_id
  local value  = cmd.value
  if type(var_id) ~= "number" or type(value) ~= "number" then
    return { ok=false, error="var_id and value required (numbers)" }
  end
  local _, err = write_var(var_id, value)
  if err then return { ok=false, error=err } end
  return { ok=true, var_id=var_id, value=value }
end

-- warp: warp player to map position
-- For same-map repositioning: just set pos_x/pos_y in SaveBlock1.
-- For cross-map warp: writes the location WarpData. The game reads this
-- on map transitions; you may need to trigger a door/warp tile or use the
-- in-game debug menu (R+START) to actually load the new map.
handlers.warp = function(cmd)
  local s1 = sb1()
  if cmd.x ~= nil and cmd.y ~= nil and cmd.map_group == nil then
    -- Same-map position set
    emu:write16(s1 + SB1.pos_x, cmd.x & 0xFFFF)
    emu:write16(s1 + SB1.pos_y, cmd.y & 0xFFFF)
    return { ok=true, note="Set player position (same map).", x=cmd.x, y=cmd.y }
  end

  local map_group = cmd.map_group
  local map_num   = cmd.map_num
  local x         = cmd.x or -1
  local y         = cmd.y or -1

  if type(map_group) ~= "number" or type(map_num) ~= "number" then
    return { ok=false, error="map_group and map_num required for cross-map warp" }
  end

  -- Write WarpData to SaveBlock1.location (offset +0x04)
  -- struct WarpData: s8 mapGroup, s8 mapNum, s8 warpId, s8 pad, s16 x, s16 y
  local loc = s1 + SB1.location
  emu:write8( loc + 0, map_group & 0xFF)
  emu:write8( loc + 1, map_num   & 0xFF)
  emu:write8( loc + 2, 0xFF)  -- warpId = -1 (use coordinates)
  emu:write8( loc + 3, 0)
  emu:write16(loc + 4, x & 0xFFFF)
  emu:write16(loc + 6, y & 0xFFFF)

  -- Also write to continueGameWarp (+0x0C) and dynamicWarp (+0x14)
  for _, off in ipairs({0x0C, 0x14}) do
    local w = s1 + off
    emu:write8( w + 0, map_group & 0xFF)
    emu:write8( w + 1, map_num   & 0xFF)
    emu:write8( w + 2, 0xFF)
    emu:write8( w + 3, 0)
    emu:write16(w + 4, x & 0xFFFF)
    emu:write16(w + 6, y & 0xFFFF)
  end

  local map_key  = (map_group << 8) | (map_num & 0xFF)
  local map_name = MAPS[map_key] or string.format("Map(%d,%d)", map_group, map_num)

  return {
    ok       = true,
    map_name = map_name,
    map_group= map_group,
    map_num  = map_num,
    x = x, y = y,
    note = "Warp destination written. Use in-game debug menu (R+START → Warp) or walk through a door to trigger map load.",
  }
end

-- press_buttons: simulate button inputs for N frames
-- cmd.keys: list of key names, e.g. ["A", "UP"]
-- cmd.frames: how many frames to hold (default 1)
handlers.press_buttons = function(cmd)
  local keys_list = cmd.keys or {}
  local hold_frames = (cmd.frames or 1)
  if hold_frames < 1 then hold_frames = 1 end
  if hold_frames > 300 then hold_frames = 300 end  -- safety cap (5 seconds at 60fps)

  local mask = 0
  for _, k in ipairs(keys_list) do
    local bit = KEYS[k:upper()]
    if bit then mask = mask | bit
    else return { ok=false, error="Unknown key: " .. k } end
  end

  -- Schedule key presses over the next N frames
  pending_keys = { mask=mask, frames_left=hold_frames, total=hold_frames }
  return { ok=true, keys=keys_list, frames=hold_frames, mask=mask }
end

-- save_state: save mGBA state to a numbered slot
handlers.save_state = function(cmd)
  local slot = cmd.slot or 1
  if type(slot) ~= "number" or slot < 1 or slot > 99 then
    return { ok=false, error="slot must be 1-99" }
  end
  emu:saveStateSlot(slot)
  return { ok=true, slot=slot }
end

-- load_state: load mGBA state from a numbered slot
handlers.load_state = function(cmd)
  local slot = cmd.slot or 1
  if type(slot) ~= "number" or slot < 1 or slot > 99 then
    return { ok=false, error="slot must be 1-99" }
  end
  emu:loadStateSlot(slot)
  return { ok=true, slot=slot }
end

-- reset: reset the game
handlers.reset = function(cmd)
  emu:reset()
  return { ok=true }
end

-- lookup_species: reverse-lookup name → id
handlers.lookup_species = function(cmd)
  local name = (cmd.name or ""):lower()
  for id, n in pairs(SPECIES) do
    if n:lower() == name then
      return { ok=true, id=id, name=n }
    end
  end
  return { ok=false, error="species not found: " .. name }
end

-- lookup_move: reverse-lookup name → id
handlers.lookup_move = function(cmd)
  local name = (cmd.name or ""):lower()
  for id, n in pairs(MOVES) do
    if n:lower() == name then
      return { ok=true, id=id, name=n }
    end
  end
  return { ok=false, error="move not found: " .. name }
end

-- lookup_map: reverse-lookup name → map_group + map_num
handlers.lookup_map = function(cmd)
  local name = (cmd.name or ""):lower()
  local results = {}
  for key, n in pairs(MAPS) do
    if n:lower():find(name, 1, true) then
      results[#results+1] = {
        name      = n,
        map_group = (key >> 8) & 0xFF,
        map_num   = key & 0xFF,
        key       = key,
      }
    end
  end
  if #results == 0 then return { ok=false, error="map not found: " .. name } end
  return { ok=true, results=results }
end

-- write_mem: raw memory write (for advanced use)
handlers.write_mem = function(cmd)
  local addr  = cmd.addr
  local value = cmd.value
  local size  = cmd.size or 1
  if type(addr) ~= "number" or type(value) ~= "number" then
    return { ok=false, error="addr and value required (numbers)" }
  end
  if size == 1 then emu:write8( addr, value & 0xFF)
  elseif size == 2 then emu:write16(addr, value & 0xFFFF)
  elseif size == 4 then emu:write32(addr, value & 0xFFFFFFFF)
  else return { ok=false, error="size must be 1, 2, or 4" } end
  return { ok=true, addr=addr, value=value, size=size }
end

-- read_mem: raw memory read
handlers.read_mem = function(cmd)
  local addr = cmd.addr
  local size = cmd.size or 1
  if type(addr) ~= "number" then
    return { ok=false, error="addr required (number)" }
  end
  local value
  if size == 1 then value = emu:read8( addr)
  elseif size == 2 then value = emu:read16(addr)
  elseif size == 4 then value = emu:read32(addr)
  else return { ok=false, error="size must be 1, 2, or 4" } end
  return { ok=true, addr=addr, value=value, size=size }
end

-- ============================================================
-- RESPONSE WRITER  (shared by frame_callback and automation_tick)
-- ============================================================
local function write_resp_to_file(resp)
  local tmp = RESP_FILE .. ".tmp"
  local rf = io.open(tmp, "w")
  if rf then
    rf:write(json.encode(resp))
    rf:close()
    os.remove(RESP_FILE)
    os.rename(tmp, RESP_FILE)
  end
end

-- ============================================================
-- AUTOMATION ENGINE  (runs one tick per frame while active)
-- ============================================================
local function automation_tick()
  if not automation then return end

  local frame  = emu:currentFrame()
  local state, cb2 = get_game_state()

  -- Global timeout guard
  if frame - automation.start_frame >= AUTO_TOTAL_TIMEOUT then
    write_resp_to_file({ ok=false, error="automation timeout after 30s",
                         state=state, seq=automation.seq })
    automation = nil
    return
  end

  local step        = automation.step
  local step_frames = frame - automation.step_frame

  -- Helper: transition to a new step
  local function goto_step(s)
    automation.step       = s
    automation.step_frame = frame
  end

  -- ── step: start ─────────────────────────────────────────────
  -- Wait for a known state before acting. Unknown states (copyright screen,
  -- fade transitions) are harmless — the global timeout handles true hangs.
  if step == "start" then
    console:log("[BPE] AUTO start: state=" .. state)
    if state == "overworld" then
      write_resp_to_file({ ok=true, state="overworld",
                           msg="already in overworld", seq=automation.seq })
      automation = nil
    elseif state == "main_menu" then
      console:log("[BPE] AUTO already at main_menu, skipping title screen")
      goto_step("menu_wait_ready")
    elseif state == "title_screen" then
      console:log("[BPE] AUTO sending START from title screen")
      pending_keys = { mask=KEYS.START, frames_left=3, total=3 }
      goto_step("wait_main_menu")
    elseif state == "loading_save" or state == "new_game" then
      goto_step("wait_overworld")
    end
    -- For unknown/copyright/transition states: keep waiting (global timeout guards)

  -- ── step: wait_main_menu ────────────────────────────────────
  -- The title screen has two phases: Phase1 (animation) skips to Phase2 on START,
  -- then Phase3 (press-start screen) sends START → CB2_InitMainMenu.
  -- We may need more than one START press, so re-send every 90 frames until done.
  elseif step == "wait_main_menu" then
    if state == "main_menu" then
      console:log("[BPE] AUTO reached main_menu")
      goto_step("menu_wait_ready")
    elseif state == "title_screen" and step_frames > 0 and step_frames % 90 == 0 then
      -- Still on title screen after a full second — send another START
      console:log("[BPE] AUTO re-sending START (step_frames=" .. step_frames .. ")")
      pending_keys = { mask=KEYS.START, frames_left=3, total=3 }
    elseif step_frames > 600 then
      write_resp_to_file({ ok=false, error="timeout waiting for main menu",
                           state=state, seq=automation.seq })
      automation = nil
    end

  -- ── step: menu_wait_ready ───────────────────────────────────
  -- Wait AUTO_STEP_MENU_WAIT frames for Task_HandleMainMenuInput to become active.
  elseif step == "menu_wait_ready" then
    if step_frames == 1 then
      console:log("[BPE] AUTO menu_wait_ready: settling " .. AUTO_STEP_MENU_WAIT .. " frames")
    end
    if step_frames >= AUTO_STEP_MENU_WAIT then
      goto_step("menu_select")
    end

  -- ── step: menu_select ───────────────────────────────────────
  elseif step == "menu_select" then
    local save_status = emu:read16(ADDR.gSaveFileStatus)
    console:log("[BPE] AUTO menu_select: save_status=" .. save_status .. " cmd=" .. automation.cmd_type)
    local has_save = (save_status == SAVE_STATUS_OK or save_status == SAVE_STATUS_ERROR)

    if automation.cmd_type == "load_save" then
      if not has_save then
        write_resp_to_file({ ok=false,
          error=string.format("no save file (gSaveFileStatus=%d)", save_status),
          seq=automation.seq })
        automation = nil
        return
      end
      -- CONTINUE is item 0 in a HAS_SAVED_GAME menu — just press A
      pending_keys = { mask=KEYS.A, frames_left=3, total=3 }
      goto_step("wait_overworld")

    else  -- new_game
      if has_save then
        -- NEW GAME is item 1 (CONTINUE is item 0) — navigate DOWN first
        pending_keys = { mask=KEYS.DOWN, frames_left=3, total=3 }
        goto_step("new_game_confirm")
      else
        -- NEW GAME is item 0 — press A directly
        pending_keys = { mask=KEYS.A, frames_left=3, total=3 }
        goto_step("wait_new_game")
      end
    end

  -- ── step: new_game_confirm ──────────────────────────────────
  -- Wait for DOWN press to register, then press A to confirm NEW GAME.
  elseif step == "new_game_confirm" then
    if step_frames >= AUTO_STEP_KEY_GAP then
      pending_keys = { mask=KEYS.A, frames_left=3, total=3 }
      goto_step("wait_new_game")
    end

  -- ── step: wait_overworld ────────────────────────────────────
  elseif step == "wait_overworld" then
    if step_frames == 1 then
      console:log("[BPE] AUTO wait_overworld: state=" .. state)
    end
    if state == "overworld" then
      console:log("[BPE] AUTO done: overworld reached")
      write_resp_to_file({ ok=true, state="overworld",
                           msg="save loaded, in overworld", seq=automation.seq })
      automation = nil
    elseif step_frames > AUTO_STEP_OW_WAIT then
      write_resp_to_file({ ok=false, error="timeout waiting for overworld after CONTINUE",
                           state=state, seq=automation.seq })
      automation = nil
    end

  -- ── step: wait_new_game ─────────────────────────────────────
  elseif step == "wait_new_game" then
    if state == "new_game" or state == "overworld" then
      write_resp_to_file({ ok=true, state=state,
                           msg="new game started", seq=automation.seq })
      automation = nil
    elseif step_frames > AUTO_STEP_OW_WAIT then
      write_resp_to_file({ ok=false, error="timeout waiting for new game to start",
                           state=state, seq=automation.seq })
      automation = nil
    end
  end
end

-- ============================================================
-- DISPATCH
-- ============================================================
local function dispatch(cmd)
  if type(cmd) ~= "table" then
    return { ok=false, error="expected JSON object" }
  end
  local name = cmd.cmd
  if not name then return { ok=false, error="missing 'cmd' field" } end
  local h = handlers[name]
  if not h then return { ok=false, error="unknown command: " .. tostring(name) } end
  local ok, result = pcall(h, cmd)
  if not ok then
    return { ok=false, error="handler error: " .. tostring(result) }
  end
  return result
end

-- ============================================================
-- FILE-BASED IPC
-- ============================================================

local heartbeat_counter = 0

local function write_heartbeat()
  -- Write directly (no temp+rename: Windows os.rename fails if target exists)
  local hf = io.open(HEARTBEAT_FILE, "w")
  if hf then
    hf:write('{"frame":' .. emu:currentFrame() .. ',"time":' .. os.time() .. ',"pid":"mgba"}')
    hf:close()
  end
end

local function frame_callback()
  -- Heartbeat: write liveness file periodically
  heartbeat_counter = heartbeat_counter + 1
  if heartbeat_counter >= HEARTBEAT_INTERVAL then
    heartbeat_counter = 0
    write_heartbeat()
  end

  -- Handle pending key presses
  if pending_keys then
    if pending_keys.frames_left > 0 then
      emu:setKeys(pending_keys.mask)
      if pending_keys.frames_left == pending_keys.total then
        console:log("[BPE] KEY START: mask=" .. pending_keys.mask .. " frames=" .. pending_keys.total)
      end
      pending_keys.frames_left = pending_keys.frames_left - 1
    else
      emu:setKeys(0)
      console:log("[BPE] KEY END")
      pending_keys = nil
    end
  end

  -- Advance multi-frame automation (load_save / new_game).
  -- Writes its own response when done; blocks command processing while active.
  automation_tick()
  if automation then return end

  -- Check for a command file every frame
  local f = io.open(CMD_FILE, "r")
  if not f then return end
  local content = f:read("*a")
  f:close()

  -- Delete command file immediately so we don't process it twice
  os.remove(CMD_FILE)

  if not content or content == "" then return end

  local cmd = json.decode(content)
  console:log("[BPE] CMD: " .. (cmd and cmd.cmd or "nil") .. " (seq=" .. (cmd and cmd.seq or "?") .. ")")
  local resp = dispatch(cmd or {})

  -- Async handlers (load_save, new_game) return {_async=true} — response written
  -- by automation_tick when the sequence completes. Don't write anything here.
  if resp._async then return end

  -- Echo sequence number and write response atomically
  if cmd and cmd.seq then
    resp.seq = cmd.seq
  end
  write_resp_to_file(resp)
end

-- ============================================================
-- STARTUP
-- ============================================================
console:log("[BPE] mgba_server.lua v1.3 starting (BPE Emerald v1.0.1)")

-- Clean stale IPC files from previous session
os.remove(CMD_FILE)
os.remove(RESP_FILE)
os.remove(CMD_FILE .. ".tmp")
os.remove(RESP_FILE .. ".tmp")
os.remove(HEARTBEAT_FILE .. ".tmp")

load_tables()
write_heartbeat()  -- immediate heartbeat so Python can detect us right away
callbacks:add("frame", frame_callback)
console:log("[BPE] Ready. Commands: read_game_state | load_save | new_game | read_state | ...")
