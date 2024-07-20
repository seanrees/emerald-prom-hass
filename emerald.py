# Credits:
# Thanks to @WeekendWarrior1's ESPhome implementation here
# https://github.com/WeekendWarrior1/emerald_electricity_advisor
# for doing the leg-work decoding theinformation.
#

import asyncio
import logging
from typing import Callable, Optional

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
CMD_RETURN_IMPULSE_RATE = "0001010602"

logger = logging.getLogger(__name__)


class EmeraldAdvisor:
    def __init__(self, mac: str):
        self._mac = mac

        # Rate of impulses, in imp/kwh
        self._impulse_rate: Optional[int] = None

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
        # Create a throwaway client to force a reset, just in case we've still
        # got a partially established session.
        throwaway_client = BleakClient(self._mac)
        await throwaway_client.disconnect()

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
            get_impulse_rate_cmd = bytearray(b"\x00\x01\x01\x05\x00")

            def update_metrics(sender, data):
                cmd = data[0:5]
                if cmd.hex() == CMD_POWER_CONSUMPTION_30S:
                    if len(data) != 11:
                        logger.warn(
                            "CMD_POWER_CONSUMPTION_30S wrong length, got %d want 11",
                            len(data),
                        )

                    if not self._impulse_rate:
                        logger.error(
                            "no impulse rate set from advisor, cannot interpret this result!"
                        )
                        return

                    date = data[5:9]
                    usage = data[9:11]
                    watt_hours = int.from_bytes(usage, "big") * (
                        self._impulse_rate / 1000
                    )

                    logger.info(
                        "sample received: pulses=%d (impulse_rate: %d imp/kwh, unparsed_date=0x%s)",
                        watt_hours,
                        self._impulse_rate,
                        date.hex(),
                    )
                    for fn in self._update_callbacks:
                        fn(watt_hours)
                if cmd.hex() == CMD_RETURN_IMPULSE_RATE:
                    # Impulse rate is imp/kWh
                    self._impulse_rate = int.from_bytes(data[5:], "big")

                    logger.info("impulse rate is %d imp/kWh", self._impulse_rate)
                else:
                    logger.debug(
                        "unknown command received: %s, full data: %s",
                        cmd.hex(),
                        data[5:].hex(),
                    )

            await client.start_notify(t_char, update_metrics)

            await client.write_gatt_char(w_char, get_impulse_rate_cmd, response=True)
            await client.write_gatt_char(w_char, auto_upload_cmd, response=True)
            try:
                await stop_event.wait()
            except asyncio.exceptions.CancelledError:
                pass

            await client.stop_notify(t_char)
