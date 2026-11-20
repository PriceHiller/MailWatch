import imaplib
import logging
import time
from collections.abc import Sequence

from imap_tools import AND, MailBox
from imap_tools.errors import UnexpectedCommandStatusError

from mailwatch.config import LoginConfig, MailBoxConfig
from mailwatch.errors import ShutdownRequested
from mailwatch.rules import MessageContext, Rule, RuleResult

logger = logging.getLogger(__name__)

INBOX_FOLDER = "INBOX"
IDLE_TIMEOUT_SECONDS = 3 * 60
SOCKET_TIMEOUT_SECONDS = 60
RECONNECT_INTERVAL_SECONDS = 29 * 60
RETRY_DELAY_SECONDS = 30

# Protocol command rejections and transport failures can invalidate a session so we'll need to login
# if we see these
CONNECTION_ERRORS = (OSError, imaplib.IMAP4.abort, UnexpectedCommandStatusError)


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
    mailbox_config: MailBoxConfig, login_config: LoginConfig, rules: Sequence[Rule]
) -> None:
    while True:
        try:
            mailbox = MailBox(
                host=mailbox_config.host,
                port=mailbox_config.port,
                timeout=SOCKET_TIMEOUT_SECONDS,
            )
            try:
                _ = mailbox.login(
                    username=login_config.username,
                    password=login_config.password,
                    initial_folder=INBOX_FOLDER,
                )
                logger.info("Connected to mailbox")
                deadline = time.monotonic() + RECONNECT_INTERVAL_SECONDS
                _process_messages(mailbox, rules)
                while (remaining := deadline - time.monotonic()) > 0:
                    _wait_for_updates(mailbox, min(IDLE_TIMEOUT_SECONDS, remaining))
                    # IDLE is just a hint, not a reliable source of message state at all >:/
                    _process_messages(mailbox, rules)
                logger.info("Refreshing mailbox connection")
            finally:
                _close_mailbox(mailbox)
        except CONNECTION_ERRORS:
            logger.exception(
                "Mailbox connection failed, will reconnect in %s seconds",
                RETRY_DELAY_SECONDS,
            )
            time.sleep(RETRY_DELAY_SECONDS)


def _wait_for_updates(mailbox: MailBox, timeout: float) -> None:
    mailbox.idle.start()
    try:
        _ = mailbox.idle.poll(timeout=timeout)
    except BaseException:
        # IdleManager.wait() can replace a shutdown request with a DONE failure.
        try:
            mailbox.idle.stop()
        except CONNECTION_ERRORS:
            logger.exception("Unable to stop IDLE while unwinding")
        raise
    else:
        mailbox.idle.stop()


def _close_mailbox(mailbox: MailBox) -> None:
    try:
        _ = mailbox.logout()
    except CONNECTION_ERRORS:
        # A failed logout must not replace the original error or shutdown request.
        logger.exception("Unable to log out of mailbox; closing connection")
        try:
            mailbox.client.shutdown()
        except OSError:
            logger.exception("Unable to shut down mailbox connection")


def _process_messages(mailbox: MailBox, rules: Sequence[Rule]) -> None:
    for msg in mailbox.fetch(AND(seen=False)):
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
        _apply_rules(MessageContext(mailbox=mailbox, message=msg), rules)


def _apply_rules(context: MessageContext, rules: Sequence[Rule]) -> None:
    for rule in rules:
        try:
            result = rule(context)
        except ShutdownRequested:
            raise
        except CONNECTION_ERRORS:
            raise
        except Exception:
            logger.exception(
                "Rule failed",
                extra={"context": {"rule": rule.name, "uid": context.message.uid}},
            )
            continue
        if result is RuleResult.STOP:
            break
