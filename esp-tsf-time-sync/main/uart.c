#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_system.h"
#include "esp_log.h"
#include "string.h"
#include "driver/gpio.h"
#include "esp_wifi.h"
#include <inttypes.h>
#include "driver/uart.h"
#include "uart_helper.h"

static const int RX_BUF_SIZE = 1024;

#define BAUD_RATE 115200
#define TXD_PIN 19
#define RXD_PIN 21


#define BAUD_DELAY 64 / BAUD_RATE

void uart_init(void)
{
    const uart_config_t uart_config = {
        .baud_rate = BAUD_RATE,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    // We won't use a buffer for sending data.
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_1, RX_BUF_SIZE * 2, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_1, &uart_config));
    ESP_ERROR_CHECK(uart_set_pin(UART_NUM_1, TXD_PIN, RXD_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    ESP_ERROR_CHECK(uart_flush(UART_NUM_1));

}

/*

void sendTime(void * arg)
{
    for (;;) {
        int64_t timenow = esp_wifi_get_tsf_time(WIFI_IF_STA);
        const uint8_t *buffer = (uint8_t*)&timenow;
        const int txBytes = uart_write_bytes(UART_NUM_1, buffer, sizeof(timenow));
        ESP_LOGI("Send Time", "Time: %lld", timenow);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
*/

#define SYNC_BYTE 0xA5

void sendTime(void *arg)
{
    while (1) {
        uint8_t frame[1 + sizeof(uint64_t)];
        frame[0] = SYNC_BYTE;

        uint64_t tsf;
        tsf = esp_wifi_get_tsf_time(WIFI_IF_STA);
        memcpy(&frame[1], &tsf, sizeof(tsf));

        uart_write_bytes(UART_NUM_1, (char *)frame, sizeof(frame));
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}


/*
void rx_task(void *arg)
{
    static const char *RX_TASK_TAG = "RX_TASK";
    esp_log_level_set(RX_TASK_TAG, ESP_LOG_INFO);
    uint8_t* data = (uint8_t*) malloc(RX_BUF_SIZE + 1);
    int64_t timestamped;
    size_t buffered_size = 0;
    while (1) {
        int64_t timenow = esp_wifi_get_tsf_time(WIFI_IF_STA);
        const int rxBytes = uart_read_bytes(UART_NUM_1, data, RX_BUF_SIZE, portMAX_DELAY);

        if (rxBytes >= sizeof(int64_t)) {
            memcpy(&timestamped, data, sizeof(int64_t));

            int64_t delay = timenow - timestamped - BAUD_DELAY;
            ESP_LOGI(RX_TASK_TAG, "Read %d bytes: timestamped: '%lld', calculated delay: '%lld'", rxBytes, timestamped,delay);
            ESP_LOG_BUFFER_HEXDUMP(RX_TASK_TAG, data, rxBytes, ESP_LOG_INFO);
        }
    }
    free(data);
}

*/

void rx_task(void *arg)
{
    uint8_t byte;
    uint64_t tsf_tx;
    uint64_t tsf_rx;

    while (1) {
        // Find sync byte
        if (uart_read_bytes(UART_NUM_1, &byte, 1, pdMS_TO_TICKS(1000)) != 1)
            continue;

        if (byte != SYNC_BYTE)
            continue;

        // Read timestamp
        int len = uart_read_bytes(
            UART_NUM_1,
            (uint8_t *)&tsf_tx,
            sizeof(tsf_tx),
            pdMS_TO_TICKS(10)
        );

        if (len != sizeof(tsf_tx))
            continue;

        // Timestamp AS SOON AS POSSIBLE
        tsf_rx = esp_wifi_get_tsf_time(WIFI_IF_STA);

        int64_t offset = (int64_t)tsf_rx - (int64_t)tsf_tx;

        ESP_LOGI("OFFSET", "ΔTSF = %lld us", offset);
    }
}
