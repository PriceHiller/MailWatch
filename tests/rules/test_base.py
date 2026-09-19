import dataclasses
import inspect
from typing import cast, final, override

import pytest
from imap_tools import MailBox, MailMessage

from mailwatch.rules import MessageContext, Rule, RuleResult


@final
class _RecordingRule(Rule):
    def __init__(self) -> None:
        self.handled: list[MessageContext] = []

    @override
    def handle(self, context: MessageContext) -> RuleResult:
        self.handled.append(context)
        return RuleResult.CONTINUE


def _context() -> MessageContext:
    mailbox = cast(MailBox, object())
    message = cast(MailMessage, object())
    return MessageContext(mailbox=mailbox, message=message)


def test_rule_is_abstract() -> None:
    assert inspect.isabstract(Rule)


def test_call_delegates_to_handle() -> None:
    rule = _RecordingRule()
    context = _context()

    result = rule(context)

    assert result is RuleResult.CONTINUE
    assert rule.handled == [context]


def test_name_returns_class_name() -> None:
    assert _RecordingRule().name == "_RecordingRule"


def test_rule_result_members() -> None:
    assert set(RuleResult) == {RuleResult.CONTINUE, RuleResult.STOP}


def test_message_context_exposes_mailbox_and_message() -> None:
    mailbox = cast(MailBox, object())
    message = cast(MailMessage, object())

    context = MessageContext(mailbox=mailbox, message=message)

    assert context.mailbox is mailbox
    assert context.message is message


def test_message_context_is_frozen() -> None:
    context = _context()

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(context, "message", context.message)
