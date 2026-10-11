from typing import cast, final

from imap_tools import MailBox, MailMessage

from mailwatch.rules import ForgejoRule, MessageContext, RuleResult


@final
class _FakeFolder:
    def __init__(self, exists: bool) -> None:
        self.already_exists = exists
        self.actions: list[tuple[str, str, bool | None]] = []

    def exists(self, folder: str) -> bool:
        self.actions.append(("exists", folder, None))
        return self.already_exists

    def create(self, folder: str) -> None:
        self.actions.append(("create", folder, None))

    def subscribe(self, folder: str, value: bool) -> None:
        self.actions.append(("subscribe", folder, value))


@final
class _FakeMailBox:
    def __init__(self, folder_exists: bool = False) -> None:
        self.folder = _FakeFolder(folder_exists)
        self.actions: list[tuple[str, str, str]] = []

    def move(self, uid: str, destination: str) -> None:
        self.actions.append(("move", uid, destination))


@final
class _FakeMessage:
    def __init__(self, from_: str, uid: str | None = "42") -> None:
        self.from_ = from_
        self.uid = uid
        self.subject = "A Forgejo notification"


def _context(
    from_: str = "forgejo@pricehiller.com",
    uid: str | None = "42",
    folder_exists: bool = False,
) -> tuple[MessageContext, _FakeMailBox]:
    mailbox = _FakeMailBox(folder_exists)
    message = _FakeMessage(from_, uid)
    context = MessageContext(
        mailbox=cast(MailBox, cast(object, mailbox)),
        message=cast(MailMessage, cast(object, message)),
    )
    return context, mailbox


def test_matching_message_creates_subscribes_and_moves() -> None:
    context, mailbox = _context()

    result = ForgejoRule()(context)

    assert result is RuleResult.CONTINUE
    assert mailbox.folder.actions == [
        ("exists", "Forgejo", None),
        ("create", "Forgejo", None),
        ("subscribe", "Forgejo", True),
    ]
    assert mailbox.actions == [("move", "42", "Forgejo")]


def test_existing_folder_is_subscribed_before_move() -> None:
    context, mailbox = _context(folder_exists=True)

    _ = ForgejoRule()(context)

    assert mailbox.folder.actions == [
        ("exists", "Forgejo", None),
        ("subscribe", "Forgejo", True),
    ]
    assert mailbox.actions == [("move", "42", "Forgejo")]


def test_non_forgejo_message_is_ignored() -> None:
    context, mailbox = _context(from_="someone@example.com")

    result = ForgejoRule()(context)

    assert result is RuleResult.CONTINUE
    assert mailbox.folder.actions == []
    assert mailbox.actions == []


def test_forgejo_message_without_uid_is_ignored() -> None:
    context, mailbox = _context(uid=None)

    result = ForgejoRule()(context)

    assert result is RuleResult.CONTINUE
    assert mailbox.folder.actions == []
    assert mailbox.actions == []
