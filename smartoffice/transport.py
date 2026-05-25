"""전송 추상화 — 업링크는 MQTT 우선 + HTTP 폴백, 다운링크(command)는 MQTT 구독.

설계 결정:
- 업링크는 "브로커 수용 = 성공"으로 간주한다. client.publish() 의 rc 가 SUCCESS 면 곧바로 성공
  처리하고 PUBACK 을 기다리지 않는다(엣지 fire-and-forget; 백엔드가 진실 원천).
- 미연결이거나 publish rc 가 SUCCESS 가 아니면 호출자가 넘긴 HTTP 폴백 클로저를 실행한다.
  → Transport 는 엔드포인트 모양을 모른다(센서/NFC 폴백 형태가 각자 다름).
- 재연결은 paho 내장 기능(connect_async + reconnect_delay_set + loop_start)에 위임한다.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Callable, Dict, Optional

import paho.mqtt.client as mqtt

from .config import MqttConfig
from .log import get_logger

log = get_logger("transport")

CommandHandler = Callable[[Dict[str, Any]], None]
HttpFallback = Callable[[], bool]


class Transport:
    def __init__(
        self,
        cfg: MqttConfig,
        command_topic: Optional[str] = None,
        command_handler: Optional[CommandHandler] = None,
    ) -> None:
        self._cfg = cfg
        self._command_topic = command_topic
        self._command_handler = command_handler

        client_id = f"{cfg.client_id}-{uuid.uuid4().hex[:8]}"
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            clean_session=True,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        if cfg.username:
            self._client.username_pw_set(cfg.username, cfg.password or "")
        if cfg.use_tls:
            # 인증서 경로가 없으면 시스템 CA 로 TLS (운영은 ca/cert/key 제공)
            self._client.tls_set(
                ca_certs=cfg.ca_certs,
                certfile=cfg.certfile,
                keyfile=cfg.keyfile,
            )
        # paho 내장 백오프 (1s~60s)
        self._client.reconnect_delay_set(min_delay=1, max_delay=60)

    # ─── 수명주기 ────────────────────────────────────────────────────────────

    def start(self) -> None:
        log.info("MQTT 연결 시도 → %s:%s (tls=%s)", self._cfg.host, self._cfg.port, self._cfg.use_tls)
        # connect_async: 브로커가 죽어 있어도 기동을 막지 않음(이후 자동 재연결)
        self._client.connect_async(self._cfg.host, self._cfg.port, keepalive=self._cfg.keepalive)
        self._client.loop_start()

    def stop(self) -> None:
        try:
            self._client.loop_stop()
            self._client.disconnect()
            log.info("MQTT 연결 종료")
        except Exception as e:  # 종료 경로 — 예외는 삼키되 기록
            log.warning("MQTT 종료 중 예외: %s", e)

    @property
    def connected(self) -> bool:
        return self._client.is_connected()

    # ─── 업링크 ──────────────────────────────────────────────────────────────

    def publish_uplink(self, topic: str, payload: Dict[str, Any], http_fallback: HttpFallback) -> bool:
        """MQTT 우선 발행, 실패/미연결 시 HTTP 폴백. 성공 여부 반환."""
        if self.connected:
            try:
                info = self._client.publish(topic, json.dumps(payload), qos=1)
                if info.rc == mqtt.MQTT_ERR_SUCCESS:
                    log.debug("MQTT 발행 → %s %s", topic, payload)
                    return True
                log.warning("MQTT 발행 rc=%s → HTTP 폴백", info.rc)
            except Exception as e:
                log.warning("MQTT 발행 예외(%s) → HTTP 폴백", e)
        else:
            log.debug("MQTT 미연결 → HTTP 폴백 (%s)", topic)
        return http_fallback()

    # ─── 콜백 ────────────────────────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            log.warning("MQTT 연결 거부: %s", reason_code)
            return
        # cleanSession=true → 재연결마다 재구독 필요
        if self._command_topic and self._command_handler:
            client.subscribe(self._command_topic, qos=1)
            # [안전장치] 실제 구독한 토픽을 한 줄 로그로 — command zone 오설정 즉시 확인 (B3)
            log.info("MQTT 연결됨. 구독: %s", self._command_topic)
        else:
            log.info("MQTT 연결됨. (command 구독 없음)")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        log.warning("MQTT 연결 끊김(reason=%s), 재연결 대기", reason_code)

    def _on_message(self, client, userdata, message) -> None:
        # paho 네트워크 스레드에서 실행 — 예외가 스레드를 죽이지 않도록 전체 보호
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            log.info("command 수신 ← %s %s", message.topic, payload)
            if self._command_handler:
                self._command_handler(payload)
        except Exception as e:
            log.error("command 처리 실패 ← %s err=%s", message.topic, e)
