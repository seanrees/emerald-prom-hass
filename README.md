# emerald-prom-hass
Prometheus and HomeAssistant Exporter for Emerald Electricity Advisor

This code is **not** affiliated in any way with Emerald Home. Use at your own
risk, etc.

## About

This code connects to an Emerald [Electricity Advisor](https://emeraldhome.com.au/electricity-advisor/),
and publishes energy readings to a Prometheus Exporter and to HomeAssistant (via MQTT).

This code was tested on a Raspberry Pi running PiOS, and expects an impulse rate of 1000. 
If you want to run on something different, you'll need to make changes.

This code is, at best, alpha quality.

## Setup

### Bluetooth

Bleak doesn't (easily) support pairing codes. On PiOS (at least), use `bluetoothctl` to pair.

### Software Setup

Recommend you setup a venv first.

```
% pip install -r requirements.txt
```

## Run

Just: `./main.py --address MACOFYOURDEVICE` should do it.

Flags:
* `--homeassistant HOST` if you want to enable HomeAssistant (also edit main.py)

### HomeAssistant notes

This integrates via HomeAssistant's [MQTT Discovery for Sensors](https://www.home-assistant.io/integrations/sensor.mqtt/).
You'll need the MQTT add-on, and a username and password.

You need to update main.py to set `HOME_ASSISTANT_USERNAME` and `HOME_ASSISTANT_PASSWORD` to
connect to MQTT. Once connected, the sensor should show up on a like this:
`homeassistant/sensor/emerald_electricity_advisor_YOURDEVICEID/energy_wh`

### Prometheus Notes

The Prometheus exporter primarily exports in joules, as suggested by
the [Metric and Label Naming](https://prometheus.io/docs/practices/naming/#base-units) guide
for base units.

The metrics of interest:
1. `emerald_latest_joules` joules consumed in the last 30 seconds (if you sum these over an hour, you'll get KWh)
1. `emerald_latest_watts` an average of power consumed in the last 30 seconds
1. `emerald_joules_total` a counter of joules
1. `emerald_device_info` device info (firmware, manufacturer, serial as labels)
