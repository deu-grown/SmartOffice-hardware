"""작은 공용 헬퍼."""

from datetime import datetime
from typing import Any, Dict, Optional

import requests


def now_ts() -> str:
    """백엔드가 기대하는 naive LocalDateTime 문자열(offset 없음).

    백엔드 검증(A3): SensorLogRequest @JsonFormat("yyyy-MM-dd'T'HH:mm:ss"),
    SensorMqttListener LocalDateTime.parse(...), TagEventRequest taggedAt 모두
    offset 없는 ISO_LOCAL_DATE_TIME 을 요구한다. tz-aware/offset 문자열은 파싱 실패.
    """
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def http_post(url: str, body: Dict[str, Any], timeout: float = 5.0) -> Optional[requests.Response]:
    """JSON POST. 네트워크 예외 시 None 반환(호출자가 폴백 실패로 처리)."""
    try:
        return requests.post(url, json=body, timeout=timeout)
    except requests.RequestException:
        return None

