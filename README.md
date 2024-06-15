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

Occasionally, exiting the Python program can result in a _failure_ to disconnect from
the device. If you see a bunch of `TimeoutError`'s, then try something like this:

```
% MAC_OF_DEVICE=30:1b:97:a:b:c"
% echo "disconnect ${MAC_OF_DEVICE}" | bluetoothctl
```

### Software Setup

Recommend you setup a venv first.

```
% pip install -r requirements.txt
```

## Run

Just: `./main.py --address MACOFYOURDEVICE` should do it.


### HomeAssistant notes

This integrates via HomeAssistant's [MQTT Discovery for Sensors](https://www.home-assistant.io/integrations/sensor.mqtt/).
You'll need the MQTT add-on, and a username and password.

To use, produce a configuration file and set it via `--config` (default is `config.ini`). `config-sample.ini`
should be a fairly self-explanatory example.

Once connected, the sensor should show up on a like this:
`homeassistant/sensor/emerald_electricity_advisor_YOURDEVICEID/energy_wh`

### Prometheus Notes

The Prometheus exporter primarily exports in joules, as suggested by
the [Metric and Label Naming](https://prometheus.io/docs/practices/naming/#base-units) guide
for base units.

The default port is `4480`, and can be overridden with `--port`. 

The metrics of interest:
1. `emerald_latest_joules` joules consumed in the last 30 seconds (if you sum these over an hour, you'll get KWh)
1. `emerald_latest_watts` an average of power consumed in the last 30 seconds
1. `emerald_joules_total` a counter of joules
1. `emerald_device_info` device info (firmware, manufacturer, serial as labels)
