// SPDX-License-Identifier: Apache-2.0

#include "board_display.h"
#include "bsp/esp_mosaico.h"
#include "esp_gsp_esp_lcd.h"
#include "esp_iris.h"
#include "esp_log.h"
#include "face_ui.h"
#include "iris_screen_mirror.h"
#include "iris_ota_support.h"
#include "nvs_flash.h"
#include "pet_hw.h"
#include "ui_bundle.h"

static const char *TAG = "drama_pet";
static face_ui_t s_face;

void app_main(void)
{
    ESP_ERROR_CHECK_WITHOUT_ABORT(esp_iris_boot_probe());
    ESP_ERROR_CHECK(nvs_flash_init());

    /* Keep Recovery reachable even when the external UI image is absent or
     * invalid. */
    iris_ota_support_start();

    esp_gsp_config_t app_config;
    const esp_err_t bundle_err = ui_bundle_open(&app_config);
    if (bundle_err != ESP_OK) {
        ESP_LOGE(TAG,
                 "GSP UI unavailable (0x%x); ESP-Iris Recovery RPC remains active",
                 bundle_err);
        return;
    }

    esp_display_present_target_config_t display;
    ESP_ERROR_CHECK(board_display_init(&display));

    esp_lcd_touch_handle_t touch = NULL;
    ESP_ERROR_CHECK(board_touch_init(&touch));

    esp_gsp_esp_lcd_config_t lcd = ESP_GSP_ESP_LCD_CONFIG_INIT();
    lcd.display = display;
    lcd.touch = touch;

    ESP_ERROR_CHECK(iris_screen_mirror_init());

    esp_gsp_handle_t ui;
    ESP_ERROR_CHECK(esp_gsp_esp_lcd_start(&app_config, &lcd, &ui));
    ESP_ERROR_CHECK(iris_screen_mirror_attach(ui));
    /* Body glue: Wi-Fi + bridge + speaker + motor + IMU. Failures are logged; the face still runs. */
    ESP_ERROR_CHECK_WITHOUT_ABORT(pet_hw_start());
    face_ui_config_t face_cfg = { .ops = *pet_hw_face_ops(), .debug_cycle = false };
    ESP_ERROR_CHECK(face_ui_init(ui, &s_face, &face_cfg));

    ESP_LOGI(TAG, "Pip (Pom-pom) face ready at %dx%d RGB565",
             BSP_LCD_H_RES, BSP_LCD_V_RES);
}
