import dataclasses
from typing import Self

from mailwatch.errors import ConfigLoadError


@dataclasses.dataclass(frozen=True)
class CliArgs:
    host: str
    port: int
    username: str
    password: str


def _get_non_empty_arg(value: str, option: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ConfigLoadError(f"The value given for '{option}' must not be empty!")
    return stripped


@dataclasses.dataclass(frozen=True)
class MailBoxConfig:
    host: str
    port: int = 993

    @classmethod
    def from_args(cls, args: CliArgs) -> Self:
        return cls(
            host=_get_non_empty_arg(args.host, "--host"),
            port=args.port,
        )


@dataclasses.dataclass(frozen=True)
class LoginConfig:
    username: str
    password: str

    @classmethod
    def from_args(cls, args: CliArgs) -> Self:
        return cls(
            username=_get_non_empty_arg(args.username, "--username"),
            password=_get_non_empty_arg(args.password, "--password"),
        )


@dataclasses.dataclass(frozen=True)
class AppConfig:
    mail_box_config: MailBoxConfig
    login_config: LoginConfig

    @classmethod
    def from_args(cls, args: CliArgs) -> Self:
        return cls(
            mail_box_config=MailBoxConfig.from_args(args),
            login_config=LoginConfig.from_args(args),
        )
