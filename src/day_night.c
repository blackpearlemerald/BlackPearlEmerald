#include "global.h"
#include "day_night.h"
#include "rtc.h"
#include "constants/day_night.h"

u8 GetCurrentTimeOfDay(void)
{
    if (gLocalTime.hours < HOUR_MORNING)
        return TIME_NIGHT;
    else if (gLocalTime.hours < HOUR_DAY)
        return TIME_MORNING;
    else if (gLocalTime.hours < HOUR_NIGHT)
        return TIME_DAY;

    return TIME_NIGHT;
}
