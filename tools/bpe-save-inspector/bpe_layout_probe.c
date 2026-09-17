// This file is compiled (never linked) to make the active BPE save structures
// available as DWARF data for generate_layout.py.
#include "global.h"
#include "pokemon_storage_system.h"
#include "save.h"

struct SaveBlock1 bpe_layout_save_block_1;
struct SaveBlock2 bpe_layout_save_block_2;
struct SaveBlock3 bpe_layout_save_block_3;
struct PokemonStorage bpe_layout_pokemon_storage;
struct SaveSector bpe_layout_save_sector;
struct Pokemon bpe_layout_pokemon;
struct BoxPokemon bpe_layout_box_pokemon;
#ifdef PACKED_BOX_MON_SIZE // 2.1 and later
struct PackedBoxMon bpe_layout_packed_box_mon;
#endif
