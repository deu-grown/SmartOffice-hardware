"""워커 공통 베이스.

- Worker: 데몬 스레드. setup()→(tick() 루프)→teardown(). stop_event.wait(interval) 로
  sleep 하므로 종료 신호 시 대기를 즉시 끊는다. setup 실패는 해당 워커만 비활성(데몬 전체는 생존).
- SensorWorker: 센서 측정값을 MQTT 우선 + HTTP 폴백으로 발행하는 publish_reading() 제공.
"""

from __future__ import annotations

import threading

from .config import HttpConfig, Peripheral
from .log import get_logger
from .transport import Transport
from .util import http_post, now_ts


class Worker(threading.Thread):
    def __init__(self, name: str, interval: float, stop_event: threading.Event) -> None:
        super().__init__(name=name, daemon=True)
        self._interval = interval
        # 주의: threading.Thread 내부에 _stop() 메서드가 있어 이름 충돌 금지 → _stop_event 사용
        self._stop_event = stop_event
        self._log = get_logger(name)  # 워커별 logger (로그에 워커명 표시)

    # 하위 클래스 훅
    def setup(self) -> None: ...
    def tick(self) -> None: raise NotImplementedError
    def teardown(self) -> None: ...

    def run(self) -> None:
        try:
            self.setup()
        except Exception as e:
            self._log.error("setup 실패 — 이 워커만 비활성: %s", e)
            return
        try:
            while not self._stop_event.is_set():
                try:
                    self.tick()
                except Exception as e:
                    self._log.error("tick 오류: %s", e)
                if self._stop_event.wait(self._interval):
                    break
        finally:
            try:
                self.teardown()
            except Exception as e:
                self._log.warning("teardown 예외: %s", e)


class SensorWorker(Worker):
    def __init__(self, name: str, interval: float, stop_event: threading.Event,
                 transport: Transport, http: HttpConfig) -> None:
        super().__init__(name, interval, stop_event)
        self._transport = transport
        self._http = http

    def publish_reading(self, p: Peripheral, value) -> bool:
        """센서 1건 발행. MQTT 페이로드엔 sensorType 없음(백엔드가 토픽에서 도출).
        HTTP 폴백 본문엔 zoneId + 대문자 sensorType 추가(엔드포인트가 본문에서 요구)."""
        ts = now_ts()
        mqtt_payload = {
            "deviceId": p.device_id,
            "value": value,
            "unit": p.unit,
            "timestamp": ts,
        }
        http_body = {
            "zoneId": p.zone_id,
            "deviceId": p.device_id,
            "sensorType": p.sensor_type,  # 대문자 TEMPERATURE/HUMIDITY/CO2
            "value": value,
            "unit": p.unit,
            "timestamp": ts,
        }

        def fallback() -> bool:
            resp = http_post(self._http.url(self._http.sensors_path), http_body, self._http.timeout)
            if resp is not None and resp.status_code in (200, 201):
                return True
            self._log.warning("HTTP 폴백 실패 (%s)", getattr(resp, "status_code", "no-response"))
            return False

        ok = self._transport.publish_uplink(p.topic, mqtt_payload, fallback)
        if ok:
            self._log.info("%s=%s%s", p.sensor_type, value, p.unit or "")
        else:
            self._log.warning("발행 실패 %s=%s", p.sensor_type, value)
        return ok
