# pyright: reportUnknownMemberType=false

import base64
import json
import time
from typing import cast, override

import httpx
import jwt
from pydantic import ValidationError

from puente.config import get_settings
from puente.domain.models import DicomStudy, MagicLink
from puente.domain.ports import MedicalStoragePort


class IdoniaAdapter(MedicalStoragePort):
    """Async adapter for Idonia medical storage."""

    def __init__(self) -> None:
        settings = get_settings()

        self.__client = httpx.AsyncClient(
            base_url=settings.idonia_base_url.removeprefix("/"),
            timeout=60.0,
        )

        self.__href_dicom = settings.idonia_href_dicom
        self.__href_report = settings.idonia_href_report

        self.__api_key = settings.idonia_api_key
        self.__api_secret = self._decode_secret(settings.idonia_api_secret)

        self.__jwt_margin_min = settings.idonia_jwt_margin_min
        self.__jwt_ttl_min = settings.idonia_jwt_ttl_min
        self.__jwt_cache_token: str | None = None
        self.__jwt_cache_expiry: int = 0

    def _decode_secret(self, secret: str) -> bytes:
        return base64.urlsafe_b64decode(secret.removeprefix("S2"))

    def _create_jwt(self) -> str:
        """Generate JWT for Idonia auth, save cache."""
        now = int(time.time())
        payload = {
            "sub": self.__api_key,
            "iat": now - self.__jwt_margin_min * 60,
            "exp": now + self.__jwt_ttl_min * 60,
        }
        token: str = jwt.encode(payload, self.__api_secret, algorithm="HS256")
        self.__jwt_cache_token = token
        self.__jwt_cache_expiry = now + (self.__jwt_ttl_min * 60) // 2
        return token

    def _get_jwt(self) -> str:
        """Check for JWT in cache, generate if expired or missing."""
        cached_token = self.__jwt_cache_token
        if (
            self.__jwt_cache_expiry > int(time.time())
            and cached_token is not None
        ):
            return cached_token
        return self._create_jwt()

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._get_jwt()}"}

    async def _upload_file(
        self,
        study: DicomStudy,
        content: bytes,
        path: str,
    ) -> str:
        """Interacts with the '/files/' upload API, return file id."""
        # Careful: httpx distinguishes between file and data transfers
        response = (
            await self.__client.post(
                f"files/{path.removeprefix('/')}",
                files={"file": content},
                data=study.model_dump(),
                headers=self._auth_headers(),
            )
        ).raise_for_status()
        data = cast(object, response.json())
        if (
            response.status_code in (200, 201)
            and isinstance(data, list)
            and len(data := cast(list[object], data)) == 1
        ):
            return str(data[0])
        raise RuntimeError(f"Unexpected Idonia file upload response: {data}")

    @override
    async def upload_dicom(self, study: DicomStudy, content: bytes) -> str:
        return await self._upload_file(study, content, self.__href_dicom)

    @override
    async def upload_report(self, study: DicomStudy, content: bytes) -> str:
        return await self._upload_file(study, content, self.__href_report)

    def _get_container_route(self, study: DicomStudy) -> str:
        """Build container route according to specifications."""
        return "/".join([study.patient_id, study.accession_number])

    @override
    async def create_magic_link(self, study: DicomStudy) -> MagicLink:
        params = {
            "route": self._get_container_route(study),
            # TODO feature: Add password protection
            "password": "",
            "expired_creation_mode": "create",
        }
        response = (
            await self.__client.put(
                "/ml",
                params=params,
                headers=self._auth_headers(),
            )
        ).raise_for_status()
        data = await response.aread()
        try:
            parsed = cast(object, json.loads(data))
            if isinstance(parsed, list):
                items = cast(list[object], parsed)
                n_items = len(items)
                if n_items == 1:
                    return MagicLink.model_validate(items[0])
                raise RuntimeError(f"Expected array of 1 item, got {n_items}")
            raise RuntimeError(f"Expected a list, got {parsed.__class__}")

        except (ValidationError, json.JSONDecodeError, RuntimeError) as e:
            raise RuntimeError(
                f"Unexpected Idonia magic link response: {data.decode()}"
            ) from e
