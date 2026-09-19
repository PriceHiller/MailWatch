import datetime
import logging
from collections.abc import Sequence
from typing import cast, final, override

import pytest
from imap_tools import MailBox

from mailwatch.config import LoginConfig
from mailwatch.handler import handle_mailbox
from mailwatch.handler.handler import format_size_bytes
from mailwatch.rules import MessageContext, Rule, RuleResult


class _Stop(Exception): ...


@final
class _FakeIdle:
    def __init__(self, responses: list[bytes]) -> None:
        self._responses = responses
        self.waits = 0

    def wait(self, timeout: int) -> list[bytes]:
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

    def login(
        self, username: str, password: str, initial_folder: str | None = None
    ) -> "_FakeMailBox":
        self.login_args = (username, password, initial_folder)
        return self

    def __enter__(self) -> "_FakeMailBox":
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False

    def fetch(self, criteria: object) -> list[_FakeMessage]:
        _ = criteria
        return self._messages


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
    with pytest.raises(_Stop):
        handle_mailbox(
            cast(MailBox, cast(object, mailbox)),
            LoginConfig(username="u", password="p"),
            rules,
        )


def test_handle_mailbox_logs_in_to_inbox() -> None:
    mailbox = _FakeMailBox([])

    _run(mailbox, [])

    assert mailbox.login_args == ("u", "p", "INBOX")


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
