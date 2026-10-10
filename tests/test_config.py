import dataclasses

import pytest

from mailwatch.cli import EnvVars, parse_cli_args
from mailwatch.config import AppConfig, CliArgs, LoginConfig, MailBoxConfig
from mailwatch.errors import ConfigLoadError

_BASE_ARGS = CliArgs(
    host="imap.example.com", port=993, username="user", password="secret"
)


def _set_env(monkeypatch: pytest.MonkeyPatch, values: dict[str, str]) -> None:
    for var, value in values.items():
        monkeypatch.setenv(var, value)


_SPACED_ENV = {
    EnvVars.HOST: " env.example.com ",
    EnvVars.PORT: "143",
    EnvVars.USERNAME: " env-user ",
    EnvVars.PASSWORD: " env-pass ",
}


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        pytest.param(
            _BASE_ARGS,
            AppConfig(
                mail_box_config=MailBoxConfig(host="imap.example.com", port=993),
                login_config=LoginConfig(username="user", password="secret"),
            ),
            id="baseline",
        ),
        pytest.param(
            dataclasses.replace(
                _BASE_ARGS,
                host="  imap.example.com  ",
                username=" user ",
                password=" secret ",
            ),
            AppConfig(
                mail_box_config=MailBoxConfig(host="imap.example.com", port=993),
                login_config=LoginConfig(username="user", password="secret"),
            ),
            id="surrounding-whitespace-is-stripped",
        ),
        pytest.param(
            dataclasses.replace(_BASE_ARGS, port=143),
            AppConfig(
                mail_box_config=MailBoxConfig(host="imap.example.com", port=143),
                login_config=LoginConfig(username="user", password="secret"),
            ),
            id="custom-port-is-accepted",
        ),
    ],
)
def test_from_args_builds_app_config(args: CliArgs, expected: AppConfig) -> None:
    assert AppConfig.from_args(args) == expected


@pytest.mark.parametrize(
    ("args", "expected_option"),
    [
        pytest.param(
            dataclasses.replace(_BASE_ARGS, host=""), "--host", id="blank-host"
        ),
        pytest.param(
            dataclasses.replace(_BASE_ARGS, host="   "), "--host", id="spaced-host"
        ),
        pytest.param(
            dataclasses.replace(_BASE_ARGS, username=""),
            "--username",
            id="blank-username",
        ),
        pytest.param(
            dataclasses.replace(_BASE_ARGS, username="   "),
            "--username",
            id="spaced-username",
        ),
        pytest.param(
            dataclasses.replace(_BASE_ARGS, password=""),
            "--password",
            id="blank-password",
        ),
        pytest.param(
            dataclasses.replace(_BASE_ARGS, password="   "),
            "--password",
            id="spaced-password",
        ),
    ],
)
def test_from_args_rejects_blank_values(args: CliArgs, expected_option: str) -> None:
    with pytest.raises(ConfigLoadError) as excinfo:
        _ = AppConfig.from_args(args)

    assert expected_option in excinfo.value.message


@pytest.mark.parametrize(
    ("env", "argv", "expected"),
    [
        pytest.param(
            _SPACED_ENV,
            [],
            AppConfig(
                mail_box_config=MailBoxConfig(host="env.example.com", port=143),
                login_config=LoginConfig(username="env-user", password="env-pass"),
            ),
            id="env-values-flow-into-app-config",
        ),
        pytest.param(
            _SPACED_ENV,
            [
                "--host",
                "flag.example.com",
                "--username",
                "flag-user",
                "--password",
                "flag-pass",
            ],
            AppConfig(
                mail_box_config=MailBoxConfig(host="flag.example.com", port=143),
                login_config=LoginConfig(username="flag-user", password="flag-pass"),
            ),
            id="flags-take-precedence-over-env-vars",
        ),
    ],
)
def test_config_is_built_from_environment(
    env: dict[str, str],
    argv: list[str],
    expected: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch, env)

    assert AppConfig.from_args(parse_cli_args(argv)) == expected


@pytest.mark.parametrize(
    ("env", "expected_error"),
    [
        pytest.param(
            {EnvVars.HOST: "   ", EnvVars.USERNAME: "u", EnvVars.PASSWORD: "p"},
            "--host",
            id="blank-env-host-is-rejected",
        ),
        pytest.param(
            {
                EnvVars.HOST: "env.example.com",
                EnvVars.USERNAME: "   ",
                EnvVars.PASSWORD: "p",
            },
            "--username",
            id="blank-env-username-is-rejected",
        ),
        pytest.param(
            {
                EnvVars.HOST: "env.example.com",
                EnvVars.USERNAME: "u",
                EnvVars.PASSWORD: "   ",
            },
            "--password",
            id="blank-env-password-is-rejected",
        ),
    ],
)
def test_blank_env_values_are_rejected(
    env: dict[str, str],
    expected_error: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch, env)

    with pytest.raises(ConfigLoadError) as excinfo:
        _ = AppConfig.from_args(parse_cli_args([]))

    assert expected_error in excinfo.value.message
