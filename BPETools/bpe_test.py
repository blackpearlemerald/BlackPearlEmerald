#!/usr/bin/env python3
"""
bpe_test.py — BPE Emerald mGBA test CLI
Connects to mgba_server.lua (port 9001) and sends JSON commands.

Usage:
  py BPETools/bpe_test.py <command> [args...]

Commands:
  read_state
  read_battle
  read_party
  read_enemy
  read_flag   <flag_id>
  set_flag    <flag_id> <0|1>
  read_var    <var_id>          (var_id as decimal or hex, e.g. 0x4001)
  set_var     <var_id> <value>
  warp        <map_group> <map_num> [x] [y]
  warp_xy     <x> <y>           (same-map position set)
  press       <KEY[,KEY,...]> [frames]
  save_state  [slot]
  load_state  [slot]
  reset
  lookup_species <name>
  lookup_move    <name>
  lookup_map     <name>
  read_mem    <addr> [size]     (addr as hex, size = 1/2/4)
  write_mem   <addr> <value> [size]
  raw         <json>            (send raw JSON, e.g. raw '{"cmd":"read_state"}')

Examples:
  py BPETools/bpe_test.py read_state
  py BPETools/bpe_test.py read_battle
  py BPETools/bpe_test.py set_flag 0x500 1
  py BPETools/bpe_test.py set_var 0x4001 5
  py BPETools/bpe_test.py warp 0 19 10 10
  py BPETools/bpe_test.py press START
  py BPETools/bpe_test.py press A,B 10
  py BPETools/bpe_test.py lookup_map route104
  py BPETools/bpe_test.py save_state 1
  py BPETools/bpe_test.py load_state 1
"""

import json
import socket
import sys

HOST = "127.0.0.1"
PORT = 9001
TIMEOUT = 5.0


def connect():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(TIMEOUT)
    try:
        s.connect((HOST, PORT))
    except ConnectionRefusedError:
        print("ERROR: Cannot connect to mGBA server on port 9001.")
        print("Make sure mGBA is running with mgba_server.lua loaded.")
        sys.exit(1)
    except TimeoutError:
        print("ERROR: Connection timed out.")
        sys.exit(1)
    return s


def send_cmd(cmd: dict) -> dict:
    s = connect()
    try:
        payload = json.dumps(cmd) + "\n"
        s.sendall(payload.encode())
        # Read response line
        buf = b""
        while b"\n" not in buf:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        line = buf.split(b"\n")[0]
        return json.loads(line.decode())
    finally:
        s.close()


def parse_int(s):
    """Parse decimal or hex integer string."""
    s = s.strip()
    if s.startswith("0x") or s.startswith("0X"):
        return int(s, 16)
    return int(s)


def pretty(resp: dict):
    """Print a response dict in a human-readable format."""
    if not resp.get("ok"):
        print(f"ERROR: {resp.get('error', resp)}")
        return

    # Special formatting for complex responses
    if "battlers" in resp:
        _print_battle(resp)
    elif "party" in resp and "count" in resp:
        _print_party(resp)
    elif "results" in resp:
        for r in resp["results"]:
            print(f"  {r.get('name','?')!r:40s} group={r.get('map_group','?')} num={r.get('map_num','?')}")
    else:
        # Generic key=value print
        for k, v in resp.items():
            if k == "ok":
                continue
            if isinstance(v, str) and len(v) > 80:
                print(f"  {k}: {v[:80]}...")
            else:
                print(f"  {k}: {v}")


def _print_battle(resp):
    trainer = "Trainer" if resp.get("is_trainer") else "Wild"
    double  = "Double" if resp.get("is_double") else "Single"
    print(f"Battle: {trainer} {double}")
    for pkm in resp.get("battlers", []):
        side = pkm.get("side", "?")
        nick = pkm.get("nickname", "")
        name = pkm.get("name", "?")
        label = nick if nick and nick != name else name
        print(f"  [{side:8s}] {label:12s} (#{pkm.get('species','?'):4})  Lv{pkm.get('level','?'):3}  "
              f"HP {pkm.get('hp','?'):>4}/{pkm.get('maxHP','?'):<4}")
        moves = pkm.get("moves", [])
        if moves:
            move_strs = [f"{m.get('name','?')}({m.get('pp','?')}pp)" for m in moves]
            print(f"           Moves: {', '.join(move_strs)}")


def _print_party(resp):
    note = resp.get("note", "")
    count = resp.get("count", 0)
    print(f"Party ({count} Pokémon):")
    for pkm in resp.get("party", []):
        hp    = pkm.get("hp", "?")
        maxhp = pkm.get("maxHP", "?")
        lvl   = pkm.get("level", "?")
        status= pkm.get("status", "")
        slot  = pkm.get("slot", "?")
        print(f"  Slot {slot}: Lv{lvl:3}  HP {hp:>4}/{maxhp:<4}  {status}")
    if note:
        print(f"  Note: {note}")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd_name = args[0].lower()
    rest = args[1:]

    # Build command dict
    if cmd_name == "read_state":
        cmd = {"cmd": "read_state"}
    elif cmd_name == "read_battle":
        cmd = {"cmd": "read_battle"}
    elif cmd_name == "read_party":
        cmd = {"cmd": "read_party"}
    elif cmd_name == "read_enemy":
        cmd = {"cmd": "read_enemy"}
    elif cmd_name == "read_flag":
        if not rest:
            print("Usage: read_flag <flag_id>"); sys.exit(1)
        cmd = {"cmd": "read_flag", "flag_id": parse_int(rest[0])}
    elif cmd_name == "set_flag":
        if len(rest) < 2:
            print("Usage: set_flag <flag_id> <0|1>"); sys.exit(1)
        cmd = {"cmd": "set_flag", "flag_id": parse_int(rest[0]), "value": parse_int(rest[1])}
    elif cmd_name == "read_var":
        if not rest:
            print("Usage: read_var <var_id>"); sys.exit(1)
        cmd = {"cmd": "read_var", "var_id": parse_int(rest[0])}
    elif cmd_name == "set_var":
        if len(rest) < 2:
            print("Usage: set_var <var_id> <value>"); sys.exit(1)
        cmd = {"cmd": "set_var", "var_id": parse_int(rest[0]), "value": parse_int(rest[1])}
    elif cmd_name == "warp":
        if len(rest) < 2:
            print("Usage: warp <map_group> <map_num> [x] [y]"); sys.exit(1)
        cmd = {"cmd": "warp", "map_group": parse_int(rest[0]), "map_num": parse_int(rest[1])}
        if len(rest) >= 3: cmd["x"] = parse_int(rest[2])
        if len(rest) >= 4: cmd["y"] = parse_int(rest[3])
    elif cmd_name == "warp_xy":
        if len(rest) < 2:
            print("Usage: warp_xy <x> <y>"); sys.exit(1)
        cmd = {"cmd": "warp", "x": parse_int(rest[0]), "y": parse_int(rest[1])}
    elif cmd_name == "press":
        if not rest:
            print("Usage: press <KEY[,KEY,...]> [frames]"); sys.exit(1)
        keys = [k.strip().upper() for k in rest[0].split(",")]
        frames = int(rest[1]) if len(rest) >= 2 else 1
        cmd = {"cmd": "press_buttons", "keys": keys, "frames": frames}
    elif cmd_name == "save_state":
        slot = int(rest[0]) if rest else 1
        cmd = {"cmd": "save_state", "slot": slot}
    elif cmd_name == "load_state":
        slot = int(rest[0]) if rest else 1
        cmd = {"cmd": "load_state", "slot": slot}
    elif cmd_name == "reset":
        cmd = {"cmd": "reset"}
    elif cmd_name == "lookup_species":
        if not rest:
            print("Usage: lookup_species <name>"); sys.exit(1)
        cmd = {"cmd": "lookup_species", "name": " ".join(rest)}
    elif cmd_name == "lookup_move":
        if not rest:
            print("Usage: lookup_move <name>"); sys.exit(1)
        cmd = {"cmd": "lookup_move", "name": " ".join(rest)}
    elif cmd_name == "lookup_map":
        if not rest:
            print("Usage: lookup_map <name>"); sys.exit(1)
        cmd = {"cmd": "lookup_map", "name": " ".join(rest)}
    elif cmd_name == "read_mem":
        if not rest:
            print("Usage: read_mem <addr> [size]"); sys.exit(1)
        cmd = {"cmd": "read_mem", "addr": parse_int(rest[0])}
        if len(rest) >= 2: cmd["size"] = int(rest[1])
    elif cmd_name == "write_mem":
        if len(rest) < 2:
            print("Usage: write_mem <addr> <value> [size]"); sys.exit(1)
        cmd = {"cmd": "write_mem", "addr": parse_int(rest[0]), "value": parse_int(rest[1])}
        if len(rest) >= 3: cmd["size"] = int(rest[2])
    elif cmd_name == "raw":
        if not rest:
            print("Usage: raw <json>"); sys.exit(1)
        try:
            cmd = json.loads(" ".join(rest))
        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}"); sys.exit(1)
    else:
        print(f"Unknown command: {cmd_name}")
        print(__doc__)
        sys.exit(1)

    resp = send_cmd(cmd)

    # Always print raw JSON if --json flag or if not a tty
    if "--json" in sys.argv or not sys.stdout.isatty():
        print(json.dumps(resp, indent=2))
    else:
        pretty(resp)


if __name__ == "__main__":
    main()
