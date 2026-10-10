import logging
from collections.abc import Sequence

from imap_tools import AND, MailBox

from mailwatch.config import LoginConfig
from mailwatch.errors import ShutdownRequested
from mailwatch.rules import MessageContext, Rule, RuleResult

logger = logging.getLogger(__name__)

INBOX_FOLDER = "INBOX"
IDLE_TIMEOUT_SECONDS = 60


# Thanks https://stackoverflow.com/a/31631711
def format_size_bytes(size_bytes: float) -> str:
    """Return the given bytes as a human friendly KB, MB, GB, or TB string."""
    size_bytes = float(size_bytes)
    KB = float(1024)
    MB = float(KB**2)  # 1,048,576
    GB = float(KB**3)  # 1,073,741,824
    TB = float(KB**4)  # 1,099,511,627,776

    if size_bytes < KB:
        unit = "Byte" if size_bytes == 1 else "Bytes"
        return f"{size_bytes:g} {unit}"
    elif KB <= size_bytes < MB:
        return f"{size_bytes / KB:.2f} KB"
    elif MB <= size_bytes < GB:
        return f"{size_bytes / MB:.2f} MB"
    elif GB <= size_bytes < TB:
        return f"{size_bytes / GB:.2f} GB"
    else:
        return f"{size_bytes / TB:.2f} TB"


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
                                "uid": msg.uid,
                                "to": msg.to,
                                "date": msg.date,
                                "size": format_size_bytes(msg.size),
                            }
                        },
                    )
                    _apply_rules(MessageContext(mailbox=logged_in, message=msg), rules)
            else:
                logger.debug(
                    "No updates", extra={"context": {"timeout": IDLE_TIMEOUT_SECONDS}}
                )


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
