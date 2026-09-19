import logging

from imap_tools import AND, MailBox

from mailwatch.config import LoginConfig

logger = logging.getLogger(__name__)

INBOX_FOLDER = "INBOX"
JUNK_FOLDER = "Junk"
JUNK_SUBJECT_PREFIX = "Testing Mailwatch"
IDLE_TIMEOUT_SECONDS = 60


def handle_mailbox(mailbox: MailBox, login_config: LoginConfig) -> None:
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
                    if msg.subject.startswith(JUNK_SUBJECT_PREFIX) and msg.uid:
                        _ = logged_in.move(msg.uid, JUNK_FOLDER)
                        logger.info("Moved message to Junk", extra={"context": {"uid": msg.uid}})
            else:
                logger.debug("No updates", extra={"context": {"timeout": IDLE_TIMEOUT_SECONDS}})
