import signal
from collections.abc import Callable, Sequence
from types import FrameType
from typing import cast

import pytest

from mailwatch.config import LoginConfig, MailBoxConfig
from mailwatch.errors import ShutdownRequested
from mailwatch.main import install_signal_handlers, main
from mailwatch.rules import DEFAULT_RULES, Rule


def test_install_signal_handlers_requests_shutdown() -> None:
    originals = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        install_signal_handlers()
        handler = cast(
            "Callable[[int, FrameType | None], object]",
            signal.getsignal(signal.SIGTERM),
        )
        with pytest.raises(ShutdownRequested):
            _ = handler(signal.SIGTERM, None)
    finally:
        for sig, original in originals.items():
            _ = signal.signal(sig, original)


def _noop(*_args: object, **_kwargs: object) -> None: ...


class _FakeIdle:
    def start(self) -> None: ...

    def stop(self) -> None: ...

    def poll(self, timeout: float) -> list[bytes]:
        _ = timeout
        raise ShutdownRequested


class _FakeMailBox:
    closed: bool = False

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.host: str = host
        self.port: int = port
        self.timeout = timeout

    def login(self, **_kwargs: object) -> "_FakeMailBox":
        return self

    def logout(self) -> None:
        type(self).closed = True

    def fetch(self, _criteria: object) -> list[object]:
        return []

    @property
    def idle(self) -> _FakeIdle:
        return _FakeIdle()


def test_main_shuts_down_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeMailBox.closed = False
    monkeypatch.setattr("mailwatch.main.configure_logging", _noop)
    monkeypatch.setattr("mailwatch.main.install_signal_handlers", _noop)
    monkeypatch.setattr("mailwatch.handler.handler.MailBox", _FakeMailBox)

    assert main(["--host", "h", "--username", "u", "--password", "p"]) == 0
    assert _FakeMailBox.closed


def test_main_passes_default_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[Sequence[Rule]] = []

    def spy(
        mailbox_config: MailBoxConfig,
        login_config: LoginConfig,
        rules: Sequence[Rule],
    ) -> None:
        assert mailbox_config == MailBoxConfig(host="h", port=993)
        assert login_config == LoginConfig(username="u", password="p")
        captured.append(rules)

    monkeypatch.setattr("mailwatch.main.configure_logging", _noop)
    monkeypatch.setattr("mailwatch.main.install_signal_handlers", _noop)
    monkeypatch.setattr("mailwatch.main.handle_mailbox", spy)

    assert main(["--host", "h", "--username", "u", "--password", "p"]) == 0
    assert captured == [DEFAULT_RULES]
