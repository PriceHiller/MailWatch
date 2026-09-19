import dataclasses


@dataclasses.dataclass(frozen=True)
class BaseError(Exception):
    message: str


class ConfigLoadError(BaseError): ...


class ShutdownRequested(Exception):
    """Raised from a signal handler to unwind the watch loop gracefully."""
