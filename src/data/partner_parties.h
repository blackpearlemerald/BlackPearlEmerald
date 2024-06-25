static const struct TrainerMon sParty_StevenPartner[] = {
    {
        .species = SPECIES_SKARMORY,
        .lvl = 78,
        .ability = ABILITY_STURDY,
        .nature = NATURE_ADAMANT,
        .iv = TRAINER_PARTY_IVS(31, 31, 31, 31, 31, 31),
        .ev = TRAINER_PARTY_EVS(0, 252, 252, 0, 6, 0),
        .heldItem = ITEM_ROCKY_HELMET,
        .moves = {MOVE_BRAVE_BIRD, MOVE_STEEL_WING, MOVE_ROCK_SLIDE, MOVE_DRILL_RUN},
    },
    {
        .species = SPECIES_CLAYDOL,
        .lvl = 78,
        .nature = NATURE_MODEST,
        .iv = TRAINER_PARTY_IVS(31, 31, 31, 31, 31, 31),
        .ev = TRAINER_PARTY_EVS(252, 0, 0, 0, 6, 252),
        .heldItem = ITEM_LEFTOVERS,
        .moves = {MOVE_PSYCHIC, MOVE_EARTH_POWER, MOVE_SHADOW_BALL, MOVE_ICE_BEAM},
    },
    {
        .species = SPECIES_AGGRON,
        .lvl = 78,
        .ability = ABILITY_ROCK_HEAD,
        .nature = NATURE_ADAMANT,
        .iv = TRAINER_PARTY_IVS(31, 31, 31, 31, 31, 31),
        .ev = TRAINER_PARTY_EVS(0, 252, 0, 0, 252, 6),
        .heldItem = ITEM_LEFTOVERS,
        .moves = {MOVE_DOUBLE_EDGE, MOVE_DRAGON_CLAW, MOVE_IRON_TAIL, MOVE_HEAD_SMASH},
    }
};
