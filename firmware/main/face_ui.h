// SPDX-License-Identifier: Apache-2.0
// PORTABLE Pom-pom face UI (device + PC simulator). Only esp_gsp.h, bundle_gsp.h and plain C.
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_gsp.h"

/* Shared expression contract with the bridge (keep in sync with AGENTS.md):
 * idle, happy, surprised, dizzy, sad, love, sleepy, talking. */
typedef enum {
    FACE_EXPR_IDLE = 0,
    FACE_EXPR_HAPPY,
    FACE_EXPR_SURPRISED,
    FACE_EXPR_DIZZY,
    FACE_EXPR_SAD,
    FACE_EXPR_LOVE,
    FACE_EXPR_SLEEPY,
    FACE_EXPR_TALKING,
    FACE_EXPR_COUNT,
} face_expr_t;

const char *face_expr_name(face_expr_t expr);
/* Parses a contract name (e.g. the bridge's X-Face header). Returns false if unknown. */
bool face_expr_from_name(const char *name, face_expr_t *out);

typedef enum {
    FACE_INPUT_POKE = 0,   /* finger down anywhere on the screen (x, y valid) */
    FACE_INPUT_HOLD,       /* 500 ms long press (GSP "long" event) */
} face_input_kind_t;

typedef struct {
    face_input_kind_t kind;
    int32_t x;
    int32_t y;
} face_input_t;

/* What the brain wants on screen. Bump seq whenever expr changes. */
typedef struct {
    uint32_t seq;
    face_expr_t expr;
    bool speaking;          /* mouth flaps while true, on top of any expression */
} face_state_t;

typedef struct {
    /* Render task; must not block (device: xQueueSend with 0 timeout). May be NULL. */
    void (*on_input)(const face_input_t *input, void *ctx);
    /* Render task; copies the latest state, false if none. May be NULL. */
    bool (*get_state)(face_state_t *out, void *ctx);
    void *ctx;
} face_ui_ops_t;

typedef struct {
    face_ui_ops_t ops;
    /* Debug: tap cycles the expressions, long press toggles talking, name shown at the bottom. */
    bool debug_cycle;
} face_ui_config_t;

typedef enum {
    FACE_MOTION_NONE = 0,
    FACE_MOTION_HOP_UP,
    FACE_MOTION_HOP_DOWN,
    FACE_MOTION_SQUASH,     /* dip down; the expression swaps at the bottom */
    FACE_MOTION_SWAPPED,    /* next tick: start the new extras and bounce back */
    FACE_MOTION_UNSQUASH,
} face_motion_t;

/* Single owner: the GSP render task (timer, event and pointer callbacks all run there). */
typedef struct {
    face_ui_config_t cfg;
    void *timer;
    uint32_t ticks;
    uint32_t next_blink;
    uint32_t rng;
    face_motion_t motion;
    uint32_t motion_until;
    face_expr_t shown;
    face_expr_t pending;
    /* What is visible right now, so updates only touch what changes
     * (GSP queues at most 24 updates per render cycle by default). */
    uint8_t vis_eyes;
    uint8_t vis_brows;
    uint8_t vis_mouth;
    bool vis_tear;
    bool vis_zzz;
    bool vis_blush;
    /* Idle life (step 9): glances and yawns while idle and quiet. */
    uint8_t fidget;
    uint32_t fidget_until;
    uint32_t next_fidget;
    uint32_t next_yawn;
    bool speaking;
    bool talk_anim;
    uint32_t brain_seq;
    face_state_t brain;
    int32_t last_x;
    int32_t last_y;
    esp_gsp_err_t last_error;
    int last_error_line;      /* face_ui.c line of the last failed GSP call */
    uint32_t error_count;
} face_ui_t;

/* cfg may be NULL (no ops, debug off). */
esp_gsp_err_t face_ui_init(esp_gsp_handle_t ui, face_ui_t *st, const face_ui_config_t *cfg);
void face_ui_deinit(esp_gsp_handle_t ui, face_ui_t *st);

/* Render-task only (timers/callbacks). Other tasks go through ops.get_state. */
void face_ui_set_expression(esp_gsp_handle_t ui, face_ui_t *st, face_expr_t expr);
void face_ui_set_speaking(esp_gsp_handle_t ui, face_ui_t *st, bool speaking);
