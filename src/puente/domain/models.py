import base64
from datetime import UTC, datetime
from typing import Annotated, ClassVar

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    SecretStr,
    field_validator,
)


def _parse_bytes_or_b64(data: bytes | str) -> bytes:
    if isinstance(data, bytes):
        return data
    return base64.b64decode(data)


type BytesOrBase64 = Annotated[
    bytes,
    BeforeValidator(_parse_bytes_or_b64),
    PlainSerializer(base64.b64encode),
]


class StrictModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        validate_default=True,
        serialize_by_alias=True,
    )


class DicomStudy(StrictModel):
    """DICOM study metadata used for routing.

    Used both in the input data of our service, and on this service's
    communication to Idonia's storage.
    """

    patient_id: str = Field(serialization_alias="DICOMPatientID")
    accession_number: str = Field(serialization_alias="DICOMAccessionNumber")
    study_description: str = Field(serialization_alias="DICOMStudyDescription")


class MedicalRecordUpload(StrictModel):
    """Aggregate root representing the complete patient upload data."""

    study: DicomStudy
    report_file: BytesOrBase64
    dicom_zip: BytesOrBase64
    password: SecretStr | None = None

    @field_validator("password", mode="after")
    @classmethod
    def _nullify_empty_password(
        cls, value: SecretStr | None
    ) -> SecretStr | None:
        return value or None


class MagicLink(StrictModel):
    """Secure shareable link as a successful result of the upload."""

    url: str = Field(alias="URL")
    pin: str = Field(alias="PIN")


class AuditChain(StrictModel):
    sequence: int
    previous_chain_hash: bytes | None
    previous_tsr_hash: bytes | None
    bucket_hash: bytes

    ts: Annotated[datetime, PlainSerializer(datetime.isoformat)] = Field(
        default_factory=lambda: datetime.now(UTC),
        strict=False,  # To parse from ISO strings
    )
    version: int = 1


class AuditRecord(StrictModel):
    chain_cbor: bytes
    signature: bytes
    tsr: bytes | None
    bucket_zstd: bytes
