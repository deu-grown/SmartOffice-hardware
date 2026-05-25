#!/usr/bin/env python3
"""
SmartOffice NFC Reader — Raspberry Pi
MFRC522(RC522) 모듈로 NFC 카드를 읽어 MQTT 또는 HTTP로 서버에 전송한다.

통신 우선순위:
  1. MQTT  → smartoffice/{ZONE_ID}/access  (QoS 1)
  2. HTTP  → POST /api/v1/access-logs/tag  (MQTT 실패 시 폴백)

설치:
  pip install mfrc522 paho-mqtt requests RPi.GPIO
"""

import json
import signal
import sys
import time
from datetime import datetime

import requests
import RPi.GPIO as GPIO
from mfrc522 import MFRC522
# import paho.mqtt.client as mqtt  # MQTT 브로커 미연결 — 연결 후 활성화

# ─── 필수 설정 ────────────────────────────────────────────────────────────────

DEVICE_ID = 1           # 관리자 화면에서 등록된 device_id
ZONE_ID   = 1           # 이 장치가 속한 zone_id
DIRECTION = "IN"        # 입구: "IN" | 출구: "OUT"

SERVER_HOST = "192.168.1.100:8080"   # 예: "192.168.1.100" 또는 "api.example.com"

# MQTT
MQTT_PORT     = 1883        # 운영 SSL: 8883
MQTT_USERNAME = ""          # 브로커 인증이 없으면 빈 문자열
MQTT_PASSWORD = ""
MQTT_USE_TLS  = False       # 운영 환경에서는 True (8883 포트와 함께)

# HTTP 폴백
HTTP_SCHEME = "http"        # 운영: "https"

# 동작 파라미터
DEBOUNCE_SECONDS = 3        # 동일 카드 재태그 무시 간격 (초)
READ_INTERVAL    = 0.1      # 카드 감지 폴링 간격 (초)

# ─── 내부 계산 ────────────────────────────────────────────────────────────────

MQTT_TOPIC = f"smartoffice/{ZONE_ID}/access"
HTTP_URL   = f"{HTTP_SCHEME}://{SERVER_HOST}/api/v1/access-logs/tag"

# ─────────────────────────────────────────────────────────────────────────────


class NfcReader:
    """RC522 모듈 래퍼 — UID를 'AA:BB:CC:DD' 형식으로 읽는다."""

    def __init__(self):
        self._reader = MFRC522()
        self._last_uid: str | None = None
        self._last_time: float = 0.0

    def read_uid(self) -> str | None:
        """카드가 감지되면 UID 문자열 반환, 없으면 None."""
        status, _ = self._reader.MFRC522_Request(self._reader.PICC_REQIDL)
        if status != self._reader.MI_OK:
            return None

        status, raw = self._reader.MFRC522_Anticoll()
        if status != self._reader.MI_OK:
            return None

        # 4바이트 UID를 'AA:BB:CC:DD' 형식으로 변환
        # NFC 카드 등록 시 동일한 형식을 사용해야 서버에서 매칭됨
        return ':'.join(f'{b:02X}' for b in raw[:4])

    def is_duplicate(self, uid: str) -> bool:
        """DEBOUNCE_SECONDS 이내 동일 UID 재감지 시 True."""
        now = time.time()
        if uid == self._last_uid and (now - self._last_time) < DEBOUNCE_SECONDS:
            return True
        self._last_uid = uid
        self._last_time = now
        return False


# ─── MQTT 클래스 (브로커 연결 후 활성화) ────────────────────────────────────
# class MqttSender:
#     """MQTT 발행 클라이언트 (자동 재연결 포함)."""
#
#     def __init__(self):
#         self.connected = False
#         self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="smartoffice-rpi")
#         self._client.on_connect    = self._on_connect
#         self._client.on_disconnect = self._on_disconnect
#
#         if MQTT_USERNAME:
#             self._client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
#         if MQTT_USE_TLS:
#             self._client.tls_set()
#
#         try:
#             self._client.connect(SERVER_HOST, MQTT_PORT, keepalive=60)
#             self._client.loop_start()
#         except Exception as e:
#             print(f"[MQTT] 초기 연결 실패: {e}  (HTTP 폴백으로 동작)")
#
#     def _on_connect(self, client, userdata, flags, reason_code, properties):
#         if reason_code == 0:
#             self.connected = True
#             print(f"[MQTT] 연결됨 → {SERVER_HOST}:{MQTT_PORT}")
#         else:
#             print(f"[MQTT] 연결 거부 (코드: {reason_code})")
#
#     def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
#         self.connected = False
#         print("[MQTT] 연결 끊김, 재연결 대기 중...")
#
#     def publish(self, payload: dict) -> bool:
#         if not self.connected:
#             return False
#         result = self._client.publish(MQTT_TOPIC, json.dumps(payload), qos=1)
#         success = result.rc == mqtt.MQTT_ERR_SUCCESS
#         if success:
#             print(f"[MQTT] 전송 완료 → {MQTT_TOPIC}")
#         else:
#             print(f"[MQTT] 전송 실패 (rc={result.rc})")
#         return success
#
#     def stop(self):
#         self._client.loop_stop()
#         self._client.disconnect()
# ─────────────────────────────────────────────────────────────────────────────


def send_http(payload: dict) -> bool:
    """HTTP POST 폴백 전송. 서버 응답(승인/거부)을 출력한다."""
    try:
        resp = requests.post(HTTP_URL, json=payload, timeout=5)
        if resp.ok:
            data = resp.json().get("data", {})
            auth   = data.get("authResult", "UNKNOWN")
            reason = data.get("denyReason") or ""
            suffix = f" ({reason})" if reason else ""
            print(f"[HTTP] 결과: {auth}{suffix}")
            return True
        print(f"[HTTP] 서버 오류 (status={resp.status_code})")
        return False
    except requests.RequestException as e:
        print(f"[HTTP] 요청 실패: {e}")
        return False


def build_payload(uid: str) -> dict:
    return {
        "deviceId":  DEVICE_ID,
        "uid":       uid,
        "direction": DIRECTION,
        "taggedAt":  datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }


def main():
    nfc = NfcReader()
    # mqtt = MqttSender()  # MQTT 브로커 연결 후 활성화

    def shutdown(sig, frame):
        print("\n[시스템] 종료 신호 수신, 정리 중...")
        # mqtt.stop()
        GPIO.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"[시스템] 시작 — device_id={DEVICE_ID}, zone_id={ZONE_ID}, direction={DIRECTION}")
    print("[시스템] HTTP 모드로 동작 중 (MQTT 비활성화)")
    print("[시스템] 카드를 접촉해 주세요...\n")

    while True:
        uid = nfc.read_uid()

        if uid is None:
            time.sleep(READ_INTERVAL)
            continue

        if nfc.is_duplicate(uid):
            time.sleep(READ_INTERVAL)
            continue

        print(f"[카드] UID: {uid}")
        payload = build_payload(uid)

        # MQTT 활성화 시 아래로 교체:
        # if not mqtt.publish(payload):
        #     print("[MQTT] 실패 → HTTP 폴백 시도")
        #     send_http(payload)
        send_http(payload)

        time.sleep(READ_INTERVAL)


if __name__ == "__main__":
    main()
