import argparse

import pytest

from mailwatch.cli import EnvVars, build_arg_parser, parse_cli_args
from mailwatch.config import CliArgs
from mailwatch.errors import ConfigLoadError


def _parse(argv: list[str]) -> argparse.Namespace:
    return build_arg_parser().parse_args(argv)


def _set_env(monkeypatch: pytest.MonkeyPatch, values: dict[str, str]) -> None:
    for var, value in values.items():
        monkeypatch.setenv(var, value)


_FULL_FLAGS = [
    "--host",
    "flag.example.com",
    "--port",
    "143",
    "--username",
    "flag-user",
    "--password",
    "flag-pass",
]

_FULL_ENV = {
    EnvVars.HOST: "env.example.com",
    EnvVars.PORT: "143",
    EnvVars.USERNAME: "env-user",
    EnvVars.PASSWORD: "env-pass",
}

_BASELINE_FLAGS = ["--host", "h", "--username", "u", "--password", "p"]


@pytest.mark.parametrize(
    ("argv", "env", "expected"),
    [
        pytest.param(
            _FULL_FLAGS,
            {},
            argparse.Namespace(
                host="flag.example.com",
                port=143,
                username="flag-user",
                password="flag-pass",
            ),
            id="flags-provide-all-values",
        ),
        pytest.param(
            [],
            _FULL_ENV,
            argparse.Namespace(
                host="env.example.com",
                port=143,
                username="env-user",
                password="env-pass",
            ),
            id="env-vars-provide-all-values",
        ),
        pytest.param(
            _FULL_FLAGS,
            _FULL_ENV,
            argparse.Namespace(
                host="flag.example.com",
                port=143,
                username="flag-user",
                password="flag-pass",
            ),
            id="flags-take-precedence-over-env-vars",
        ),
        pytest.param(
            ["--username", "flag-user"],
            {EnvVars.HOST: "env.example.com", EnvVars.PASSWORD: "env-pass"},
            argparse.Namespace(
                host="env.example.com",
                port=993,
                username="flag-user",
                password="env-pass",
            ),
            id="flags-and-env-vars-can-be-mixed",
        ),
        pytest.param(
            _BASELINE_FLAGS,
            {},
            argparse.Namespace(host="h", port=993, username="u", password="p"),
            id="port-defaults-to-993-when-absent",
        ),
        pytest.param(
            _BASELINE_FLAGS + ["--port", "143"],
            {EnvVars.PORT: "abc"},
            argparse.Namespace(host="h", port=143, username="u", password="p"),
            id="invalid-env-port-ignored-when-flag-is-given",
        ),
    ],
)
def test_values_are_resolved(
    argv: list[str],
    env: dict[str, str],
    expected: argparse.Namespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch, env)

    assert _parse(argv) == expected


@pytest.mark.parametrize(
    ("argv", "env", "expected_error"),
    [
        pytest.param(
            [],
            {},
            "the following arguments are required: --host, --username, --password",
            id="missing-values-are-required",
        ),
        pytest.param(
            ["--username", "u", "--password", "p"],
            {EnvVars.HOST: ""},
            "--host",
            id="empty-env-var-counts-as-unset",
        ),
        pytest.param(
            _BASELINE_FLAGS + ["--port", "abc"],
            {},
            "--port",
            id="invalid-flag-port-is-not-a-number",
        ),
        pytest.param(
            _BASELINE_FLAGS + ["--port", "0"],
            {},
            "--port",
            id="invalid-flag-port-is-below-range",
        ),
        pytest.param(
            _BASELINE_FLAGS + ["--port", "70000"],
            {},
            "--port",
            id="invalid-flag-port-is-above-range",
        ),
        pytest.param(
            _BASELINE_FLAGS + ["--port", ""],
            {},
            "--port",
            id="invalid-flag-port-is-empty",
        ),
        pytest.param(
            [],
            _FULL_ENV | {EnvVars.PORT: "abc"},
            "--port",
            id="invalid-env-port-is-not-a-number",
        ),
        pytest.param(
            [],
            _FULL_ENV | {EnvVars.PORT: "0"},
            "--port",
            id="invalid-env-port-is-below-range",
        ),
        pytest.param(
            [],
            _FULL_ENV | {EnvVars.PORT: "70000"},
            "--port",
            id="invalid-env-port-is-above-range",
        ),
    ],
)
def test_invalid_values_are_rejected(
    argv: list[str],
    env: dict[str, str],
    expected_error: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _set_env(monkeypatch, env)

    with pytest.raises(SystemExit) as excinfo:
        _ = _parse(argv)

    assert excinfo.value.code == 2
    assert expected_error in capsys.readouterr().err


def test_parse_cli_args_returns_typed_args(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch, _FULL_ENV)

    assert parse_cli_args([]) == CliArgs(
        host="env.example.com", port=143, username="env-user", password="env-pass"
    )


def test_parse_cli_args_rejects_mistyped_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--host", type=int, default=1)
    _ = parser.add_argument("--port", type=int, default=993)
    _ = parser.add_argument("--username", default="u")
    _ = parser.add_argument("--password", default="p")
    monkeypatch.setattr("mailwatch.cli.build_arg_parser", lambda: parser)

    with pytest.raises(ConfigLoadError) as excinfo:
        _ = parse_cli_args([])

    assert "host" in excinfo.value.message
