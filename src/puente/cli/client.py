import asyncio
import ipaddress
from types import TracebackType
from typing import Self
from urllib.parse import urljoin

import httpx

from puente.config import get_settings
from puente.domain.models import MagicLink, MedicalRecordUpload


class DemoClient:
    def __init__(self) -> None:
        self.__host = self.infer_endpoint()
        self.__client = httpx.AsyncClient(base_url=self.__host, timeout=10)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.__client.aclose()

    @property
    def host(self) -> str:
        return self.__host

    @staticmethod
    def resolve_host(host: str) -> str:
        addr = ipaddress.ip_address(host)
        # For 0.0.0.0 and ::/0 bind configurations, return localhost
        if addr.is_unspecified:
            return (
                "::1"
                if isinstance(addr, ipaddress.IPv6Address)
                else "127.0.0.1"
            )
        return host

    @classmethod
    def infer_endpoint(cls) -> str:
        """Return the URL that points to the internal active API server."""
        settings = get_settings()
        host = cls.resolve_host(settings.app_host)
        return urljoin(
            f"http://{host}:{settings.app_port}/",
            settings.api_root,
        )

    async def healthcheck(self) -> None:
        """Try persistently to obtain a healthcheck from the active server."""
        source_exception = None
        for i in range(3):
            if i > 0:
                await asyncio.sleep(5)
            try:
                _ = (await self.__client.get("/health")).raise_for_status()
                return
            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.HTTPStatusError,
            ) as e:
                source_exception = e
        raise RuntimeError(
            f"Server at {self.__host} is unreachable"
        ) from source_exception

    async def run_pipeline(self, record: MedicalRecordUpload) -> MagicLink:
        """Send a medical record to the running API server."""
        response = (
            await self.__client.post(
                "/pipeline/run",
                json=record.model_dump(mode="json", by_alias=False),
            )
        ).raise_for_status()
        return MagicLink.model_validate(response.json())
