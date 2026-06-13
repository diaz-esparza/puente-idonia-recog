from datetime import UTC, datetime
from typing import Annotated, ClassVar

from pydantic import Base64Bytes, BaseModel, ConfigDict, Field, PlainSerializer


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
    # We need non-strict fields because we coerce from b64 strings
    report_file: Base64Bytes = Field(strict=False)
    dicom_file: Base64Bytes = Field(strict=False)


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
