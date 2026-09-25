// Loads a flash image with the game's own save engine (src/save_engine.c) and
// writes what the game would hold in RAM, so tools can compare it.
//
//   save_verify <image.sav> <out.bin>
//
// out.bin: u8 status, u32 load flags, u32 game id, u32 counter, then
// SaveBlock2, the 41-box storage header, SaveBlock3, SaveBlock1 and the
// packed PC records. Sizes are the 2.1 sizes checked by test/save.c.

#ifndef SAVE_ENGINE_HOST
#define SAVE_ENGINE_HOST
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "save_engine.h"

#define SB2_SIZE    2852
#define HEADER_SIZE 812
#define SB3_SIZE    4
// Must equal SAVEBLOCK1_SIZE in BPETools/bpe_save_format.py, not the game's
// current sizeof(struct SaveBlock1): this tool streams the blocks back to
// test_bpe_save_format.py, which slices them at the Python sizes.
#define SB1_SIZE    15836
#define MON_COUNT   (41 * 30)

static unsigned char flash[SAVE_SECTOR_COUNT * SAVE_SECTOR_SIZE];

void SaveIo_ReadSector(u8 sector, u8 *dst)
{
    memcpy(dst, flash + sector * SAVE_SECTOR_SIZE, SAVE_SECTOR_SIZE);
}

bool8 SaveIo_ProgramSector(u8 sector, const u8 *src)
{
    return TRUE;
}

bool8 SaveIo_ProgramSectorSkipByte(u8 sector, const u8 *src, u16 skipOffset)
{
    return TRUE;
}

bool8 SaveIo_ProgramByte(u8 sector, u16 offset, u8 value)
{
    return TRUE;
}

bool8 SaveIo_MonChangeGainsData(const u8 *oldMon, const u8 *newMon)
{
    return TRUE;
}

int main(int argc, char **argv)
{
    static u8 sb2[SB2_SIZE], header[HEADER_SIZE], sb3[SB3_SIZE], sb1[SB1_SIZE], boxes[MON_COUNT * SAVE_BOX_MON_SIZE];
    struct SaveEngineLayout layout = {0};
    FILE *file;
    u8 status;
    u32 value;

    if (argc != 3)
    {
        fprintf(stderr, "usage: save_verify <image> <out>\n");
        return 2;
    }
    file = fopen(argv[1], "rb");
    if (!file || fread(flash, 1, sizeof(flash), file) != sizeof(flash))
    {
        fprintf(stderr, "could not read 128 KiB from %s\n", argv[1]);
        return 2;
    }
    fclose(file);

    layout.part0[0].data = sb2;
    layout.part0[0].size = SB2_SIZE;
    layout.part0[1].data = header;
    layout.part0[1].size = HEADER_SIZE;
    layout.part0[2].data = sb3;
    layout.part0[2].size = SB3_SIZE;
    layout.part0Count = 3;
    layout.progressTail = sb1;
    layout.progressTailSize = SB1_SIZE;
    layout.boxData = boxes;
    layout.boxMonCount = MON_COUNT;
    SaveEngine_SetLayout(&layout);

    status = SaveEngine_Load();

    file = fopen(argv[2], "wb");
    if (!file)
        return 2;
    fwrite(&status, 1, 1, file);
    value = SaveEngine_GetLoadFlags();
    fwrite(&value, 4, 1, file);
    value = SaveEngine_GetGameId();
    fwrite(&value, 4, 1, file);
    value = SaveEngine_GetCounter();
    fwrite(&value, 4, 1, file);
    fwrite(sb2, 1, sizeof(sb2), file);
    fwrite(header, 1, sizeof(header), file);
    fwrite(sb3, 1, sizeof(sb3), file);
    fwrite(sb1, 1, sizeof(sb1), file);
    fwrite(boxes, 1, sizeof(boxes), file);
    fclose(file);
    return 0;
}
