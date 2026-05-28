import ipaddress

import httpx

from puente.config import get_settings


def _resolve(bind_host: str) -> str:
    addr = ipaddress.ip_address(bind_host)
    if addr.is_unspecified:
        return (
            "::1" if isinstance(addr, ipaddress.IPv6Address) else "127.0.0.1"
        )
    return bind_host


def main() -> None:
    settings = get_settings()
    _ = httpx.get(
        f"http://{_resolve(settings.app_host)}:{settings.app_port}/health",
        timeout=10,
    ).raise_for_status()
