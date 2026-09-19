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
JUNK_SUBJECT_REGEX = re.compile("Testing Mailwatch")


def matches_junk_subject(message: MailMessage) -> bool:
    return JUNK_SUBJECT_REGEX.search(message.subject) is not None


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
        _ = context.mailbox.flag(message.uid, self.spam_flag, True)
        _ = context.mailbox.move(message.uid, self.junk_folder)
        logger.info(
            "Moved message to Junk",
            extra={"context": {"uid": message.uid, "folder": self.junk_folder}},
        )
        return RuleResult.STOP
