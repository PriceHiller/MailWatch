from mailwatch.rules.base import MessageContext, Rule, RuleResult
from mailwatch.rules.junk import JunkRule, matches_junk_subject

DEFAULT_RULES: tuple[Rule, ...] = (JunkRule(matches=matches_junk_subject),)

__all__ = [
    "DEFAULT_RULES",
    "JunkRule",
    "MessageContext",
    "Rule",
    "RuleResult",
    "matches_junk_subject",
]
