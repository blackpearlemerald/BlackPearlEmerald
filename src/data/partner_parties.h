static const struct TrainerMon sParty_StevenPartner[] = {
    {
        .species = SPECIES_METAGROSS,
        .lvl = 78,
        .nature = NATURE_ADAMANT,
        .iv = TRAINER_PARTY_IVS(31, 31, 31, 31, 31, 31),
        .ev = TRAINER_PARTY_EVS(0, 252, 252, 0, 6, 0),
        .heldItem = ITEM_OCCA_BERRY,
        .moves = {MOVE_ROCK_SLIDE, MOVE_METEOR_MASH, MOVE_PROTECT, MOVE_ZEN_HEADBUTT},
    },
    {
        .species = SPECIES_ANNIHILAPE,
        .lvl = 78,
        .nature = NATURE_ADAMANT,
        .iv = TRAINER_PARTY_IVS(31, 31, 31, 31, 31, 31),
        .ev = TRAINER_PARTY_EVS(252, 0, 0, 0, 6, 252),
        .heldItem = ITEM_CHESTO_BERRY,
        .moves = {MOVE_BULK_UP, MOVE_DRAIN_PUNCH, MOVE_RAGE_FIST, MOVE_REST},
    },
    {
        .species = SPECIES_DRAGONITE,
        .lvl = 78,
        .nature = NATURE_ADAMANT,
        .iv = TRAINER_PARTY_IVS(31, 31, 31, 31, 31, 31),
        .ev = TRAINER_PARTY_EVS(0, 252, 0, 0, 252, 6),
        .heldItem = ITEM_LEFTOVERS,
        .moves = {MOVE_EXTREME_SPEED, MOVE_DRAGON_DANCE, MOVE_DRAGON_CLAW, MOVE_WATERFALL},
    }
};
