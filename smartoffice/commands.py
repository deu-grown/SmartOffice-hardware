"""command 다운링크 디스패치.

smartoffice/{zone}/command 페이로드 {"command","value","deviceId"} 를 받아 액추에이터로 라우팅.
ControlCommandType: AC·LIGHT·FAN·DOOR_LOCK·SET_TEMPERATURE.
  LIGHT     → LED (value on/off)
  DOOR_LOCK → 솔레노이드 (value lock/unlock) — 백엔드에서 ADMIN 전용
  AC/FAN/SET_TEMPERATURE → 하드웨어 없음, 로그만
디스패치는 command type 기준이며 deviceId 와 무관(payload deviceId 는 참고용).
"""

from __future__ import annotations

from typing import Optional

from .log import get_logger
from .peripherals.led import LedActuator
from .peripherals.solenoid import SolenoidActuator

log = get_logger("command")

_NOOP = {"AC", "FAN", "SET_TEMPERATURE"}


class CommandDispatcher:
    def __init__(self, led: Optional[LedActuator] = None,
                 solenoid: Optional[SolenoidActuator] = None) -> None:
        self._led = led
        self._solenoid = solenoid

    def dispatch(self, payload: dict) -> None:
        cmd = str(payload.get("command", "")).upper()
        value = str(payload.get("value", "")).lower()
        try:
            if cmd == "LIGHT":
                self._light(value)
            elif cmd == "DOOR_LOCK":
                self._door(value)
            elif cmd in _NOOP:
                log.info("%s 무시(하드웨어 없음) value=%s", cmd, value)
            else:
                log.warning("알 수 없는 command: %r", cmd)
        except Exception as e:
            log.error("%s 처리 오류: %s", cmd, e)

    def _light(self, value: str) -> None:
        if self._led is None:
            log.warning("LIGHT 수신했으나 LED 미구성")
            return
        if value in ("on", "1", "true"):
            self._led.on()
        elif value in ("off", "0", "false"):
            self._led.off()
        else:
            log.warning("LIGHT 알 수 없는 value: %r", value)

    def _door(self, value: str) -> None:
        if self._solenoid is None:
            log.warning("DOOR_LOCK 수신했으나 솔레노이드 미구성")
            return
        if value in ("lock", "close", "1"):
            self._solenoid.lock()
        elif value in ("unlock", "open", "0"):
            self._solenoid.unlock()
        else:
            log.warning("DOOR_LOCK 알 수 없는 value: %r", value)
