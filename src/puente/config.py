from functools import lru_cache
from importlib.metadata import version
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="PUENTE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    idonia_base_url: str = "https://connect-staging.idonia.com"
    idonia_href_dicom: str = "dicom_hak_num3"
    idonia_href_report: str = "report_hak_num3"

    idonia_jwt_margin_min: int = 5
    idonia_jwt_ttl_min: int = 10

    idonia_output_url: str = "https://demo.idonia.com/v"

    # Requires instantiation from .env file
    idonia_api_key: str = Field(init=False)
    idonia_api_secret: str = Field(init=False)

    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_reload: bool = True

    humanized_suffix: str = "_HUMANIZADO"

    version: str = version(__package__) if __package__ is not None else "dev"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
