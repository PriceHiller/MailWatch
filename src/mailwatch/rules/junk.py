import dataclasses
import logging
import re
from collections.abc import Callable
from typing import override

from imap_tools import MailMessage

from mailwatch.rules.base import MessageContext, Rule, RuleResult

logger = logging.getLogger(__name__)

JUNK_FOLDER = "Junk"
JUNK_FLAG = "$Junk"


def matches_junk(message: MailMessage) -> bool:
    if "@gmail.com" not in message.from_:
        return False

    matchers = [
        re.compile(r".*ppd\.nvim.*", re.IGNORECASE),
        re.compile(r".*Hi PriceHiller.*(G|g)ithub", re.DOTALL),
    ]
    for matcher in matchers:
        if (
            matcher.search(message.subject)
            or matcher.search(message.text)
            or matcher.search(message.html)
        ):
            return True
    return False


@dataclasses.dataclass(frozen=True)
class JunkRule(Rule):
    matches: Callable[[MailMessage], bool]
    junk_folder: str = JUNK_FOLDER
    spam_flag: str = JUNK_FLAG

    @override
    def handle(self, context: MessageContext) -> RuleResult:
        message = context.message
        if not message.uid or not self.matches(message):
            return RuleResult.CONTINUE
        _ = context.mailbox.flag(message.uid, self.spam_flag, True)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        _ = context.mailbox.move(message.uid, self.junk_folder)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        logger.info(
            "Moved message to Junk",
            extra={"context": {"uid": message.uid, "folder": self.junk_folder}},
        )
        return RuleResult.STOP
