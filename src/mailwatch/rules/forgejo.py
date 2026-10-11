import dataclasses
import logging
from typing import override

from mailwatch.rules.base import MessageContext, Rule, RuleResult

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class ForgejoRule(Rule):
    ci_folder: str = "Forgejo"

    @override
    def handle(self, context: MessageContext) -> RuleResult:
        message = context.message
        mailbox = context.mailbox
        if message.from_ != "forgejo@pricehiller.com" or not message.uid:
            return RuleResult.CONTINUE

        if not mailbox.folder.exists(self.ci_folder):
            logger.warning(
                f"Folder for Forgejo did not exist on mail server, creating '{self.ci_folder}' on server",
                extra={"context": {"folder": self.ci_folder}},
            )
            _ = mailbox.folder.create(self.ci_folder)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

        _ = mailbox.move(message.uid, self.ci_folder)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        logger.info(
            f"Moved message to '{self.ci_folder}', subject: '{message.subject}'"
        )

        return RuleResult.CONTINUE
