import datetime
import logging
from collections.abc import Callable
from typing import cast, final

import pytest
from imap_tools import MailBox, MailMessage

from mailwatch.rules import JunkRule, MessageContext, RuleResult, matches_junk_subject


@final
class _FakeMailBox:
    def __init__(self) -> None:
        self.actions: list[tuple[str, str, str | bool]] = []

    def flag(self, uid_list: str, flag_set: str, value: bool) -> None:
        self.actions.append(("flag", uid_list, flag_set if value else f"-{flag_set}"))

    def move(self, uid: str, destination: str) -> None:
        self.actions.append(("move", uid, destination))


@final
class _FakeMessage:
    def __init__(
        self,
        subject: str = "",
        uid: str | None = "42",
        text: str = "",
        html: str = "",
    ) -> None:
        self.subject = subject
        self.uid = uid
        self.text = text
        self.html = html
        self.date = datetime.datetime(2026, 9, 19, 12, 0)


def _context(
    subject: str = "", uid: str | None = "42", text: str = "", html: str = ""
) -> tuple[MessageContext, _FakeMailBox]:
    mailbox = _FakeMailBox()
    message = _FakeMessage(subject, uid, text=text, html=html)
    context = MessageContext(
        mailbox=cast(MailBox, cast(object, mailbox)),
        message=cast(MailMessage, cast(object, message)),
    )
    return context, mailbox


def _always(value: bool) -> Callable[[MailMessage], bool]:
    def matches(_message: MailMessage) -> bool:
        return value

    return matches


def test_matching_message_is_flagged_as_spam_and_moved() -> None:
    context, mailbox = _context()

    result = JunkRule(matches=_always(True))(context)

    assert result is RuleResult.STOP
    assert mailbox.actions == [("flag", "42", "$Junk"), ("move", "42", "Junk")]


def test_non_matching_message_is_ignored() -> None:
    context, mailbox = _context()

    result = JunkRule(matches=_always(False))(context)

    assert result is RuleResult.CONTINUE
    assert mailbox.actions == []


def test_matching_message_without_uid_is_ignored() -> None:
    context, mailbox = _context(uid=None)

    result = JunkRule(matches=_always(True))(context)

    assert result is RuleResult.CONTINUE
    assert mailbox.actions == []


def test_matches_receives_the_message() -> None:
    received: list[MailMessage] = []

    def matches(message: MailMessage) -> bool:
        received.append(message)
        return False

    context, _ = _context(subject="Hello")

    _ = JunkRule(matches=matches)(context)

    assert received == [context.message]


def test_custom_junk_folder_is_used() -> None:
    context, mailbox = _context()

    result = JunkRule(matches=_always(True), junk_folder="Spam")(context)

    assert result is RuleResult.STOP
    assert mailbox.actions == [("flag", "42", "$Junk"), ("move", "42", "Spam")]


def test_custom_spam_flag_is_used() -> None:
    context, mailbox = _context()

    result = JunkRule(matches=_always(True), spam_flag="$NotJunk")(context)

    assert result is RuleResult.STOP
    assert mailbox.actions == [("flag", "42", "$NotJunk"), ("move", "42", "Junk")]


def test_logs_uid_and_folder(caplog: pytest.LogCaptureFixture) -> None:
    context, _ = _context()

    with caplog.at_level(logging.INFO):
        _ = JunkRule(matches=_always(True), junk_folder="Spam")(context)

    record = next(r for r in caplog.records if r.getMessage() == "Moved message to Junk")
    logged = cast("dict[str, object]", getattr(record, "context", None))
    assert logged["uid"] == "42"
    assert logged["folder"] == "Spam"


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        pytest.param("Testing Mailwatch", True, id="exact"),
        pytest.param("Re: Testing Mailwatch report", True, id="contains"),
        pytest.param("Hello World", False, id="absent"),
    ],
)
def test_matches_junk_subject(subject: str, expected: bool) -> None:
    message = cast(MailMessage, cast(object, _FakeMessage(subject=subject)))

    assert matches_junk_subject(message) is expected
