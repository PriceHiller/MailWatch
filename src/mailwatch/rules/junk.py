import dataclasses
import logging
import re
from typing import override

from imap_tools import MailMessage

from mailwatch.rules.base import MessageContext, Rule, RuleResult

logger = logging.getLogger(__name__)

JUNK_FOLDER = "Junk"
JUNK_SUBJECT_REGEX = re.compile("Testing Mailwatch")
JUNK_FLAG = "$Junk"


@dataclasses.dataclass(frozen=True)
class JunkRule(Rule):
    junk_folder: str = JUNK_FOLDER
    subject_regex: re.Pattern[str] | None = JUNK_SUBJECT_REGEX
    body_regex: re.Pattern[str] | None = None
    spam_flag: str = JUNK_FLAG

    @override
    def handle(self, context: MessageContext) -> RuleResult:
        message = context.message
        if not message.uid or not self._matches(message):
            return RuleResult.CONTINUE
        _ = context.mailbox.flag(message.uid, self.spam_flag, True)
        _ = context.mailbox.move(message.uid, self.junk_folder)
        logger.info(
            "Moved message to Junk",
            extra={"context": {"uid": message.uid, "folder": self.junk_folder}},
        )
        return RuleResult.STOP

    def _matches(self, message: MailMessage) -> bool:
        body = f"{message.text}\n{message.html}"
        return self._search(self.subject_regex, message.subject) or self._search(
            self.body_regex, body
        )

    @staticmethod
    def _search(regex: re.Pattern[str] | None, value: str) -> bool:
        return regex is not None and regex.search(value) is not None
