#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

bool switchnet_dual_hid_send(
    uint8_t report_id,
    const void* data,
    uint16_t len
);

bool switchnet_dual_hid_ready(void);
bool switchnet_dual_hid_second_open(void);
uint32_t switchnet_dual_hid_reports_sent(void);
uint32_t switchnet_dual_hid_outputs_received(void);

bool switchnet_dual_hid_active_hook(void);
const uint8_t* switchnet_dual_hid_report_descriptor_hook(void);
uint16_t switchnet_dual_hid_report_descriptor_length_hook(void);
void switchnet_dual_hid_output_hook(
    uint8_t report_id,
    const uint8_t* data,
    uint16_t len
);

#ifdef __cplusplus
}
#endif
