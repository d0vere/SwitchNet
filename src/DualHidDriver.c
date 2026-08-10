/*
 * SwitchNet second HID interface driver.
 *
 * The class-driver structure and HID request handling follow TinyUSB's
 * hid_device.c design. TinyUSB is MIT licensed:
 * SPDX-FileCopyrightText: Copyright (c) 2019 Ha Thach (tinyusb.org)
 * SPDX-License-Identifier: MIT
 */

#include "DualHidDriver.h"

#include <string.h>

#include "tusb.h"
#include "device/usbd.h"
#include "device/usbd_pvt.h"
#include "class/hid/hid.h"
#include "class/hid/hid_device.h"

#define SN_HID_REPORT_DESC_LEN 203
#define SN_HID_EP_SIZE 64
#define SN_SECOND_ITF 1
#define SN_SECOND_EP_OUT 0x02
#define SN_SECOND_EP_IN  0x82

typedef struct
{
    uint8_t itf_num;
    uint8_t ep_in;
    uint8_t ep_out;
    uint8_t protocol_mode;
    uint8_t idle_rate;
    const tusb_hid_descriptor_hid_t* hid_descriptor;
    uint8_t ctrl[SN_HID_EP_SIZE];
    uint8_t epin[SN_HID_EP_SIZE];
    uint8_t epout[SN_HID_EP_SIZE];
} sn_hid_state_t;

static sn_hid_state_t sn_hid;
static uint32_t sn_reports_sent = 0;
static uint32_t sn_outputs_received = 0;

enum
{
    SN_SINGLE_TOTAL_LEN =
        TUD_CONFIG_DESC_LEN +
        TUD_HID_INOUT_DESC_LEN,

    SN_DUAL_TOTAL_LEN =
        TUD_CONFIG_DESC_LEN +
        TUD_HID_INOUT_DESC_LEN * 2
};

static uint8_t const sn_single_config[] =
{
    TUD_CONFIG_DESCRIPTOR(
        1,
        1,
        0,
        SN_SINGLE_TOTAL_LEN,
        0xA0,
        500
    ),

    TUD_HID_INOUT_DESCRIPTOR(
        0,
        0,
        HID_ITF_PROTOCOL_NONE,
        SN_HID_REPORT_DESC_LEN,
        0x01,
        0x81,
        SN_HID_EP_SIZE,
        1
    )
};

static uint8_t const sn_dual_config[] =
{
    TUD_CONFIG_DESCRIPTOR(
        1,
        2,
        0,
        SN_DUAL_TOTAL_LEN,
        0xA0,
        500
    ),

    TUD_HID_INOUT_DESCRIPTOR(
        0,
        0,
        HID_ITF_PROTOCOL_NONE,
        SN_HID_REPORT_DESC_LEN,
        0x01,
        0x81,
        SN_HID_EP_SIZE,
        1
    ),

    TUD_HID_INOUT_DESCRIPTOR(
        1,
        0,
        HID_ITF_PROTOCOL_NONE,
        SN_HID_REPORT_DESC_LEN,
        SN_SECOND_EP_OUT,
        SN_SECOND_EP_IN,
        SN_HID_EP_SIZE,
        1
    )
};

/*
 * Arduino-ESP32's implementation is weak, so this application callback can
 * provide the exact one- or two-interface descriptor required by the lab.
 */
uint8_t const* tud_descriptor_configuration_cb(uint8_t index)
{
    (void)index;

    return switchnet_dual_hid_active_hook()
        ? sn_dual_config
        : sn_single_config;
}

static void sn_init(void)
{
    memset(&sn_hid, 0, sizeof(sn_hid));
    sn_hid.protocol_mode = HID_PROTOCOL_REPORT;
    sn_reports_sent = 0;
    sn_outputs_received = 0;
}

static bool sn_deinit(void)
{
    return true;
}

static void sn_reset(uint8_t rhport)
{
    (void)rhport;
    memset(&sn_hid, 0, sizeof(sn_hid));
    sn_hid.protocol_mode = HID_PROTOCOL_REPORT;
}

static uint16_t sn_open(
    uint8_t rhport,
    tusb_desc_interface_t const* desc_itf,
    uint16_t max_len
)
{
    if (
        !switchnet_dual_hid_active_hook() ||
        desc_itf == NULL ||
        desc_itf->bInterfaceClass != TUSB_CLASS_HID ||
        desc_itf->bInterfaceNumber != SN_SECOND_ITF
    )
    {
        return 0;
    }

    uint16_t const drv_len =
        (uint16_t)(
            sizeof(tusb_desc_interface_t) +
            sizeof(tusb_hid_descriptor_hid_t) +
            desc_itf->bNumEndpoints *
                sizeof(tusb_desc_endpoint_t)
        );

    if (max_len < drv_len)
    {
        return 0;
    }

    uint8_t const* p_desc =
        (uint8_t const*)desc_itf;

    p_desc = tu_desc_next(p_desc);

    if (tu_desc_type(p_desc) != HID_DESC_TYPE_HID)
    {
        return 0;
    }

    sn_hid.hid_descriptor =
        (tusb_hid_descriptor_hid_t const*)p_desc;

    p_desc = tu_desc_next(p_desc);

    if (!usbd_open_edpt_pair(
        rhport,
        p_desc,
        desc_itf->bNumEndpoints,
        TUSB_XFER_INTERRUPT,
        &sn_hid.ep_out,
        &sn_hid.ep_in
    ))
    {
        return 0;
    }

    sn_hid.itf_num = desc_itf->bInterfaceNumber;
    sn_hid.protocol_mode = HID_PROTOCOL_REPORT;

    if (sn_hid.ep_out)
    {
        if (!usbd_edpt_xfer(
            rhport,
            sn_hid.ep_out,
            sn_hid.epout,
            sizeof(sn_hid.epout),
            false
        ))
        {
            return 0;
        }
    }

    return drv_len;
}

static bool sn_control(
    uint8_t rhport,
    uint8_t stage,
    tusb_control_request_t const* request
)
{
    if (
        request == NULL ||
        request->bmRequestType_bit.recipient !=
            TUSB_REQ_RCPT_INTERFACE ||
        (uint8_t)request->wIndex != sn_hid.itf_num
    )
    {
        return false;
    }

    if (
        request->bmRequestType_bit.type ==
        TUSB_REQ_TYPE_STANDARD
    )
    {
        if (stage != CONTROL_STAGE_SETUP)
        {
            return true;
        }

        uint8_t const desc_type =
            tu_u16_high(request->wValue);

        if (
            request->bRequest ==
                TUSB_REQ_GET_DESCRIPTOR &&
            desc_type == HID_DESC_TYPE_HID
        )
        {
            if (sn_hid.hid_descriptor == NULL)
            {
                return false;
            }

            return tud_control_xfer(
                rhport,
                request,
                (void*)(uintptr_t)sn_hid.hid_descriptor,
                sn_hid.hid_descriptor->bLength
            );
        }

        if (
            request->bRequest ==
                TUSB_REQ_GET_DESCRIPTOR &&
            desc_type == HID_DESC_TYPE_REPORT
        )
        {
            const uint8_t* report =
                switchnet_dual_hid_report_descriptor_hook();

            if (report == NULL)
            {
                return false;
            }

            return tud_control_xfer(
                rhport,
                request,
                (void*)(uintptr_t)report,
                switchnet_dual_hid_report_descriptor_length_hook()
            );
        }

        return false;
    }

    if (
        request->bmRequestType_bit.type !=
        TUSB_REQ_TYPE_CLASS
    )
    {
        return false;
    }

    switch (request->bRequest)
    {
        case HID_REQ_CONTROL_SET_REPORT:
        {
            if (stage == CONTROL_STAGE_SETUP)
            {
                if (request->wLength > sizeof(sn_hid.ctrl))
                {
                    return false;
                }

                return tud_control_xfer(
                    rhport,
                    request,
                    sn_hid.ctrl,
                    request->wLength
                );
            }

            if (stage == CONTROL_STAGE_ACK)
            {
                uint8_t const report_type =
                    tu_u16_high(request->wValue);
                uint8_t const report_id =
                    tu_u16_low(request->wValue);

                if (
                    report_type ==
                        HID_REPORT_TYPE_OUTPUT ||
                    report_type ==
                        HID_REPORT_TYPE_FEATURE
                )
                {
                    switchnet_dual_hid_output_hook(
                        report_id,
                        sn_hid.ctrl,
                        request->wLength
                    );
                    sn_outputs_received++;
                }
            }

            return true;
        }

        case HID_REQ_CONTROL_SET_IDLE:
            if (stage == CONTROL_STAGE_SETUP)
            {
                sn_hid.idle_rate =
                    tu_u16_high(request->wValue);
                return tud_control_status(
                    rhport,
                    request
                );
            }
            return true;

        case HID_REQ_CONTROL_GET_IDLE:
            if (stage == CONTROL_STAGE_SETUP)
            {
                return tud_control_xfer(
                    rhport,
                    request,
                    &sn_hid.idle_rate,
                    1
                );
            }
            return true;

        case HID_REQ_CONTROL_SET_PROTOCOL:
            if (stage == CONTROL_STAGE_SETUP)
            {
                sn_hid.protocol_mode =
                    (uint8_t)request->wValue;
                return tud_control_status(
                    rhport,
                    request
                );
            }
            return true;

        case HID_REQ_CONTROL_GET_PROTOCOL:
            if (stage == CONTROL_STAGE_SETUP)
            {
                return tud_control_xfer(
                    rhport,
                    request,
                    &sn_hid.protocol_mode,
                    1
                );
            }
            return true;

        default:
            return false;
    }
}

static bool sn_xfer(
    uint8_t rhport,
    uint8_t ep_addr,
    xfer_result_t result,
    uint32_t xferred_bytes
)
{
    if (
        ep_addr != sn_hid.ep_out &&
        ep_addr != sn_hid.ep_in
    )
    {
        return false;
    }

    if (ep_addr == sn_hid.ep_out)
    {
        if (result == XFER_RESULT_SUCCESS)
        {
            switchnet_dual_hid_output_hook(
                0,
                sn_hid.epout,
                (uint16_t)xferred_bytes
            );
            sn_outputs_received++;
        }

        return usbd_edpt_xfer(
            rhport,
            sn_hid.ep_out,
            sn_hid.epout,
            sizeof(sn_hid.epout),
            false
        );
    }

    return true;
}

/*
 * Application class drivers are explicitly supported by TinyUSB through
 * usbd_app_driver_get_cb(). The built-in HID class claims interface 0;
 * this driver only accepts interface 1.
 */
static usbd_class_driver_t const sn_driver =
{
    .name = "SwitchNet HID2",
    .init = sn_init,
    .deinit = sn_deinit,
    .reset = sn_reset,
    .open = sn_open,
    .control_xfer_cb = sn_control,
    .xfer_cb = sn_xfer
};

usbd_class_driver_t const*
usbd_app_driver_get_cb(uint8_t* driver_count)
{
    if (driver_count == NULL)
    {
        return NULL;
    }

    *driver_count = 1;
    return &sn_driver;
}

bool switchnet_dual_hid_ready(void)
{
    return
        switchnet_dual_hid_active_hook() &&
        sn_hid.ep_in != 0 &&
        tud_ready() &&
        !usbd_edpt_busy(0, sn_hid.ep_in);
}

bool switchnet_dual_hid_send(
    uint8_t report_id,
    const void* data,
    uint16_t len
)
{
    if (
        !switchnet_dual_hid_ready() ||
        data == NULL ||
        len + (report_id ? 1U : 0U) >
            sizeof(sn_hid.epin)
    )
    {
        return false;
    }

    uint16_t total = len;

    if (report_id)
    {
        sn_hid.epin[0] = report_id;
        memcpy(
            sn_hid.epin + 1,
            data,
            len
        );
        total++;
    }
    else
    {
        memcpy(
            sn_hid.epin,
            data,
            len
        );
    }

    if (!usbd_edpt_claim(0, sn_hid.ep_in))
    {
        return false;
    }

    if (!usbd_edpt_xfer(
        0,
        sn_hid.ep_in,
        sn_hid.epin,
        total,
        false
    ))
    {
        usbd_edpt_release(0, sn_hid.ep_in);
        return false;
    }

    sn_reports_sent++;
    return true;
}

bool switchnet_dual_hid_second_open(void)
{
    return sn_hid.ep_in != 0;
}

uint32_t switchnet_dual_hid_reports_sent(void)
{
    return sn_reports_sent;
}

uint32_t switchnet_dual_hid_outputs_received(void)
{
    return sn_outputs_received;
}
