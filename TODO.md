# TODO

1. Revert trainer locations to original game (keep teams, just remove forced trainer battles on every route) — complete through Route 124 (Route 122 is water-only, no trainers)
2. Add a teleport option to Trick Room
3. Make Trick Room celebrities easier to understand — Rooms 1 (Kanto E4), 2 (Johto E4), 3 (Hoenn E4), 4 (Sinnoh E4), and 5 (Unova E4) DONE and verified in-game: real sprites, portraits, Elite Four class + authentic battle music. Remaining work:
   - Room 6 (Kalos E4: Malva/Drasna/Siebold/Wikstrom) NEEDS WORK — wired up & builds, but verified "very scuffed" in-game. Issues: (a) Malva/Wikstrom/Siebold battle portraits from Gnomowladny sheet + Drasna has NO battle portrait (stays Cooltrainer F — no full-body 2D sprite exists anywhere); (b) OW sprites are downscales/4G mix that read poorly at GBA scale; (c) XY music port (vgmusic VS_shitenno.mid on vg191) sounds off. Likely all of sprites + music need redo. Consider: better-sourced Kalos sprites (hand-pixeled), and swap music to a confirmed-good in-ROM E4 theme (DPPt) or a cleaner MIDI.
   - Rooms 7-8 unconverted: Room 7 = Alola+Galar mix (Hala/Olivia/Nessa/Hop), Room 8 = Paldea E4 (Rika/Hassel/Larry/Poppy). Hard: Gen 6-9 have no official 2D sprites (community customs only) and no pre-ported music (NDS Expansion fork caps at Gen 5)
   - Room 2 (HGSS) and Room 5 (BW) battle themes sound off despite being byte-identical to the NDS Music Expansion fork output (voicegroups/mid2agb/aif2pcm/include-order all verified) — either GBA renditions inherently sound like this or source MIDIs are weak; options: A/B against a fork-built ROM, find better community MIDIs, or swap Room 2 to mus_hg_vs_gym_leader and Room 5 to the DPPt E4 theme
   - Aaron/Flint + all four Unova portraits are auto-devamps — replace if community packs ever cover them
   - Cameo trainers still use vanilla dialogue
4. New auto-updating documentation on GitHub page

