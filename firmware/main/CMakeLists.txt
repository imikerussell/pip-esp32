idf_component_register(
    SRCS "main.c" "face_ui.c" "pet_hw.c" "board_display.c"
    INCLUDE_DIRS "."
    REQUIRES esp_iris esp-mosaico-bsp esp_mosaico_app_recovery
        esp_mosaico_gsp_bundle esp_mosaico_gsp_iris freertos nvs_flash
    PRIV_REQUIRES esp_timer esp-gsp esp_display_present esp_lcd
        esp_wifi esp_netif esp_event esp_http_client esp_driver_ppa esp_driver_jpeg esp_mm)
include("${MOSAICO_UTILS_ROOT}/mosaico-tools/cmake/gsp_bundle.cmake")
mosaico_gsp_add_ui_bundle(${COMPONENT_LIB} "../ui/main.json")
