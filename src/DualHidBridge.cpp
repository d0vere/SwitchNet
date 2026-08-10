#include "DualHidBridge.h"

#include "DualHidDriver.h"
#include "NintendoProControllerBackend.h"

namespace
{
NintendoProControllerBackend* backend_ = nullptr;
bool active_ = false;
}

void DualHidBridge::configure(
    NintendoProControllerBackend* backend,
    bool active
)
{
    backend_ = backend;
    active_ = active;
}

bool DualHidBridge::active()
{
    return active_;
}

bool DualHidBridge::ready()
{
    return switchnet_dual_hid_ready();
}

bool DualHidBridge::secondOpen()
{
    return switchnet_dual_hid_second_open();
}

bool DualHidBridge::send(
    std::uint8_t reportId,
    const void* data,
    std::uint16_t length
)
{
    return switchnet_dual_hid_send(
        reportId,
        data,
        length
    );
}

std::uint32_t DualHidBridge::reportsSent()
{
    return switchnet_dual_hid_reports_sent();
}

std::uint32_t DualHidBridge::outputsReceived()
{
    return switchnet_dual_hid_outputs_received();
}

extern "C" bool switchnet_dual_hid_active_hook(void)
{
    return active_;
}

extern "C" const uint8_t*
switchnet_dual_hid_report_descriptor_hook(void)
{
    return
        NintendoProControllerBackend::
            reportDescriptor();
}

extern "C" uint16_t
switchnet_dual_hid_report_descriptor_length_hook(void)
{
    return
        NintendoProControllerBackend::
            reportDescriptorLength();
}

extern "C" void switchnet_dual_hid_output_hook(
    uint8_t reportId,
    const uint8_t* data,
    uint16_t len
)
{
    if (backend_ != nullptr)
    {
        backend_->processSecondaryOutput(
            reportId,
            data,
            len
        );
    }
}
