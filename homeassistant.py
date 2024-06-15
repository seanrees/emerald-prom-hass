import datetime
import logging
import json

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class HomeAssistantSensor:
    def __init__(self, mqtt_host: str, username: str, password: str, device_id: str):
        self._mqtt_host = mqtt_host
        self._username = username
        self._password = password
        self._device_id = device_id
        self._last_reset = datetime.datetime.now()
        self._connected = False
        self._mqttc = None

    def _get_discovery_topic(self):
        return (
            f"homeassistant/sensor/emerald_electricity_advisor_{self._device_id}/config"
        )

    def _get_state_topic(self):
        return f"homeassistant/sensor/emerald_electricity_advisor_{self._device_id}/energy_wh"

    def _get_discovery_descriptor(self) -> str:
        return json.dumps(
            {
                "name": "Emerald Electricity Advisor",
                "state_topic": self._get_state_topic(),
                "device_class": "energy",
                "unique_id": f"emerald_electricity_advisor_{self._device_id}",
                "device": {
                    "manufacturer": "Emerald EMS pty ltd",
                    "model": "Electricity Advisor",
                    "serial_number": f"{self._device_id}",
                    "identifiers": [self._device_id],
                },
                "state_class": "total",
                "unit_of_measurement": "Wh",
                "last_reset_value_template": "{{ value_json.last_reset }}",
                "value_template": "{{ value_json.energy_wh }}",
            }
        )

    def connect(self) -> None:
        def on_connect(client, userdata, flags, rc, properties):
            if rc == "Success":
                self._connected = True
                logger.info("connected to MQTT broker %s", self._mqtt_host)

                logging.debug(
                    "Home Assistant discovery to %s: %s",
                    self._get_discovery_topic(),
                    self._get_discovery_descriptor(),
                )

                self._mqttc.publish(
                    self._get_discovery_topic(), self._get_discovery_descriptor(), qos=0
                )
            else:
                logger.error(
                    "could not connect to MQTT broker %s: %s", self._mqtt_host, rc
                )

        def on_publish(client, userdata, mid, rc, properties):
            logger.debug("mid = %s, rc = %s", mid, rc)

        mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        mqttc.on_connect = on_connect
        mqttc.on_publish = on_publish
        mqttc.username_pw_set(username=self._username, password=self._password)

        mqttc.connect(self._mqtt_host)
        mqttc.loop_start()
        self._mqttc = mqttc

    def shutdown(self) -> None:
        self._mqttc.disconnect()
        self._mqttc.loop_stop()

    def update(self, energy_wh: int) -> None:
        if self._connected:
            message = json.dumps(
                {
                    "last_reset": datetime.datetime.now().isoformat(),
                    "energy_wh": energy_wh,
                }
            )

            msg_info = self._mqttc.publish(self._get_state_topic(), message, qos=0)
            logger.info("published val=%s, mid=%s", message, msg_info.mid)
