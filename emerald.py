# Credits:
# Thanks to @WeekendWarrior1's ESPhome implementation here
# https://github.com/WeekendWarrior1/emerald_electricity_advisor
# for doing the leg-work decoding theinformation.
#

import asyncio
import logging
from typing import Callable

from bleak import BleakClient


# Device Info
SERVICE_DEVICE_INFO_UUID = "0000180A-0000-1000-8000-00805f9b34fb"
CHAR_DEVICE_MANUFACTURER_UUID = "00002A29-0000-1000-8000-00805f9b34fb"
CHAR_DEVICE_SERIAL_UUID = "00002A25-0000-1000-8000-00805f9b34fb"
CHAR_DEVICE_FIRMWARE_UUID = "00002A26-0000-1000-8000-00805f9b34fb"

# Energy Monitoring
TIME_SERVICE_UUID = "00001910-0000-1000-8000-00805f9b34fb"
CHAR_TIME_READ_UUID = "00002b10-0000-1000-8000-00805f9b34fb"
CHAR_TIME_WRITE_UUID = "00002b11-0000-1000-8000-00805f9b34fb"

CMD_POWER_CONSUMPTION_30S = "0001020a06"


logger = logging.getLogger(__name__)


class EmeraldAdvisor:
    def __init__(self, mac: str):
        self._mac = mac
        self._identify_callbacks = set()
        self._update_callbacks = set()

    # An identification callback is triggered when we've identified the
    # device. Example signature:
    #
    # def cb(mac_address: str, manufacturer: str, serial_number: str, fw_version: str):
    #    pass
    #
    def add_identification_callback(
        self, fn: Callable[[str, str, str, str], None]
    ) -> None:
        self._identify_callbacks.add(fn)

    # An update callback is triggered when we have a new sample from the
    # sensor. Units are watt hours (Wh). Example signature:
    #
    # def cb(energy_wh: int):
    #   pass
    #
    def add_update_callback(self, fn: Callable[[int], None]) -> None:
        self._update_callbacks.add(fn)

    async def start(self, stop_event):
        async with BleakClient(self._mac) as client:
            device_info = client.services.get_service(SERVICE_DEVICE_INFO_UUID)

            mfg_char = device_info.get_characteristic(CHAR_DEVICE_MANUFACTURER_UUID)
            mfg = await client.read_gatt_char(mfg_char)

            serial_char = device_info.get_characteristic(CHAR_DEVICE_SERIAL_UUID)
            serial = await client.read_gatt_char(serial_char)

            fw_char = device_info.get_characteristic(CHAR_DEVICE_FIRMWARE_UUID)
            fw = await client.read_gatt_char(fw_char)

            mfg = mfg.decode("utf-8")
            serial = serial.decode("utf-8")
            fw = fw.decode("utf-8")

            for fn in self._identify_callbacks:
                fn(self._mac, mfg, serial, fw)

            logger.info(
                "connected to %s advisor (serial=%s, firmware=%s, mac=%s)",
                mfg,
                serial,
                fw,
                self._mac,
            )

            timesvc = client.services.get_service(TIME_SERVICE_UUID)
            t_char = timesvc.get_characteristic(CHAR_TIME_READ_UUID)

            logger.info("sending auto-upload command and listening for notifications")

            # Tell the device to auto upload stats
            w_char = timesvc.get_characteristic(CHAR_TIME_WRITE_UUID)
            auto_upload_cmd = bytearray(b"\x00\x01\x02\x0b\x01\x01")

            def update_metrics(sender, data):
                cmd = data[0:5]
                if cmd.hex() == CMD_POWER_CONSUMPTION_30S:
                    if len(data) != 11:
                        logger.warn(
                            "CMD_POWER_CONSUMPTION_30S wrong length, got %d want 11",
                            len(data),
                        )

                    date = data[5:9]
                    usage = data[9:11]
                    watt_hours = int.from_bytes(
                        usage, "big"
                    )  # measured in pulses, 1 pulse = 1 watt-hour

                    logger.info(
                        "sample received: pulses=%d (unparsed_date=0x%s)",
                        watt_hours,
                        date.hex(),
                    )
                    for fn in self._update_callbacks:
                        fn(watt_hours)

            await client.write_gatt_char(w_char, auto_upload_cmd, response=True)
            await client.start_notify(t_char, update_metrics)
            try:
                await stop_event.wait()
            except asyncio.exceptions.CancelledError:
                pass

            await client.stop_notify(t_char)
