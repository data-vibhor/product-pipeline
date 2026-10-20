from pipeline.repair import generate_checked


class SeqLLM:
    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    def chat(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if len(self.replies) > 1:
            return self.replies.pop(0)
        return self.replies[0]


def no_bad(text: str) -> list[str]:
    return ["contains BAD"] if "BAD" in text else []


def test_passing_draft_makes_one_call():
    llm = SeqLLM(["good"])
    text, issues = generate_checked(llm, "sys", "user", no_bad)
    assert text == "good"
    assert issues == []
    assert len(llm.calls) == 1


def test_failing_draft_is_repaired():
    llm = SeqLLM(["BAD draft", "good draft"])
    text, issues = generate_checked(llm, "sys", "user", no_bad)
    assert text == "good draft"
    assert issues == []
    assert len(llm.calls) == 2
    assert "contains BAD" in llm.calls[1][1]
    assert "BAD draft" in llm.calls[1][1]


def test_stops_after_max_repairs():
    llm = SeqLLM(["BAD"])
    _text, issues = generate_checked(llm, "sys", "user", no_bad, max_repairs=2)
    assert issues == ["contains BAD"]
    assert len(llm.calls) == 3
