// SPDX-License-Identifier: Apache-2.0
// DEVICE-ONLY: Wi-Fi, brain bridge client, camera, speaker, vibration motor and IMU gestures.
// Never listed in pc/CMakeLists.txt.
#pragma once

#include "esp_err.h"
#include "face_ui.h"

typedef enum {
    PET_EVENT_BOOT = 0,
    PET_EVENT_POKE,
    PET_EVENT_HOLD,
    PET_EVENT_PICKUP,
    PET_EVENT_SHAKE,
    PET_EVENT_FLIP,
    PET_EVENT_PUTDOWN,
    PET_EVENT_STATS,       /* double tap */
    PET_EVENT_LOOK,        /* camera glance every PET_LOOK_SECONDS while quiet */
    PET_EVENT_IDLE,        /* nothing happened for a while */
    PET_EVENT_COUNT,
} pet_event_t;

/* Starts speaker, motor, IMU, Wi-Fi and the brain task. Missing hardware is logged and skipped. */
esp_err_t pet_hw_start(void);

/* face_ui ops backed by the brain task (pokes in, expression + speaking out). */
const face_ui_ops_t *pet_hw_face_ops(void);
