#ifndef GUARD_PACKED_BOX_MON_H
#define GUARD_PACKED_BOX_MON_H

// BPE 2.1: Pokémon in the PC are stored as 60-byte records (480 bits) in RAM
// and in the save file. Party, battle and daycare Pokémon keep the 80-byte
// struct BoxPokemon.
//
// A record is unencrypted and has no checksum of its own; each save sector
// has a CRC-32. An empty slot is all zero bytes. Values are written least
// significant bit first, starting at bit 0 of byte 0. The first 8 bytes are
// the personality and original trainer id (the save engine relies on this).
//
// Not stored: current HP, status and PP (the Pokémon is healed), contest
// stats, all ribbons except the Champion Ribbon, the Pokémon's own checksum,
// and unused bits. hasSpecies is derived from the species.
//
// Keep BPETools and the website Save Converter in sync with this layout.

#define PACKED_BOX_MON_SIZE 60

struct BoxPokemon;

struct PackedBoxMon
{
    u8 data[PACKED_BOX_MON_SIZE];
};

//                               bit offset, width
#define PB_PERSONALITY               0, 32
#define PB_OT_ID                    32, 32
#define PB_NICKNAME_CHAR(i)         64 + 8 * (i), 8 // 12 characters
#define PB_OT_NAME_CHAR(i)         160 + 8 * (i), 8 // 7 characters
#define PB_LANGUAGE                216, 3
#define PB_HIDDEN_NATURE_MODIFIER  219, 5
#define PB_IS_BAD_EGG              224, 1
#define PB_IS_EGG                  225, 1
#define PB_DEAD                    226, 1
#define PB_DAYS_SINCE_FORM_CHANGE  227, 3
#define PB_MARKINGS                230, 4
#define PB_SHINY_MODIFIER          234, 1
#define PB_SPECIES                 235, 11
#define PB_TERA_TYPE               246, 5
#define PB_HELD_ITEM               251, 10
#define PB_EXPERIENCE              261, 21
#define PB_PP_BONUSES              282, 8
#define PB_FRIENDSHIP              290, 8
#define PB_POKEBALL                298, 6
#define PB_MOVE(i)                 304 + 11 * (i), 11
#define PB_EVOLUTION_TRACKER_1     348, 5
#define PB_EVOLUTION_TRACKER_2     353, 5
#define PB_HYPER_TRAINED(i)        358 + (i), 1 // HP, Atk, Def, Speed, SpAtk, SpDef
#define PB_EV(i)                   364 + 8 * (i), 8 // HP, Atk, Def, Speed, SpAtk, SpDef
#define PB_POKERUS                 412, 8
#define PB_MET_LOCATION            420, 8
#define PB_MET_LEVEL               428, 7
#define PB_MET_GAME                435, 4
#define PB_DYNAMAX_LEVEL           439, 4
#define PB_OT_GENDER               443, 1
#define PB_IV(i)                   444 + 5 * (i), 5 // HP, Atk, Def, Speed, SpAtk, SpDef
#define PB_GIGANTAMAX_FACTOR       474, 1
#define PB_CHAMPION_RIBBON         475, 1
#define PB_IS_SHADOW               476, 1
#define PB_ABILITY_NUM             477, 2
#define PB_MODERN_FATEFUL_ENCOUNTER 479, 1
#define PB_TOTAL_BITS              480

#define PB_NICKNAME_LENGTH 12

enum
{
    UNPACK_EMPTY,     // All zero: an empty slot
    UNPACK_OK,
    UNPACK_REPAIRED,  // An out-of-range item, move, ball, type or ability was cleared
    UNPACK_INVALID,   // No valid species; the slot was treated as empty
};

u32 GetPackedBits(const u8 *data, u32 offset, u32 width);
void SetPackedBits(u8 *data, u32 offset, u32 width, u32 value);
bool32 IsPackedBoxMonEmpty(const struct PackedBoxMon *mon);
void PackBoxMon(struct PackedBoxMon *dst, const struct BoxPokemon *src);
u32 UnpackBoxMon(struct BoxPokemon *dst, const struct PackedBoxMon *src);
// Returns TRUE and sets *value for fields that can be read without unpacking.
bool32 TryGetPackedBoxMonData(const struct PackedBoxMon *mon, s32 field, u8 *data, u32 *value);

#endif // GUARD_PACKED_BOX_MON_H
