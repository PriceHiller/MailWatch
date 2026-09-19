from mailwatch.rules.base import MessageContext, Rule, RuleResult
from mailwatch.rules.junk import JunkRule

DEFAULT_RULES: tuple[Rule, ...] = (JunkRule(),)

__all__ = ["DEFAULT_RULES", "JunkRule", "MessageContext", "Rule", "RuleResult"]
