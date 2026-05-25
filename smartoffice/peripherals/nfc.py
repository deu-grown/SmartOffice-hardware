"""NFC(RC522) 출입 워커. tests/nfc_test.py 의 NfcReader/디바운스/HTTP 결과 파싱 이식.

업링크: MQTT 우선(smartoffice/{zone}/access) + HTTP 폴백(/api/v1/access-logs/tag).
HTTP 폴백 경로에서만 즉답(authResult)으로 직접 도어 개방한다. MQTT 경로는 백엔드가
판정 후 command(DOOR_LOCK)로 내려보내는 흐름에 맡긴다.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from ..config import HttpConfig, Peripheral
from ..log import get_logger
from ..transport import Transport
from ..util import http_post, now_ts
from ..workers import Worker

log = get_logger("nfc")

DEBOUNCE_SECONDS = 3
DIRECTION = "IN"  # 입구 리더기. 출구면 "OUT"


class NfcReader:
    """RC522 래퍼 — UID 를 'AA:BB:CC:DD' 형식으로 읽는다."""

    def __init__(self) -> None:
        from mfrc522 import MFRC522  # lazy import
        self._reader = MFRC522()
        self._last_uid: Optional[str] = None
        self._last_time = 0.0

    def read_uid(self) -> Optional[str]:
        status, _ = self._reader.MFRC522_Request(self._reader.PICC_REQIDL)
        if status != self._reader.MI_OK:
            return None
        status, raw = self._reader.MFRC522_Anticoll()
        if status != self._reader.MI_OK:
            return None
        return ":".join(f"{b:02X}" for b in raw[:4])

    def is_duplicate(self, uid: str) -> bool:
        now = time.time()
        if uid == self._last_uid and (now - self._last_time) < DEBOUNCE_SECONDS:
            return True
        self._last_uid = uid
        self._last_time = now
        return False


class NfcWorker(Worker):
    def __init__(self, nfc: Peripheral, transport: Transport, http: HttpConfig,
                 stop_event: threading.Event, dry_run: bool, solenoid=None,
                 interval: float = 0.1) -> None:
        super().__init__("nfc", interval, stop_event)
        self._p = nfc
        self._transport = transport
        self._http = http
        self._dry_run = dry_run
        self._solenoid = solenoid
        self._reader: Optional[NfcReader] = None
        self._dry_emitted = False

    def setup(self) -> None:
        if self._dry_run:
            log.info("dry-run (합성 1회 태그)")
            return
        self._reader = NfcReader()
        log.info("RC522 ready (zone%s/dev%s, dir=%s)", self._p.zone_id, self._p.device_id, DIRECTION)

    def tick(self) -> None:
        uid = self._read_uid()
        if uid is None:
            return
        log.info("UID %s", uid)
        self._handle(uid)

    def _read_uid(self) -> Optional[str]:
        if self._dry_run:
            if not self._dry_emitted:  # 반복 스팸 방지 — 1회만 방출
                self._dry_emitted = True
                return "DE:AD:BE:EF"
            return None
        uid = self._reader.read_uid()
        if uid is None or self._reader.is_duplicate(uid):
            return None
        return uid

    def _handle(self, uid: str) -> None:
        body = {
            "deviceId": self._p.device_id,
            "uid": uid,
            "direction": DIRECTION,
            "taggedAt": now_ts(),
        }

        def fallback() -> bool:
            resp = http_post(self._http.url(self._http.access_path), body, self._http.timeout)
            if resp is None:
                log.warning("HTTP 폴백 무응답")
                return False
            if resp.status_code not in (200, 201):
                log.warning("HTTP 폴백 오류 status=%s", resp.status_code)
                return False
            try:
                data = resp.json().get("data", {}) or {}
            except Exception:
                data = {}
            auth = data.get("authResult", "UNKNOWN")
            reason = data.get("denyReason") or ""
            log.info("판정(HTTP): %s%s", auth, f" ({reason})" if reason else "")
            # 즉답 경로에서만 직접 도어 개방
            if auth == "APPROVED" and self._solenoid is not None:
                self._solenoid.unlock()
            return True

        self._transport.publish_uplink(self._p.topic, body, fallback)
