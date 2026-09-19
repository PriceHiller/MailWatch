import dataclasses


@dataclasses.dataclass(frozen=True)
class BaseError(Exception):
    message: str


class ConfigLoadError(BaseError): ...
