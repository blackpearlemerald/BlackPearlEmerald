# Generate sound/voicegroups/voicegroup_bw_e4_gm.inc
# GM-ordered voicegroup for the improved BW Elite Four theme, reusing vg274 / Drum1 samples.
DUMMY = "\tvoice_square_1 60, 0, 0, 2, 0, 0, 15, 0\t@ dummy"
SQUARE = "\tvoice_directsound 60, 0, DirectSoundWaveData_puresquare_50, 255, 242, 25, 0\t@ GB square lead"

entries = {i: DUMMY for i in range(128)}
entries[0]  = "\tvoice_keysplit voicegroupInst1, KeySplitTable90\t@ piano"
entries[1]  = "\tvoice_keysplit_all voicegroupDrum1\t@ drum kit (GM-mapped notes)"
entries[9]  = "\tvoice_directsound 60, 0, DirectSoundWaveData_bw_glockenspiel_c5, 255, 249, 0, 208\t@ glockenspiel"
entries[29] = "\tvoice_keysplit voicegroup249, KeySplitTable32\t@ distortion guitar"
entries[35] = "\tvoice_keysplit voicegroup253, KeySplitTable43\t@ fingered bass"
entries[38] = "\tvoice_keysplit voicegroup254, KeySplitTable44\t@ synth bass"
entries[47] = "\tvoice_keysplit voicegroup260, KeySplitTable40\t@ timpani"
entries[48] = "\tvoice_keysplit voicegroup255, KeySplitTable45\t@ strings"
entries[55] = "\tvoice_directsound 60, 0, DirectSoundWaveData_bw_orch_hit_c5, 255, 250, 2, 208\t@ orchestra hit"
entries[56] = "\tvoice_keysplit voicegroup261, KeySplitTable39\t@ trumpet"
entries[58] = "\tvoice_keysplit voicegroupInst34, KeySplitTable22\t@ tuba"
entries[60] = "\tvoice_keysplit voicegroup264, KeySplitTable50\t@ french horn"
entries[72] = "\tvoice_keysplit voicegroup251, KeySplitTable41\t@ clean guitar"
entries[80] = SQUARE
entries[81] = SQUARE  # GB sawtooth lead (square stand-in; .sf2 saw is the refinement)
entries[83] = SQUARE  # GB chiff
entries[84] = SQUARE  # GB charang

lines = ["\t.align 2", "voicegroup_bw_e4_gm:: @ improved BW Elite Four (GM-mapped onto vg274/Drum1 samples)"]
for i in range(128):
    lines.append(entries[i])

with open("sound/voicegroups/voicegroup_bw_e4_gm.inc", "w", newline="\n") as f:
    f.write("\n".join(lines) + "\n")
print("wrote voicegroup_bw_e4_gm.inc with 128 entries")
