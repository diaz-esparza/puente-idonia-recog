"""Shared HTTP mock façades for offline testing."""

from typing import Any

import orjson
import respx


class IdoniaMock:
    """Convenient façade over ``respx`` routes for the Idonia staging API."""

    def __init__(self, router: respx.MockRouter, base_url: str) -> None:
        self.__base = base_url.rstrip("/")
        self.__dicom_route = router.post(
            f"{self.__base}/files/dicom_hak_num3",
            name="idonia_dicom",
        ).respond(200, json=["dicom-file-id"])
        self.__report_route = router.post(
            f"{self.__base}/files/report_hak_num3",
            name="idonia_report",
        ).respond(200, json=["report-file-id"])
        self.__magic_put_route = router.put(
            f"{self.__base}/ml",
            name="idonia_magic",
        ).respond(200, json=[{"URL": "https://magic.test/123", "PIN": "5678"}])

    def assert_dicom_uploaded(self, *, times: int = 1) -> None:
        assert self.__dicom_route.call_count == times, (
            f"Expected DICOM upload {times} time(s), "
            f"got {self.__dicom_route.call_count}"
        )

    def assert_report_uploaded(self, *, times: int = 1) -> None:
        assert self.__report_route.call_count == times, (
            f"Expected report upload {times} time(s), "
            f"got {self.__report_route.call_count}"
        )

    def assert_magic_link_created(self) -> None:
        assert self.__magic_put_route.called, (
            "Magic link creation was not requested"
        )

    def respond_dicom_error(self, status: int) -> None:
        """Replace the DICOM route response with an error."""
        _ = self.__dicom_route.respond(status)

    def respond_report_error(self, status: int) -> None:
        """Replace the report route response with an error."""
        _ = self.__report_route.respond(status)


class RecogMock:
    """Convenient façade over ``respx`` routes for the Recog AI API."""

    def __init__(self, router: respx.MockRouter, url: str) -> None:
        self.__url = url
        self.__route = router.post(self.__url, name="recog_humanize")

    def respond_with_pdf(self, pdf_bytes: bytes) -> None:
        _ = self.__route.respond(200, content=pdf_bytes)

    def respond_with_error(self, status: int) -> None:
        """Replace the Recog route response with an error status."""
        _ = self.__route.respond(status)

    def assert_humanization_requested(self) -> None:
        assert self.__route.called, "Recog humanization was not requested"

    def latest_request_body(self) -> dict[str, Any]:
        self.assert_humanization_requested()
        request = self.__route.calls.last.request
        return orjson.loads(request.content)
