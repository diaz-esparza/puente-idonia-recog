import ipaddress
import socket
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, ClassVar, Self

from pydantic import (
    AfterValidator,
    Field,
    FilePath,
    HttpUrl,
    PositiveInt,
    SecretStr,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).parent.parent.parent


def _validate_http_url(url: str) -> str:
    return HttpUrl(url).unicode_string().rstrip("/")


type _HttpUrlStr = Annotated[str, AfterValidator(_validate_http_url)]
type _UpperCaseStr = Annotated[str, StringConstraints(to_upper=True)]


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="PUENTE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    idonia_base_url: _HttpUrlStr = "https://connect-staging.idonia.com"
    idonia_href_dicom: str = "dicom_hak_num3"
    idonia_href_report: str = "report_hak_num3"
    idonia_jwt_margin_min: PositiveInt = 5
    idonia_jwt_ttl_min: PositiveInt = 10
    idonia_output_url: _HttpUrlStr = "https://demo.idonia.com/v"
    # Requires instantiation from .env file
    idonia_api_key: SecretStr = Field(init=False)
    idonia_api_secret: SecretStr = Field(init=False)

    recog_url: _HttpUrlStr = (
        "https://api.recog.es/relisten/dictation/process/report-results"
    )
    recog_timeout_s: PositiveInt = 60
    recog_api_key: SecretStr = SecretStr("")

    humanized_suffix: str = "_HUMANIZADO"
    humanized_mock: bool = True

    presidio_mock: bool = False
    presidio_config_file: FilePath = (
        _PROJECT_ROOT / "config" / "presidio-analyzer.yaml"
    )
    presidio_anonymizer_operator: str = "replace"

    otel_service_name: str = "PUENTE"
    otel_environment: str = "dev"
    otel_log_level: _UpperCaseStr = "INFO"
    otel_endpoint: str | None = None
    otel_connect_insecurely: bool = False

    audit_sqlite_file: Path = _PROJECT_ROOT / ".runtime" / "audit.db"
    audit_public_key_file: Path = (
        _PROJECT_ROOT / ".runtime" / "signing_key.pub"
    )
    audit_private_key_file: Path = (
        _PROJECT_ROOT / ".private" / "signing_key.pem"
    )
    audit_private_key_password: bytes | None = None
    audit_tsa_url: _HttpUrlStr = "https://freetsa.org/tsr"
    audit_flush_interval_s: PositiveInt = 300
    audit_app_host: str = "127.0.0.1"
    audit_app_port: int = Field(default=8001, gt=0, le=65535)

    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8000, gt=0, le=65535)

    api_root: str = "/v1"
    version: str = version(__package__) if __package__ is not None else "dev"

    @property
    def humanized_provider(self) -> str:
        return "Recog AI" if not self.humanized_mock else "Mock local"

    @property
    def presidio_provider(self) -> str:
        return (
            "Microsoft Presidio"
            if not self.presidio_mock
            else "Mock local (sin anonimización)"
        )

    @model_validator(mode="after")
    def validate_recog_config(self) -> Self:
        if not self.humanized_mock and not self.recog_api_key:
            prefix = self.model_config.get("env_prefix", "")
            raise ValueError(
                f"{prefix}RECOG_API_KEY is required when "
                + f"{prefix}HUMANIZED_MOCK is false",
            )
        return self

    @field_validator("app_host", "audit_app_host", mode="after")
    @classmethod
    def normalize_app_host(cls, v: str, info: ValidationInfo) -> str:
        try:
            _ = ipaddress.ip_address(v)
            return v
        except ValueError:
            pass
        for family in (socket.AF_INET, socket.AF_INET6):
            try:
                addrs = socket.getaddrinfo(v, None, family=family)
            except socket.gaierror:
                continue
            host = addrs[0][4][0]
            if isinstance(host, str):
                return host
        prefix = cls.model_config.get("env_prefix", "")
        field_name = info.field_name.upper() if info.field_name else "APP_HOST"
        raise ValueError(
            f"{prefix}{field_name} must be a valid IP or resolvable hostname, "
            + f"got: '{v}'"
        ) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
