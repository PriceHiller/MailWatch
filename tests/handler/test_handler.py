import datetime
from typing import cast, final

import pytest
from imap_tools import MailBox

from mailwatch.config import LoginConfig
from mailwatch.handler import handle_mailbox


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
    def __init__(self, subject: str, uid: str | None) -> None:
        self.subject = subject
        self.uid = uid
        self.date = datetime.datetime(2026, 9, 19, 12, 0)


@final
class _FakeMailBox:
    def __init__(self, messages: list[_FakeMessage]) -> None:
        self._messages = messages
        self.idle = _FakeIdle([b"* 1 EXISTS"])
        self.moved: list[tuple[str, str]] = []
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

    def move(self, uid: str, destination: str) -> None:
        self.moved.append((uid, destination))


def _run(mailbox: _FakeMailBox) -> None:
    with pytest.raises(_Stop):
        handle_mailbox(cast(MailBox, cast(object, mailbox)), LoginConfig(username="u", password="p"))


def test_handle_mailbox_logs_in_to_inbox() -> None:
    mailbox = _FakeMailBox([])

    _run(mailbox)

    assert mailbox.login_args == ("u", "p", "INBOX")


def test_handle_mailbox_moves_matching_messages() -> None:
    mailbox = _FakeMailBox([_FakeMessage("Testing Mailwatch Validation", "42")])

    _run(mailbox)

    assert mailbox.moved == [("42", "Junk")]


def test_handle_mailbox_ignores_non_matching_messages() -> None:
    mailbox = _FakeMailBox([_FakeMessage("Hello World", "43")])

    _run(mailbox)

    assert mailbox.moved == []


def test_handle_mailbox_ignores_matching_message_without_uid() -> None:
    mailbox = _FakeMailBox([_FakeMessage("Testing Mailwatch", None)])

    _run(mailbox)

    assert mailbox.moved == []


def test_handle_mailbox_logs_message_context(caplog: pytest.LogCaptureFixture) -> None:
    mailbox = _FakeMailBox([_FakeMessage("Hello World", "43")])

    with caplog.at_level("INFO"):
        _run(mailbox)

    record = next(r for r in caplog.records if r.getMessage() == "Received message")
    context = cast("dict[str, object]", getattr(record, "context", None))
    assert context["subject"] == "Hello World"
    assert context["uid"] == "43"
