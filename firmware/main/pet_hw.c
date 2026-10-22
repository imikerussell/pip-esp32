// SPDX-License-Identifier: Apache-2.0
// DEVICE-ONLY glue for Pip:
//   touch/IMU event -> queue -> brain task -> HTTP POST /react?event=... (X-Pet-Key)
//   -> X-Face header sets the expression -> raw PCM body streams to the ES8311 speaker
//   while the talking mouth flaps. Bridge down -> sleepy face, keep running.
#include "pet_hw.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

#include <strings.h>

#include "bsp/esp_mosaico.h"
#include "driver/jpeg_encode.h"
#include "driver/ppa.h"
#include "esp_cache.h"
#include "esp_check.h"
#include "esp_codec_dev.h"
#include "esp_event.h"
#include "esp_heap_caps.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "linux/videodev2.h"
#include "mosaico_module_camera.h"
#include "secrets.h"   /* generated from .env by scripts/gen_secrets.py */

#define PET_PCM_RATE            16000
#define PET_PCM_CHUNK           4096
#define PET_SPEAKER_VOLUME      80
#define PET_HTTP_TIMEOUT_MS     20000
#define PET_WIFI_WAIT_MS        20000
#define PET_FACE_HOLD_MS        6000    /* keep the brain's face this long after speaking */
#define PET_POKE_BUZZ_MS        45
#define PET_MOTOR_STRENGTH      70
#define PET_IMU_PERIOD_MS       40
#define PET_SHAKE_DELTA_G       1.4f
#define PET_PICKUP_DPS          110.0f
#define PET_PICKUP_DELTA_G      0.30f
#define PET_REST_DPS            10.0f
#define PET_REST_DELTA_G        0.08f
#define PET_BASE_REST_MS        1000
#define PET_PUTDOWN_REST_MS     700
#define PET_FLIP_DOT            (-0.55f)
#define PET_FLIP_HOLD_MS        350
#define PET_UNFLIP_DOT          0.30f
#define PET_UPRIGHT_DOT         0.80f
#define PET_IMU_COOLDOWN_MS     2500
#define PET_DOUBLE_TAP_MS       380
#define PET_IDLE_EVENT_MS       150000  /* quiet this long -> "idle" (Pip may chat about the stats) */
#define PET_LOOK_MS             (PET_LOOK_SECONDS * 1000)
#define PET_IMG_W               480U
#define PET_IMG_H               480U
#define PET_IMG_BYTES           (PET_IMG_W * PET_IMG_H * 2U)
#define PET_BUF_ALIGN           128U
#define PET_JPEG_QUALITY        75U

static const char *TAG = "pet_hw";

static const char *const s_event_names[PET_EVENT_COUNT] = {
    "boot", "poke", "hold", "pickup", "shake", "flip", "putdown", "stats", "look", "idle",
};

/* Shared state. `state` is written by the brain task and read by the render task (lock, never block
 * on the render side). Everything else is owned by the brain task or the IMU task as noted. */
typedef struct {
    QueueHandle_t events;
    SemaphoreHandle_t lock;
    face_state_t state;
    esp_codec_dev_handle_t speaker;
    uint8_t *pcm;               /* brain task: PET_PCM_CHUNK + 1 (odd-byte carry) */
    volatile bool wifi_up;
    volatile bool busy;         /* brain task is talking to the bridge / playing */
    bool motor;
    /* camera: owned by the brain task */
    mosaico_camera_handle_t camera;
    ppa_client_handle_t ppa;
    jpeg_encoder_handle_t jpeg;
    uint8_t *rgb;
    uint8_t *jpeg_out;
    size_t jpeg_cap;
} pet_t;

/* Response headers captured by the HTTP event handler (esp_http_client_get_header reads REQUEST headers). */
typedef struct {
    char face[16];
    char line[128];
} pet_reply_t;

static pet_t s_pet;

/* ---------- face_ui ops (GSP render task: never block) ---------- */

static void face_on_input(const face_input_t *input, void *ctx)
{
    pet_t *p = ctx;
    const pet_event_t ev = input->kind == FACE_INPUT_HOLD ? PET_EVENT_HOLD : PET_EVENT_POKE;
    (void)xQueueSend(p->events, &ev, 0);
}

static bool face_get_state(face_state_t *out, void *ctx)
{
    pet_t *p = ctx;
    if (xSemaphoreTake(p->lock, 0) != pdTRUE) {
        return false;
    }
    *out = p->state;
    xSemaphoreGive(p->lock);
    return true;
}

static const face_ui_ops_t s_face_ops = {
    .on_input = face_on_input, .get_state = face_get_state, .ctx = &s_pet,
};

const face_ui_ops_t *pet_hw_face_ops(void)
{
    return &s_face_ops;
}

static void set_face(face_expr_t expr, bool speaking)
{
    xSemaphoreTake(s_pet.lock, portMAX_DELAY);
    if (s_pet.state.expr != expr) {
        s_pet.state.expr = expr;
        s_pet.state.seq++;
    }
    s_pet.state.speaking = speaking;
    xSemaphoreGive(s_pet.lock);
}

static face_expr_t current_face(void)
{
    xSemaphoreTake(s_pet.lock, portMAX_DELAY);
    const face_expr_t e = s_pet.state.expr;
    xSemaphoreGive(s_pet.lock);
    return e;
}

/* ---------- Wi-Fi STA (secrets.h from .env) ---------- */

static void wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    (void)arg;
    (void)data;
    if (base == WIFI_EVENT && (id == WIFI_EVENT_STA_START || id == WIFI_EVENT_STA_DISCONNECTED)) {
        if (id == WIFI_EVENT_STA_DISCONNECTED && s_pet.wifi_up) {
            ESP_LOGW(TAG, "wifi lost, reconnecting");
        }
        s_pet.wifi_up = false;
        (void)esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        const ip_event_got_ip_t *ev = data;
        ESP_LOGI(TAG, "wifi up, ip " IPSTR, IP2STR(&ev->ip_info.ip));
        s_pet.wifi_up = true;
    }
}

static esp_err_t wifi_start(void)
{
    esp_err_t err = esp_netif_init();
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        return err;
    }
    err = esp_event_loop_create_default();
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        return err;
    }
    ESP_RETURN_ON_FALSE(esp_netif_create_default_wifi_sta(), ESP_ERR_NO_MEM, TAG, "sta netif");
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_RETURN_ON_ERROR(esp_wifi_init(&init), TAG, "wifi init");
    ESP_RETURN_ON_ERROR(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event, NULL), TAG, "evt");
    ESP_RETURN_ON_ERROR(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, wifi_event, NULL), TAG, "ip");
    wifi_config_t cfg = {0};
    strlcpy((char *)cfg.sta.ssid, PET_WIFI_SSID, sizeof(cfg.sta.ssid));
    strlcpy((char *)cfg.sta.password, PET_WIFI_PASS, sizeof(cfg.sta.password));
    ESP_RETURN_ON_ERROR(esp_wifi_set_storage(WIFI_STORAGE_RAM), TAG, "storage");
    ESP_RETURN_ON_ERROR(esp_wifi_set_mode(WIFI_MODE_STA), TAG, "mode");
    ESP_RETURN_ON_ERROR(esp_wifi_set_config(WIFI_IF_STA, &cfg), TAG, "config");
    ESP_RETURN_ON_ERROR(esp_wifi_start(), TAG, "start");
    (void)esp_wifi_set_ps(WIFI_PS_NONE);   /* lowest latency for streamed audio */
    return ESP_OK;
}

/* ---------- motor ---------- */

static void buzz(uint32_t ms)
{
    if (!s_pet.motor) {
        return;
    }
    (void)bsp_motor_set(true);
    vTaskDelay(pdMS_TO_TICKS(ms));
    (void)bsp_motor_set(false);
}


/* ---------- camera (LEFT slot): UYVY frame -> centre square -> 480x480 RGB565 -> HW JPEG ---------- */

static esp_err_t camera_start(void)
{
    mosaico_camera_config_t cfg = MOSAICO_CAMERA_DEFAULT_CONFIG();
    cfg.allow_unidentified = true;
    ESP_RETURN_ON_ERROR(mosaico_camera_new(&cfg, &s_pet.camera), TAG, "camera new (LEFT slot?)");
    esp_err_t err = mosaico_camera_open(s_pet.camera);
    if (err == ESP_OK) {
        err = mosaico_camera_start_stream(s_pet.camera);
    }
    if (err != ESP_OK) {
        (void)mosaico_camera_del(s_pet.camera);
        s_pet.camera = NULL;
        return err;
    }
    const ppa_client_config_t ppa_cfg = { .oper_type = PPA_OPERATION_SRM, .max_pending_trans_num = 1 };
    ESP_RETURN_ON_ERROR(ppa_register_client(&ppa_cfg, &s_pet.ppa), TAG, "ppa");
    const jpeg_encode_engine_cfg_t eng = { .intr_priority = 0, .timeout_ms = 1000 };
    ESP_RETURN_ON_ERROR(jpeg_new_encoder_engine(&eng, &s_pet.jpeg), TAG, "jpeg engine");
    s_pet.rgb = heap_caps_aligned_calloc(PET_BUF_ALIGN, 1, PET_IMG_BYTES,
                                         MALLOC_CAP_SPIRAM | MALLOC_CAP_DMA | MALLOC_CAP_8BIT);
    const jpeg_encode_memory_alloc_cfg_t mem = { .buffer_direction = JPEG_ENC_ALLOC_OUTPUT_BUFFER };
    s_pet.jpeg_out = jpeg_alloc_encoder_mem(PET_IMG_BYTES / 4U, &mem, &s_pet.jpeg_cap);
    ESP_RETURN_ON_FALSE(s_pet.rgb && s_pet.jpeg_out, ESP_ERR_NO_MEM, TAG, "camera buffers");
    return ESP_OK;
}

static size_t camera_capture_jpeg(void)
{
    if (s_pet.camera == NULL || s_pet.rgb == NULL) {
        return 0;
    }
    (void)mosaico_camera_discard_frames(s_pet.camera, 1);
    mosaico_camera_frame_t frame = {0};
    if (mosaico_camera_get_frame(s_pet.camera, &frame) != ESP_OK) {
        return 0;
    }
    esp_err_t err = frame.pixel_format == V4L2_PIX_FMT_UYVY ? ESP_OK : ESP_ERR_NOT_SUPPORTED;
    if (err == ESP_OK) {
        const uint32_t crop = (frame.width < frame.height ? frame.width : frame.height) & ~1U;
        const uint32_t stride = frame.bytes_per_line ? frame.bytes_per_line : frame.width * 2U;
        (void)esp_cache_msync((void *)frame.data, frame.size,
                              ESP_CACHE_MSYNC_FLAG_DIR_M2C | ESP_CACHE_MSYNC_FLAG_INVALIDATE);
        (void)esp_cache_msync(s_pet.rgb, PET_IMG_BYTES, ESP_CACHE_MSYNC_FLAG_DIR_C2M);
        const ppa_srm_oper_config_t op = {
            .in = {
                .buffer = frame.data, .pic_w = stride / 2U, .pic_h = frame.height,
                .block_w = crop, .block_h = crop,
                .block_offset_x = ((frame.width - crop) / 2U) & ~1U,
                .block_offset_y = ((frame.height - crop) / 2U) & ~1U,
                .srm_cm = PPA_SRM_COLOR_MODE_YUV422_UYVY,
                .yuv_range = PPA_COLOR_RANGE_LIMIT,
                .yuv_std = PPA_COLOR_CONV_STD_RGB_YUV_BT601,
            },
            .out = {
                .buffer = s_pet.rgb, .buffer_size = PET_IMG_BYTES,
                .pic_w = PET_IMG_W, .pic_h = PET_IMG_H, .srm_cm = PPA_SRM_COLOR_MODE_RGB565,
            },
            .rotation_angle = PPA_SRM_ROTATION_ANGLE_270,
            .scale_x = (float)PET_IMG_W / (float)crop,
            .scale_y = (float)PET_IMG_H / (float)crop,
            .mode = PPA_TRANS_MODE_BLOCKING,
        };
        err = ppa_do_scale_rotate_mirror(s_pet.ppa, &op);
    }
    (void)mosaico_camera_return_frame(s_pet.camera, &frame);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "camera convert failed: %s", esp_err_to_name(err));
        return 0;
    }
    const jpeg_encode_cfg_t enc = {
        .width = PET_IMG_W, .height = PET_IMG_H,
        .src_type = JPEG_ENCODE_IN_FORMAT_RGB565, .sub_sample = JPEG_DOWN_SAMPLING_YUV420,
        .image_quality = PET_JPEG_QUALITY, .pixel_reverse = false,
    };
    uint32_t n = 0;
    if (jpeg_encoder_process(s_pet.jpeg, &enc, s_pet.rgb, PET_IMG_BYTES, s_pet.jpeg_out, s_pet.jpeg_cap, &n) != ESP_OK) {
        return 0;
    }
    return n;
}

/* ---------- brain bridge ---------- */

static esp_err_t http_event(esp_http_client_event_t *e)
{
    pet_reply_t *r = e->user_data;
    if (e->event_id == HTTP_EVENT_ON_HEADER && r != NULL && e->header_key && e->header_value) {
        if (strcasecmp(e->header_key, "X-Face") == 0) {
            strlcpy(r->face, e->header_value, sizeof(r->face));
        } else if (strcasecmp(e->header_key, "X-Line") == 0) {
            strlcpy(r->line, e->header_value, sizeof(r->line));
        }
    }
    return ESP_OK;
}

/* Writes PCM to the speaker, keeping an odd trailing byte for the next chunk so samples stay aligned. */
static void play_stream(esp_http_client_handle_t h)
{
    size_t carry = 0;
    for (;;) {
        const int n = esp_http_client_read(h, (char *)s_pet.pcm + carry, PET_PCM_CHUNK);
        if (n <= 0) {
            break;
        }
        const size_t have = carry + (size_t)n;
        const size_t even = have & ~(size_t)1;
        if (even > 0 && s_pet.speaker) {
            (void)esp_codec_dev_write(s_pet.speaker, s_pet.pcm, (int)even);
        }
        carry = have - even;
        if (carry) {
            s_pet.pcm[0] = s_pet.pcm[even];
        }
    }
}

/* Returns ESP_OK and sets *spoke when Pip said something (200). */
static esp_err_t brain_exchange(pet_event_t ev, bool *spoke)
{
    *spoke = false;
    char url[160];
    snprintf(url, sizeof(url), "%s?event=%s", PET_BRIDGE_URL, s_event_names[ev]);
    pet_reply_t reply = {0};
    const esp_http_client_config_t cfg = {
        .url = url, .method = HTTP_METHOD_POST, .timeout_ms = PET_HTTP_TIMEOUT_MS, .buffer_size = 4096,
        .event_handler = http_event, .user_data = &reply,
    };
    const size_t jpeg_len = camera_capture_jpeg();
    esp_http_client_handle_t h = esp_http_client_init(&cfg);
    ESP_RETURN_ON_FALSE(h, ESP_ERR_NO_MEM, TAG, "http init");
    (void)esp_http_client_set_header(h, "X-Pet-Key", PET_KEY);
    (void)esp_http_client_set_header(h, "Content-Type", jpeg_len ? "image/jpeg" : "application/octet-stream");
    const int64_t t0 = esp_timer_get_time();
    esp_err_t err = esp_http_client_open(h, (int)jpeg_len);
    if (err == ESP_OK && jpeg_len) {
        const int w = esp_http_client_write(h, (const char *)s_pet.jpeg_out, (int)jpeg_len);
        err = w == (int)jpeg_len ? ESP_OK : ESP_FAIL;
    }
    if (err == ESP_OK) {
        (void)esp_http_client_fetch_headers(h);
        const int status = esp_http_client_get_status_code(h);
        face_expr_t face = FACE_EXPR_IDLE;
        const bool known = face_expr_from_name(reply.face, &face);
        if (ev != PET_EVENT_LOOK || status == 200) {
            ESP_LOGI(TAG, "%s (%u B jpeg) -> http %d face=%s \"%s\" (%lld ms)", s_event_names[ev],
                     (unsigned)jpeg_len, status, reply.face[0] ? reply.face : "-", reply.line,
                     (esp_timer_get_time() - t0) / 1000);
        }
        if (status == 200) {
            set_face(known ? face : FACE_EXPR_HAPPY, true);
            play_stream(h);
            set_face(known ? face : FACE_EXPR_HAPPY, false);
            *spoke = true;
        } else if (status == 204) {
            if (known) {
                set_face(face, false);
            }
        } else {
            err = ESP_FAIL;
        }
    } else {
        ESP_LOGW(TAG, "bridge unreachable: %s", esp_err_to_name(err));
    }
    esp_http_client_close(h);
    esp_http_client_cleanup(h);
    return err;
}

/* Immediate local reaction while the brain thinks (~2 s), so motion never feels laggy. */
static void local_reaction(pet_event_t ev)
{
    switch (ev) {
    case PET_EVENT_SHAKE:   set_face(FACE_EXPR_DIZZY, false); break;
    case PET_EVENT_FLIP:    set_face(FACE_EXPR_SURPRISED, false); break;
    case PET_EVENT_PICKUP:  set_face(FACE_EXPR_SURPRISED, false); break;
    case PET_EVENT_PUTDOWN: set_face(FACE_EXPR_IDLE, false); break;
    case PET_EVENT_HOLD:    set_face(FACE_EXPR_LOVE, false); break;
    default: break;
    }
}

/* Keep only the newest event that piled up while Pip was talking. */
static bool latest_pending(pet_event_t *out)
{
    bool got = false;
    pet_event_t ev;
    while (xQueueReceive(s_pet.events, &ev, 0) == pdTRUE) {
        *out = ev;
        got = true;
    }
    return got;
}

static int64_t now_ms(void)
{
    return esp_timer_get_time() / 1000;
}

static void brain_task(void *arg)
{
    (void)arg;
    const int64_t wifi_deadline = now_ms() + PET_WIFI_WAIT_MS;
    while (!s_pet.wifi_up && now_ms() < wifi_deadline) {
        vTaskDelay(pdMS_TO_TICKS(200));
    }
    pet_event_t ev = PET_EVENT_BOOT;
    bool have = s_pet.wifi_up;   /* say hello once we are online */
    if (!have) {
        set_face(FACE_EXPR_SLEEPY, false);
    }
    int64_t revert_at = 0;
    int64_t last_look = now_ms();
    int64_t last_activity = now_ms();
    for (;;) {
        if (!have) {
            have = xQueueReceive(s_pet.events, &ev, pdMS_TO_TICKS(250)) == pdTRUE;
        }
        const int64_t now = now_ms();
        if (!have) {
            if (revert_at && now >= revert_at) {
                revert_at = 0;
                set_face(s_pet.wifi_up ? FACE_EXPR_IDLE : FACE_EXPR_SLEEPY, false);
            }
            if (s_pet.wifi_up && now - last_activity >= PET_IDLE_EVENT_MS) {
                ev = PET_EVENT_IDLE;
                have = true;
            } else if (s_pet.wifi_up && s_pet.camera && revert_at == 0 && now - last_look >= PET_LOOK_MS) {
                ev = PET_EVENT_LOOK;
                have = true;
            } else {
                continue;
            }
        }
        have = false;
        if (ev == PET_EVENT_POKE) {
            buzz(PET_POKE_BUZZ_MS);
            pet_event_t second;
            if (xQueuePeek(s_pet.events, &second, pdMS_TO_TICKS(PET_DOUBLE_TAP_MS)) == pdTRUE &&
                second == PET_EVENT_POKE) {
                (void)xQueueReceive(s_pet.events, &second, 0);
                ev = PET_EVENT_STATS;
                buzz(PET_POKE_BUZZ_MS);
            }
        }
        if (ev != PET_EVENT_LOOK) {
            last_activity = now_ms();
        }
        local_reaction(ev);
        if (!s_pet.wifi_up) {
            ESP_LOGW(TAG, "%s ignored: no wifi", s_event_names[ev]);
            set_face(FACE_EXPR_SLEEPY, false);
            revert_at = 0;
            continue;
        }
        bool spoke = false;
        s_pet.busy = true;
        const esp_err_t err = brain_exchange(ev, &spoke);
        s_pet.busy = false;
        last_look = now_ms();   /* every exchange carries a fresh frame */
        if (spoke) {
            last_activity = now_ms();
        }
        if (err != ESP_OK) {
            set_face(FACE_EXPR_SLEEPY, false);
            revert_at = now_ms() + PET_FACE_HOLD_MS;
        } else if (spoke) {
            const face_expr_t f = current_face();
            revert_at = (f == FACE_EXPR_IDLE || f == FACE_EXPR_SLEEPY) ? 0 : now_ms() + PET_FACE_HOLD_MS;
        } else if (ev != PET_EVENT_LOOK) {
            revert_at = now_ms() + PET_FACE_HOLD_MS;
        }
        have = latest_pending(&ev);
    }
}

/* ---------- IMU gestures: pickup, shake, flip (relative to resting pose), putdown ---------- */

typedef struct {
    bool have_base;
    float bx, by, bz;      /* unit gravity vector when resting in the normal pose */
    float smooth;          /* low-passed |a| */
    bool held;
    bool flipped;
    int32_t rest_ms;
    int32_t flip_ms;
    int64_t last_sent_ms;
} imu_state_t;

static void imu_send(imu_state_t *s, pet_event_t ev, int64_t now, bool ignore_cooldown)
{
    if (!ignore_cooldown && now - s->last_sent_ms < PET_IMU_COOLDOWN_MS) {
        return;
    }
    s->last_sent_ms = now;
    ESP_LOGI(TAG, "imu: %s", s_event_names[ev]);
    (void)xQueueSend(s_pet.events, &ev, 0);
}

static void imu_task(void *arg)
{
    (void)arg;
    imu_state_t s = { .smooth = 1.0f };
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(PET_IMU_PERIOD_MS));
        float ax, ay, az, gx, gy, gz;
        if (bsp_imu_get_accel(&ax, &ay, &az) != ESP_OK || bsp_imu_get_gyro(&gx, &gy, &gz) != ESP_OK) {
            continue;
        }
        const int64_t now = esp_timer_get_time() / 1000;
        const float mag = sqrtf(ax * ax + ay * ay + az * az);
        const float rot = sqrtf(gx * gx + gy * gy + gz * gz);
        const float jolt = fabsf(mag - s.smooth);
        s.smooth = 0.9f * s.smooth + 0.1f * mag;
        const bool resting = fabsf(mag - 1.0f) < PET_REST_DELTA_G && rot < PET_REST_DPS;
        s.rest_ms = resting ? s.rest_ms + PET_IMU_PERIOD_MS : 0;
        if (!s.have_base) {
            if (s.rest_ms >= PET_BASE_REST_MS && mag > 0.5f) {
                s.bx = ax / mag; s.by = ay / mag; s.bz = az / mag;
                s.have_base = true;
                ESP_LOGI(TAG, "imu: resting pose %.2f %.2f %.2f", s.bx, s.by, s.bz);
            }
            continue;
        }
        const float dot = mag > 0.3f ? (ax * s.bx + ay * s.by + az * s.bz) / mag : 1.0f;

        if (jolt > PET_SHAKE_DELTA_G) {
            s.held = true;
            imu_send(&s, PET_EVENT_SHAKE, now, false);
            continue;
        }
        if (dot < PET_FLIP_DOT) {
            s.flip_ms += PET_IMU_PERIOD_MS;
            if (!s.flipped && s.flip_ms >= PET_FLIP_HOLD_MS) {
                s.flipped = true;
                s.held = true;
                imu_send(&s, PET_EVENT_FLIP, now, true);
            }
        } else {
            s.flip_ms = 0;
            if (dot > PET_UNFLIP_DOT) {
                s.flipped = false;
            }
        }
        if (!s.held && (rot > PET_PICKUP_DPS || fabsf(mag - 1.0f) > PET_PICKUP_DELTA_G)) {
            s.held = true;
            imu_send(&s, PET_EVENT_PICKUP, now, false);
        } else if (s.held && s.rest_ms >= PET_PUTDOWN_REST_MS) {
            s.held = false;
            if (dot > PET_UPRIGHT_DOT) {
                imu_send(&s, PET_EVENT_PUTDOWN, now, true);
            }
        }
    }
}

/* ---------- start ---------- */

esp_err_t pet_hw_start(void)
{
    s_pet.lock = xSemaphoreCreateMutex();
    s_pet.events = xQueueCreate(6, sizeof(pet_event_t));
    s_pet.pcm = heap_caps_malloc(PET_PCM_CHUNK + 1U, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    ESP_RETURN_ON_FALSE(s_pet.lock && s_pet.events && s_pet.pcm, ESP_ERR_NO_MEM, TAG, "alloc");
    s_pet.state = (face_state_t){ .seq = 1, .expr = FACE_EXPR_IDLE, .speaking = false };

    s_pet.speaker = bsp_audio_codec_speaker_init();
    if (s_pet.speaker) {
        esp_codec_dev_sample_info_t fs = {
            .sample_rate = PET_PCM_RATE, .bits_per_sample = 16, .channel = 1, .channel_mask = 0,
        };
        if (esp_codec_dev_open(s_pet.speaker, &fs) != ESP_CODEC_DEV_OK) {
            ESP_LOGE(TAG, "speaker open failed");
            s_pet.speaker = NULL;
        } else {
            (void)esp_codec_dev_set_out_vol(s_pet.speaker, PET_SPEAKER_VOLUME);
        }
    } else {
        ESP_LOGE(TAG, "speaker unavailable");
    }
    if (bsp_motor_init() == ESP_OK) {
        s_pet.motor = true;
        (void)bsp_motor_set_strength(PET_MOTOR_STRENGTH);
    }
    const bsp_imu_config_t imu = BSP_IMU_CONFIG_DEFAULT();
    if (bsp_imu_init() == ESP_OK && bsp_imu_start(&imu) == ESP_OK) {
        if (xTaskCreate(imu_task, "pet_imu", 4096, NULL, 4, NULL) != pdPASS) {
            ESP_LOGW(TAG, "imu task not started");
        }
    } else {
        ESP_LOGW(TAG, "IMU unavailable");
    }
    esp_err_t err = camera_start();
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "camera unavailable: %s", esp_err_to_name(err));
    } else {
        ESP_LOGI(TAG, "camera ready");
    }
    err = wifi_start();
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "wifi unavailable: %s", esp_err_to_name(err));
    }
    ESP_RETURN_ON_FALSE(xTaskCreate(brain_task, "pet_brain", 8192, NULL, 5, NULL) == pdPASS,
                        ESP_ERR_NO_MEM, TAG, "brain task");
    ESP_LOGI(TAG, "started: bridge %s", PET_BRIDGE_URL);
    return ESP_OK;
}
