import logging
from threading import Lock
import time

import prometheus_client
import prometheus_client.samples
import prometheus_client.values

logger = logging.getLogger(__name__)


class TimestampedValue(prometheus_client.values.MutexValue):
    """A float protected by a mutex."""

    def __init__(
        self, typ, metric_name, name, labelnames, labelvalues, help_text, **kwargs
    ):
        super().__init__(
            typ, metric_name, name, labelnames, labelvalues, help_text, **kwargs
        )
        self._timestamp = None

    def set(self, value, timestamp=None):
        with self._lock:
            self._value = value
            self._timestamp = timestamp

    def get(self):
        with self._lock:
            return (self._value, self._timestamp)


class TimedGauge(prometheus_client.Gauge):
    def _metric_init(self) -> None:
        self._value = TimestampedValue(
            self._type,
            self._name,
            self._name,
            self._labelnames,
            self._labelvalues,
            self._documentation,
        )

    def set(self, value: float) -> None:
        """Set gauge to the given value."""
        self._raise_if_not_observable()
        self._value.set(float(value), timestamp=time.time())

    def _child_samples(self):
        value, timestamp = self._value.get()
        return (prometheus_client.samples.Sample("", {}, value, timestamp, None),)


class PrometheusClient(object):
    def __init__(self, port):
        self._port = port
        self._dev_info = prometheus_client.Info("emerald_device", "Device Information")
        self._joules_gauge = TimedGauge(
            "emerald_latest_joules", "Number of joules in last 30 second sample"
        )
        self._watts_gauge = TimedGauge(
            "emerald_latest_watts", "Watts demanded (avg) over the last sample"
        )
        self._joules_counter = prometheus_client.Counter(
            "emerald_joules", "Counter of joules"
        )
        self._last_sample_time = prometheus_client.Gauge(
            "emerald_last_sample_time", "Timestamp of last sample from sensor"
        )

    def start(self):
        prometheus_client.start_http_server(self._port)

    def set_dev_info(self, mac: str, mfg: str, serial: str, fwver: str) -> None:
        self._dev_info.info(
            {
                "manufacturer": mfg,
                "serial": serial,
                "firmware_version": fwver,
                "mac": mac,
            }
        )

    def update(self, energy_wh: int) -> None:
        watts_avg = energy_wh * (
            3600 / 30
        )  # 3600 seconds in an hour, samples every 30 sec
        joules = energy_wh * 3600

        logger.info(
            "updating prometheus metrics with %d Wh (%.2fW avg, %dJ)",
            energy_wh,
            watts_avg,
            joules,
        )

        self._joules_counter.inc(joules)
        self._joules_gauge.set(joules)
        self._watts_gauge.set(watts_avg)
        self._last_sample_time.set_to_current_time()
