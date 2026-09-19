import logging
from collections.abc import Sequence

from imap_tools import AND, MailBox

from mailwatch.config import LoginConfig
from mailwatch.errors import ShutdownRequested
from mailwatch.rules import MessageContext, Rule, RuleResult

logger = logging.getLogger(__name__)

INBOX_FOLDER = "INBOX"
IDLE_TIMEOUT_SECONDS = 60


def handle_mailbox(
    mailbox: MailBox, login_config: LoginConfig, rules: Sequence[Rule]
) -> None:
    with mailbox.login(
        username=login_config.username,
        password=login_config.password,
        initial_folder=INBOX_FOLDER,
    ) as logged_in:
        while True:
            responses = logged_in.idle.wait(timeout=IDLE_TIMEOUT_SECONDS)
            if responses:
                for msg in logged_in.fetch(AND(seen=False)):
                    logger.info(
                        "Received message",
                        extra={
                            "context": {
                                "date": msg.date,
                                "subject": msg.subject,
                                "uid": msg.uid,
                            }
                        },
                    )
                    _apply_rules(MessageContext(mailbox=logged_in, message=msg), rules)
            else:
                logger.debug("No updates", extra={"context": {"timeout": IDLE_TIMEOUT_SECONDS}})


def _apply_rules(context: MessageContext, rules: Sequence[Rule]) -> None:
    for rule in rules:
        try:
            result = rule(context)
        except ShutdownRequested:
            raise
        except Exception:
            logger.exception(
                "Rule failed",
                extra={"context": {"rule": rule.name, "uid": context.message.uid}},
            )
            continue
        if result is RuleResult.STOP:
            break
