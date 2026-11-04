#ifndef FIDO_STATUS_LCD_H
#define FIDO_STATUS_LCD_H

#include <stdint.h>

/* Starts the ST7735 status display task when the firmware is built with
 * FIDO_STATUS_LCD (ESP32-S3 target only). Safe to call once from app_main. */
void fido_status_lcd_init(void);

/* Publish the button wait in board_millis() units. A zero timeout clears it. */
void fido_status_lcd_set_button_wait(uint32_t started_ms, uint32_t timeout_ms,
                                     uint32_t limit_ms);

#endif
