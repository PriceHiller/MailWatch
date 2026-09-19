import datetime
import logging
import re
from typing import cast, final

import pytest
from imap_tools import MailBox, MailMessage

from mailwatch.rules import JunkRule, MessageContext, RuleResult


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
        subject: str,
        uid: str | None,
        text: str = "",
        html: str = "",
    ) -> None:
        self.subject = subject
        self.uid = uid
        self.text = text
        self.html = html
        self.date = datetime.datetime(2026, 9, 19, 12, 0)


def _context(
    subject: str, uid: str | None, text: str = "", html: str = ""
) -> tuple[MessageContext, _FakeMailBox]:
    mailbox = _FakeMailBox()
    message = _FakeMessage(subject, uid, text=text, html=html)
    context = MessageContext(
        mailbox=cast(MailBox, cast(object, mailbox)),
        message=cast(MailMessage, cast(object, message)),
    )
    return context, mailbox


def test_default_subject_regex_searches_subject() -> None:
    context, mailbox = _context("FW: Testing Mailwatch hello", "42")

    result = JunkRule()(context)

    assert result is RuleResult.STOP
    assert mailbox.actions == [("flag", "42", "$Junk"), ("move", "42", "Junk")]


def test_non_matching_message_is_ignored() -> None:
    context, mailbox = _context("Hello World", "43")

    result = JunkRule()(context)

    assert result is RuleResult.CONTINUE
    assert mailbox.actions == []


def test_matching_message_without_uid_is_ignored() -> None:
    context, mailbox = _context("Testing Mailwatch hello", None)

    result = JunkRule()(context)

    assert result is RuleResult.CONTINUE
    assert mailbox.actions == []


def test_body_regex_matches_text() -> None:
    context, mailbox = _context("Hello", "42", text="this message is SPAM")

    result = JunkRule(subject_regex=None, body_regex=re.compile("spam", re.IGNORECASE))(
        context
    )

    assert result is RuleResult.STOP
    assert mailbox.actions == [("flag", "42", "$Junk"), ("move", "42", "Junk")]


def test_body_regex_matches_html() -> None:
    context, mailbox = _context("Hello", "42", html="<p>Buy now</p>")

    result = JunkRule(
        subject_regex=None, body_regex=re.compile("buy now", re.IGNORECASE)
    )(context)

    assert result is RuleResult.STOP
    assert mailbox.actions == [("flag", "42", "$Junk"), ("move", "42", "Junk")]


def test_subject_and_body_regexes_are_ored() -> None:
    subject_only, subject_mailbox = _context("Testing Mailwatch", "42", text="nothing")
    body_only, body_mailbox = _context("Hello", "43", text="spam here")

    subject_result = JunkRule(body_regex=re.compile("spam"))(subject_only)
    body_result = JunkRule(body_regex=re.compile("spam"))(body_only)

    assert subject_result is RuleResult.STOP
    assert subject_mailbox.actions == [("flag", "42", "$Junk"), ("move", "42", "Junk")]
    assert body_result is RuleResult.STOP
    assert body_mailbox.actions == [("flag", "43", "$Junk"), ("move", "43", "Junk")]


def test_no_regexes_never_matches() -> None:
    context, mailbox = _context("Testing Mailwatch", "42", text="Testing Mailwatch")

    result = JunkRule(subject_regex=None, body_regex=None)(context)

    assert result is RuleResult.CONTINUE
    assert mailbox.actions == []


def test_custom_subject_regex_changes_matching() -> None:
    context, mailbox = _context("Junk this", "42")

    result = JunkRule(subject_regex=re.compile("Junk"))(context)

    assert result is RuleResult.STOP
    assert mailbox.actions == [("flag", "42", "$Junk"), ("move", "42", "Junk")]


def test_custom_junk_folder_is_used() -> None:
    context, mailbox = _context("Testing Mailwatch hello", "42")

    result = JunkRule(junk_folder="Spam")(context)

    assert result is RuleResult.STOP
    assert mailbox.actions == [("flag", "42", "$Junk"), ("move", "42", "Spam")]


def test_custom_spam_flag_is_used() -> None:
    context, mailbox = _context("Testing Mailwatch hello", "42")

    result = JunkRule(spam_flag="$NotJunk")(context)

    assert result is RuleResult.STOP
    assert mailbox.actions == [("flag", "42", "$NotJunk"), ("move", "42", "Junk")]


def test_logs_uid_and_folder(caplog: pytest.LogCaptureFixture) -> None:
    context, _ = _context("Testing Mailwatch hello", "42")

    with caplog.at_level(logging.INFO):
        _ = JunkRule(junk_folder="Spam")(context)

    record = next(r for r in caplog.records if r.getMessage() == "Moved message to Junk")
    logged = cast("dict[str, object]", getattr(record, "context", None))
    assert logged["uid"] == "42"
    assert logged["folder"] == "Spam"
