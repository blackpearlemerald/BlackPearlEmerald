static const struct TrainerMon sParty_StevenPartner[] = {
    {
        .species = SPECIES_METAGROSS,
        .lvl = 78,
        .nature = NATURE_BRAVE,
        .iv = TRAINER_PARTY_IVS(31, 31, 31, 31, 31, 31),
        .ev = TRAINER_PARTY_EVS(0, 252, 252, 0, 6, 0),
        .heldItem = ITEM_METAGROSSITE,
        .moves = {MOVE_ROCK_SLIDE, MOVE_METEOR_MASH, MOVE_ICE_PUNCH, MOVE_EARTHQUAKE},
    },
    {
        .species = SPECIES_SKARMORY,
        .lvl = 78,
        .nature = NATURE_IMPISH,
        .iv = TRAINER_PARTY_IVS(31, 31, 31, 31, 31, 31),
        .ev = TRAINER_PARTY_EVS(252, 0, 0, 0, 6, 252),
        .heldItem = ITEM_OCCA_BERRY,
        .moves = {MOVE_ROOST, MOVE_IRON_HEAD, MOVE_DRILL_RUN, MOVE_ROCK_SLIDE},
    },
    {
        .species = SPECIES_AGGRON,
        .lvl = 78,
        .nature = NATURE_ADAMANT,
        .iv = TRAINER_PARTY_IVS(31, 31, 31, 31, 31, 31),
        .ev = TRAINER_PARTY_EVS(0, 252, 0, 0, 252, 6),
        .heldItem = ITEM_OCCA_BERRY,
        .moves = {MOVE_ROCK_SLIDE, MOVE_EARTHQUAKE, MOVE_DOUBLE_EDGE, MOVE_IRON_HEAD},
    }
};
