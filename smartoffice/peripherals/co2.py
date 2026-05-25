"""CO2(MH-Z19 계열, UART) 워커. tests/echo_filter.py 의 에코 필터 파서 이식.

개선: 시리얼 포트를 워커 수명 동안 1회만 열어 유지(원본은 read 마다 open/close).
주의: tests/co2_bug.py 는 9바이트 blind read 로 에코를 받는 버그 버전 — 이식 금지.
"""

from __future__ import annotations

import random
import threading
import time

from ..config import HttpConfig, Peripheral
from ..log import get_logger
from ..transport import Transport
from ..workers import SensorWorker

log = get_logger("co2")

# 가스 농도 읽기 명령 (0x86)
_CMD = b"\xff\x01\x86\x00\x00\x00\x00\x00\x79"


class Co2Worker(SensorWorker):
    def __init__(self, co2: Peripheral, transport: Transport, http: HttpConfig,
                 stop_event: threading.Event, dry_run: bool, interval: float = 5.0) -> None:
        super().__init__("co2", interval, stop_event, transport, http)
        self._p = co2
        self._dry_run = dry_run
        self._ser = None

    def setup(self) -> None:
        if self._dry_run:
            log.info("dry-run (합성 데이터)")
            return
        import serial  # lazy import (pyserial)
        self._ser = serial.Serial(self._p.port, baudrate=9600, timeout=2)
        log.info("serial open %s (zone%s/dev%s)", self._p.port, self._p.zone_id, self._p.device_id)

    def tick(self) -> None:
        value = self._read()
        if value is not None and self._p.enabled:
            self.publish_reading(self._p, value)

    def _read(self):
        if self._dry_run:
            return random.randint(450, 800)
        try:
            self._ser.reset_input_buffer()
            self._ser.write(_CMD)
            time.sleep(0.5)  # 라파5 UART 에코+응답 도착 대기 (원본 검증값)
            data = self._ser.read(20)
            if not data:
                log.debug("무응답")
                return None
            # 에코([요청 9B])가 앞에 섞여 오므로 응답 시작점 FF 86 을 탐색
            i = data.find(b"\xff\x86")
            if i == -1 or len(data) < i + 9:
                log.debug("FF86 미발견 raw=%s", data.hex())
                return None
            res = data[i:i + 9]
            co2 = res[2] * 256 + res[3]
            if 300 < co2 < 10000:
                return co2
            log.debug("범위 밖: %s", co2)
            return None
        except Exception as e:
            log.warning("read 오류: %s", e)
            return None

    def teardown(self) -> None:
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
