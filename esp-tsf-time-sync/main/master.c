#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_system.h"
#include "nvs_flash.h"
#include "esp_log.h"
#include "uart_helper.h"
#include "wifi_helper.h"


static const char *TAG = "main";

void app_main(void) {
    //Initialize NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
      ESP_ERROR_CHECK(nvs_flash_erase());
      ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    if (CONFIG_LOG_MAXIMUM_LEVEL > CONFIG_LOG_DEFAULT_LEVEL) {
        /* If you only want to open more logs in the wifi module, you need to make the max level greater than the default level,
         * and call esp_log_level_set() before esp_wifi_init() to improve the log level of the wifi module. */
        esp_log_level_set("wifi", CONFIG_LOG_MAXIMUM_LEVEL);
    }

    ESP_LOGI(TAG, "ESP_WIFI_MODE_STA");
    wifi_init_sta();
    uart_init();
    #ifdef CONFIG_DEVICE_ROLE_MASTER
    ESP_LOGI(TAG,"Sending Time");
    xTaskCreate(sendTime,"SEND_TASK", 2048, NULL, 5, NULL);
    #endif 

    #ifdef CONFIG_DEVICE_ROLE_SLAVE
    ESP_LOGI(TAG,"Reading Time");
    xTaskCreate(rx_task,"RX_TASK", 2048, NULL, 5, NULL);
    #endif

}


