import signal
from collections.abc import Callable
from types import FrameType
from typing import cast

import pytest

from mailwatch.errors import ShutdownRequested
from mailwatch.main import install_signal_handlers, main


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
    def wait(self, timeout: int) -> list[bytes]:
        _ = timeout
        raise ShutdownRequested


class _FakeMailBox:
    closed: bool = False

    def __init__(self, host: str, port: int) -> None:
        self.host: str = host
        self.port: int = port

    def login(self, **_kwargs: object) -> "_FakeMailBox":
        return self

    def __enter__(self) -> "_FakeMailBox":
        return self

    def __exit__(self, *_exc: object) -> bool:
        type(self).closed = True
        return False

    @property
    def idle(self) -> _FakeIdle:
        return _FakeIdle()


def test_main_shuts_down_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeMailBox.closed = False
    monkeypatch.setattr("mailwatch.main.configure_logging", _noop)
    monkeypatch.setattr("mailwatch.main.install_signal_handlers", _noop)
    monkeypatch.setattr("mailwatch.main.MailBox", _FakeMailBox)

    assert main(["--host", "h", "--username", "u", "--password", "p"]) == 0
    assert _FakeMailBox.closed
