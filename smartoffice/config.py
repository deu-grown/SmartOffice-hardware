"""통합 데몬 설정 — 단일 진실 원천.

계층(뒤가 우선): dataclass 기본값  ←  설정 파일(JSON)  ←  환경변수(시크릿/prod 스위치).

- 장치 맵·브로커 host·TLS 경로 등 구조적 값은 파일(config.json)에서.
- 시크릿(MQTT 비밀번호)·로컬/운영 스위치는 환경변수에서.

환경변수:
  SMARTOFFICE_ENV          local(기본) | prod   → prod 시 MQTT 8883 + TLS 기본 적용
  SMARTOFFICE_CONFIG       설정 파일 경로(기본 ./config.json)
  SMARTOFFICE_MQTT_HOST    브로커 host
  SMARTOFFICE_MQTT_USER / _PASS
  SMARTOFFICE_MQTT_CA / _CERT / _KEY   TLS 인증서 경로
  SMARTOFFICE_API_BASE     HTTP 폴백 베이스 URL
  SMARTOFFICE_DRY_RUN      1/true 시 GPIO·시리얼 없이 합성 동작
"""

from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# ─── dataclass 스키마 ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MqttConfig:
    host: str = "localhost"
    port: int = 1883
    use_tls: bool = False
    username: Optional[str] = None
    password: Optional[str] = None
    ca_certs: Optional[str] = None
    certfile: Optional[str] = None
    keyfile: Optional[str] = None
    client_id: str = "smartoffice-rpi"
    keepalive: int = 60


@dataclass(frozen=True)
class HttpConfig:
    api_base: str = "http://localhost:8080"
    timeout: float = 5.0
    sensors_path: str = "/api/v1/sensors/logs"
    access_path: str = "/api/v1/access-logs/tag"

    def url(self, path: str) -> str:
        return self.api_base.rstrip("/") + path


@dataclass(frozen=True)
class Peripheral:
    """주변장치 1개. name 은 토픽 접미사(소문자: temperature/humidity/co2/access)."""
    name: str
    zone_id: int
    device_id: int
    unit: Optional[str] = None
    pin: Optional[int] = None      # BCM 핀 (DHT=4)
    port: Optional[str] = None     # 시리얼 포트 (CO2)
    enabled: bool = True

    @property
    def topic(self) -> str:
        return f"smartoffice/{self.zone_id}/{self.name}"

    @property
    def sensor_type(self) -> str:
        """HTTP 폴백 본문용 대문자 sensorType (TEMPERATURE/HUMIDITY/CO2)."""
        return self.name.upper()


@dataclass(frozen=True)
class ActuatorConfig:
    # LED/솔레노이드는 이 zone 의 command 토픽을 구독해 구동된다.
    command_zone_id: int = 2
    led_pin: int = 23              # BCM23, 반전(LOW=on)
    led_device_id: int = 21       # 백엔드 LIGHT device (로그/검증용; 디스패치는 command type 기준)
    solenoid_pin: int = 24        # BCM24, gpiozero active_high=False
    solenoid_device_id: int = 14  # A2 V20__seed_rpi_devices.sql 의 DOOR_LOCK devices_id 와 일치해야 함

    @property
    def command_topic(self) -> str:
        return f"smartoffice/{self.command_zone_id}/command"


@dataclass(frozen=True)
class AppConfig:
    mqtt: MqttConfig
    http: HttpConfig
    peripherals: Dict[str, Peripheral]
    actuators: ActuatorConfig
    dry_run: bool = False


# ─── 기본 시드 신원 (코드로 검증된 백엔드 시드 매핑) ──────────────────────────
# nfc=zone2/dev1, temperature=zone5/dev3, humidity=zone5/dev4 는 기존 시드.
# co2=zone5/dev13 은 A2 V20__seed_rpi_devices.sql 의 devices_id 와 일치해야 함.
_DEFAULT_PERIPHERALS: Dict[str, Dict[str, Any]] = {
    "temperature": {"name": "temperature", "zone_id": 5, "device_id": 3, "unit": "C",  "pin": 4},
    "humidity":    {"name": "humidity",    "zone_id": 5, "device_id": 4, "unit": "%",  "pin": 4},
    "co2":         {"name": "co2",         "zone_id": 5, "device_id": 13, "unit": "ppm", "port": "/dev/serial0"},
    "nfc":         {"name": "access",      "zone_id": 2, "device_id": 1},
}


# ─── 로딩 ────────────────────────────────────────────────────────────────────

def _filter_fields(cls, data: Dict[str, Any]) -> Dict[str, Any]:
    """dataclass 에 정의된 필드만 추려 알 수 없는 키로 인한 TypeError 방지."""
    names = {f.name for f in dataclasses.fields(cls)}
    return {k: v for k, v in data.items() if k in names}


def _env(name: str) -> Optional[str]:
    val = os.environ.get(name)
    return val if val not in (None, "") else None


def _as_bool(val: Any) -> bool:
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def load_config() -> AppConfig:
    path = os.environ.get("SMARTOFFICE_CONFIG", "config.json")
    raw: Dict[str, Any] = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)

    is_prod = (os.environ.get("SMARTOFFICE_ENV", "local").lower() == "prod")

    # MQTT: 기본 ← 파일 ← (prod 스위치) ← env
    mqtt_data: Dict[str, Any] = {}
    mqtt_data.update(raw.get("mqtt", {}))
    if is_prod:
        mqtt_data.setdefault("port", 8883)
        mqtt_data.setdefault("use_tls", True)
    for env_key, field_key in (
        ("SMARTOFFICE_MQTT_HOST", "host"),
        ("SMARTOFFICE_MQTT_USER", "username"),
        ("SMARTOFFICE_MQTT_PASS", "password"),
        ("SMARTOFFICE_MQTT_CA", "ca_certs"),
        ("SMARTOFFICE_MQTT_CERT", "certfile"),
        ("SMARTOFFICE_MQTT_KEY", "keyfile"),
    ):
        v = _env(env_key)
        if v is not None:
            mqtt_data[field_key] = v
    mqtt = MqttConfig(**_filter_fields(MqttConfig, mqtt_data))

    # HTTP
    http_data: Dict[str, Any] = {}
    http_data.update(raw.get("http", {}))
    api_base = _env("SMARTOFFICE_API_BASE")
    if api_base is not None:
        http_data["api_base"] = api_base
    http = HttpConfig(**_filter_fields(HttpConfig, http_data))

    # 주변장치: 기본 ← 파일(키별 부분 override)
    periph_raw = raw.get("peripherals", {})
    peripherals: Dict[str, Peripheral] = {}
    for key, defaults in _DEFAULT_PERIPHERALS.items():
        merged = {**defaults, **periph_raw.get(key, {})}
        peripherals[key] = Peripheral(**_filter_fields(Peripheral, merged))

    # 액추에이터
    actuators = ActuatorConfig(**_filter_fields(ActuatorConfig, raw.get("actuators", {})))

    # dry-run: 파일 ← env
    dry_run = _as_bool(raw.get("dry_run", False))
    if _env("SMARTOFFICE_DRY_RUN") is not None:
        dry_run = _as_bool(os.environ["SMARTOFFICE_DRY_RUN"])

    return AppConfig(
        mqtt=mqtt,
        http=http,
        peripherals=peripherals,
        actuators=actuators,
        dry_run=dry_run,
    )
