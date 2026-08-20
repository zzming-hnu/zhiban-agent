"""Unit tests for main-agent routing decisions."""

from zhiban.agent.router import _parse_decision


def test_parse_decision_memory() -> None:
    d = _parse_decision('{"target": "memory", "reason": "用户要记住名字"}')
    assert d.target == "memory"
    assert "名字" in d.reason


def test_parse_decision_none() -> None:
    d = _parse_decision('{"target": "none", "reason": "普通闲聊"}')
    assert d.target == "none"


def test_parse_decision_unknown_target_falls_back_to_none() -> None:
    d = _parse_decision('{"target": "weather", "reason": "未知子代理"}')
    assert d.target == "none"


def test_parse_decision_code_fenced() -> None:
    d = _parse_decision('```json\n{"target": "general", "reason": "x"}\n```')
    assert d.target == "general"


def test_parse_decision_invalid_json_falls_back_to_none() -> None:
    d = _parse_decision("not json at all")
    assert d.target == "none"
