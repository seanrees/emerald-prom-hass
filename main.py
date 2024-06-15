#!/usr/bin/env python3

import argparse
import asyncio
import configparser
from dataclasses import dataclass
import logging
import sys
import time

import emerald
import homeassistant
import prometheus


logger = logging.getLogger(__name__)


@dataclass(init=False)
class Configuration:
    hass_enabled: bool
    hass_mqtt_address: str
    hass_mqtt_username: str
    hass_mqtt_password: str

    def __init__(self):
        self.hass_enabled = False


def _sleep_forever() -> None:
    """Sleeps the calling thread until a keyboard interrupt occurs."""
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            break


def _read_config(filename: str) -> Configuration:
    logger.info("reading %s", filename)

    config = configparser.ConfigParser()
    try:
        config.read(filename)
    except configparser.Error as e:
        logger.critical('Could not read "%s": %s', filename, e)
        raise

    try:
        ret = Configuration()

        if "Home Assistant" in config:
            hass = config["Home Assistant"]

            ret.hass_enabled = hass.getboolean("Enabled", fallback=False)
            ret.hass_mqtt_address = hass.get("MqttAddress")
            ret.hass_mqtt_username = hass.get("MqttUsername")
            ret.hass_mqtt_password = hass.get("MqttPassword")

        return ret
    except KeyError as e:
        logging.critical('Required key missing in "%s": %s', filename, e)
        raise


def main(argv):
    """Main body of the program."""
    parser = argparse.ArgumentParser(prog=argv[0])
    parser.add_argument(
        "--port", help="HTTP server port [default: %(default)d]", type=int, default=4480
    )
    parser.add_argument("--address", help="Address of paired EIAdv device")
    parser.add_argument(
        "--config",
        help="Configuration file [default: %(default)s]",
        default="config.ini",
    )
    parser.add_argument(
        "--log_level",
        help="Logging level (DEBUG, INFO, WARNING, ERROR) [default: %(default)s]",
        type=str,
        default="INFO",
    )

    args = parser.parse_args()

    try:
        level = getattr(logging, args.log_level)
    except AttributeError:
        print(f"Invalid --log_level: {args.log_level}")
        sys.exit(-1)
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s [%(name)14s %(thread)d] %(levelname)10s %(message)s",
        datefmt="%Y/%m/%d %H:%M:%S",
        level=level,
    )

    logger.info("Starting up on port=%s, EIAdv address=%s", args.port, args.address)

    config = _read_config(args.config)
    em = emerald.EmeraldAdvisor(args.address)
    hass = None

    if config.hass_enabled:

        def start_hass(mac: str, mfg: str, serial: str, fwver: str):
            logger.info(
                "registering %s device (serial=%s, fwver=%s) with HomeAssistant",
                mfg,
                serial,
                fwver,
            )

            hass = homeassistant.HomeAssistantSensor(
                config.hass_mqtt_address,
                config.hass_mqtt_username,
                config.hass_mqtt_password,
                serial,
            )
            hass.connect()

            em.add_update_callback(hass.update)

        em.add_identification_callback(start_hass)

    prom = prometheus.PrometheusClient(args.port)

    em.add_identification_callback(prom.set_dev_info)
    em.add_update_callback(prom.update)

    prom.start()

    stop_event = asyncio.Event()
    asyncio.run(em.start(stop_event))
    _sleep_forever()

    if hass:
        hass.shutdown()

    stop_event.set()


if __name__ == "__main__":
    main(sys.argv)
