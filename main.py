#!/usr/bin/env python3
"""SmartOffice Raspberry Pi 통합 데몬 진입점.

센서 수집(DHT22·CO2) + NFC 출입 + 액추에이터 원격제어(command 구독)를 하나의 프로세스로.
전송은 MQTT 우선 + HTTP 폴백, command 는 MQTT 구독.

실행:  python main.py        (설정: ./config.json, 없으면 기본값)
검증:  SMARTOFFICE_DRY_RUN=1 python main.py   (GPIO/시리얼 없이 합성 동작)
"""

from __future__ import annotations

import signal
import threading

from smartoffice.commands import CommandDispatcher
from smartoffice.config import load_config
from smartoffice.log import get_logger, setup_logging
from smartoffice.peripherals.co2 import Co2Worker
from smartoffice.peripherals.dht22 import DhtWorker
from smartoffice.peripherals.led import LedActuator
from smartoffice.peripherals.nfc import NfcWorker
from smartoffice.peripherals.solenoid import SolenoidActuator
from smartoffice.transport import Transport

log = get_logger("main")


def _build_actuator(actuator, label: str):
    """setup 시도 후 실패하면 None 반환(해당 액추에이터만 비활성, 데몬은 생존)."""
    try:
        actuator.setup()
        return actuator
    except Exception as e:
        log.error("%s setup 실패 — 비활성: %s", label, e)
        return None


def main() -> None:
    setup_logging()
    cfg = load_config()
    log.info("설정 로드 완료 (dry_run=%s, broker=%s:%s, api=%s)",
             cfg.dry_run, cfg.mqtt.host, cfg.mqtt.port, cfg.http.api_base)

    stop = threading.Event()

    # ── 액추에이터 ───────────────────────────────────────────────────────────
    led = _build_actuator(LedActuator(cfg.actuators.led_pin, cfg.dry_run), "LED")
    solenoid = _build_actuator(SolenoidActuator(cfg.actuators.solenoid_pin, cfg.dry_run), "솔레노이드")
    dispatcher = CommandDispatcher(led=led, solenoid=solenoid)

    # ── 전송(업링크 발행 + command 구독) ─────────────────────────────────────
    transport = Transport(
        cfg.mqtt,
        command_topic=cfg.actuators.command_topic,
        command_handler=dispatcher.dispatch,
    )
    transport.start()

    # ── 센서/NFC 워커 ────────────────────────────────────────────────────────
    p = cfg.peripherals
    workers = [
        DhtWorker(p["temperature"], p["humidity"], transport, cfg.http, stop, cfg.dry_run),
        NfcWorker(p["nfc"], transport, cfg.http, stop, cfg.dry_run, solenoid=solenoid),
    ]
    co2 = p["co2"]
    if co2.enabled and co2.device_id > 0:
        workers.append(Co2Worker(co2, transport, cfg.http, stop, cfg.dry_run))
    else:
        log.warning("[co2] 비활성 (enabled=%s, device_id=%s — V20 시드 후 config 설정)",
                    co2.enabled, co2.device_id)

    for w in workers:
        w.start()
    log.info("워커 %d개 가동: %s", len(workers), ", ".join(w.name for w in workers))

    # ── 시그널 → 종료 ────────────────────────────────────────────────────────
    def _sig(signum, _frame):
        log.info("시그널 %s 수신 — 종료 절차 시작", signum)
        stop.set()

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    # 메인 스레드 대기 (1s 폴링 — 시그널이 wait 를 확실히 깨우도록)
    try:
        while not stop.wait(1.0):
            pass
    except KeyboardInterrupt:
        stop.set()

    # ── 정렬된 종료 ──────────────────────────────────────────────────────────
    log.info("종료: transport 정지 → 워커 join → 액추에이터 안전화 → GPIO cleanup")
    transport.stop()
    for w in workers:
        w.join(timeout=5)
    if solenoid is not None:
        solenoid.close()   # 안전: 솔레노이드 de-energize (과열 방지)
    if led is not None:
        led.close()
    if not cfg.dry_run:
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()  # 전역 1회 (LED 핀 등 RPi.GPIO 관리 핀)
        except Exception:
            pass
    log.info("종료 완료")


if __name__ == "__main__":
    main()
