import datetime
import logging
from typing import cast, final

import pytest
from imap_tools import MailBox, MailMessage

from mailwatch.rules import JunkRule, MessageContext, RuleResult


@final
class _FakeMailBox:
    def __init__(self) -> None:
        self.moves: list[tuple[str, str]] = []

    def move(self, uid: str, destination: str) -> None:
        self.moves.append((uid, destination))


@final
class _FakeMessage:
    def __init__(self, subject: str, uid: str | None) -> None:
        self.subject = subject
        self.uid = uid
        self.date = datetime.datetime(2026, 9, 19, 12, 0)


def _context(subject: str, uid: str | None) -> tuple[MessageContext, _FakeMailBox]:
    mailbox = _FakeMailBox()
    message = _FakeMessage(subject, uid)
    context = MessageContext(
        mailbox=cast(MailBox, cast(object, mailbox)),
        message=cast(MailMessage, cast(object, message)),
    )
    return context, mailbox


def test_matching_message_is_moved_to_junk() -> None:
    context, mailbox = _context("Testing Mailwatch hello", "42")

    result = JunkRule()(context)

    assert result is RuleResult.STOP
    assert mailbox.moves == [("42", "Junk")]


def test_non_matching_message_is_ignored() -> None:
    context, mailbox = _context("Hello World", "43")

    result = JunkRule()(context)

    assert result is RuleResult.CONTINUE
    assert mailbox.moves == []


def test_matching_message_without_uid_is_ignored() -> None:
    context, mailbox = _context("Testing Mailwatch hello", None)

    result = JunkRule()(context)

    assert result is RuleResult.CONTINUE
    assert mailbox.moves == []


def test_custom_junk_folder_is_used() -> None:
    context, mailbox = _context("Testing Mailwatch hello", "42")

    result = JunkRule(junk_folder="Spam")(context)

    assert result is RuleResult.STOP
    assert mailbox.moves == [("42", "Spam")]


def test_custom_subject_prefix_changes_matching() -> None:
    context, mailbox = _context("Junk this", "42")

    result = JunkRule(subject_prefix="Junk")(context)

    assert result is RuleResult.STOP
    assert mailbox.moves == [("42", "Junk")]


def test_logs_uid_and_folder(caplog: pytest.LogCaptureFixture) -> None:
    context, _ = _context("Testing Mailwatch hello", "42")

    with caplog.at_level(logging.INFO):
        _ = JunkRule(junk_folder="Spam")(context)

    record = next(r for r in caplog.records if r.getMessage() == "Moved message to Junk")
    logged = cast("dict[str, object]", getattr(record, "context", None))
    assert logged["uid"] == "42"
    assert logged["folder"] == "Spam"
