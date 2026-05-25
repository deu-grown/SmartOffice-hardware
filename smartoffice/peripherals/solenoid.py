"""솔레노이드 도어락 액추에이터 (BCM24, gpiozero). tests/solenoid_bug.py 이식.

OutputDevice(active_high=False): .on()=핀 Low=릴레이 ON=잠금, .off()=해제.
안전 불변식: 종료 시 항상 de-energize(off) — 솔레노이드 과열 방지(원본 finally 동작).
"""

from __future__ import annotations

import threading

from ..log import get_logger

log = get_logger("solenoid")


class SolenoidActuator:
    def __init__(self, pin: int, dry_run: bool = False) -> None:
        self._pin = pin
        self._dry_run = dry_run
        self._dev = None
        self._lock = threading.Lock()

    def setup(self) -> None:
        if self._dry_run:
            log.info("dry-run (BCM%s)", self._pin)
            return
        from gpiozero import OutputDevice  # lazy import
        self._dev = OutputDevice(self._pin, active_high=False, initial_value=False)
        log.info("ready (BCM%s, active_high=False, 시작=해제)", self._pin)

    def lock(self) -> None:
        with self._lock:
            if self._dry_run:
                log.info("(dry) LOCK")
                return
            self._dev.on()
            log.info("LOCK")

    def unlock(self) -> None:
        with self._lock:
            if self._dry_run:
                log.info("(dry) UNLOCK")
                return
            self._dev.off()
            log.info("UNLOCK")

    def close(self) -> None:
        # 안전: 종료 시 반드시 전원 차단(과열 방지)
        with self._lock:
            if self._dry_run:
                log.info("(dry) de-energize on close")
                return
            if self._dev is not None:
                try:
                    self._dev.off()
                    self._dev.close()
                except Exception:
                    pass
            log.info("de-energized & closed")
