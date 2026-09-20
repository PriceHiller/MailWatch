from mailwatch.rules.base import MessageContext, Rule, RuleResult
from mailwatch.rules.junk import JunkRule, matches_junk

DEFAULT_RULES: tuple[Rule, ...] = (JunkRule(matches=matches_junk),)

__all__ = [
    "DEFAULT_RULES",
    "JunkRule",
    "MessageContext",
    "Rule",
    "RuleResult",
    "matches_junk",
]
