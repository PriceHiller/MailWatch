from mailwatch.rules import DEFAULT_RULES, JunkRule, Rule, matches_junk_subject


def test_default_rules_is_a_tuple_of_rules() -> None:
    assert isinstance(DEFAULT_RULES, tuple)
    assert all(isinstance(rule, Rule) for rule in DEFAULT_RULES)


def test_default_rules_contains_a_junk_rule_with_default_matcher() -> None:
    assert DEFAULT_RULES == (JunkRule(matches=matches_junk_subject),)
