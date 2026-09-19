import dataclasses
from abc import ABC, abstractmethod
from enum import Enum, auto

from imap_tools import MailBox, MailMessage


@dataclasses.dataclass(frozen=True)
class MessageContext:
    mailbox: MailBox
    message: MailMessage


class RuleResult(Enum):
    CONTINUE = auto()
    STOP = auto()


class Rule(ABC):
    @property
    def name(self) -> str:
        return type(self).__name__

    def __call__(self, context: MessageContext) -> RuleResult:
        return self.handle(context)

    @abstractmethod
    def handle(self, context: MessageContext) -> RuleResult: ...
