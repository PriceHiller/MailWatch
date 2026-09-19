import dataclasses
import logging
from typing import override

from mailwatch.rules.base import MessageContext, Rule, RuleResult

logger = logging.getLogger(__name__)

JUNK_FOLDER = "Junk"
JUNK_SUBJECT_PREFIX = "Testing Mailwatch"


@dataclasses.dataclass(frozen=True)
class JunkRule(Rule):
    junk_folder: str = JUNK_FOLDER
    subject_prefix: str = JUNK_SUBJECT_PREFIX

    @override
    def handle(self, context: MessageContext) -> RuleResult:
        message = context.message
        if not (message.subject.startswith(self.subject_prefix) and message.uid):
            return RuleResult.CONTINUE
        _ = context.mailbox.move(message.uid, self.junk_folder)
        logger.info(
            "Moved message to Junk",
            extra={"context": {"uid": message.uid, "folder": self.junk_folder}},
        )
        return RuleResult.STOP
