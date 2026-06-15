import base64
import time
from hashlib import sha256
from typing import cast, override

import httpx
import jwt
import orjson
from opentelemetry import trace
from pydantic import SecretBytes, SecretStr, ValidationError

from puente.config import get_settings
from puente.domain.models import DicomStudy, MagicLink
from puente.domain.ports import MedicalStoragePort
from puente.telemetry.getters import get_logger
from puente.telemetry.timer import Timer

_logger = get_logger(__name__)
_tracer = trace.get_tracer(__name__)


class IdoniaAdapter(MedicalStoragePort):
    """Async adapter for Idonia medical storage."""

    def __init__(self) -> None:
        settings = get_settings()

        self.__client = httpx.AsyncClient(
            base_url=settings.idonia_base_url.rstrip("/"),
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

    def _decode_secret(self, secret: SecretStr) -> SecretBytes:
        prefix = "S2"
        decoded_secret = secret.get_secret_value()
        if not decoded_secret.startswith(prefix):
            raise ValueError(f"API secret must start with '{prefix}' prefix.")
        return SecretBytes(
            base64.urlsafe_b64decode(decoded_secret.removeprefix(prefix))
        )

    def _create_jwt(self) -> str:
        """Generate JWT for Idonia auth, save cache."""
        _logger.debug("jwt_creation")
        now = int(time.time())
        payload = {
            "sub": self.__api_key.get_secret_value(),
            "iat": now - self.__jwt_margin_min * 60,
            "exp": now + self.__jwt_ttl_min * 60,
        }
        token: str = jwt.encode(
            payload,
            self.__api_secret.get_secret_value(),
            algorithm="HS256",
        )
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
        href = f"files/{path.removeprefix('/')}"
        with Timer() as timer:
            response = (
                await self.__client.post(
                    href,
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
            file_id = str(data[0])
            _logger.info(
                "idonia_uploaded",
                href=href,
                file_size=len(content),
                file_id=file_id,
                endpoint_duration_ms=timer.duration_ms,
            )
            return file_id
        raise RuntimeError(f"Unexpected Idonia file upload response: {data}")

    @override
    async def upload_dicom(self, study: DicomStudy, content: bytes) -> str:
        with _tracer.start_as_current_span("phase_ingest_dicom"):
            return await self._upload_file(study, content, self.__href_dicom)

    @override
    async def upload_report(self, study: DicomStudy, content: bytes) -> str:
        with _tracer.start_as_current_span("phase_ingest_report"):
            return await self._upload_file(study, content, self.__href_report)

    def _get_container_route(self, study: DicomStudy) -> str:
        """Build container route according to specifications."""
        return "/".join([study.patient_id, study.accession_number])

    @staticmethod
    def _serialize_password(password: SecretStr | None) -> str:
        """Hash a magic-link password the way Idonia expects.

        Idonia requires the lowercase hexadecimal digest of the
        SHA256 of the plain password, encoded as base64.

        An empty string is sent when no password is configured.
        """
        if password is None:
            return ""
        hash_hex = sha256(password.get_secret_value().encode()).hexdigest()
        return base64.b64encode(hash_hex.encode()).decode()

    @override
    async def create_magic_link(
        self,
        study: DicomStudy,
        password: SecretStr | None,
    ) -> MagicLink:
        route = self._get_container_route(study)
        params = {
            "route": route,
            "password": self._serialize_password(password),
            "expired_creation_mode": "create",
        }
        with Timer() as timer:
            response = (
                await self.__client.put(
                    "/ml",
                    params=params,
                    headers=self._auth_headers(),
                )
            ).raise_for_status()
            data = await response.aread()
        try:
            parsed = cast(object, orjson.loads(data))
            if isinstance(parsed, list):
                items = cast(list[object], parsed)
                n_items = len(items)
                if n_items == 1:
                    magic = MagicLink.model_validate(items[0])
                    _logger.info(
                        "idonia_magic_link_created",
                        route=route,
                        url_length=len(magic.url),
                        endpoint_duration_ms=timer.duration_ms,
                    )
                    return magic
                raise RuntimeError(f"Expected array of 1 item, got {n_items}")
            raise RuntimeError(f"Expected a list, got {parsed.__class__}")

        except (ValidationError, orjson.JSONDecodeError, RuntimeError) as e:
            raise RuntimeError(
                f"Unexpected Idonia magic link response: {data.decode()}"
            ) from e
