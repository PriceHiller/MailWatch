import datetime
import imaplib
import logging
from collections.abc import Sequence
from types import SimpleNamespace
from typing import cast, final, override

import pytest
from imap_tools.errors import (
    MailboxFetchError,
    MailboxLoginError,
    MailboxTaggedResponseError,
)

from mailwatch.config import LoginConfig, MailBoxConfig
from mailwatch.errors import ShutdownRequested
from mailwatch.handler import handle_mailbox
from mailwatch.handler import handler as handler_module
from mailwatch.handler.handler import format_size_bytes
from mailwatch.rules import MessageContext, Rule, RuleResult


class _Stop(Exception): ...


@final
class _FakeIdle:
    def __init__(self, responses: list[bytes]) -> None:
        self._responses = responses
        self.waits = 0

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def poll(self, timeout: float) -> list[bytes]:
        _ = timeout
        self.waits += 1
        if self.waits > 1:
            raise _Stop
        return self._responses


@final
class _FakeMessage:
    def __init__(
        self,
        subject: str,
        uid: str | None,
        to: tuple[str, ...] = ("test@example.com",),
        size: int = 0,
    ) -> None:
        self.subject = subject
        self.uid = uid
        self.to = to
        self.size = size
        self.date = datetime.datetime(2026, 9, 19, 12, 0)


@final
class _FakeMailBox:
    def __init__(self, messages: list[_FakeMessage]) -> None:
        self._messages = messages
        self.idle = _FakeIdle([b"* 1 EXISTS"])
        self.login_args: tuple[str, str, str | None] | None = None
        self.closed = False
        self.fetches = 0

    def login(
        self, username: str, password: str, initial_folder: str | None = None
    ) -> "_FakeMailBox":
        assert self.login_args is None, "Cannot log in twice on the same connection"
        assert not self.closed, "Cannot reuse a closed connection"
        self.login_args = (username, password, initial_folder)
        return self

    def logout(self) -> None:
        self.closed = True

    def fetch(self, criteria: object) -> list[_FakeMessage]:
        _ = criteria
        self.fetches += 1
        messages, self._messages = self._messages, []
        return messages


@final
class _RecordingRule(Rule):
    def __init__(self, label: str, result: RuleResult, calls: list[str]) -> None:
        self.label = label
        self.result = result
        self.calls = calls

    @override
    def handle(self, context: MessageContext) -> RuleResult:
        _ = context
        self.calls.append(self.label)
        return self.result


@final
class _RaisingRule(Rule):
    @override
    def handle(self, context: MessageContext) -> RuleResult:
        _ = context
        raise RuntimeError("boom")


def _run(mailbox: _FakeMailBox, rules: Sequence[Rule]) -> None:
    with pytest.MonkeyPatch.context() as patch, pytest.raises(_Stop):
        patch.setattr("mailwatch.handler.handler.MailBox", lambda **_kwargs: mailbox)
        handle_mailbox(
            MailBoxConfig(host="h"),
            LoginConfig(username="u", password="p"),
            rules,
        )


def test_handle_mailbox_logs_in_to_inbox() -> None:
    mailbox = _FakeMailBox([])

    _run(mailbox, [])

    assert mailbox.login_args == ("u", "p", "INBOX")
    assert mailbox.closed


def test_handle_mailbox_runs_rules_in_order() -> None:
    calls: list[str] = []
    mailbox = _FakeMailBox([_FakeMessage("Hello", "1")])
    rules = [
        _RecordingRule("first", RuleResult.CONTINUE, calls),
        _RecordingRule("second", RuleResult.CONTINUE, calls),
    ]

    _run(mailbox, rules)

    assert calls == ["first", "second"]


def test_handle_mailbox_stops_after_stop_result() -> None:
    calls: list[str] = []
    mailbox = _FakeMailBox([_FakeMessage("Hello", "1")])
    rules = [
        _RecordingRule("stop", RuleResult.STOP, calls),
        _RecordingRule("after", RuleResult.CONTINUE, calls),
    ]

    _run(mailbox, rules)

    assert calls == ["stop"]


def test_handle_mailbox_logs_rule_failure_and_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[str] = []
    mailbox = _FakeMailBox([_FakeMessage("Hello", "1")])
    rules = [_RaisingRule(), _RecordingRule("after", RuleResult.CONTINUE, calls)]

    with caplog.at_level(logging.ERROR):
        _run(mailbox, rules)

    assert calls == ["after"]
    record = next(r for r in caplog.records if r.getMessage() == "Rule failed")
    logged = cast("dict[str, object]", getattr(record, "context", None))
    assert logged["rule"] == "_RaisingRule"
    assert logged["uid"] == "1"


def test_handle_mailbox_logs_message_context(caplog: pytest.LogCaptureFixture) -> None:
    mailbox = _FakeMailBox(
        [_FakeMessage("Hello World", "43", to=("dest@example.com",), size=2048)]
    )

    with caplog.at_level("INFO"):
        _run(mailbox, [])

    record = next(r for r in caplog.records if r.getMessage() == "Received message")
    logged = cast("dict[str, object]", getattr(record, "context", None))
    assert logged["uid"] == "43"
    assert logged["to"] == ("dest@example.com",)
    assert logged["size"] == "2.00 KB"


def test_handle_mailbox_fetches_after_empty_idle_timeout() -> None:
    mailbox = _FakeMailBox([])
    mailbox.idle = _FakeIdle([])

    _run(mailbox, [])

    assert mailbox.fetches == 2  # Once on login, once after the timeout.


def test_handle_mailbox_processes_backlog_before_idle() -> None:
    mailbox = _FakeMailBox([_FakeMessage("Backlog", "1")])
    calls: list[str] = []
    rule = _RecordingRule("backlog", RuleResult.CONTINUE, calls)

    def poll(timeout: float) -> list[bytes]:
        assert calls == ["backlog"]
        raise _Stop

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(mailbox.idle, "poll", poll)
        _run(mailbox, [rule])


@pytest.mark.parametrize(
    "phase", ["construct", "login", "idle_start", "idle", "idle_stop", "fetch"]
)
@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("timed out"),
        ConnectionResetError("reset"),
        OSError("transport failure"),
        imaplib.IMAP4.abort("disconnected"),
        MailboxLoginError(("NO", [b"unavailable"]), "OK"),
        MailboxFetchError(("NO", [b"unavailable"]), "OK"),
        MailboxTaggedResponseError(("NO", [b"unavailable"]), "OK"),
    ],
)
def test_handle_mailbox_reconnects_with_new_client(
    monkeypatch: pytest.MonkeyPatch, phase: str, error: Exception
) -> None:
    first = _FakeMailBox([])
    second = _FakeMailBox([])
    attempts: list[dict[str, object]] = []
    sleeps: list[int] = []

    def fail(*_args: object, **_kwargs: object) -> None:
        raise error

    if phase == "login":
        monkeypatch.setattr(first, "login", fail)
    elif phase == "idle":
        monkeypatch.setattr(first.idle, "poll", fail)
    elif phase == "idle_start":
        monkeypatch.setattr(first.idle, "start", fail)
    elif phase == "idle_stop":
        monkeypatch.setattr(first.idle, "stop", fail)
    elif phase == "fetch":
        monkeypatch.setattr(first, "fetch", fail)

    def factory(**kwargs: object) -> _FakeMailBox:
        attempts.append(kwargs)
        if len(attempts) == 1:
            if phase == "construct":
                raise error
            return first
        assert len(attempts) == 2
        return second

    monkeypatch.setattr(handler_module, "MailBox", factory)
    monkeypatch.setattr(handler_module.time, "sleep", sleeps.append)

    with pytest.raises(_Stop):
        handle_mailbox(MailBoxConfig(host="h", port=123), LoginConfig("u", "p"), [])

    assert attempts == [{"host": "h", "port": 123, "timeout": 60}] * 2
    assert sleeps == [30]
    assert first.closed == (phase != "construct")
    assert second.closed


def test_handle_mailbox_refreshes_connection_at_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _FakeMailBox([])
    second = _FakeMailBox([])
    clients = iter([first, second])
    # First connection starts at 0, waits with ten seconds left, then expires.
    times = iter([0.0, 1730.0, 1740.0, 1740.0, 1740.0])
    timeouts: list[float] = []

    def poll(timeout: float) -> list[bytes]:
        timeouts.append(timeout)
        return []

    def sleep(_seconds: float) -> None:
        pytest.fail("Scheduled refresh should not use failure backoff")

    def stop(timeout: float) -> list[bytes]:
        raise _Stop

    monkeypatch.setattr(first.idle, "poll", poll)
    monkeypatch.setattr(second.idle, "poll", stop)
    monkeypatch.setattr(handler_module, "MailBox", lambda **_kwargs: next(clients))
    monkeypatch.setattr(handler_module.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(handler_module.time, "sleep", sleep)

    with pytest.raises(_Stop):
        handle_mailbox(MailBoxConfig("h"), LoginConfig("u", "p"), [])

    assert timeouts == [10.0]
    assert first.closed and second.closed
    assert first.fetches == 2
    assert second.fetches == 1


@pytest.mark.parametrize("phase", ["login", "idle", "rule"])
def test_shutdown_survives_cleanup_errors(
    monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    mailbox = _FakeMailBox([_FakeMessage("Hello", "1")])
    shutdowns: list[bool] = []

    def request_shutdown(*_args: object, **_kwargs: object) -> None:
        raise ShutdownRequested

    def fail_cleanup() -> None:
        raise imaplib.IMAP4.abort("connection lost during cleanup")

    def sleep(_seconds: float) -> None:
        pytest.fail("Shutdown must not enter the retry loop")

    rules: list[Rule] = []
    if phase == "login":
        monkeypatch.setattr(mailbox, "login", request_shutdown)
    elif phase == "idle":
        monkeypatch.setattr(mailbox.idle, "poll", request_shutdown)
        monkeypatch.setattr(mailbox.idle, "stop", fail_cleanup)
    else:
        rule = _RecordingRule("shutdown", RuleResult.CONTINUE, [])
        monkeypatch.setattr(rule, "handle", request_shutdown)
        rules.append(rule)

    monkeypatch.setattr(mailbox, "logout", fail_cleanup)
    monkeypatch.setattr(
        mailbox,
        "client",
        SimpleNamespace(shutdown=lambda: shutdowns.append(True)),
        raising=False,
    )
    monkeypatch.setattr(handler_module, "MailBox", lambda **_kwargs: mailbox)
    monkeypatch.setattr(handler_module.time, "sleep", sleep)

    with pytest.raises(ShutdownRequested):
        handle_mailbox(MailBoxConfig("h"), LoginConfig("u", "p"), rules)

    assert shutdowns == [True]


def test_rule_connection_failure_triggers_reconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _FakeMailBox([_FakeMessage("Hello", "1")])
    second = _FakeMailBox([])
    clients = iter([first, second])
    calls: list[str] = []
    rule = _RecordingRule("failed", RuleResult.CONTINUE, calls)
    after = _RecordingRule("after", RuleResult.CONTINUE, calls)
    sleeps: list[int] = []

    def fail(_context: MessageContext) -> RuleResult:
        raise imaplib.IMAP4.abort("connection lost during rule")

    monkeypatch.setattr(rule, "handle", fail)
    monkeypatch.setattr(handler_module, "MailBox", lambda **_kwargs: next(clients))
    monkeypatch.setattr(handler_module.time, "sleep", sleeps.append)

    with pytest.raises(_Stop):
        handle_mailbox(MailBoxConfig("h"), LoginConfig("u", "p"), [rule, after])

    assert calls == []
    assert sleeps == [30]
    assert first.closed and second.closed


def test_programming_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    mailbox = _FakeMailBox([])

    def fail(*_args: object, **_kwargs: object) -> None:
        raise imaplib.IMAP4.error("illegal command state")

    def sleep(_seconds: float) -> None:
        pytest.fail("Programming errors must not be retried")

    monkeypatch.setattr(mailbox, "login", fail)
    monkeypatch.setattr(handler_module, "MailBox", lambda **_kwargs: mailbox)
    monkeypatch.setattr(handler_module.time, "sleep", sleep)

    with pytest.raises(imaplib.IMAP4.error, match="illegal command state"):
        handle_mailbox(MailBoxConfig("h"), LoginConfig("u", "p"), [])

    assert mailbox.closed


def test_shutdown_during_connection_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    def factory(**_kwargs: object) -> None:
        raise ShutdownRequested

    def sleep(_seconds: float) -> None:
        pytest.fail("Shutdown must not be retried")

    monkeypatch.setattr(handler_module, "MailBox", factory)
    monkeypatch.setattr(handler_module.time, "sleep", sleep)

    with pytest.raises(ShutdownRequested):
        handle_mailbox(MailBoxConfig("h"), LoginConfig("u", "p"), [])


def test_shutdown_during_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    def factory(**_kwargs: object) -> None:
        raise ConnectionRefusedError("unavailable")

    def sleep(_seconds: float) -> None:
        raise ShutdownRequested

    monkeypatch.setattr(handler_module, "MailBox", factory)
    monkeypatch.setattr(handler_module.time, "sleep", sleep)

    with pytest.raises(ShutdownRequested):
        handle_mailbox(MailBoxConfig("h"), LoginConfig("u", "p"), [])


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        pytest.param(0, "0 Bytes", id="zero"),
        pytest.param(1, "1 Byte", id="one-byte"),
        pytest.param(512, "512 Bytes", id="bytes"),
        pytest.param(1024, "1.00 KB", id="kilobyte"),
        pytest.param(1536, "1.50 KB", id="kilobytes"),
        pytest.param(1024**2, "1.00 MB", id="megabyte"),
        pytest.param(1024**3, "1.00 GB", id="gigabyte"),
        pytest.param(1024**4, "1.00 TB", id="terabyte"),
    ],
)
def test_format_size_bytes(size: int, expected: str) -> None:
    assert format_size_bytes(size) == expected
