"""DHT22 온·습도 워커. tests/testpy.py 의 read+retry 패턴 이식.

수정 사항: "TEMPARATURE" 오타 → "TEMPERATURE"(config.sensor_type 가 대문자 처리),
하드코딩 zone2/dev1 → config 시드 ID(temp=zone5/dev3, humi=zone5/dev4),
인라인 POST 제거 → transport.publish_uplink.
"""

from __future__ import annotations

import random
import threading

from ..config import HttpConfig, Peripheral
from ..log import get_logger
from ..transport import Transport
from ..workers import SensorWorker

log = get_logger("dht")


class DhtWorker(SensorWorker):
    def __init__(self, temp: Peripheral, humi: Peripheral, transport: Transport,
                 http: HttpConfig, stop_event: threading.Event, dry_run: bool,
                 interval: float = 2.0) -> None:
        super().__init__("dht", interval, stop_event, transport, http)
        self._temp = temp
        self._humi = humi
        self._dry_run = dry_run
        self._dht = None

    def setup(self) -> None:
        if self._dry_run:
            log.info("dry-run (합성 데이터)")
            return
        import adafruit_dht  # lazy import — 없으면 이 워커만 비활성
        import board
        self._dht = adafruit_dht.DHT22(getattr(board, f"D{self._temp.pin}"))
        log.info("DHT22 on D%s (temp zone%s/dev%s, humi zone%s/dev%s)",
                 self._temp.pin, self._temp.zone_id, self._temp.device_id,
                 self._humi.zone_id, self._humi.device_id)

    def tick(self) -> None:
        temp, humi = self._read()
        if temp is not None and self._temp.enabled:
            self.publish_reading(self._temp, round(float(temp), 2))
        if humi is not None and self._humi.enabled:
            self.publish_reading(self._humi, round(float(humi), 2))

    def _read(self):
        if self._dry_run:
            return round(random.uniform(20, 26), 1), round(random.uniform(40, 60), 1)
        try:
            return self._dht.temperature, self._dht.humidity
        except RuntimeError as e:
            # DHT22 일시적 read 실패는 흔함 → 다음 tick 에서 재시도
            log.debug("일시 read 오류: %s", e)
            return None, None

    def teardown(self) -> None:
        if self._dht is not None:
            try:
                self._dht.exit()
            except Exception:
                pass
