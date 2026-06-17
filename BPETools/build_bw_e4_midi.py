# One-off: prepare the new BW Elite Four MIDI for mid2agb porting onto voicegroup_bw_e4_gm.
# - percussion channels 7,8,9 -> program 1 (which the voicegroup maps to voice_keysplit_all voicegroupDrum1)
# - translate GM drum note numbers -> voicegroupDrum1 native entry indices (preserves Drum1 tuning)
# - strip 0xFF 0x01-0x07 (text/name) and 0xFF 0x7F (sequencer-specific) meta, carrying delta times forward
# - keep tempo(0x51), time sig(0x58), key sig(0x59), end-of-track(0x2F)
import struct

SRC = "BPETools/Resources/unova music/Battle! Unova Elite Four.mid"
DST = "sound/songs/midi/mus_bw_vs_elite_four.mid"

DRUM_CHANS = {7, 8, 9}
DRUM_PROGRAM = 1
# GM drum note -> voicegroupDrum1 entry index (native position = correct tuning)
NOTE_MAP = {
    34: 45,  # -> closed hi-hat (tentative)
    35: 36, 36: 36,   # kick
    38: 43,  # acoustic snare -> dp_093snare
    40: 41,  # main snare -> dp_oct_snare
    42: 45,  # closed hi-hat -> hg_062chh
    46: 49,  # open hi-hat -> hg_063ohh
    48: 52,  # ch8 cymbal -> crash
    49: 52,  # crash 1 -> hg_032crash
    52: 55,  # china -> hg_022china
    53: 56,  # ride bell -> dp_ridecap
    54: 57,  # tambourine -> dp_tambourine
    55: 58,  # splash -> hg_114splash
    57: 53,  # crash 2 -> hg_032crash (alt)
    9:  51,  # ch8 low cymbal -> orch cymbal
    90: 90,  # triangle (native)
}

def read_vlq(d, i):
    v = 0
    while True:
        b = d[i]; i += 1; v = (v << 7) | (b & 0x7f)
        if not b & 0x80:
            break
    return v, i

def write_vlq(v):
    out = bytearray([v & 0x7f])
    v >>= 7
    while v:
        out.insert(0, (v & 0x7f) | 0x80)
        v >>= 7
    return bytes(out)

def parse_track(body):
    """Return list of (delta, kind, bytes) events; kind in {'meta','sysex','chan'}."""
    i = 0; status = 0; evs = []
    while i < len(body):
        delta, i = read_vlq(body, i)
        b = body[i]
        if b & 0x80:
            status = b; i += 1
        # else running status; status unchanged, data starts at i
        if status == 0xFF:
            mtype = body[i]; i += 1
            ln, i = read_vlq(body, i)
            data = body[i:i+ln]; i += ln
            evs.append((delta, 'meta', mtype, data))
        elif status in (0xF0, 0xF7):
            ln, i = read_vlq(body, i)
            data = body[i:i+ln]; i += ln
            evs.append((delta, 'sysex', status, data))
        else:
            hi = status & 0xF0
            if hi in (0xC0, 0xD0):
                p = body[i]; i += 1
                evs.append((delta, 'chan', status, bytes([p])))
            else:
                p = body[i:i+2]; i += 2
                evs.append((delta, 'chan', status, p))
    return evs

def rewrite_track(evs):
    out = []
    carry = 0
    chans_here = set(e[2] & 0x0F for e in evs if e[1] == 'chan')
    is_drum_track = bool(chans_here & DRUM_CHANS) and not (chans_here - DRUM_CHANS)
    forced_pc = not is_drum_track  # for drum tracks, force a PC1 at start
    for delta, kind, a, data in evs:
        d = delta + carry
        if kind == 'meta':
            mtype = a
            if mtype in range(0x01, 0x08) or mtype == 0x7F:
                carry = d  # drop, carry delta forward
                continue
            out.append((d, bytes([0xFF, mtype]) + write_vlq(len(data)) + data))
            carry = 0
        elif kind == 'sysex':
            out.append((d, bytes([a]) + write_vlq(len(data)) + data))
            carry = 0
        else:  # chan
            status = a; ch = status & 0x0F; hi = status & 0xF0
            if ch in DRUM_CHANS:
                if not forced_pc:
                    # inject a program-change to DRUM_PROGRAM at the very start
                    out.append((d, bytes([0xC0 | ch, DRUM_PROGRAM])))
                    forced_pc = True
                    d = 0
                if hi == 0xC0:
                    # rewrite any program change on drum channel to DRUM_PROGRAM
                    out.append((d, bytes([status, DRUM_PROGRAM])))
                elif hi in (0x90, 0x80):  # note on/off -> translate note number
                    note = data[0]
                    note = NOTE_MAP.get(note, note)
                    out.append((d, bytes([status, note, data[1]])))
                else:
                    out.append((d, bytes([status]) + data))
            else:
                out.append((d, bytes([status]) + data))
            carry = 0
    return out

def serialize_track(out):
    body = bytearray()
    for delta, raw in out:
        body += write_vlq(delta) + raw
    return bytes(body)

with open(SRC, 'rb') as f:
    d = f.read()
assert d[:4] == b'MThd'
fmt, ntrk, div = struct.unpack('>HHH', d[8:14])
pos = 14
tracks = []
while pos < len(d) and d[pos:pos+4] == b'MTrk':
    ln = struct.unpack('>I', d[pos+4:pos+8])[0]
    tracks.append(d[pos+8:pos+8+ln]); pos += 8 + ln

new_tracks = []
for body in tracks:
    evs = parse_track(body)
    out = rewrite_track(evs)
    new_tracks.append(serialize_track(out))

with open(DST, 'wb') as f:
    f.write(b'MThd' + struct.pack('>IHHH', 6, fmt, len(new_tracks), div))
    for t in new_tracks:
        f.write(b'MTrk' + struct.pack('>I', len(t)) + t)

print(f"wrote {DST}: format={fmt} tracks={len(new_tracks)} div={div}")
print(f"src bytes={len(d)} dst bytes={14 + sum(8+len(t) for t in new_tracks)}")
