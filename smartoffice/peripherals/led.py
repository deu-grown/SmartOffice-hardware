"""LED 스트립 액추에이터 (BCM23, RPi.GPIO). tests/led_test.py 의 반전 로직 이식.

반전: GPIO.LOW = 켜짐, GPIO.HIGH = 꺼짐.
command(LIGHT)는 paho 네트워크 스레드에서 들어오므로 Lock 으로 보호하고 idempotent 하게 둔다.
"""

from __future__ import annotations

import threading

from ..log import get_logger

log = get_logger("led")


class LedActuator:
    def __init__(self, pin: int, dry_run: bool = False) -> None:
        self._pin = pin
        self._dry_run = dry_run
        self._gpio = None
        self._on = False
        self._lock = threading.Lock()

    def setup(self) -> None:
        if self._dry_run:
            log.info("dry-run (BCM%s)", self._pin)
            return
        import RPi.GPIO as GPIO  # lazy import
        self._gpio = GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self._pin, GPIO.OUT)
        GPIO.output(self._pin, GPIO.HIGH)  # 시작은 꺼짐(HIGH)
        log.info("ready (BCM%s, LOW=on)", self._pin)

    def on(self) -> None:
        with self._lock:
            if self._on:
                return
            self._on = True
            if self._dry_run:
                log.info("(dry) ON")
                return
            self._gpio.output(self._pin, self._gpio.LOW)  # 반전: LOW=on
            log.info("ON")

    def off(self) -> None:
        with self._lock:
            if not self._on:
                return
            self._on = False
            if self._dry_run:
                log.info("(dry) OFF")
                return
            self._gpio.output(self._pin, self._gpio.HIGH)
            log.info("OFF")

    def close(self) -> None:
        # GPIO.cleanup() 은 전역이라 main 에서 1회 — 여기선 끄기만.
        self.off()
