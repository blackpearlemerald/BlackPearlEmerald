#ifndef GUARD_FIELD_SPECIALS_H
#define GUARD_FIELD_SPECIALS_H

#include "constants/species.h"

extern bool8 gBikeCyclingChallenge;
extern u8 gBikeCollisions;
extern u16 gScrollableMultichoice_ScrollOffset;

u8 GetLeadMonIndex(void);
bool8 IsDestinationBoxFull(void);
u16 GetPCBoxToSendMon(void);
bool8 InMultiPartnerRoom(void);
void UpdateTrainerFansAfterLinkBattle(void);
void IncrementBirthIslandRockStepCount(void);
bool8 AbnormalWeatherHasExpired(void);
bool8 ShouldDoBrailleRegicePuzzle(void);
bool32 ShouldDoWallyCall(void);
bool32 ShouldDoScottFortreeCall(void);
bool32 ShouldDoScottBattleFrontierCall(void);
bool32 ShouldDoRoxanneCall(void);
bool32 ShouldDoRivalRayquazaCall(void);
bool32 CountSSTidalStep(u16 delta);
enum SSTidalLocation GetSSTidalLocation(s8 *mapGroup, s8 *mapNum, s16 *x, s16 *y);
void ShowScrollableMultichoice(void);
void FrontierGamblerSetWonOrLost(bool8 won);
u8 TryGainNewFanFromCounter(u8 incrementId);
bool8 InPokemonCenter(void);
void SetShoalItemFlag(u16 unused);
void UpdateFrontierManiac(u16 daysSince);
void UpdateFrontierGambler(u16 daysSince);
void ResetCyclingRoadChallengeData(void);
bool8 UsedPokemonCenterWarp(void);
void ResetFanClub(void);
bool8 ShouldShowBoxWasFullMessage(void);
void SetPCBoxToSendMon(u8 boxId);
void PreparePartyForSkyBattle(void);
void GetObjectPosition(u16*, u16*, u32, u32);
bool32 CheckObjectAtXY(u32, u32);
bool32 CheckPartyHasSpecies(enum Species);
bool8 CutMoveRuinValleyCheck(void);
void CutMoveOpenDottedHoleDoor(void);

// BPE: ticked every overworld frame from DoCB1_Overworld. Renames the location
// popup while the player stands on Mirage Island, a sub-area of Route 130.
void UpdateMirageIslandNamePopup(void);

// BPE: whether a Mirage Island pool legendary has been caught there, so the
// island no longer offers it.
bool32 IsIslandLegendaryCaught(u16 species);
void RecordIslandLegendaryCatch(void);

// BPE: sets the pre-Elite Four legendaries' hide flags from their catch state.
// Runs on every map load, before the map's ON_TRANSITION script.
void UpdatePreE4Legendaries(void);

// BPE: the Pokemon the player picked from the Birch Case.
enum Species GetPlayerStarterSpecies(void);

#endif // GUARD_FIELD_SPECIALS_H
