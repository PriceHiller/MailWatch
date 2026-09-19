import pytest

from mailwatch.cli import EnvVars

_ALL_ENV_VARS = (EnvVars.HOST, EnvVars.PORT, EnvVars.USERNAME, EnvVars.PASSWORD)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _ALL_ENV_VARS:
        monkeypatch.delenv(var, raising=False)