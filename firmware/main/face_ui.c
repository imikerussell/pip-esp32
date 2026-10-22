// SPDX-License-Identifier: Apache-2.0
// PORTABLE Pom-pom face UI. Compiled for the device AND the PC simulator.
//   Layers (all inside the `pom` container): body, brows, eyes, mouth, extras (tear, zzz, love blush).
//   An expression = which layer variant is visible + its little animation.
//   Changing expression: quick squash down, swap at the bottom, bounce back.
//   Speaking: the talk mouth replaces the expression mouth and flaps (morph closed<->open).
#include "face_ui.h"

#include <stddef.h>
#include <string.h>
#include "bundle_gsp.h"

#define FACE_TICK_MS          100U
#define FACE_POM_X            40
#define FACE_POM_REST_Y       44
#define FACE_POM_BREATH_Y     52       /* bob depth 8 px */
#define FACE_POM_SLEEP_Y      56       /* deeper, slower breaths when sleepy */
#define FACE_POM_HOP_Y        14       /* poke hop: 30 px */
#define FACE_POM_SQUASH_Y     58       /* expression change dip: 14 px */
#define FACE_BREATH_MS        1800U    /* one way */
#define FACE_SLEEP_BREATH_MS  2600U
#define FACE_BLINK_MS         90U
#define FACE_SLOW_BLINK_MS    420U
#define FACE_SLEEP_CLOSE_MS   500U
#define FACE_BLINK_MIN_TICKS  25U
#define FACE_BLINK_SPAN_TICKS 25U
#define FACE_DOUBLE_BLINK_PCT 20U
#define FACE_HOP_UP_MS        130U
#define FACE_HOP_DOWN_MS      260U
#define FACE_SQUASH_MS        90U
#define FACE_UNSQUASH_MS      220U
#define FACE_TALK_FLAP_MS     110U
#define FACE_DIZZY_SPIN_MS    900U
#define FACE_DIZZY_SWAY_MS    450U
#define FACE_DIZZY_SWAY_PX    8
#define FACE_TEAR_X           298
#define FACE_TEAR_Y           214
#define FACE_TEAR_DROP_Y      240
#define FACE_TEAR_DROP_MS     1300U
#define FACE_ZZZ_X            316
#define FACE_ZZZ_Y            10
#define FACE_ZZZ_RISE_Y       -14
#define FACE_ZZZ_RISE_MS      1600U
#define FACE_EYES_X           88
#define FACE_EYES_Y           158
#define FACE_GLANCE_PX        16
#define FACE_GLANCE_UP_PX     6
#define FACE_GLANCE_MS        260U
#define FACE_FIDGET_MIN_TICKS 50U      /* 5 s */
#define FACE_FIDGET_SPAN_TICKS 60U     /* + up to 6 s */
#define FACE_YAWN_MIN_TICKS   450U     /* 45 s */
#define FACE_YAWN_SPAN_TICKS  450U
#define FACE_YAWN_OPEN_MS     700U
#define FACE_YAWN_TICKS       18U

enum { FIDGET_NONE = 0, FIDGET_GLANCE, FIDGET_YAWN };

static const char *const s_names[FACE_EXPR_COUNT] = {
    "idle", "happy", "surprised", "dizzy", "sad", "love", "sleepy", "talking",
};

const char *face_expr_name(face_expr_t expr)
{
    return (unsigned)expr < FACE_EXPR_COUNT ? s_names[expr] : "idle";
}

bool face_expr_from_name(const char *name, face_expr_t *out)
{
    if (name == NULL) {
        return false;
    }
    for (unsigned i = 0; i < FACE_EXPR_COUNT; i++) {
        if (strcmp(name, s_names[i]) == 0) {
            *out = (face_expr_t)i;
            return true;
        }
    }
    return false;
}

static void keep_at(face_ui_t *st, esp_err_t e, int line)
{
    if (e != ESP_GSP_OK) {
        st->last_error = (esp_gsp_err_t)e;
        st->last_error_line = line;
        st->error_count++;
    }
}
#define keep(st, e) keep_at((st), (e), __LINE__)

/* ---- layer variants ---- */

typedef enum { EYES_NORMAL = 0, EYES_HAPPY, EYES_SURPRISED, EYES_DIZZY, EYES_LOVE, EYES_COUNT } eyes_t;
typedef enum { BROWS_NORMAL = 0, BROWS_SAD, BROWS_UP, BROWS_COUNT } brows_t;
typedef enum {
    MOUTH_IDLE = 0, MOUTH_HAPPY, MOUTH_SURPRISED, MOUTH_DIZZY, MOUTH_SAD, MOUTH_LOVE, MOUTH_SLEEPY,
    MOUTH_TALK, MOUTH_COUNT,
} mouth_t;

typedef struct {
    eyes_t eyes;
    brows_t brows;
    mouth_t mouth;
    bool tear;
    bool zzz;
    bool blush;
} look_t;

static const look_t s_looks[FACE_EXPR_COUNT] = {
    [FACE_EXPR_IDLE]      = { EYES_NORMAL,    BROWS_NORMAL, MOUTH_IDLE,      false, false, false },
    [FACE_EXPR_HAPPY]     = { EYES_HAPPY,     BROWS_NORMAL, MOUTH_HAPPY,     false, false, false },
    [FACE_EXPR_SURPRISED] = { EYES_SURPRISED, BROWS_UP,     MOUTH_SURPRISED, false, false, false },
    [FACE_EXPR_DIZZY]     = { EYES_DIZZY,     BROWS_UP,     MOUTH_DIZZY,     false, false, false },
    [FACE_EXPR_SAD]       = { EYES_NORMAL,    BROWS_SAD,    MOUTH_SAD,       true,  false, false },
    [FACE_EXPR_LOVE]      = { EYES_LOVE,      BROWS_NORMAL, MOUTH_LOVE,      false, false, true  },
    [FACE_EXPR_SLEEPY]    = { EYES_NORMAL,    BROWS_NORMAL, MOUTH_SLEEPY,    false, true,  false },
    [FACE_EXPR_TALKING]   = { EYES_NORMAL,    BROWS_NORMAL, MOUTH_TALK,      false, false, false },
};

typedef esp_err_t (*vis_fn_t)(esp_gsp_handle_t, bool);

static const vis_fn_t s_eyes_l[EYES_COUNT] = {
    gsp_face_eye_l_set_visible, gsp_face_eye_happy_l_set_visible, gsp_face_eye_surprised_l_set_visible,
    gsp_face_eye_dizzy_l_set_visible, gsp_face_eye_love_l_set_visible,
};
static const vis_fn_t s_eyes_r[EYES_COUNT] = {
    gsp_face_eye_r_set_visible, gsp_face_eye_happy_r_set_visible, gsp_face_eye_surprised_r_set_visible,
    gsp_face_eye_dizzy_r_set_visible, gsp_face_eye_love_r_set_visible,
};
static const vis_fn_t s_brows[BROWS_COUNT] = {
    gsp_face_brows_normal_set_visible, gsp_face_brows_sad_set_visible, gsp_face_brows_up_set_visible,
};
static const vis_fn_t s_mouths[MOUTH_COUNT] = {
    gsp_face_mouth_idle_set_visible, gsp_face_mouth_happy_set_visible, gsp_face_mouth_surprised_set_visible,
    gsp_face_mouth_dizzy_set_visible, gsp_face_mouth_sad_set_visible, gsp_face_mouth_love_set_visible,
    gsp_face_mouth_sleepy_set_visible, gsp_face_mouth_talk_set_visible,
};

/* Hide the old variant, show the new one: 2 queued updates (4 for eyes), 0 if unchanged. */
static void swap_layer(esp_gsp_handle_t ui, face_ui_t *st, const vis_fn_t *fns, uint8_t *cur, unsigned want)
{
    if (*cur == want) {
        return;
    }
    keep(st, fns[*cur](ui, false));
    keep(st, fns[want](ui, true));
    *cur = (uint8_t)want;
}

static void show_eyes(esp_gsp_handle_t ui, face_ui_t *st, eyes_t which)
{
    uint8_t cur = st->vis_eyes;
    swap_layer(ui, st, s_eyes_l, &cur, which);
    swap_layer(ui, st, s_eyes_r, &st->vis_eyes, which);
}

static void show_flag(esp_gsp_handle_t ui, face_ui_t *st, vis_fn_t fn, bool *cur, bool want)
{
    if (*cur != want) {
        keep(st, fn(ui, want));
        *cur = want;
    }
}

/* ---- small animations ---- */

static uint32_t rnd(face_ui_t *st, uint32_t span)
{
    st->rng = st->rng * 1664525U + 1013904223U;
    return (st->rng >> 16) % span;
}

static esp_gsp_animation_config_t loop_cfg(uint32_t ms, bool alternate, esp_gsp_ease_t ease)
{
    return (esp_gsp_animation_config_t){
        .duration_ms = ms, .delay_ms = 0, .iterations = 0, .alternate = alternate, .ease = ease,
    };
}

static bool eyes_can_blink(const face_ui_t *st)
{
    return s_looks[st->shown].eyes == EYES_NORMAL && st->shown != FACE_EXPR_SLEEPY;
}

static void blink(esp_gsp_handle_t ui, face_ui_t *st, uint32_t one_way_ms, uint32_t times)
{
    if (!eyes_can_blink(st)) {
        return;
    }
    const esp_gsp_animation_config_t cfg = {
        .duration_ms = one_way_ms, .delay_ms = 0, .iterations = times * 2U,
        .alternate = true, .ease = ESP_GSP_EASE_IN_OUT,
    };
    keep(st, gsp_face_eye_l_play_morph(ui, 0, 100, &cfg));
    keep(st, gsp_face_eye_r_play_morph(ui, 0, 100, &cfg));
}

static void schedule_blink(face_ui_t *st)
{
    st->next_blink = st->ticks + FACE_BLINK_MIN_TICKS + rnd(st, FACE_BLINK_SPAN_TICKS);
}

static void breathe(esp_gsp_handle_t ui, face_ui_t *st)
{
    const bool sleepy = st->shown == FACE_EXPR_SLEEPY;
    const esp_gsp_animation_config_t cfg =
        loop_cfg(sleepy ? FACE_SLEEP_BREATH_MS : FACE_BREATH_MS, true, ESP_GSP_EASE_IN_OUT);
    keep(st, gsp_face_pom_play_y(ui, FACE_POM_REST_Y, sleepy ? FACE_POM_SLEEP_Y : FACE_POM_BREATH_Y, &cfg));
}

static void set_talk_anim(esp_gsp_handle_t ui, face_ui_t *st, bool on)
{
    if (on == st->talk_anim) {
        return;
    }
    st->talk_anim = on;
    if (on) {
        const esp_gsp_animation_config_t cfg = loop_cfg(FACE_TALK_FLAP_MS, true, ESP_GSP_EASE_IN_OUT);
        keep(st, gsp_face_mouth_talk_play_morph(ui, 0, 100, &cfg));
    } else {
        keep(st, gsp_face_mouth_talk_stop_morph(ui));
        keep(st, gsp_face_mouth_talk_set_morph(ui, 0));
    }
}

/* Stops the little animations of the expression being left (at most 6 queued updates). */
static void stop_extras(esp_gsp_handle_t ui, face_ui_t *st, face_expr_t expr)
{
    if (expr == FACE_EXPR_DIZZY) {
        keep(st, gsp_face_eye_dizzy_l_stop_rotation(ui));
        keep(st, gsp_face_eye_dizzy_r_stop_rotation(ui));
        keep(st, gsp_face_eye_dizzy_l_set_rotation(ui, 0));
        keep(st, gsp_face_eye_dizzy_r_set_rotation(ui, 0));
        keep(st, gsp_face_pom_stop_x(ui));
        keep(st, gsp_face_pom_set_x(ui, FACE_POM_X));
    } else if (expr == FACE_EXPR_SAD) {
        keep(st, gsp_face_tear_stop_y(ui));
        keep(st, gsp_face_tear_set_y(ui, FACE_TEAR_Y));
    } else if (expr == FACE_EXPR_SLEEPY) {
        keep(st, gsp_face_zzz_stop_y(ui));
        keep(st, gsp_face_zzz_set_y(ui, FACE_ZZZ_Y));
        keep(st, gsp_face_eye_l_animate_morph_to(ui, 0, FACE_SLEEP_CLOSE_MS / 2U, ESP_GSP_EASE_OUT));
        keep(st, gsp_face_eye_r_animate_morph_to(ui, 0, FACE_SLEEP_CLOSE_MS / 2U, ESP_GSP_EASE_OUT));
    }
}

static void start_extras(esp_gsp_handle_t ui, face_ui_t *st, face_expr_t expr)
{
    if (expr == FACE_EXPR_DIZZY) {
        const esp_gsp_animation_config_t spin = loop_cfg(FACE_DIZZY_SPIN_MS, false, ESP_GSP_EASE_LINEAR);
        const esp_gsp_animation_config_t sway = loop_cfg(FACE_DIZZY_SWAY_MS, true, ESP_GSP_EASE_IN_OUT);
        keep(st, gsp_face_eye_dizzy_l_play_rotation(ui, 0, 360, &spin));
        keep(st, gsp_face_eye_dizzy_r_play_rotation(ui, 0, 360, &spin));
        keep(st, gsp_face_pom_play_x(ui, FACE_POM_X - FACE_DIZZY_SWAY_PX, FACE_POM_X + FACE_DIZZY_SWAY_PX, &sway));
    } else if (expr == FACE_EXPR_SAD) {
        const esp_gsp_animation_config_t drip = loop_cfg(FACE_TEAR_DROP_MS, false, ESP_GSP_EASE_IN_OUT);
        keep(st, gsp_face_tear_play_y(ui, FACE_TEAR_Y, FACE_TEAR_DROP_Y, &drip));
    } else if (expr == FACE_EXPR_SLEEPY) {
        const esp_gsp_animation_config_t rise = loop_cfg(FACE_ZZZ_RISE_MS, true, ESP_GSP_EASE_IN_OUT);
        keep(st, gsp_face_zzz_play_y(ui, FACE_ZZZ_Y, FACE_ZZZ_RISE_Y, &rise));
        keep(st, gsp_face_eye_l_animate_morph_to(ui, 100, FACE_SLEEP_CLOSE_MS, ESP_GSP_EASE_IN_OUT));
        keep(st, gsp_face_eye_r_animate_morph_to(ui, 100, FACE_SLEEP_CLOSE_MS, ESP_GSP_EASE_IN_OUT));
    }
}

static void show_debug_name(esp_gsp_handle_t ui, face_ui_t *st)
{
    if (!st->cfg.debug_cycle) {
        return;
    }
    char text[40];
    size_t n = 0;
    const char *name = face_expr_name(st->shown);
    while (name[n] != '\0' && n < sizeof(text) - 1U) {
        text[n] = name[n];
        n++;
    }
    static const char k_talk[] = " + talking";
    if (st->speaking && st->shown != FACE_EXPR_TALKING) {
        for (size_t i = 0; k_talk[i] != '\0' && n < sizeof(text) - 1U; i++) {
            text[n++] = k_talk[i];
        }
    }
    text[n] = '\0';
    keep(st, gsp_face_dbg_set_text(ui, text));
}

/* Makes the current look (expression + speaking) visible. No motion. */
static void apply_look(esp_gsp_handle_t ui, face_ui_t *st)
{
    const look_t *look = &s_looks[st->shown];
    const bool talk = st->speaking || st->shown == FACE_EXPR_TALKING;
    show_eyes(ui, st, look->eyes);
    swap_layer(ui, st, s_brows, &st->vis_brows, look->brows);
    swap_layer(ui, st, s_mouths, &st->vis_mouth, talk ? MOUTH_TALK : look->mouth);
    show_flag(ui, st, gsp_face_tear_set_visible, &st->vis_tear, look->tear);
    show_flag(ui, st, gsp_face_zzz_set_visible, &st->vis_zzz, look->zzz);
    show_flag(ui, st, gsp_face_blush_love_set_visible, &st->vis_blush, look->blush);
    set_talk_anim(ui, st, talk);
    show_debug_name(ui, st);
}

static void set_motion(face_ui_t *st, face_motion_t motion, uint32_t ms)
{
    st->motion = motion;
    st->motion_until = st->ticks + (ms + FACE_TICK_MS - 1U) / FACE_TICK_MS;
}

static void advance_motion(esp_gsp_handle_t ui, face_ui_t *st)
{
    if (st->motion == FACE_MOTION_NONE || st->ticks < st->motion_until) {
        return;
    }
    switch (st->motion) {
    case FACE_MOTION_HOP_UP:
        keep(st, gsp_face_pom_animate_y_to(ui, FACE_POM_REST_Y, FACE_HOP_DOWN_MS, ESP_GSP_EASE_IN_OUT));
        set_motion(st, FACE_MOTION_HOP_DOWN, FACE_HOP_DOWN_MS);
        break;
    case FACE_MOTION_SQUASH:
        /* Split over two ticks to stay well inside the GSP update queue. */
        stop_extras(ui, st, st->shown);
        st->shown = st->pending;
        apply_look(ui, st);
        set_motion(st, FACE_MOTION_SWAPPED, 0U);
        break;
    case FACE_MOTION_SWAPPED:
        start_extras(ui, st, st->shown);
        keep(st, gsp_face_pom_animate_y_to(ui, FACE_POM_REST_Y, FACE_UNSQUASH_MS, ESP_GSP_EASE_OUT));
        set_motion(st, FACE_MOTION_UNSQUASH, FACE_UNSQUASH_MS);
        break;
    default:
        st->motion = FACE_MOTION_NONE;
        if (st->pending != st->shown) {
            face_ui_set_expression(ui, st, st->pending);   /* a request arrived mid-swap */
        } else {
            breathe(ui, st);
        }
        break;
    }
}


/* ---- idle life: glance around, yawn now and then (only while idle, quiet and still) ---- */

static bool calm(const face_ui_t *st)
{
    return st->shown == FACE_EXPR_IDLE && !st->speaking && st->motion == FACE_MOTION_NONE;
}

static void end_fidget(esp_gsp_handle_t ui, face_ui_t *st)
{
    if (st->fidget == FIDGET_GLANCE) {
        keep(st, gsp_face_eyes_animate_x_to(ui, FACE_EYES_X, FACE_GLANCE_MS, ESP_GSP_EASE_IN_OUT));
        keep(st, gsp_face_eyes_animate_y_to(ui, FACE_EYES_Y, FACE_GLANCE_MS, ESP_GSP_EASE_IN_OUT));
    } else if (st->fidget == FIDGET_YAWN) {
        if (!st->talk_anim) {
            keep(st, gsp_face_mouth_talk_set_morph(ui, 0));
            apply_look(ui, st);
        }
        if (st->shown != FACE_EXPR_SLEEPY) {
            keep(st, gsp_face_eye_l_animate_morph_to(ui, 0, 300U, ESP_GSP_EASE_OUT));
            keep(st, gsp_face_eye_r_animate_morph_to(ui, 0, 300U, ESP_GSP_EASE_OUT));
        }
    }
    st->fidget = FIDGET_NONE;
    st->next_fidget = st->ticks + FACE_FIDGET_MIN_TICKS + rnd(st, FACE_FIDGET_SPAN_TICKS);
}

static void advance_fidget(esp_gsp_handle_t ui, face_ui_t *st)
{
    if (st->fidget != FIDGET_NONE) {
        if (st->ticks >= st->fidget_until || !calm(st)) {
            end_fidget(ui, st);
        }
        return;
    }
    if (!calm(st) || st->ticks < st->next_fidget) {
        return;
    }
    if (st->ticks >= st->next_yawn) {
        st->fidget = FIDGET_YAWN;
        st->next_yawn = st->ticks + FACE_YAWN_MIN_TICKS + rnd(st, FACE_YAWN_SPAN_TICKS);
        swap_layer(ui, st, s_mouths, &st->vis_mouth, MOUTH_TALK);
        keep(st, gsp_face_mouth_talk_animate_morph_to(ui, 100, FACE_YAWN_OPEN_MS, ESP_GSP_EASE_IN_OUT));
        keep(st, gsp_face_eye_l_animate_morph_to(ui, 80, FACE_YAWN_OPEN_MS, ESP_GSP_EASE_IN_OUT));
        keep(st, gsp_face_eye_r_animate_morph_to(ui, 80, FACE_YAWN_OPEN_MS, ESP_GSP_EASE_IN_OUT));
        st->fidget_until = st->ticks + FACE_YAWN_TICKS;
    } else {
        const int32_t dir = rnd(st, 2U) ? 1 : -1;
        const int32_t up = rnd(st, 3U) == 0 ? -FACE_GLANCE_UP_PX : 0;
        st->fidget = FIDGET_GLANCE;
        keep(st, gsp_face_eyes_animate_x_to(ui, FACE_EYES_X + dir * FACE_GLANCE_PX, FACE_GLANCE_MS, ESP_GSP_EASE_IN_OUT));
        keep(st, gsp_face_eyes_animate_y_to(ui, FACE_EYES_Y + up, FACE_GLANCE_MS, ESP_GSP_EASE_IN_OUT));
        st->fidget_until = st->ticks + 10U + rnd(st, 12U);
    }
}

void face_ui_set_expression(esp_gsp_handle_t ui, face_ui_t *st, face_expr_t expr)
{
    if ((unsigned)expr >= FACE_EXPR_COUNT) {
        expr = FACE_EXPR_IDLE;
    }
    st->pending = expr;
    if (st->motion == FACE_MOTION_SQUASH || st->motion == FACE_MOTION_SWAPPED || expr == st->shown) {
        return;   /* a squash in flight picks up the newest pending expression */
    }
    keep(st, gsp_face_pom_stop_y(ui));
    keep(st, gsp_face_pom_animate_y_to(ui, FACE_POM_SQUASH_Y, FACE_SQUASH_MS, ESP_GSP_EASE_OUT));
    set_motion(st, FACE_MOTION_SQUASH, FACE_SQUASH_MS);
}

void face_ui_set_speaking(esp_gsp_handle_t ui, face_ui_t *st, bool speaking)
{
    if (speaking == st->speaking) {
        return;
    }
    st->speaking = speaking;
    if (st->motion != FACE_MOTION_SQUASH) {
        apply_look(ui, st);
    }   /* during a squash the swap applies it */
}

static void start_hop(esp_gsp_handle_t ui, face_ui_t *st)
{
    if (st->motion == FACE_MOTION_SQUASH || st->motion == FACE_MOTION_SWAPPED) {
        return;
    }
    keep(st, gsp_face_pom_stop_y(ui));
    keep(st, gsp_face_pom_animate_y_to(ui, FACE_POM_HOP_Y, FACE_HOP_UP_MS, ESP_GSP_EASE_OUT));
    set_motion(st, FACE_MOTION_HOP_UP, FACE_HOP_UP_MS);
}

static void tick(esp_gsp_handle_t ui, void *ctx)
{
    face_ui_t *st = ctx;
    st->ticks++;
    advance_motion(ui, st);
    if (st->cfg.ops.get_state != NULL && st->cfg.ops.get_state(&st->brain, st->cfg.ops.ctx)) {
        if (st->brain.seq != st->brain_seq) {
            st->brain_seq = st->brain.seq;
            face_ui_set_expression(ui, st, st->brain.expr);
        }
        face_ui_set_speaking(ui, st, st->brain.speaking);
    }
    if (st->ticks >= st->next_blink && st->fidget != FIDGET_YAWN) {
        blink(ui, st, FACE_BLINK_MS, rnd(st, 100U) < FACE_DOUBLE_BLINK_PCT ? 2U : 1U);
        schedule_blink(st);
    }
    advance_fidget(ui, st);
}

/* Raw touch samples (render task): remember where the finger is. */
static void pointer(esp_gsp_handle_t ui, int32_t x, int32_t y, bool pressed, void *ctx)
{
    (void)ui;
    face_ui_t *st = ctx;
    if (pressed) {
        st->last_x = x;
        st->last_y = y;
    }
}

static void on_event(esp_gsp_handle_t ui, const esp_gsp_event_t *event, void *ctx)
{
    face_ui_t *st = ctx;
    face_input_t in = { .x = st->last_x, .y = st->last_y };
    if (gsp_face_event_is_poke(event)) {
        in.kind = FACE_INPUT_POKE;
        if (st->cfg.debug_cycle) {
            const bool swapping = st->motion == FACE_MOTION_SQUASH || st->motion == FACE_MOTION_SWAPPED;
            const face_expr_t base = swapping ? st->pending : st->shown;
            face_ui_set_expression(ui, st, (face_expr_t)((base + 1U) % FACE_EXPR_COUNT));
        } else {
            blink(ui, st, FACE_BLINK_MS, 1U);
            start_hop(ui, st);
        }
    } else if (gsp_face_event_is_hold(event)) {
        in.kind = FACE_INPUT_HOLD;
        if (st->cfg.debug_cycle) {
            face_ui_set_speaking(ui, st, !st->speaking);
        } else {
            blink(ui, st, FACE_SLOW_BLINK_MS, 1U);
        }
    } else {
        return;
    }
    schedule_blink(st);
    if (st->cfg.ops.on_input != NULL) {
        st->cfg.ops.on_input(&in, st->cfg.ops.ctx);
    }
}

esp_gsp_err_t face_ui_init(esp_gsp_handle_t ui, face_ui_t *st, const face_ui_config_t *cfg)
{
    /* vis_* mirror the scene's authored defaults (idle visible, everything else hidden). */
    *st = (face_ui_t){ .rng = 0x9E3779B9U, .shown = FACE_EXPR_IDLE, .pending = FACE_EXPR_IDLE,
                       .vis_eyes = EYES_NORMAL, .vis_brows = BROWS_NORMAL, .vis_mouth = MOUTH_IDLE };
    if (cfg != NULL) {
        st->cfg = *cfg;
    }
    schedule_blink(st);
    st->next_fidget = FACE_FIDGET_MIN_TICKS;
    st->next_yawn = FACE_YAWN_MIN_TICKS;
    esp_gsp_err_t err = esp_gsp_set_press_feedback_enabled(ui, false);
    if (err == ESP_GSP_OK) {
        err = esp_gsp_set_pointer_observer(ui, pointer, st);
    }
    if (err == ESP_GSP_OK) {
        err = esp_gsp_on_event(ui, on_event, st);
    }
    if (err != ESP_GSP_OK) {
        return err;
    }
    st->timer = esp_gsp_timer_create(ui, FACE_TICK_MS, tick, st);
    if (st->timer == NULL) {
        (void)esp_gsp_on_event(ui, NULL, NULL);
        (void)esp_gsp_set_pointer_observer(ui, NULL, NULL);
        return ESP_GSP_ERR_NO_MEM;
    }
    keep(st, gsp_face_dbg_set_visible(ui, st->cfg.debug_cycle));
    apply_look(ui, st);
    breathe(ui, st);
    return ESP_GSP_OK;
}

void face_ui_deinit(esp_gsp_handle_t ui, face_ui_t *st)
{
    if (st->timer) {
        (void)esp_gsp_timer_delete(ui, st->timer);
        st->timer = NULL;
    }
    (void)esp_gsp_on_event(ui, NULL, NULL);
    (void)esp_gsp_set_pointer_observer(ui, NULL, NULL);
}
