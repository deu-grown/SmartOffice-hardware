"""로깅 설정 — stdout으로 출력해 systemd journald가 수집하도록 한다."""

import logging
import os
import sys


def setup_logging() -> None:
    """루트 로거를 stdout 핸들러로 1회 구성한다. 레벨은 SMARTOFFICE_LOG_LEVEL(기본 INFO)."""
    level_name = os.environ.get("SMARTOFFICE_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    if root.handlers:  # 중복 구성 방지
        root.setLevel(level)
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
