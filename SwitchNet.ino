#include <ESPmDNS.h>
#include <BLEDevice.h>
#include "src/App.h"

App app;

void setup()
{
    app.begin();
}

void loop()
{
    app.update();
}
