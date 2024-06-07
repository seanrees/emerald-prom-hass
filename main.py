#!/usr/bin/env python3

import argparse
import asyncio
import logging
import sys
import time

import emerald
import homeassistant
import prometheus


logger = logging.getLogger(__name__)

# TODO: move this to a config file.
HOME_ASSISTANT_USERNAME = "username"
HOME_ASSISTANT_PASSWORD = "password"


def _sleep_forever() -> None:
    """Sleeps the calling thread until a keyboard interrupt occurs."""
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            break


def main(argv):
    """Main body of the program."""
    parser = argparse.ArgumentParser(prog=argv[0])
    parser.add_argument("--port", help="HTTP server port", type=int, default=4480)
    parser.add_argument("--address", help="Address of paired EIAdv device")
    parser.add_argument(
        "--homeassistant",
        help="HomeAssistant MQTT broker to publish events to",
        default="",
    )
    parser.add_argument(
        "--log_level",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
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
        format="%(asctime)s [%(name)10s %(thread)d] %(levelname)10s %(message)s",
        datefmt="%Y/%m/%d %H:%M:%S",
        level=level,
    )

    logger.info("Starting up on port=%s, EIAdv address=%s", args.port, args.address)

    em = emerald.EmeraldAdvisor(args.address)
    hass = None

    if args.homeassistant:

        def start_hass(mac: str, mfg: str, serial: str, fwver: str):
            logger.info(
                "registering %s device (serial=%s, fwver=%s) with HomeAssistant",
                mfg,
                serial,
                fwver,
            )

            hass = homeassistant.HomeAssistantSensor(
                args.homeassistant,
                HOME_ASSISTANT_USERNAME,
                HOME_ASSISTANT_PASSWORD,
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
