from mailwatch.rules.base import MessageContext, Rule, RuleResult
from mailwatch.rules.forgejo import ForgejoRule
from mailwatch.rules.junk import JunkRule, matches_junk

DEFAULT_RULES: tuple[Rule, ...] = (JunkRule(matches=matches_junk), ForgejoRule())

__all__ = [
    "DEFAULT_RULES",
    "ForgejoRule",
    "JunkRule",
    "MessageContext",
    "Rule",
    "RuleResult",
    "matches_junk",
]
