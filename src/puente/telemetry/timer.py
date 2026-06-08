from time import perf_counter_ns
from typing import Self


class Timer:
    def __init__(
        self,
    ) -> None:
        self.__elapsed_ns: int | None = None
        self.__start_ns: int | None = None

    def start(self) -> Self:
        self.__start_ns = perf_counter_ns()
        return self

    def stop(self) -> None:
        if self.__start_ns is None:
            raise RuntimeError("Timer not started")
        self.__elapsed_ns = perf_counter_ns() - self.__start_ns

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        self.stop()

    @property
    def duration_ms(self) -> int:
        if self.__elapsed_ns is None:
            raise RuntimeError("Timer not stopped")
        return self.__elapsed_ns // 1_000
