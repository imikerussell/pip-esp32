// SPDX-License-Identifier: Apache-2.0
// Simulator entry: runs the same portable face UI as the device.
#include <stdio.h>

#include "face_ui.h"
#include "gsp_sim_bridge.h"

static face_ui_t s_face;
static unsigned s_pokes;
static unsigned s_holds;

static void log_input(const face_input_t *in, void *ctx)
{
    (void)ctx;
    if (in->kind == FACE_INPUT_POKE) {
        s_pokes++;
    } else {
        s_holds++;
    }
    fprintf(stderr, "face_backend: %s -> showing %s%s\n", in->kind == FACE_INPUT_POKE ? "poke" : "hold",
            face_expr_name(s_face.pending), s_face.speaking ? " (speaking)" : "");
}

esp_gsp_err_t gsp_bridge_app_init(esp_gsp_handle_t ui)
{
    static const face_ui_config_t cfg = { .ops = { .on_input = log_input }, .debug_cycle = true };
    return face_ui_init(ui, &s_face, &cfg);
}

void gsp_bridge_app_deinit(esp_gsp_handle_t ui)
{
    face_ui_deinit(ui, &s_face);
    fprintf(stderr, "face_backend: pokes=%u holds=%u errors=%u last_error=%d at face_ui.c:%d\n",
            s_pokes, s_holds, (unsigned)s_face.error_count, (int)s_face.last_error, s_face.last_error_line);
}
