import datetime
import logging
from collections.abc import Callable
from typing import cast, final

import pytest
from imap_tools import MailBox, MailMessage

from mailwatch.rules import JunkRule, MessageContext, RuleResult, matches_junk


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
        from_: str = "",
    ) -> None:
        self.subject = subject
        self.uid = uid
        self.text = text
        self.html = html
        self.from_ = from_
        self.date = datetime.datetime(2026, 9, 19, 12, 0)


def _context(
    subject: str = "",
    uid: str | None = "42",
    text: str = "",
    html: str = "",
    from_: str = "",
) -> tuple[MessageContext, _FakeMailBox]:
    mailbox = _FakeMailBox()
    message = _FakeMessage(subject, uid, text=text, html=html, from_=from_)
    context = MessageContext(
        mailbox=cast(MailBox, cast(object, mailbox)),
        message=cast(MailMessage, cast(object, message)),
    )
    return context, mailbox


def _message(**fields: str) -> MailMessage:
    return cast(MailMessage, cast(object, _FakeMessage(**fields)))


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

    record = next(
        r for r in caplog.records if r.getMessage() == "Moved message to Junk"
    )
    logged = cast("dict[str, object]", getattr(record, "context", None))
    assert logged["uid"] == "42"
    assert logged["folder"] == "Spam"


@pytest.mark.parametrize(
    ("from_", "subject", "text", "html", "expected"),
    [
        pytest.param(
            "spammer@gmail.com", "ppd.nvim release", "", "", True, id="ppd-subject"
        ),
        pytest.param(
            "spammer@gmail.com",
            "",
            "check out pricehiller/ppd.nvim",
            "",
            True,
            id="ppd-text",
        ),
        pytest.param(
            "spammer@gmail.com", "", "", "<a href='ppd.nvim'>x</a>", True, id="ppd-html"
        ),
        pytest.param(
            "spammer@gmail.com",
            "PPD.NVIM release",
            "",
            "",
            True,
            id="ppd-case-insensitive",
        ),
        pytest.param(
            "spammer@gmail.com",
            "ppdXnvim release",
            "",
            "",
            False,
            id="ppd-dot-is-literal",
        ),
        pytest.param(
            "spammer@gmail.com",
            "Hi PriceHiller, saw you on Github",
            "",
            "",
            True,
            id="pricehiller-subject",
        ),
        pytest.param(
            "spammer@gmail.com",
            "",
            "Hi PriceHiller, found your github page",
            "",
            True,
            id="pricehiller-text-lowercase",
        ),
        pytest.param(
            "spammer@gmail.com",
            "",
            "",
            "<p>Hi PriceHiller on Github</p>",
            True,
            id="pricehiller-html",
        ),
        pytest.param(
            "spammer@gmail.com",
            "Hi PriceHiller",
            "",
            "",
            False,
            id="pricehiller-requires-github",
        ),
        pytest.param(
            "spammer@gmail.com",
            "see my Github",
            "",
            "",
            False,
            id="pricehiller-requires-greeting",
        ),
        pytest.param(
            "spammer@gmail.com",
            "",
            "Hi PriceHiller,\n\nI saw you on Github",
            "",
            True,
            id="pricehiller-across-lines",
        ),
        pytest.param(
            "spammer@gmail.com", "hello", "hi", "<p>hi</p>", False, id="gmail-no-match"
        ),
        pytest.param(
            "spammer@example.com", "ppd.nvim release", "", "", False, id="non-gmail"
        ),
        pytest.param("", "ppd.nvim release", "", "", False, id="empty-sender"),
        pytest.param(
            "michealandre396@gmail.com",
            "why PriceHiller/ppd.nvim has 2 stars",
            """
            Hi PriceHiller,

            Great code does not sell itself.
            PriceHiller/ppd.nvim is solid, but 2 stars says the right people have not
            found it yet.

            You approve everything before it goes out, so you stay fully in control of
            how PriceHiller/ppd.nvim is presented.

            Want me to send a short plan for PriceHiller/ppd.nvim? A one line reply is
            all I need.
            """,
            "",
            True,
            id="actual-email-received-should-be-marked-spam",
        ),
    ],
)
def test_matches_junk(
    from_: str, subject: str, text: str, html: str, expected: bool
) -> None:
    message = _message(from_=from_, subject=subject, text=text, html=html)

    assert matches_junk(message) is expected
