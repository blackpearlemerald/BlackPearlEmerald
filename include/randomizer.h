#ifndef GUARD_RANDOMIZER_H
#define GUARD_RANDOMIZER_H

#include "constants/randomizer.h"
#include "constants/species.h"
#include "constants/items.h"
#include "constants/moves.h"
#include "constants/pokemon.h"

struct Evolution;
struct LevelUpMove;
struct Trainer;
struct TrainerMon;
struct Pokemon;

// The randomizer's settings while they are being chosen. In a game they live in
// the save variables listed in include/constants/randomizer.h.
struct RandomizerSettings
{
    u32 seed;
    u16 options[RANDOMIZER_OPTION_COUNT];
};

// Settings
bool32 Randomizer_IsActive(void);
u32 Randomizer_GetOption(enum RandomizerOption option);
u32 Randomizer_GetOptionMax(enum RandomizerOption option);
u32 Randomizer_GetSavedVersion(void);
void Randomizer_ApplyPreset(struct RandomizerSettings *settings, enum RandomizerPreset preset);
enum RandomizerPreset Randomizer_GetPreset(const struct RandomizerSettings *settings);
void Randomizer_LoadSettings(struct RandomizerSettings *settings);
void Randomizer_SaveSettings(const struct RandomizerSettings *settings);
void Randomizer_ClearSettings(void);
u32 Randomizer_NewSeed(void);
void Randomizer_EncodeSeedCode(const struct RandomizerSettings *settings, u8 *dest);
enum RandomizerCodeResult Randomizer_DecodeSeedCode(const u8 *code, struct RandomizerSettings *settings);
u8 Randomizer_GetCodeChar(u32 index);
u32 Randomizer_GetCodeAlphabetSize(void);
void Randomizer_BufferSeedCode(u8 *dest);

// Species pool
bool32 Randomizer_IsSpeciesInPool(enum Species species);
bool32 Randomizer_IsLegendary(enum Species species);
u32 Randomizer_GetSpeciesGeneration(enum Species species);
enum Species Randomizer_GetFamilyRoot(enum Species species);
u32 Randomizer_GetEvolutionStage(enum Species species);
u32 Randomizer_GetFamilyLength(enum Species species);

// Pokémon the player meets
enum Species Randomizer_GetWildSpecies(enum Species species, u16 mapId, u32 area);
enum Species Randomizer_GetCurrentMapWildSpecies(enum Species species, u32 area);
enum Species Randomizer_GetWildSwapOriginal(enum Species species);
enum Species Randomizer_GetGiftSpecies(enum Species species);
enum Species Randomizer_GetStaticSpecies(enum Species species);
enum Species Randomizer_GetStaticSpeciesOnMap(enum Species species, u16 mapId);
enum Species Randomizer_GetTradeSpecies(u32 trade, enum Species species);
enum Species Randomizer_GetTradeRequestedSpecies(u32 trade, enum Species species);
enum Species Randomizer_GetStoryWildSpecies(enum Species species, u16 mapId);
enum Species Randomizer_GetWallyCatchSpecies(enum Species species);
enum Species Randomizer_GetStarterSpecies(u32 ball, enum Species original);
void Randomizer_FillStarters(u16 *species, u32 count);
void Randomizer_EnsureStarterCanAttack(struct Pokemon *mon);
u16 Randomizer_GetStaticObjectGraphics(u16 mapId, u16 graphicsId);
enum Species Randomizer_GetStaticCrySpecies(enum Species species);
enum Species Randomizer_GetEggSpecies(enum Species species);
bool32 Randomizer_IsFullHoennDexPossible(void);

// Trainers
bool32 Randomizer_ShouldRandomizeTrainer(const struct Trainer *trainer);
bool32 Randomizer_KeepsTrainerAbilities(const struct Trainer *trainer);
enum Species Randomizer_GetTrainerSpecies(const struct Trainer *trainer, u32 monIndex);
enum Item Randomizer_GetTrainerHeldItem(enum Species original, enum Species species, enum Item item);
void Randomizer_GiveTrainerMonMoves(struct Pokemon *mon);

// Species data
enum Ability Randomizer_GetSpeciesAbility(enum Species species, u32 slot, enum Ability ability);
enum Type Randomizer_GetSpeciesType(enum Species species, u32 slot, enum Type type);
u32 Randomizer_GetSpeciesBaseStat(enum Species species, u32 stat, u32 value);
u16 Randomizer_GetLevelUpMove(enum Species species, u32 index, u16 move);
bool32 Randomizer_CanLearnTeachableMove(enum Species species, enum Move move, bool32 canLearn);
enum Species Randomizer_GetEvolutionTarget(enum Species species, enum Species target);
u32 Randomizer_GetTypeChartType(u32 type);

// TMs
u32 Randomizer_GetTMIndexContents(u32 tmIndex);
u32 Randomizer_GetTMIndexTeaching(u32 tmIndex);

// Field items
bool32 Randomizer_GetFieldItem(u16 flag, u16 *item, u16 *amount);

// HMs
bool32 Randomizer_HasHMFallback(enum Move move);

#endif // GUARD_RANDOMIZER_H
