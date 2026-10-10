import argparse
import dataclasses
import os
from collections.abc import Sequence
from typing import cast

from mailwatch.config import CliArgs
from mailwatch.constants import APP_NAME
from mailwatch.errors import ConfigLoadError


@dataclasses.dataclass(frozen=True, init=False)
class EnvVars:
    HOST: str = "MAILWATCH_HOST"
    PORT: str = "MAILWATCH_PORT"
    USERNAME: str = "MAILWATCH_USERNAME"
    PASSWORD: str = "MAILWATCH_PASSWORD"


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected a port number, received '{value}'"
        ) from None
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(
            f"expected a port between 1 and 65535, received '{value}'"
        )
    return port


def _env(name: str) -> str | None:
    # This will additionally coerece all falsy strings to None -- e.g. "" will return None
    return os.getenv(name) or None


def _arg_value[T](args: argparse.Namespace, name: str, expected: type[T]) -> T:
    value = cast(object, getattr(args, name))
    if not isinstance(value, expected):
        raise ConfigLoadError(
            f"Expected '{name}' to be a {expected.__name__}, received {type(value).__name__}."
        )
    return value


def parse_cli_args(argv: Sequence[str] | None = None) -> CliArgs:
    args = build_arg_parser().parse_args(argv)
    return CliArgs(
        host=_arg_value(args, "host", str),
        port=_arg_value(args, "port", int),
        username=_arg_value(args, "username", str),
        password=_arg_value(args, "password", str),
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="Watch a mailbox on a mail server and process incoming messages.",
        epilog="Each option can also be set via its environment variable; flags take precedence.",
    )

    host = _env(EnvVars.HOST)
    _ = parser.add_argument(
        "--host",
        default=host,
        required=host is None,
        help=f"mail server host (env: {EnvVars.HOST})",
    )
    _ = parser.add_argument(
        "--port",
        type=_port,
        default=_env(EnvVars.PORT) or 993,
        help=f"mail server port (default: 993, env: {EnvVars.PORT})",
    )
    username = _env(EnvVars.USERNAME)
    _ = parser.add_argument(
        "--username",
        default=username,
        required=username is None,
        help=f"login username (env: {EnvVars.USERNAME})",
    )
    password = _env(EnvVars.PASSWORD)
    _ = parser.add_argument(
        "--password",
        default=password,
        required=password is None,
        help=f"login password (env: {EnvVars.PASSWORD})",
    )
    return parser
