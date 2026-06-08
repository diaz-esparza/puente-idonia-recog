from typing import cast

import structlog

type LoggerType = structlog.stdlib.BoundLogger


def get_logger(module_name: str) -> LoggerType:
    return cast(LoggerType, structlog.get_logger(module_name))
