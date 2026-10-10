import logging
import signal
from collections.abc import Sequence
from types import FrameType
from typing import Never

from imap_tools import MailBox

from mailwatch.cli import parse_cli_args
from mailwatch.config import AppConfig
from mailwatch.constants import APP_NAME
from mailwatch.errors import BaseError, ShutdownRequested
from mailwatch.handler import handle_mailbox
from mailwatch.log import configure_logging
from mailwatch.rules import DEFAULT_RULES

logger = logging.getLogger(__name__)


def _handle_shutdown_signal(signum: int, _frame: FrameType | None) -> Never:
    logger.info(
        "Shutdown requested",
        extra={"context": {"signal": signal.Signals(signum).name}},
    )
    raise ShutdownRequested


def install_signal_handlers() -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        _ = signal.signal(sig, _handle_shutdown_signal)


def main(argv: Sequence[str] | None = None) -> int:
    configure_logging()

    try:
        args = parse_cli_args(argv)
        cfg = AppConfig.from_args(args)
    except BaseError as error:
        logger.error("Unable to start %s: %s", APP_NAME, error.message)
        raise

    logger.info(
        "Connecting to mailbox",
        extra={
            "context": {
                "host": cfg.mail_box_config.host,
                "port": cfg.mail_box_config.port,
            }
        },
    )
    try:
        install_signal_handlers()
        mailbox = MailBox(host=cfg.mail_box_config.host, port=cfg.mail_box_config.port)
        handle_mailbox(mailbox, cfg.login_config, DEFAULT_RULES)
    except ShutdownRequested:
        logger.info("Shutdown complete")
        return 0
    return 0
